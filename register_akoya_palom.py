#!/usr/bin/env python
"""
Register pre-stitched Akoya Phenocycler OME-TIFF cycles using palom,
and write a pyramidal stitched+registered OME-TIFF that can be used
directly by MCMICRO (with workflow.start-at: segmentation).

Typical usage (with defaults, FULL RES):
conda activate palom
python register_akoya_palom.py \
  --input-dir ome_cycles \
  --pattern "c*.ome.tiff" \
  --output registration/c_registered.ome.tiff

Defaults:
  --ref-index 0
  --ref-channel 0
  --moving-channel 0
  --level 0              (FULL-RES)
  --compression zlib
  pyramidal output enabled

Example with specific channel selection (0-based indices):
  # cycle 0 (c1) -> channels 0,1
  # cycle 1 (c2) -> channels 0,2
python register_akoya_palom.py \
  --input-dir ome_cycles \
  --pattern "c*.ome.tiff" \
  --output registration/c_registered.ome.tiff \
  --cycle-channels "0:0,1;1:0,2"
"""

import argparse
from pathlib import Path
import numpy as np
import palom
import tifffile

# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Register pre-stitched Akoya OME-TIFF cycles with palom."
    )
    p.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing per-cycle OME-TIFF files.",
    )
    p.add_argument(
        "--pattern",
        type=str,
        required=True,
        help='Glob pattern, e.g. "c*.ome.tiff".',
    )
    p.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output OME-TIFF path for MCMICRO registration.",
    )
    p.add_argument(
        "--markers",
        type=str,
        default=None,
        help="Optional path to markers.csv file for channel names.",
    )
    p.add_argument(
        "--ref-index",
        type=int,
        default=0,
        help="Index of reference cycle in sorted file list (0-based). Default: 0.",
    )
    p.add_argument(
        "--ref-channel",
        type=int,
        default=0,
        help="Channel index in reference image used for registration. Default: 0.",
    )
    p.add_argument(
        "--moving-channel",
        type=int,
        default=0,
        help="Channel index in moving images used for registration. Default: 0.",
    )
    p.add_argument(
        "--level",
        type=int,
        default=0,
        help=(
            "Pyramid level for registration/output "
            "(0 = full-res; >0 = downsampled output). Default: 0."
        ),
    )
    p.add_argument(
        "--thumbnail-size",
        type=int,
        default=2000,
        help="Approximate thumbnail size in pixels for coarse alignment. Default: 2000.",
    )
    p.add_argument(
        "--cycle-channels",
        type=str,
        default=None,
        help=(
            "Optional per-cycle channel selection (0-based indices). "
            "Format: 'cycleIdx:ch,ch;cycleIdx:ch,ch;...'. "
            "Example: '0:0,1;1:0,2' keeps channels 0,1 from cycle 0 and 0,2 from cycle 1. "
            "If omitted, all channels from each cycle are kept."
        ),
    )
    p.add_argument(
        "--max-pyramid-levels",
        type=int,
        default=5,
        help="Maximum number of pyramid levels (including full-res). Default: 5.",
    )
    p.add_argument(
        "--min-size-for-next-level",
        type=int,
        default=512,
        help="Minimum min(H,W) to continue building pyramid. Default: 512.",
    )
    p.add_argument(
        "--tile-size",
        type=int,
        default=512,
        help="Tile size (square) for pyramidal TIFF tiles. Default: 512.",
    )
    p.add_argument(
        "--compression",
        type=str,
        default="zlib",
        choices=["none", "zlib", "lzw"],
        help="TIFF compression for all pyramid levels (lossless). Default: zlib.",
    )
    return p.parse_args()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def parse_cycle_channels(spec: str, n_files: int):
    """
    Parse a string like '0:0,1;1:0,2' into {0: [0,1], 1: [0,2]}.
    cycle indices are 0-based and refer to the sorted order of files.
    channel indices are also 0-based.
    """
    mapping = {}
    if spec is None:
        return mapping
    blocks = [b.strip() for b in spec.split(";") if b.strip()]
    for block in blocks:
        if ":" not in block:
            raise ValueError(
                f"Invalid cycle-channels block '{block}'. Expected 'idx:ch,ch,...'."
            )
        idx_str, chans_str = block.split(":", 1)
        idx = int(idx_str)
        if not (0 <= idx < n_files):
            raise ValueError(
                f"cycle index {idx} in --cycle-channels is out of range [0, {n_files-1}]."
            )
        chans = []
        for c in chans_str.split(","):
            c = c.strip()
            if not c:
                continue
            chans.append(int(c))
        if not chans:
            raise ValueError(
                f"No channels specified for cycle {idx} in --cycle-channels."
            )
        mapping[idx] = chans
    return mapping


def build_pyramid(
    data: np.ndarray,
    max_levels: int = 5,
    min_size_for_next: int = 512,
):
    """
    Build a simple 2x–downsampling pyramid from a 3D array (C, H, W).
    Returns a list of levels: [level0(full-res), level1, ...].
    """
    levels = [data]
    for lvl in range(1, max_levels):
        prev = levels[-1]
        _, h, w = prev.shape
        if min(h, w) < min_size_for_next:
            break
        # simple 2x decimation (can be replaced by mean pooling if desired)
        h2 = h // 2
        w2 = w // 2
        down = prev[:, : 2 * h2 : 2, : 2 * w2 : 2]
        levels.append(down)
    return levels


def write_pyramidal_ometiff(
    path: Path,
    data: np.ndarray,
    pixel_size: float,
    axes: str = "CYX",
    tile_size: int = 512,
    max_levels: int = 5,
    min_size_for_next: int = 512,
    compression: str = "zlib",
):
    """
    Write a pyramidal OME-TIFF from a CYX NumPy array.
    - data: (C, H, W) array
    - pixel_size: physical size (µm) at full resolution (level 0)
    - axes: OME axes string, default "CYX"
    - compression: "none", "zlib", or "lzw"
    """
    print("\n=== Output data summary ===")
    print(f"  Shape (C,H,W): {data.shape}")
    print(f"  Dtype        : {data.dtype}")
    bytes_total = data.nbytes
    print(f"  Raw bytes    : {bytes_total}  (~{bytes_total / 1e9:.2f} GB)")

    if compression == "none":
        tif_compression = None
    else:
        tif_compression = compression  # "zlib" or "lzw"

    print(
        f"\nBuilding pyramid for output OME-TIFF "
        f"(max_levels={max_levels}, min_size_for_next={min_size_for_next})..."
    )
    pyr = build_pyramid(
        data,
        max_levels=max_levels,
        min_size_for_next=min_size_for_next,
    )
    print(f"  Pyramid levels: {len(pyr)}")
    for i, lvl in enumerate(pyr):
        print(f"    Level {i}: shape={lvl.shape}")

    # Write pyramidal BigTIFF with subIFDs
    with tifffile.TiffWriter(str(path), bigtiff=True) as tif:
        n_sub = len(pyr) - 1

        # Full-res level (level 0) with OME metadata
        print("  Writing level 0 (full-res)...")
        tif.write(
            pyr[0],
            tile=(tile_size, tile_size),
            compression=tif_compression,
            subifds=n_sub if n_sub > 0 else None,
            metadata={
                "axes": axes,
                # IMPORTANT: keep physical size exactly from the reference image
                "PhysicalSizeX": float(pixel_size),
                "PhysicalSizeY": float(pixel_size),
                "PhysicalSizeXUnit": "um",
                "PhysicalSizeYUnit": "um",
            },
        )

        # Reduced-resolution levels as subIFDs
        for i in range(1, len(pyr)):
            print(f"  Writing level {i} (downsampled)...")
            tif.write(
                pyr[i],
                tile=(tile_size, tile_size),
                compression=tif_compression,
                subfiletype=1,  # reduced-resolution image
            )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def load_marker_names(markers_path, n_channels):
    """Load marker names from markers.csv if it exists."""
    if markers_path is None or not Path(markers_path).exists():
        return [f"Channel_{i}" for i in range(n_channels)]
    
    try:
        import csv
        marker_names = []
        with open(markers_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try common column names
                name = row.get('marker_name') or row.get('marker') or row.get('name') or row.get('channel_name')
                if name:
                    marker_names.append(name)
        
        if len(marker_names) == n_channels:
            return marker_names
        else:
            print(f"Warning: markers.csv has {len(marker_names)} entries but expected {n_channels}. Using default names.")
            return [f"Channel_{i}" for i in range(n_channels)]
    except Exception as e:
        print(f"Warning: Could not read markers.csv: {e}. Using default names.")
        return [f"Channel_{i}" for i in range(n_channels)]


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    
    # Handle brace expansion in pattern like "*.{ome.tiff,ome.tif}"
    pattern = args.pattern.strip()
    files = []
    if "{" in pattern and "}" in pattern:
        # Extract extensions from brace expansion pattern
        prefix = pattern.split("{")[0]
        extensions_str = pattern.split("{")[1].split("}")[0]
        extensions = [ext.strip() for ext in extensions_str.split(",")]
        for ext in extensions:
            files.extend(input_dir.glob(f"{prefix}{ext}"))
    else:
        # Simple pattern
        files.extend(input_dir.glob(pattern))
    
    files = sorted(files)
    if not files:
        raise FileNotFoundError(
            f"No files found in {input_dir} matching {args.pattern}"
        )

    n_files = len(files)
    cycle_channel_map = parse_cycle_channels(args.cycle_channels, n_files)

    print("Found cycles (sorted):")
    for i, f in enumerate(files):
        keep_txt = (
            f"keep channels {cycle_channel_map[i]}"
            if i in cycle_channel_map
            else "keep ALL channels"
        )
        print(f"  [{i}] {f}  -> {keep_txt}")

    if not (0 <= args.ref_index < len(files)):
        raise ValueError(
            f"ref-index {args.ref_index} is out of range for {len(files)} files."
        )

    ref_path = files[args.ref_index]
    print(f"\nUsing reference cycle index {args.ref_index}: {ref_path}")

    # --- Reference reader ---
    ref_reader = palom.reader.OmePyramidReader(str(ref_path))
    level = args.level
    thumb_level = ref_reader.get_thumbnail_level_of_size(args.thumbnail_size)
    print(f"Using level={level}, thumbnail_level={thumb_level}")

    if level > 0:
        print(
            f"INFO: Using pyramid level {level} for registration and output.\n"
            f"      This reduces memory usage while maintaining high quality.\n"
            f"      Level 1 = half resolution (1/4 memory), Level 2 = quarter resolution (1/16 memory).\n"
            f"      For full resolution (requires 32GB+ Docker RAM), use '--level 0'."
        )
    else:
        print(
            "INFO: Using level 0 (full resolution).\n"
            "      This requires significant RAM (~25-30GB for large datasets).\n"
            "      If you encounter memory errors, use '--level 1' for half resolution."
        )

    # Registration channel as dask (keep dask for palom)
    ref_reg_level = ref_reader.read_level_channels(level, args.ref_channel)
    # Thumbnails as NumPy
    ref_reg_thumb = ref_reader.read_level_channels(
        thumb_level, args.ref_channel
    ).compute()

    # Channels to keep from reference cycle (0-based)
    ref_keep = cycle_channel_map.get(args.ref_index, None)

    # Get reference cycle info but DON'T compute all channels yet
    ref_mosaic_da = ref_reader.read_level_channels(level, slice(None))  # C x H x W
    n_ref_channels = ref_mosaic_da.shape[0]
    
    # Determine which channels to keep
    ref_keep = cycle_channel_map.get(args.ref_index, None)
    if ref_keep is not None:
        print(f"Reference cycle: will select channels {ref_keep}")
        ref_channels_to_process = ref_keep
    else:
        print("Reference cycle: will keep ALL channels")
        ref_channels_to_process = list(range(n_ref_channels))
    
    print(f"Reference cycle will have {len(ref_channels_to_process)} channels")
    print(f"Detected pixel size at level 0 (from ref): {ref_reader.pixel_size} µm")

    # Store (cycle_index, reader, level, channels_to_keep, aligner_or_none)
    # We'll process these incrementally during writing
    cycles_info = [(args.ref_index, ref_reader, level, ref_channels_to_process, None)]

    # Pixel size for metadata: **keep exactly as in level 0**, no scaling
    pixel_size = float(ref_reader.pixel_size)
    print(f"Pixel size used in output metadata (all pyramid levels): {pixel_size} µm")

    # --- Register each moving cycle ---
    for idx, path in enumerate(files):
        if idx == args.ref_index:
            continue

        print(f"\nRegistering moving cycle index {idx}: {path}")
        mov_reader = palom.reader.OmePyramidReader(str(path))

        # Moving registration channel as dask
        mov_reg_level = mov_reader.read_level_channels(level, args.moving_channel)
        # Thumbnails as NumPy
        mov_reg_thumb = mov_reader.read_level_channels(
            thumb_level, args.moving_channel
        ).compute()

        # Aligner (feature-based affine + local shifts)
        aligner = palom.align.Aligner(
            ref_img=ref_reg_level,
            moving_img=mov_reg_level,
            ref_thumbnail=ref_reg_thumb,
            moving_thumbnail=mov_reg_thumb,
            ref_thumbnail_down_factor=ref_reader.level_downsamples[thumb_level]
            / ref_reader.level_downsamples[level],
            moving_thumbnail_down_factor=mov_reader.level_downsamples[thumb_level]
            / mov_reader.level_downsamples[level],
        )

        aligner.coarse_register_affine(n_keypoints=4000)
        aligner.compute_shifts()

        # Robust constrain_shifts with fallback
        try:
            aligner.constrain_shifts()
        except Exception as e:
            print(
                "  WARNING: constrain_shifts failed "
                "(likely no valid block shifts). "
                "Proceeding with unconstrained shifts. "
                f"Error: {repr(e)}"
            )

        # Determine which channels to keep for this cycle
        keep_chans = cycle_channel_map.get(idx, None)
        mov_full_da = mov_reader.read_level_channels(level, slice(None))
        n_mov_channels = mov_full_da.shape[0]
        
        if keep_chans is not None:
            print(f"  Will select channels {keep_chans} for cycle {idx}")
            channels_to_process = keep_chans
        else:
            print(f"  Will keep ALL {n_mov_channels} channels for cycle {idx}")
            channels_to_process = list(range(n_mov_channels))
        
        # Store info for later processing - DON'T compute yet
        cycles_info.append((idx, mov_reader, level, channels_to_process, aligner))
        
        # Keep references alive - we'll process during writing
        print(f"  Alignment complete for cycle {idx}")

    # --- Build and write pyramidal OME-TIFF directly ---
    out_path = Path(args.output)
    
    # Sanitize filename: replace spaces with underscores to avoid downstream issues
    if ' ' in out_path.name:
        sanitized_name = out_path.name.replace(' ', '_')
        out_path = out_path.parent / sanitized_name
        print(f"\nNote: Sanitized filename (spaces -> underscores): {out_path.name}")
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("\nBuilding pyramidal OME-TIFF (memory-efficient mode)...")
    
    # Calculate total channels
    total_channels = sum(len(chans) for _, _, _, chans, _ in cycles_info)
    print(f"Total channels: {total_channels}")
    
    # Determine compression
    if args.compression == "none":
        tif_compression = None
    else:
        tif_compression = args.compression
    
    # Process and write with pyramid
    print(f"Writing pyramidal TIFF to: {out_path}")
    import gc
    
    # We'll build pyramid by processing all channels at level 0, then downsample
    # Store level 0 channels temporarily
    import tempfile
    import os
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Step 1: Process and save all level 0 channels to temp files
        print("\nStep 1: Processing full-resolution channels...")
        temp_files = []
        global_channel_idx = 0
        
        for cycle_idx, reader, lvl, channels_to_keep, aligner in cycles_info:
            print(f"  Cycle {cycle_idx} ({len(channels_to_keep)} channels)...")
            cycle_da = reader.read_level_channels(lvl, slice(None))
            
            for local_ch_idx in channels_to_keep:
                print(f"    Channel {global_channel_idx + 1}/{total_channels}...", end=" ", flush=True)
                
                channel_da = cycle_da[local_ch_idx]
                
                if aligner is not None:
                    print("transforming...", end=" ", flush=True)
                    channel_da = palom.align.block_affine_transformed_moving_img(
                        ref_img=ref_reg_level,
                        moving_img=channel_da,
                        mxs=aligner.block_affine_matrices_da,
                    )
                
                print("computing...", end=" ", flush=True)
                channel_np = channel_da.compute()
                
                # Save to temp file
                temp_file = os.path.join(temp_dir, f"ch_{global_channel_idx:03d}.npy")
                np.save(temp_file, channel_np)
                temp_files.append(temp_file)
                print("saved")
                
                global_channel_idx += 1
                del channel_np, channel_da
                gc.collect()
            
            del cycle_da
            gc.collect()
        
        # Step 2: Load marker names
        print("\nStep 2: Loading marker names...")
        marker_names = load_marker_names(args.markers, total_channels)
        print(f"  Channel names: {marker_names[:5]}{'...' if len(marker_names) > 5 else ''}")
        
        # Step 3: Build pyramid by loading channels one at a time
        print(f"\nStep 3: Building {args.max_pyramid_levels}-level pyramid...")
        
        # Get dimensions from first channel
        first_ch = np.load(temp_files[0])
        h, w = first_ch.shape
        dtype = first_ch.dtype
        del first_ch
        gc.collect()
        
        print(f"  Full resolution: {total_channels} x {h} x {w}, dtype: {dtype}")
        
        # Calculate pyramid dimensions
        pyramid_shapes = [(h, w)]
        for i in range(1, args.max_pyramid_levels):
            prev_h, prev_w = pyramid_shapes[-1]
            if min(prev_h, prev_w) < args.min_size_for_next_level:
                break
            pyramid_shapes.append((prev_h // 2, prev_w // 2))
        
        n_levels = len(pyramid_shapes)
        print(f"  Creating {n_levels} pyramid levels:")
        for i, (ph, pw) in enumerate(pyramid_shapes):
            print(f"    Level {i}: {ph} x {pw}")
        
        # Use memory-mapped arrays to avoid loading everything into RAM
        print("\n  Building pyramid using memory-mapped arrays (ultra memory-efficient)...")
        
        # Calculate pyramid dimensions
        pyramid_shapes = [(h, w)]
        for i in range(1, args.max_pyramid_levels):
            prev_h, prev_w = pyramid_shapes[-1]
            if min(prev_h, prev_w) < args.min_size_for_next_level:
                break
            pyramid_shapes.append((prev_h // 2, prev_w // 2))
        
        n_levels = len(pyramid_shapes)
        print(f"  Creating {n_levels} pyramid levels:")
        for i, (ph, pw) in enumerate(pyramid_shapes):
            print(f"    Level {i}: {total_channels} x {ph} x {pw}")
        
        # Create memory-mapped files for each pyramid level
        mmap_files = []
        mmap_arrays = []
        
        for level_idx in range(n_levels):
            level_h, level_w = pyramid_shapes[level_idx]
            mmap_file = os.path.join(temp_dir, f"level_{level_idx}.dat")
            
            # Create memory-mapped array
            mmap_array = np.memmap(
                mmap_file,
                dtype=dtype,
                mode='w+',
                shape=(total_channels, level_h, level_w)
            )
            
            print(f"\n  Building level {level_idx} ({level_h} x {level_w})...")
            
            # Process each channel
            for ch_idx, temp_file in enumerate(temp_files):
                if ch_idx % 10 == 0:
                    print(f"    Channel {ch_idx + 1}/{total_channels}...", end="\r")
                
                # Load full-res channel
                channel_full = np.load(temp_file)
                
                # Downsample to current level
                if level_idx == 0:
                    mmap_array[ch_idx] = channel_full
                else:
                    # Downsample by factor of 2^level_idx
                    channel_level = channel_full
                    for _ in range(level_idx):
                        h2, w2 = channel_level.shape[0] // 2, channel_level.shape[1] // 2
                        channel_level = channel_level[::2, ::2][:h2, :w2]
                    mmap_array[ch_idx] = channel_level
                    del channel_level
                
                del channel_full
            
            # Flush to disk
            mmap_array.flush()
            print(f"    Level {level_idx} complete" + " " * 30)
            
            mmap_files.append(mmap_file)
            mmap_arrays.append(mmap_array)
            gc.collect()
        
        # Now write the pyramidal TIFF using chunked loading
        print(f"\n  Writing pyramidal OME-TIFF to: {out_path}")
        
        # Close memory-mapped arrays to ensure data is flushed
        for mmap_array in mmap_arrays:
            mmap_array.flush()
            del mmap_array
        gc.collect()
        
        # Strategy: Load channels in small batches and write level-by-level
        # This keeps memory usage bounded while maintaining proper TIFF structure
        batch_size = 3  # Process 3 channels at a time (adjustable based on available RAM)
        
        with tifffile.TiffWriter(str(out_path), bigtiff=True) as tif:
            n_sub = n_levels - 1
            
            for level_idx in range(n_levels):
                level_h, level_w = pyramid_shapes[level_idx]
                print(f"    Writing level {level_idx} ({level_h} x {level_w})...")
                
                # Reopen memory-mapped file for this level (read-only)
                mmap_array = np.memmap(
                    mmap_files[level_idx],
                    dtype=dtype,
                    mode='r',
                    shape=(total_channels, level_h, level_w)
                )
                
                # Process in batches to limit memory usage
                for batch_start in range(0, total_channels, batch_size):
                    batch_end = min(batch_start + batch_size, total_channels)
                    
                    if batch_start % 10 == 0:
                        print(f"      Channels {batch_start + 1}-{batch_end}/{total_channels}...", end="\r")
                    
                    # Load this batch into RAM (small enough to fit)
                    batch_data = np.array(mmap_array[batch_start:batch_end])
                    
                    # Write this batch
                    if level_idx == 0 and batch_start == 0:
                        # Very first write with OME metadata
                        tif.write(
                            batch_data,
                            tile=(args.tile_size, args.tile_size),
                            compression=tif_compression,
                            subifds=n_sub if n_sub > 0 else None,
                            metadata={
                                "axes": "CYX",
                                "PhysicalSizeX": float(pixel_size),
                                "PhysicalSizeY": float(pixel_size),
                                "PhysicalSizeXUnit": "um",
                                "PhysicalSizeYUnit": "um",
                            },
                            contiguous=False,
                        )
                    elif level_idx == 0:
                        # Subsequent batches at level 0
                        tif.write(
                            batch_data,
                            tile=(args.tile_size, args.tile_size),
                            compression=tif_compression,
                            subifds=n_sub if n_sub > 0 else None,
                            contiguous=False,
                        )
                    else:
                        # Downsampled levels as subIFDs
                        tif.write(
                            batch_data,
                            tile=(args.tile_size, args.tile_size),
                            compression=tif_compression,
                            subfiletype=1,
                            contiguous=False,
                        )
                    
                    del batch_data
                    gc.collect()
                
                print(f"      Level {level_idx} complete" + " " * 30)
                del mmap_array
                gc.collect()
        
        print(f"\n  Successfully wrote {n_levels}-level pyramidal OME-TIFF")
        print(f"\n=== Output summary ===")
        print(f"  File: {out_path}")
        print(f"  Shape: {total_channels} x {h} x {w}")
        print(f"  Pyramid levels: {n_levels}")
        print(f"  Compression: {args.compression}")
        print(f"  Pixel size: {pixel_size} µm")
        
        print(f"\nSuccessfully wrote pyramidal OME-TIFF with {n_levels} levels")
        
    finally:
        # Clean up temp files
        print("Cleaning up temporary files...")
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    print("\nRegistration complete!")
    print(f"Output: {out_path}")
    print(f"Format: Pyramidal OME-TIFF with {n_levels} levels")

    print("\nDone. You can now use this as the MCMICRO registration image:")
    print(f"  {out_path}")
    print(
        "In MCMICRO: put it under registration/ and set workflow.start-at: segmentation"
    )


if __name__ == "__main__":
    main()

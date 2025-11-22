#!/usr/bin/env python
"""
Memory-efficient version of PALOM registration that writes pyramidal OME-TIFF
without loading all channels into memory at once.

Key improvements:
1. Processes channels one at a time during transformation
2. Uses memory-mapped temporary storage
3. Writes TIFF pages individually with proper OME-XML metadata
4. Works within Docker's memory constraints (tested with 20GB limit)

Usage: Same as register_akoya_palom.py
"""

import argparse
from pathlib import Path
import numpy as np
import palom
import tifffile
import tempfile
import dask
import dask.array as da
import os
import gc
import shutil
from typing import List, Tuple


def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser(
        description="Register pre-stitched Akoya OME-TIFF cycles with palom (memory-efficient)."
    )
    p.add_argument("--input-dir", type=str, required=True, help="Directory containing per-cycle OME-TIFF files.")
    p.add_argument("--pattern", type=str, required=True, help='Glob pattern, e.g. "c*.ome.tiff".')
    p.add_argument("--output", type=str, required=True, help="Output OME-TIFF path for MCMICRO registration.")
    p.add_argument("--markers", type=str, default=None, help="Optional path to markers.csv file for channel names.")
    p.add_argument("--ref-index", type=int, default=0, help="Index of reference cycle (0-based). Default: 0.")
    p.add_argument("--ref-channel", type=int, default=0, help="Channel index in reference for registration. Default: 0.")
    p.add_argument("--moving-channel", type=int, default=0, help="Channel index in moving for registration. Default: 0.")
    p.add_argument("--level", type=int, default=0, help="Pyramid level for registration/output (0=full-res). Default: 0.")
    p.add_argument("--thumbnail-size", type=int, default=2000, help="Thumbnail size for coarse alignment. Default: 2000.")
    p.add_argument("--cycle-channels", type=str, default=None, help="Per-cycle channel selection. Format: '0:0,1;1:0,2'.")
    p.add_argument("--max-pyramid-levels", type=int, default=5, help="Maximum pyramid levels. Default: 5.")
    p.add_argument("--min-size-for-next-level", type=int, default=512, help="Min size to continue pyramid. Default: 512.")
    p.add_argument("--tile-size", type=int, default=512, help="Tile size for TIFF. Default: 512.")
    p.add_argument("--compression", type=str, default="zlib", choices=["none", "zlib", "lzw"], help="TIFF compression. Default: zlib.")
    return p.parse_args()


def parse_cycle_channels(spec: str, n_files: int):
    """Parse cycle-channels specification like '0:0,1;1:0,2' into {0: [0,1], 1: [0,2]}."""
    mapping = {}
    if spec is None:
        return mapping
    blocks = [b.strip() for b in spec.split(";") if b.strip()]
    for block in blocks:
        if ":" not in block:
            raise ValueError(f"Invalid cycle-channels block '{block}'. Expected 'idx:ch,ch,...'.")
        idx_str, chans_str = block.split(":", 1)
        idx = int(idx_str)
        if not (0 <= idx < n_files):
            raise ValueError(f"cycle index {idx} in --cycle-channels is out of range [0, {n_files-1}].")
        chans = [int(c.strip()) for c in chans_str.split(",") if c.strip()]
        if not chans:
            raise ValueError(f"No channels specified for cycle {idx} in --cycle-channels.")
        mapping[idx] = chans
    return mapping


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


def downsample_2x(img: np.ndarray) -> np.ndarray:
    """Downsample 2D image by factor of 2 using simple decimation."""
    h, w = img.shape
    h2, w2 = h // 2, w // 2
    return img[:2*h2:2, :2*w2:2]


def build_pyramid_for_channel(channel_data: np.ndarray, max_levels: int, min_size: int) -> List[np.ndarray]:
    """Build pyramid levels for a single channel."""
    levels = [channel_data]
    for _ in range(1, max_levels):
        prev = levels[-1]
        if min(prev.shape) < min_size:
            break
        levels.append(downsample_2x(prev))
    return levels


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    
    # Handle brace expansion in pattern
    pattern = args.pattern.strip()
    files = []
    if "{" in pattern and "}" in pattern:
        prefix = pattern.split("{")[0]
        extensions_str = pattern.split("{")[1].split("}")[0]
        extensions = [ext.strip() for ext in extensions_str.split(",")]
        for ext in extensions:
            files.extend(input_dir.glob(f"{prefix}{ext}"))
    else:
        files.extend(input_dir.glob(pattern))
    
    files = sorted(files)
    if not files:
        raise FileNotFoundError(f"No files found in {input_dir} matching {args.pattern}")

    n_files = len(files)
    cycle_channel_map = parse_cycle_channels(args.cycle_channels, n_files)

    print("Found cycles (sorted):")
    for i, f in enumerate(files):
        keep_txt = f"keep channels {cycle_channel_map[i]}" if i in cycle_channel_map else "keep ALL channels"
        print(f"  [{i}] {f}  -> {keep_txt}")

    if not (0 <= args.ref_index < len(files)):
        raise ValueError(f"ref-index {args.ref_index} is out of range for {len(files)} files.")

    ref_path = files[args.ref_index]
    print(f"\nUsing reference cycle index {args.ref_index}: {ref_path}")

    # Reference reader
    ref_reader = palom.reader.OmePyramidReader(str(ref_path))
    level = args.level
    thumb_level = ref_reader.get_thumbnail_level_of_size(args.thumbnail_size)
    print(f"Using level={level}, thumbnail_level={thumb_level}")

    # Registration channels
    ref_reg_level = ref_reader.read_level_channels(level, args.ref_channel)
    ref_reg_thumb = ref_reader.read_level_channels(thumb_level, args.ref_channel).compute()

    # Determine channels to keep from reference
    ref_mosaic_da = ref_reader.read_level_channels(level, slice(None))
    n_ref_channels = ref_mosaic_da.shape[0]
    ref_keep = cycle_channel_map.get(args.ref_index, None)
    
    if ref_keep is not None:
        print(f"Reference cycle: will select channels {ref_keep}")
        ref_channels_to_process = ref_keep
    else:
        print("Reference cycle: will keep ALL channels")
        ref_channels_to_process = list(range(n_ref_channels))
    
    print(f"Reference cycle will have {len(ref_channels_to_process)} channels")
    
    pixel_size = float(ref_reader.pixel_size)
    print(f"Pixel size: {pixel_size} µm")

    # Get image dimensions for later
    h, w = ref_reg_level.shape
    print(f"Image dimensions: {h} x {w}")

    # Create temporary directory for storing channels
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    # Process and save reference channels first
    print("\nProcessing reference cycle channels...")
    temp_channel_files = []
    global_channel_idx = 0
    
    for local_ch_idx in ref_channels_to_process:
        print(f"  Channel {global_channel_idx + 1}...", end=" ", flush=True)
        channel_da = ref_reader.read_level_channels(level, local_ch_idx)
        channel_np = channel_da.compute()
        temp_file = os.path.join(temp_dir, f"ch_{global_channel_idx:03d}.npy")
        np.save(temp_file, channel_np)
        temp_channel_files.append(temp_file)
        print("saved")
        global_channel_idx += 1
        del channel_da, channel_np
        gc.collect()

    # Register and process each moving cycle immediately
    for idx, path in enumerate(files):
        if idx == args.ref_index:
            continue

        print(f"\nRegistering and processing moving cycle index {idx}: {path}")
        mov_reader = palom.reader.OmePyramidReader(str(path))

        mov_reg_level = mov_reader.read_level_channels(level, args.moving_channel)
        mov_reg_thumb = mov_reader.read_level_channels(thumb_level, args.moving_channel).compute()

        aligner = palom.align.Aligner(
            ref_img=ref_reg_level,
            moving_img=mov_reg_level,
            ref_thumbnail=ref_reg_thumb,
            moving_thumbnail=mov_reg_thumb,
            ref_thumbnail_down_factor=ref_reader.level_downsamples[thumb_level] / ref_reader.level_downsamples[level],
            moving_thumbnail_down_factor=mov_reader.level_downsamples[thumb_level] / mov_reader.level_downsamples[level],
        )

        aligner.coarse_register_affine(n_keypoints=4000)
        aligner.compute_shifts()

        try:
            aligner.constrain_shifts()
        except Exception as e:
            print(f"  WARNING: constrain_shifts failed. Proceeding with unconstrained shifts. Error: {repr(e)}")

        keep_chans = cycle_channel_map.get(idx, None)
        mov_full_da = mov_reader.read_level_channels(level, slice(None))
        n_mov_channels = mov_full_da.shape[0]
        
        if keep_chans is not None:
            print(f"  Will select channels {keep_chans} for cycle {idx}")
            channels_to_process = keep_chans
        else:
            print(f"  Will keep ALL {n_mov_channels} channels for cycle {idx}")
            channels_to_process = list(range(n_mov_channels))
        
        # Transform and save channels immediately
        for local_ch_idx in channels_to_process:
            print(f"  Channel {global_channel_idx + 1}...", end=" ", flush=True)
            channel_da = mov_reader.read_level_channels(level, local_ch_idx)
            
            # Apply transformation
            channel_da = palom.align.block_affine_transformed_moving_img(
                ref_img=ref_reg_level,
                moving_img=channel_da,
                mxs=aligner.block_affine_matrices_da,
            )
            
            channel_np = channel_da.compute()
            temp_file = os.path.join(temp_dir, f"ch_{global_channel_idx:03d}.npy")
            np.save(temp_file, channel_np)
            temp_channel_files.append(temp_file)
            print("saved")
            global_channel_idx += 1
            del channel_da, channel_np
            gc.collect()
        
        print(f"  Alignment complete for cycle {idx}")
        
        # Aggressive cleanup to free memory
        del mov_reader, mov_reg_level, mov_reg_thumb, aligner, mov_full_da
        gc.collect()

    # Clean up reference registration data
    del ref_reg_level, ref_reg_thumb, ref_reader
    gc.collect()

    # Calculate total channels
    total_channels = global_channel_idx
    print(f"\nTotal channels processed: {total_channels}")
    
    try:
        # Step 1: Load marker names
        print("\nStep 1: Loading marker names...")
        marker_names = load_marker_names(args.markers, total_channels)
        
        # Step 2: Create dask array directly from individual channel files
        # This avoids creating a 17GB memory-mapped file
        print(f"\nStep 2: Creating dask array from individual channel files...")
        
        # Create delayed dask arrays that load from files on-demand
        print(f"  Creating lazy dask arrays for {total_channels} channels...")
        
        def load_channel(filepath):
            """Delayed function to load a channel from file."""
            return np.load(filepath)
        
        # Get dtype from first channel
        first_channel = np.load(temp_channel_files[0])
        dtype = first_channel.dtype
        del first_channel
        gc.collect()
        
        # Create dask arrays for each channel (lazy - doesn't load yet)
        channel_arrays = []
        for ch_idx, temp_file in enumerate(temp_channel_files):
            if ch_idx % 5 == 0:
                print(f"    Channel {ch_idx + 1}/{total_channels}...")
            
            # Create delayed dask array that will load from file when needed
            channel_delayed = da.from_delayed(
                dask.delayed(load_channel)(temp_file),
                shape=(h, w),
                dtype=dtype
            )
            # Rechunk to tile size for efficient processing
            channel_rechunked = channel_delayed.rechunk((args.tile_size, args.tile_size))
            channel_arrays.append(channel_rechunked)
        
        # Stack into multi-channel array (still lazy!)
        print(f"  Stacking into multi-channel dask array (lazy)...")
        mosaic_dask = da.stack(channel_arrays, axis=0)
        print(f"  Shape: {mosaic_dask.shape}, chunks: {mosaic_dask.chunks}")
        print(f"  Memory: 0GB (lazy - data loaded tile-by-tile during write)")
        
        # Step 3: Write pyramidal OME-TIFF using palom's function
        print("\nStep 3: Writing pyramidal OME-TIFF using palom.pyramid.write_pyramid()...")
        print("  (Data will be loaded tile-by-tile as needed)")
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Calculate expected pyramid levels
        min_dim = min(h, w)
        max_levels = 1
        current_size = min_dim
        while current_size >= args.min_size_for_next_level and max_levels < args.max_pyramid_levels:
            current_size = current_size // 2
            max_levels += 1
        
        print(f"  Expected pyramid levels: {max_levels}")
        print(f"  Tile size: {args.tile_size}")
        print(f"  Compression: {args.compression}")
        
        # Use palom's write_pyramid - it will read tiles on-demand!
        # This is the same approach ASHLAR uses for large files
        palom.pyramid.write_pyramid(
            [mosaic_dask],  # Lazy dask array - loads tiles as needed
            str(out_path),
            pixel_size=pixel_size,
            downscale_factor=2,
            compression=args.compression if args.compression != "none" else None,
            tile_size=args.tile_size,
        )
        
        # Clean up
        del mosaic_dask, channel_arrays
        gc.collect()
        
        print(f"\n=== Output summary ===")
        print(f"  File: {out_path}")
        print(f"  Shape: {total_channels} x {h} x {w}")
        print(f"  Pyramid levels: {max_levels}")
        print(f"  Compression: {args.compression}")
        print(f"  Pixel size: {pixel_size} µm")
        if out_path.exists():
            print(f"  File size: {out_path.stat().st_size / 1e9:.2f} GB")
        
    finally:
        # Clean up temp files
        print("\nCleaning up temporary files...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    print("\nRegistration complete!")
    print(f"Output: {out_path}")
    print("In MCMICRO: put it under registration/ and set workflow.start-at: segmentation")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PALOM registration script for MCMICRO pipeline.
Registers pre-stitched multi-cycle OME-TIFF files using feature-based alignment.
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import tifffile
from palom import reader, align
from palom.pyramid import write_pyramid


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Register multi-cycle OME-TIFF images using PALOM"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing input cycle images"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.ome.tif*",
        help="Glob pattern for input files (default: *.ome.tif*)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output filename for registered image"
    )
    parser.add_argument(
        "--ref-index",
        type=int,
        default=0,
        help="Index of reference cycle (default: 0)"
    )
    parser.add_argument(
        "--ref-channel",
        type=int,
        default=0,
        help="Channel index for reference registration (default: 0)"
    )
    parser.add_argument(
        "--moving-channel",
        type=int,
        default=0,
        help="Channel index for moving registration (default: 0)"
    )
    parser.add_argument(
        "--level",
        type=int,
        default=0,
        help="Pyramid level for registration (default: 0 = full resolution)"
    )
    parser.add_argument(
        "--cycle-channels",
        type=str,
        default=None,
        help='Channel selection per cycle, e.g., "0:0,1;1:0,2" (default: all channels)'
    )
    parser.add_argument(
        "--thumbnail-size",
        type=int,
        default=2000,
        help="Thumbnail size for coarse alignment (default: 2000)"
    )
    parser.add_argument(
        "--max-pyramid-levels",
        type=int,
        default=6,
        help="Maximum number of pyramid levels (default: 6)"
    )
    parser.add_argument(
        "--min-size-for-next-level",
        type=int,
        default=512,
        help="Minimum dimension for next pyramid level (default: 512)"
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=512,
        help="Tile size for output TIFF (default: 512)"
    )
    parser.add_argument(
        "--compression",
        type=str,
        default="zlib",
        choices=["none", "zlib", "lzw"],
        help="Compression method (default: zlib)"
    )
    
    return parser.parse_args()


def parse_cycle_channels(spec, n_files):
    """
    Parse cycle-channels specification.
    
    Args:
        spec: String like "0:0,1;1:0,2" meaning cycle 0 channels 0,1 and cycle 1 channels 0,2
        n_files: Number of cycle files
    
    Returns:
        Dictionary mapping cycle index to list of channel indices
    """
    if spec is None:
        return None
    
    result = {}
    for cycle_spec in spec.split(";"):
        parts = cycle_spec.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid cycle-channels format: {cycle_spec}")
        
        idx = int(parts[0])
        if idx not in range(n_files):
            raise ValueError(
                f"Cycle index {idx} in --cycle-channels is out of range [0, {n_files-1}]"
            )
        
        channels = [int(c) for c in parts[1].split(",")]
        result[idx] = channels
    
    return result


def build_pyramid(img, max_levels=6, min_size=512):
    """
    Build image pyramid with 2x downsampling.
    
    Args:
        img: Input image array (C, Y, X)
        max_levels: Maximum number of pyramid levels
        min_size: Minimum dimension for next level
    
    Returns:
        List of pyramid levels
    """
    from skimage.transform import downscale_local_mean
    
    pyramid = [img]
    current = img
    
    for level in range(1, max_levels):
        # Check if we should create another level
        if min(current.shape[-2:]) < min_size * 2:
            break
        
        # Downsample by exactly 2x using local mean
        if current.ndim == 3:  # Multi-channel (C, Y, X)
            downsampled = np.stack([
                downscale_local_mean(current[c], (2, 2))
                for c in range(current.shape[0])
            ])
        else:  # Single channel
            downsampled = downscale_local_mean(current, (2, 2))
        
        pyramid.append(downsampled)
        current = downsampled
    
    return pyramid


def write_pyramidal_ometiff(pyramid, output_path, pixel_size, tile_size=512, compression="zlib"):
    """
    Write pyramidal OME-TIFF with metadata.
    
    Args:
        pyramid: List of pyramid levels (each is C, Y, X array)
        output_path: Output file path
        pixel_size: Physical pixel size in micrometers (NOT scaled by pyramid level)
        tile_size: Tile size for TIFF (default: 512)
        compression: Compression method (default: zlib)
    """
    # Map compression names
    compression_map = {
        "none": None,
        "zlib": "zlib",
        "lzw": "lzw"
    }
    comp = compression_map.get(compression, "zlib")
    
    # Prepare OME metadata with pixel size from reference (level 0)
    n_channels = pyramid[0].shape[0]
    metadata = {
        "axes": "CYX",
        "PhysicalSizeX": pixel_size,
        "PhysicalSizeY": pixel_size,
        "PhysicalSizeXUnit": "µm",
        "PhysicalSizeYUnit": "µm",
        "Channel": {"Name": [f"Channel_{i}" for i in range(n_channels)]}
    }
    
    # Write pyramidal OME-TIFF with subIFDs
    with tifffile.TiffWriter(output_path, bigtiff=True) as tif:
        # Write level 0 (full resolution) with OME metadata
        tif.write(
            pyramid[0],
            tile=(tile_size, tile_size),
            compression=comp,
            metadata=metadata,
            subfiletype=0
        )
        
        # Write reduced-resolution levels as subIFDs
        for level_img in pyramid[1:]:
            tif.write(
                level_img,
                tile=(tile_size, tile_size),
                compression=comp,
                subfiletype=1
            )


def main():
    """Main registration workflow."""
    args = parse_args()
    
    # Use pathlib.Path.glob to find files matching pattern
    input_dir = Path(args.input_dir)
    
    # Parse pattern like "*.{ome.tiff,ome.tif}" or "*.ome.tiff"
    pattern = args.pattern.strip()
    if "{" in pattern and "}" in pattern:
        # Extract extensions from brace expansion pattern
        prefix = pattern.split("{")[0].strip("*")
        extensions_str = pattern.split("{")[1].split("}")[0]
        extensions = [ext.strip() for ext in extensions_str.split(",")]
    else:
        # Simple pattern like "*.ome.tiff"
        extensions = [pattern.strip("*")]
    
    files = []
    for ext in extensions:
        files.extend(input_dir.glob(f"*{ext}"))
    
    # Sort files alphabetically to establish consistent cycle order
    files = sorted(files)
    
    # Raise clear error if no files found
    if not files:
        raise FileNotFoundError(
            f"No files found in {input_dir} matching {args.pattern}"
        )
    
    # Print discovered files with cycle indices for user verification
    print(f"Found {len(files)} cycle files:")
    for i, f in enumerate(files):
        print(f"  Cycle {i}: {f.name}")
    
    # Validate cycle index is in valid range before processing
    if not (0 <= args.ref_index < len(files)):
        raise ValueError(
            f"ref-index {args.ref_index} is out of range for {len(files)} files"
        )
    
    # Parse cycle-channels specification into mapping dict
    cycle_channels = parse_cycle_channels(args.cycle_channels, len(files))
    
    # Load reference cycle
    print(f"\nLoading reference cycle {args.ref_index}...")
    ref_reader = reader.OmePyramidReader(files[args.ref_index])
    ref_img = ref_reader.pyramid[args.level]
    
    # Extract pixel_size from reference reader at level 0 (without scaling)
    pixel_size = float(ref_reader.pixel_size)
    
    print(f"Reference image shape: {ref_img.shape}")
    print(f"Pixel size: {pixel_size} µm")
    
    # Validate reference channel index exists in input images
    if args.ref_channel >= ref_img.shape[0]:
        raise ValueError(
            f"ref-channel {args.ref_channel} is out of range for {ref_img.shape[0]} channels"
        )
    
    # Extract reference registration channel
    ref_channel = ref_img[args.ref_channel]
    
    # Prepare list to store alignment information for each cycle
    # We'll write directly to output instead of accumulating in memory
    aligners = []
    readers_and_indices = []
    
    for i, file_path in enumerate(files):
        if i == args.ref_index:
            # Store reference info
            aligners.append(None)  # No aligner needed for reference
            readers_and_indices.append((ref_reader, i))
            print(f"Cycle {i}: Reference (shape: {ref_img.shape})")
            continue
        
        print(f"\nRegistering cycle {i}...")
        moving_reader = reader.OmePyramidReader(file_path)
        moving_img = moving_reader.pyramid[args.level]
        
        # Validate channel indices exist in input images
        if args.moving_channel >= moving_img.shape[0]:
            raise ValueError(
                f"moving-channel {args.moving_channel} is out of range for {moving_img.shape[0]} channels in cycle {i}"
            )
        
        moving_channel = moving_img[args.moving_channel]
        
        # Compute thumbnails for alignment
        ref_thumbnail_down_factor = max(ref_channel.shape) // args.thumbnail_size
        moving_thumbnail_down_factor = max(moving_channel.shape) // args.thumbnail_size
        
        ref_thumbnail = ref_channel[::ref_thumbnail_down_factor, ::ref_thumbnail_down_factor]
        moving_thumbnail = moving_channel[::moving_thumbnail_down_factor, ::moving_thumbnail_down_factor]
        
        # Create aligner
        aligner = align.Aligner(
            ref_channel,
            moving_channel,
            ref_thumbnail,
            moving_thumbnail,
            ref_thumbnail_down_factor=ref_thumbnail_down_factor,
            moving_thumbnail_down_factor=moving_thumbnail_down_factor
        )
        
        # Wrap coarse_register_affine in try-except with clear error message
        try:
            aligner.coarse_register_affine(n_keypoints=4000)
            print(f"  Coarse alignment: {aligner.coarse_affine_matrix}")
        except Exception as e:
            print(f"ERROR: Coarse registration failed for cycle {i}.", file=sys.stderr)
            print(f"Insufficient image features for alignment.", file=sys.stderr)
            print(f"Details: {repr(e)}", file=sys.stderr)
            sys.exit(1)
        
        # Add try-except for constrain_shifts with fallback to unconstrained
        try:
            aligner.compute_shifts()
            aligner.constrain_shifts()
        except Exception as e:
            print(f"WARNING: constrain_shifts failed for cycle {i}", file=sys.stderr)
            print(f"(likely no valid block shifts). Proceeding with unconstrained shifts.", file=sys.stderr)
            print(f"Error: {repr(e)}", file=sys.stderr)
        
        # Store aligner and reader for later use
        aligners.append(aligner)
        readers_and_indices.append((moving_reader, i))
        print(f"  Registration complete")
    
    # Now write output using PALOM's PyramidWriter for memory efficiency
    print(f"\nWriting registered output to {args.output}...")
    from palom.pyramid import PyramidWriter
    
    # Create pyramid writer
    writer = PyramidWriter(
        args.output,
        ref_img.shape[1:],  # (height, width)
        pixel_size=pixel_size,
        tile_size=args.tile_size,
        compression=args.compression
    )
    
    # Write each cycle
    for idx, (reader_or_aligner_tuple, aligner) in enumerate(zip(readers_and_indices, aligners)):
        cycle_reader, cycle_idx = reader_or_aligner_tuple
        cycle_img = cycle_reader.pyramid[args.level]
        
        print(f"  Writing cycle {cycle_idx}...")
        
        if aligner is None:
            # Reference cycle - write as-is
            for c in range(cycle_img.shape[0]):
                writer.write_channel(cycle_img[c].compute() if hasattr(cycle_img[c], 'compute') else cycle_img[c])
        else:
            # Registered cycle - apply transformation and write
            for c in range(cycle_img.shape[0]):
                print(f"    Transforming and writing channel {c}...")
                # Apply coarse affine transformation only (faster, less memory)
                from skimage import transform as tf
                tform = tf.AffineTransform(matrix=aligner.coarse_affine_matrix)
                
                # Get channel data
                channel_data = cycle_img[c]
                if hasattr(channel_data, 'compute'):
                    channel_data = channel_data.compute()
                
                # Transform
                transformed = tf.warp(
                    channel_data,
                    tform.inverse,
                    output_shape=ref_channel.shape,
                    preserve_range=True,
                    order=1
                ).astype(channel_data.dtype)
                
                writer.write_channel(transformed)
    
    # Finalize the pyramid
    print(f"  Finalizing pyramid...")
    writer.close()
    print(f"Output written successfully!")
    
    return
    
    # OLD CODE BELOW - KEEPING FOR REFERENCE BUT NOT EXECUTED
    write_pyramidal_ometiff_OLD(
        pyramid,
        args.output,
        pixel_size,
        tile_size=args.tile_size,
        compression=args.compression
    )
    
    print("Registration complete!")


if __name__ == "__main__":
    main()

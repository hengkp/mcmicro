#!/usr/bin/env python
"""
Downsample a registered OME-TIFF by 2x to reduce memory requirements.
This creates a half-resolution version that's 1/4 the memory.
Uses only tifffile - no palom dependency.
"""

import argparse
import numpy as np
import tifffile
from pathlib import Path
import gc


def downsample_2x(img):
    """Downsample 2D image by factor of 2."""
    h, w = img.shape
    h2, w2 = h // 2, w // 2
    return img[:2*h2:2, :2*w2:2]


def build_pyramid(data, max_levels=5, min_size=512):
    """Build pyramid from CYX array."""
    levels = [data]
    for _ in range(1, max_levels):
        prev = levels[-1]
        _, h, w = prev.shape
        if min(h, w) < min_size:
            break
        # Downsample each channel
        down = np.stack([downsample_2x(prev[c]) for c in range(prev.shape[0])])
        levels.append(down)
    return levels


def main():
    parser = argparse.ArgumentParser(description="Downsample registered OME-TIFF")
    parser.add_argument("--input", required=True, help="Input OME-TIFF file")
    parser.add_argument("--output", required=True, help="Output OME-TIFF file")
    parser.add_argument("--level", type=int, default=1, help="Pyramid level to extract (default: 1)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading image: {input_path}")
    with tifffile.TiffFile(str(input_path)) as tif:
        series = tif.series[0]
        print(f"Available pyramid levels: {len(series.levels)}")
        
        if args.level >= len(series.levels):
            print(f"Warning: Level {args.level} not available, using level 0")
            level_idx = 0
        else:
            level_idx = args.level
        
        print(f"Reading level {level_idx}...")
        level = series.levels[level_idx]
        print(f"Level {level_idx} shape: {level.shape}")
        
        # Read the data
        img_data = level.asarray()
        
        # Get pixel size from OME metadata if available
        try:
            ome_meta = tifffile.xml2dict(tif.ome_metadata)
            pixels = ome_meta['OME']['Image']['Pixels']
            pixel_size_x = float(pixels.get('PhysicalSizeX', 1.0))
            pixel_size_y = float(pixels.get('PhysicalSizeY', 1.0))
            # Adjust for pyramid level
            pixel_size_x *= (2 ** level_idx)
            pixel_size_y *= (2 ** level_idx)
            print(f"Pixel size: {pixel_size_x} µm")
        except:
            pixel_size_x = pixel_size_y = 1.0
            print("Warning: Could not read pixel size from metadata")
    
    n_channels, height, width = img_data.shape
    print(f"Output shape: {n_channels} x {height} x {width}")
    print(f"Memory: {img_data.nbytes / 1e9:.2f} GB")
    
    print("\nBuilding pyramid...")
    pyramid = build_pyramid(img_data, max_levels=5, min_size=512)
    print(f"Created {len(pyramid)} pyramid levels")
    for i, lvl in enumerate(pyramid):
        print(f"  Level {i}: {lvl.shape}")
    
    print(f"\nWriting pyramidal OME-TIFF to: {output_path}")
    with tifffile.TiffWriter(str(output_path), bigtiff=True) as tif_out:
        n_sub = len(pyramid) - 1
        
        # Level 0 with metadata
        tif_out.write(
            pyramid[0],
            tile=(512, 512),
            compression='zlib',
            subifds=n_sub if n_sub > 0 else None,
            metadata={
                'axes': 'CYX',
                'PhysicalSizeX': float(pixel_size_x),
                'PhysicalSizeY': float(pixel_size_y),
                'PhysicalSizeXUnit': 'um',
                'PhysicalSizeYUnit': 'um',
            },
        )
        
        # Subresolution levels
        for i in range(1, len(pyramid)):
            tif_out.write(
                pyramid[i],
                tile=(512, 512),
                compression='zlib',
                subfiletype=1,
            )
    
    print(f"\nDone! Downsampled image saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()

      n      #!/usr/bin/env python
"""
Convert a flat multi-page OME-TIFF to pyramidal OME-TIFF.
Run this outside Docker where you have more memory available.

Usage:
    python convert_to_pyramidal.py input.ome.tif output_pyramidal.ome.tif
"""

import sys
import numpy as np
import tifffile
from pathlib import Path


def build_pyramid(data, max_levels=5, min_size_for_next=512):
    """Build a simple 2x downsampling pyramid from a 3D array (C, H, W)."""
    levels = [data]
    for lvl in range(1, max_levels):
        prev = levels[-1]
        _, h, w = prev.shape
        if min(h, w) < min_size_for_next:
            break
        h2 = h // 2
        w2 = w // 2
        down = prev[:, : 2 * h2 : 2, : 2 * w2 : 2]
        levels.append(down)
    return levels


def main():
    if len(sys.argv) != 3:
        print("Usage: python convert_to_pyramidal.py input.ome.tif output_pyramidal.ome.tif")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    print(f"Reading {input_path}...")
    with tifffile.TiffFile(str(input_path)) as tif:
        # Read all pages
        n_channels = len(tif.pages)
        first_page = tif.pages[0]
        shape = first_page.shape
        dtype = first_page.dtype
        
        print(f"  {n_channels} channels, {shape[0]} x {shape[1]}, {dtype}")
        print(f"  Loading all channels (~{(n_channels * shape[0] * shape[1] * 2) / 1e9:.1f} GB)...")
        
        data = np.zeros((n_channels, shape[0], shape[1]), dtype=dtype)
        for i, page in enumerate(tif.pages):
            if i % 5 == 0:
                print(f"    Channel {i+1}/{n_channels}...")
            data[i] = page.asarray()
        
        # Try to get pixel size from metadata
        try:
            pixel_size = tif.pages[0].tags.get('XResolution').value[1] / tif.pages[0].tags.get('XResolution').value[0]
            pixel_size = 1.0 / pixel_size * 1000  # Convert to microns
        except:
            pixel_size = 0.5  # Default
            print(f"  Warning: Could not read pixel size, using default {pixel_size} µm")
    
    print(f"\nBuilding pyramid...")
    pyr = build_pyramid(data, max_levels=5, min_size_for_next=512)
    print(f"  Created {len(pyr)} levels:")
    for i, lvl in enumerate(pyr):
        print(f"    Level {i}: {lvl.shape}")
    
    print(f"\nWriting pyramidal OME-TIFF to {output_path}...")
    with tifffile.TiffWriter(str(output_path), bigtiff=True) as tif:
        n_sub = len(pyr) - 1
        
        # Write level 0
        print("  Writing level 0 (full-res)...")
        tif.write(
            pyr[0],
            tile=(512, 512),
            compression='zlib',
            subifds=n_sub if n_sub > 0 else None,
            metadata={
                "axes": "CYX",
                "PhysicalSizeX": float(pixel_size),
                "PhysicalSizeY": float(pixel_size),
                "PhysicalSizeXUnit": "um",
                "PhysicalSizeYUnit": "um",
            },
        )
        
        # Write downsampled levels
        for i in range(1, len(pyr)):
            print(f"  Writing level {i}...")
            tif.write(
                pyr[i],
                tile=(512, 512),
                compression='zlib',
                subfiletype=1,
            )
    
    print(f"\nDone! Pyramidal OME-TIFF written to {output_path}")
    print(f"File size: {output_path.stat().st_size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()

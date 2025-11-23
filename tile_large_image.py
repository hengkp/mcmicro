#!/usr/bin/env python
"""
Tile a large OME-TIFF into smaller tiles for memory-efficient processing.
Each tile will be processed separately and then stitched back together.
"""

import argparse
import numpy as np
import tifffile
from pathlib import Path
import palom


def main():
    parser = argparse.ArgumentParser(description="Tile large OME-TIFF for processing")
    parser.add_argument("--input", required=True, help="Input OME-TIFF file")
    parser.add_argument("--output-dir", required=True, help="Output directory for tiles")
    parser.add_argument("--tile-size", type=int, default=10000, help="Tile size (default: 10000)")
    parser.add_argument("--overlap", type=int, default=500, help="Overlap between tiles (default: 500)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading image: {input_path}")
    reader = palom.reader.OmePyramidReader(str(input_path))
    
    # Read full resolution
    img_da = reader.read_level_channels(0, slice(None))
    n_channels, height, width = img_da.shape
    
    print(f"Image shape: {n_channels} x {height} x {width}")
    print(f"Tile size: {args.tile_size}, Overlap: {args.overlap}")
    
    # Calculate tile positions
    stride = args.tile_size - args.overlap
    tiles_info = []
    
    for y in range(0, height, stride):
        for x in range(0, width, stride):
            y_end = min(y + args.tile_size, height)
            x_end = min(x + args.tile_size, width)
            tiles_info.append((y, y_end, x, x_end))
    
    print(f"Creating {len(tiles_info)} tiles...")
    
    # Save tile positions for later stitching
    tile_info_file = output_dir / "tile_info.txt"
    with open(tile_info_file, 'w') as f:
        f.write(f"original_shape: {n_channels},{height},{width}\n")
        f.write(f"tile_size: {args.tile_size}\n")
        f.write(f"overlap: {args.overlap}\n")
        for idx, (y, y_end, x, x_end) in enumerate(tiles_info):
            f.write(f"tile_{idx:03d}: {y},{y_end},{x},{x_end}\n")
    
    # Extract and save each tile
    for idx, (y, y_end, x, x_end) in enumerate(tiles_info):
        print(f"  Tile {idx+1}/{len(tiles_info)}: [{y}:{y_end}, {x}:{x_end}]")
        
        tile_da = img_da[:, y:y_end, x:x_end]
        tile_np = tile_da.compute()
        
        output_file = output_dir / f"tile_{idx:03d}.ome.tif"
        
        tifffile.imwrite(
            str(output_file),
            tile_np,
            photometric='minisblack',
            metadata={'axes': 'CYX'},
        )
        
        del tile_np
    
    print(f"\nDone! Created {len(tiles_info)} tiles in {output_dir}")
    print(f"Tile info saved to: {tile_info_file}")


if __name__ == "__main__":
    main()

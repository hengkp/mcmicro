#!/usr/bin/env python3
"""
Create a simple non-pyramidal OME-TIFF to test QuPath compatibility.
This will help us isolate whether the issue is with:
1. The OME-XML structure
2. The pyramidal SubIFD structure
3. Something else
"""

import sys
import numpy as np
import tifffile
from pathlib import Path

def create_simple_ometiff(input_path, output_path):
    """Create a simple non-pyramidal OME-TIFF from the pyramidal one."""
    print(f"Reading: {input_path}")
    
    with tifffile.TiffFile(str(input_path)) as tif:
        # Get basic info
        n_pages = len(tif.pages)
        print(f"  Found {n_pages} pages")
        
        # Read first few pages to get structure
        first_page = tif.pages[0]
        h, w = first_page.shape
        dtype = first_page.dtype
        
        print(f"  Shape: {h} x {w}, dtype: {dtype}")
        
        # Count main IFDs (not SubIFDs)
        main_ifds = [p for p in tif.pages if not p.is_reduced]
        n_channels = len(main_ifds)
        print(f"  Main IFDs (channels): {n_channels}")
        
        # Read all main IFDs
        print(f"\nReading {n_channels} channels...")
        data = np.zeros((n_channels, h, w), dtype=dtype)
        for i, page in enumerate(main_ifds):
            if i % 5 == 0:
                print(f"  Channel {i+1}/{n_channels}...")
            data[i] = page.asarray()
    
    # Create simple OME-XML
    print(f"\nCreating simple OME-TIFF (no pyramid)...")
    
    with tifffile.TiffWriter(str(output_path), bigtiff=True) as tif_out:
        # Write as multi-channel CYX
        tif_out.write(
            data,
            photometric='minisblack',
            tile=(512, 512),
            compression='zlib',
            metadata={
                'axes': 'CYX',
                'PhysicalSizeX': 0.4995241762370626,
                'PhysicalSizeY': 0.4995241762370626,
                'PhysicalSizeXUnit': 'um',
                'PhysicalSizeYUnit': 'um',
            }
        )
    
    print(f"\nCreated: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1e9:.2f} GB")
    print("\nTry opening this in QuPath to test if the issue is with pyramids.")


if __name__ == "__main__":
    input_path = Path('/Users/heng/Dropbox/Macbook Pro/Projects/Spatial project/CyCIF (NY&Folk)/QPTIFF for Alignment/registration/QPTIFF for Alignment.ome.tif')
    output_path = Path('/Users/heng/Dropbox/Macbook Pro/Projects/Spatial project/CyCIF (NY&Folk)/QPTIFF for Alignment/registration/QPTIFF_simple.ome.tif')
    
    create_simple_ometiff(input_path, output_path)

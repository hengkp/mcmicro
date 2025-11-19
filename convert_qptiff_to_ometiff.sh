#!/bin/bash

# Path to bfconvert
BFCONVERT="/Users/heng/opt/bftools/bfconvert"

# Change to the raw_qptiff directory
cd '/Users/heng/Dropbox/Macbook Pro/Projects/Spatial project/CyCIF (NY&Folk)/QPTIFF for Alignment/raw_qptiff'

# Create output directory if needed
mkdir -p "../raw"

# Process each qptiff file
for f in c*.qptiff; do
    base=$(basename "$f" .qptiff)
    echo "Converting $f to ${base}.ome.tiff..."
    
    # Write pyramidal OME-TIFF, BigTIFF, tiled
    "$BFCONVERT" \
        -nolookup \
        -pyramid-scale 2 \
        -tilex 1024 -tiley 1024 \
        "$f" "../raw/${base}.ome.tiff"
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully converted $f"
    else
        echo "✗ Failed to convert $f"
    fi
done

echo ""
echo "Conversion complete. Checking output files:"
ls -lh '../raw/'*.ome.tiff

#!/bin/bash
# Final solution - Memory-efficient QuPath-compatible pyramidal OME-TIFF
# Each channel written as separate page with its own pyramid (standard OME-TIFF format)

echo "=== Cleaning ALL previous attempts ==="
rm -rf '/Users/heng/Documents/GitHub/mcmicro/work'/*

echo ""
echo "=== Running MCMICRO with memory-efficient PALOM registration ==="
echo "Format: Each channel as separate page (QuPath-compatible)"
echo "Expected time: 30-45 minutes"
echo "Peak memory: ~2GB"
echo ""

nextflow run /Users/heng/Documents/GitHub/mcmicro \
  --in '/Users/heng/Dropbox/Macbook Pro/Projects/Spatial project/CyCIF (NY&Folk)/QPTIFF for Alignment'

echo ""
echo "=== Done! ==="
echo "Output: registration/QPTIFF for Alignment.ome.tif"
echo ""
echo "To verify:"
echo "  1. Check file size: ls -lh registration/'QPTIFF for Alignment.ome.tif'"
echo "  2. Check structure: tiffinfo registration/'QPTIFF for Alignment.ome.tif' | head -50"
echo "  3. Open in QuPath - should load instantly with all 20 channels"
echo ""

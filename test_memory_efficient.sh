#!/bin/bash
# Test script for memory-efficient PALOM registration

set -e

echo "=== Building Docker image with memory-efficient script ==="
docker build -t hengkp/palom:2.0.0 .

echo ""
echo "=== Testing memory-efficient registration ==="
echo "This will process channels one at a time to stay within memory limits"
echo ""

# Run with memory limit
docker run --rm \
  -v $(pwd):/work \
  -m 20g \
  --memory-swap 20g \
  hengkp/palom:2.0.0 \
  python /usr/local/bin/register_akoya_palom_v2.py \
  --input-dir /work/ome_cycles \
  --pattern "c*.{ome.tiff,ome.tif}" \
  --output /work/registration/c_registered_v2.ome.tiff \
  --level 0 \
  --compression zlib \
  --max-pyramid-levels 5

echo ""
echo "=== Registration complete! ==="
echo "Output: registration/c_registered_v2.ome.tiff"
echo ""
echo "To monitor memory usage during execution, run in another terminal:"
echo "  docker stats"

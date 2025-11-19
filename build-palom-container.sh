#!/bin/bash
# Build script for PALOM container

set -e

VERSION=${1:-"1.0.0"}
REGISTRY=${2:-"labsyspharm/palom-mcmicro"}

echo "Building PALOM container..."
echo "Version: ${VERSION}"
echo "Registry: ${REGISTRY}"

# Build the container
docker build -t ${REGISTRY}:${VERSION} -t ${REGISTRY}:latest .

echo ""
echo "Build complete!"
echo ""
echo "To test the container:"
echo "  docker run --rm ${REGISTRY}:${VERSION} python /usr/local/bin/register_akoya_palom.py --help"
echo ""
echo "To push to registry:"
echo "  docker push ${REGISTRY}:${VERSION}"
echo "  docker push ${REGISTRY}:latest"

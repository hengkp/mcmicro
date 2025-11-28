#!/bin/bash
# Build and push PALOM container to Docker Hub (multi-platform)

set -e

REGISTRY="hengkp/palom"
VERSION="1.0.8"

echo "=========================================="
echo "PALOM Container Build & Push"
echo "=========================================="
echo "Registry: ${REGISTRY}"
echo "Version: ${VERSION}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running."
    echo "Please start Docker and try again."
    exit 1
fi

# Check Docker Hub login
echo "Checking Docker Hub authentication..."
echo "(You should already be logged in as hengkp)"
echo ""

# Create and use buildx builder for multi-platform
echo "Setting up multi-platform builder..."
docker buildx create --name palom-builder --use 2>/dev/null || docker buildx use palom-builder

# Build and push multi-platform image (linux/amd64 and linux/arm64)
echo ""
echo "Building and pushing multi-platform container..."
echo "Platforms: linux/amd64, linux/arm64"
echo ""

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t ${REGISTRY}:${VERSION} \
    -t ${REGISTRY}:latest \
    --push \
    .

echo ""
echo "=========================================="
echo "SUCCESS!"
echo "=========================================="
echo ""
echo "Pushed multi-platform images:"
echo "  - ${REGISTRY}:${VERSION}"
echo "  - ${REGISTRY}:latest"
echo ""
echo "Platforms: linux/amd64, linux/arm64"
echo ""
echo "To use in MCMICRO, the config is already set:"
echo "  container: ${REGISTRY}"
echo "  version: ${VERSION}"
echo ""
echo "Test on another machine with:"
echo "  docker pull ${REGISTRY}:${VERSION}"
echo ""
echo "To test locally:"
echo "  docker run --rm ${REGISTRY}:${VERSION} python /usr/local/bin/register_akoya_palom_v2.py --help"

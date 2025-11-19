#!/bin/bash
# Script to tag and push PALOM container to registry

set -e

VERSION=${1:-"1.0.0"}
REGISTRY=${2:-"labsyspharm/palom-mcmicro"}

echo "=========================================="
echo "PALOM Container Push Script"
echo "=========================================="
echo "Version: ${VERSION}"
echo "Registry: ${REGISTRY}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running."
    echo "Please start Docker and try again."
    exit 1
fi

# Check if the image exists locally
if ! docker images | grep -q "palom"; then
    echo "WARNING: No PALOM image found locally."
    echo "Building the container first..."
    ./build-palom-container.sh ${VERSION} ${REGISTRY}
fi

# Tag the container
echo ""
echo "Tagging container..."
docker tag ${REGISTRY}:latest ${REGISTRY}:${VERSION}

# Verify tags
echo ""
echo "Current PALOM images:"
docker images | grep -E "(REPOSITORY|palom)"

# Push to registry
echo ""
echo "Pushing to registry..."
echo "Note: You must be logged in to the registry (docker login)"
echo ""
read -p "Do you want to push now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing ${REGISTRY}:${VERSION}..."
    docker push ${REGISTRY}:${VERSION}
    
    echo "Pushing ${REGISTRY}:latest..."
    docker push ${REGISTRY}:latest
    
    echo ""
    echo "=========================================="
    echo "SUCCESS! Container pushed to registry."
    echo "=========================================="
    echo ""
    echo "Pushed images:"
    echo "  - ${REGISTRY}:${VERSION}"
    echo "  - ${REGISTRY}:latest"
    echo ""
    echo "Next steps:"
    echo "  1. Verify config/defaults.yml has the correct version"
    echo "  2. Test the container from the registry"
    echo "  3. Commit and push the configuration changes"
else
    echo ""
    echo "Push cancelled. To push manually, run:"
    echo "  docker push ${REGISTRY}:${VERSION}"
    echo "  docker push ${REGISTRY}:latest"
fi

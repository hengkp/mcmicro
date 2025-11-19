#!/bin/bash
# Verification script for PALOM container deployment readiness

echo "=========================================="
echo "PALOM Deployment Verification"
echo "=========================================="
echo ""

# Check Docker
echo "1. Checking Docker..."
if docker info > /dev/null 2>&1; then
    echo "   ✓ Docker is running"
    docker --version
else
    echo "   ✗ Docker is not running"
    echo "   → Start Docker and try again"
    exit 1
fi

echo ""

# Check for local PALOM images
echo "2. Checking for local PALOM images..."
if docker images | grep -q "palom"; then
    echo "   ✓ PALOM images found:"
    docker images | grep palom | awk '{print "     - " $1 ":" $2 " (" $7 " " $8 ")"}'
else
    echo "   ✗ No PALOM images found locally"
    echo "   → Run: ./build-palom-container.sh 1.0.0"
fi

echo ""

# Check config file
echo "3. Checking config/defaults.yml..."
if [ -f "config/defaults.yml" ]; then
    VERSION=$(grep -A 3 "registration-palom:" config/defaults.yml | grep "version:" | awk '{print $2}')
    CONTAINER=$(grep -A 3 "registration-palom:" config/defaults.yml | grep "container:" | awk '{print $2}')
    
    if [ -n "$VERSION" ]; then
        echo "   ✓ PALOM module configured"
        echo "     - Container: ${CONTAINER}"
        echo "     - Version: ${VERSION}"
    else
        echo "   ✗ PALOM module not found in config"
    fi
else
    echo "   ✗ config/defaults.yml not found"
fi

echo ""

# Check Dockerfile
echo "4. Checking Dockerfile..."
if [ -f "Dockerfile" ]; then
    echo "   ✓ Dockerfile exists"
    if grep -q "register_akoya_palom.py" Dockerfile; then
        echo "   ✓ Includes register_akoya_palom.py"
    fi
else
    echo "   ✗ Dockerfile not found"
fi

echo ""

# Check registration script
echo "5. Checking registration script..."
if [ -f "register_akoya_palom.py" ]; then
    echo "   ✓ register_akoya_palom.py exists"
    LINES=$(wc -l < register_akoya_palom.py)
    echo "     - ${LINES} lines"
else
    echo "   ✗ register_akoya_palom.py not found"
fi

echo ""

# Check registry authentication
echo "6. Checking registry authentication..."
if docker info 2>/dev/null | grep -q "Username"; then
    USERNAME=$(docker info 2>/dev/null | grep "Username:" | awk '{print $2}')
    echo "   ✓ Logged in as: ${USERNAME}"
else
    echo "   ⚠ Not logged in to Docker registry"
    echo "   → Run: docker login"
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Ready to deploy? Check the items above."
echo ""
echo "To deploy:"
echo "  ./push-palom-container.sh 1.0.0 labsyspharm/palom-mcmicro"
echo ""
echo "For detailed instructions, see:"
echo "  PALOM_CONTAINER_DEPLOYMENT.md"

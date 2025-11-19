#!/bin/bash
# Quick validation script - runs Python tests and shows summary
# This is the fastest way to validate the PALOM integration

set -e

echo "========================================"
echo "PALOM Integration - Quick Validation"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "main.nf" ]; then
    echo "ERROR: Please run this script from the project root directory"
    exit 1
fi

echo "Running Python integration tests..."
echo ""

# Run Python tests
if python tests/integration/test_palom_integration.py; then
    echo ""
    echo "========================================"
    echo "✓ All validation tests PASSED"
    echo "========================================"
    echo ""
    echo "What was tested:"
    echo "  ✓ PALOM module configuration"
    echo "  ✓ Registration workflow engine selection"
    echo "  ✓ Backward compatibility with ASHLAR"
    echo "  ✓ Output format compatibility"
    echo "  ✓ Error handling and validation"
    echo "  ✓ PALOM-specific options"
    echo ""
    echo "Next steps:"
    echo "  - Run full pipeline test: ./tests/integration/test_palom_integration.sh"
    echo "  - Test with real data: nextflow run main.nf --in <data> -params-file <params>"
    echo ""
    exit 0
else
    echo ""
    echo "========================================"
    echo "✗ Some validation tests FAILED"
    echo "========================================"
    echo ""
    echo "Please check the output above for details."
    echo ""
    exit 1
fi

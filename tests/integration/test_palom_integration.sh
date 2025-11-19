#!/bin/bash
# Integration tests for PALOM registration module in MCMICRO pipeline
# This script tests all aspects of PALOM integration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    log_info "Test $TESTS_RUN: $1"
}

test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log_info "✓ PASSED: $1"
}

test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log_error "✗ FAILED: $1"
}

# Check if file exists and is not empty
check_file_exists() {
    local file=$1
    if [ -f "$file" ] && [ -s "$file" ]; then
        return 0
    else
        return 1
    fi
}

# Check if OME-TIFF has pyramidal structure
check_pyramidal_tiff() {
    local file=$1
    # Use tiffinfo to check for SubIFDs (pyramid levels)
    if command -v tiffinfo &> /dev/null; then
        if tiffinfo "$file" | grep -q "SubIFD"; then
            return 0
        else
            log_warning "tiffinfo available but no SubIFDs found"
            return 1
        fi
    else
        log_warning "tiffinfo not available, skipping pyramidal check"
        return 0  # Pass if tool not available
    fi
}

# Check OME-TIFF metadata
check_ome_metadata() {
    local file=$1
    # Use tiffcomment or strings to check for OME-XML
    if command -v tiffcomment &> /dev/null; then
        if tiffcomment "$file" | grep -q "OME"; then
            return 0
        else
            return 1
        fi
    elif strings "$file" | grep -q "PhysicalSizeX"; then
        return 0
    else
        log_warning "Cannot verify OME metadata (tools not available)"
        return 0  # Pass if tools not available
    fi
}

# Print test summary
print_summary() {
    echo ""
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo "Total tests run: $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    else
        echo "Failed: $TESTS_FAILED"
    fi
    echo "========================================"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_info "All tests passed!"
        return 0
    else
        log_error "Some tests failed!"
        return 1
    fi
}

# Cleanup function
cleanup_test_dir() {
    local dir=$1
    if [ -d "$dir" ]; then
        log_info "Cleaning up test directory: $dir"
        rm -rf "$dir"
    fi
}

echo "========================================"
echo "PALOM Integration Test Suite"
echo "========================================"
echo ""

# Export this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log_info "Project root: $PROJECT_ROOT"
log_info "Test directory: $SCRIPT_DIR"

# Run all test subtasks
source "$SCRIPT_DIR/subtasks/test_8.1_palom_registration.sh"
source "$SCRIPT_DIR/subtasks/test_8.2_backward_compatibility.sh"
source "$SCRIPT_DIR/subtasks/test_8.3_downstream_compatibility.sh"
source "$SCRIPT_DIR/subtasks/test_8.4_error_handling.sh"
source "$SCRIPT_DIR/subtasks/test_8.5_palom_options.sh"

# Print final summary
print_summary
exit $?

# Quick Start Guide - PALOM Integration Tests

## Quick Test (Python - Recommended)

Run the Python test suite for fast validation of configuration and code structure:

```bash
python tests/integration/test_palom_integration.py
```

This will verify:
- ✓ Configuration files are correct
- ✓ PALOM module is properly defined
- ✓ Registration workflow has engine selection logic
- ✓ Error handling is implemented
- ✓ Options are properly configured

**Expected output**: All 13 tests should pass in < 1 second.

## Full Integration Test (Bash)

Run the full bash test suite for comprehensive testing:

```bash
./tests/integration/test_palom_integration.sh
```

This includes:
- Configuration validation (always runs)
- Pipeline execution tests (requires Nextflow + test data)
- Output validation (requires tiffinfo)

## Test Levels

### Level 1: Configuration Only (No Dependencies)
- Verifies all configuration files
- Checks code structure and validation logic
- **Requirements**: Python 3 or Bash
- **Time**: < 1 second

### Level 2: With Nextflow (Requires Nextflow)
- Executes actual pipeline runs
- Tests engine selection
- Validates error handling
- **Requirements**: Nextflow installed
- **Time**: Depends on data size

### Level 3: Full Validation (Requires Test Data)
- Tests with real imaging data
- Validates output format
- Tests downstream compatibility
- **Requirements**: Nextflow + exemplar-001 or test-data
- **Time**: Several minutes

## Individual Test Subtasks

Run specific test subtasks:

```bash
# Source the main test script to load helper functions
source tests/integration/test_palom_integration.sh

# Run individual subtask
source tests/integration/subtasks/test_8.1_palom_registration.sh
source tests/integration/subtasks/test_8.2_backward_compatibility.sh
source tests/integration/subtasks/test_8.3_downstream_compatibility.sh
source tests/integration/subtasks/test_8.4_error_handling.sh
source tests/integration/subtasks/test_8.5_palom_options.sh
```

## Continuous Integration

For CI/CD pipelines, use the Python tests:

```yaml
# Example GitHub Actions
- name: Run PALOM Integration Tests
  run: python tests/integration/test_palom_integration.py
```

## Troubleshooting

### All tests fail immediately
- Check that you're in the project root directory
- Verify file paths are correct

### "Nextflow not available" warnings
- This is normal if Nextflow isn't installed
- Configuration tests will still run and pass

### "No test data found" warnings
- This is normal if exemplar-001 isn't present
- Configuration tests will still run and pass

### Python import errors
- Ensure you're running from project root
- Check Python version (3.6+ required)

## Test Output

- **Python tests**: Output to `tests/integration/test_output_py/`
- **Bash tests**: Output to `tests/integration/test_output/`

Both directories are created automatically and can be safely deleted.

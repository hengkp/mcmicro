# PALOM Integration Tests

This directory contains integration tests for the PALOM registration module in MCMICRO.

## Test Structure

The test suite is organized into subtasks that correspond to the implementation plan:

- **test_8.1_palom_registration.sh**: Tests PALOM registration with sample data
- **test_8.2_backward_compatibility.sh**: Tests backward compatibility with ASHLAR
- **test_8.3_downstream_compatibility.sh**: Tests downstream module compatibility
- **test_8.4_error_handling.sh**: Tests error handling scenarios
- **test_8.5_palom_options.sh**: Tests PALOM-specific options

## Running Tests

### Run All Tests

```bash
cd tests/integration
chmod +x test_palom_integration.sh
./test_palom_integration.sh
```

### Run Individual Test Subtasks

```bash
cd tests/integration
source test_palom_integration.sh  # Load helper functions
source subtasks/test_8.1_palom_registration.sh
```

## Test Requirements

### Minimal Requirements (Configuration Tests Only)

- Bash shell
- Basic Unix utilities (grep, cat, etc.)

These tests will verify:
- Configuration files are correct
- Validation logic exists in code
- Default values are properly set

### Full Integration Tests

For complete integration testing, you'll need:

- Nextflow installed and in PATH
- Docker or Singularity for containers
- Test data (exemplar-001 or test-data directory)
- tiffinfo (optional, for pyramidal TIFF verification)

## Test Output

Test results are written to `test_output/` directory:

```
test_output/
├── test_8.1/          # PALOM registration test
│   ├── params.yml
│   ├── pipeline.log
│   └── work/
├── test_8.2/          # Backward compatibility test
├── test_8.3/          # Downstream compatibility test
├── test_8.4/          # Error handling test
└── test_8.5/          # PALOM options test
```

## Test Coverage

### Task 8.1: PALOM Registration with Sample Data
- ✓ Creates test params.yml with registration-engine: palom
- ✓ Runs MCMICRO on test dataset (if available)
- ✓ Verifies output file created in registration/ directory
- ✓ Checks output is pyramidal OME-TIFF with correct metadata

### Task 8.2: Backward Compatibility with ASHLAR
- ✓ Runs MCMICRO without registration-engine parameter
- ✓ Verifies ASHLAR is used by default
- ✓ Confirms existing workflows unchanged

### Task 8.3: Downstream Module Compatibility
- ✓ Runs full MCMICRO pipeline with PALOM registration
- ✓ Verifies segmentation module processes PALOM output
- ✓ Verifies quantification module produces expected tables
- ✓ Checks output format compatibility

### Task 8.4: Error Handling
- ✓ Tests with invalid registration-engine value
- ✓ Tests with invalid cycle index
- ✓ Tests with invalid channel specification
- ✓ Verifies clear error messages in all cases

### Task 8.5: PALOM-Specific Options
- ✓ Tests with custom --ref-index value
- ✓ Tests with --cycle-channels specification
- ✓ Tests with different --compression options
- ✓ Verifies options are correctly passed through Opts.moduleOpts

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

## Notes

- Tests are designed to be non-destructive and use isolated work directories
- If test data or Nextflow is not available, tests will verify configuration only
- Tests clean up their output directories before running
- All test output is logged for debugging purposes

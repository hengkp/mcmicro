# Implementation Plan

- [x] 1. Create PALOM container image
  - Build Dockerfile with conda environment and palom package
  - Copy register_akoya_palom.py script into container at /usr/local/bin/
  - Set appropriate permissions and entrypoint
  - Test container builds successfully locally
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 2. Update configuration files for PALOM module
  - [x] 2.1 Add registration-engine parameter to config/schema.yml
    - Add 'registration-engine' to the workflow parameter list
    - _Requirements: 1.3_
  
  - [x] 2.2 Add PALOM module specification to config/defaults.yml
    - Add registration-engine: ashlar to workflow section (default)
    - Add palom: --level 0 --ref-index 0 to options section
    - Add registration-palom module spec with container and version info
    - _Requirements: 1.2, 2.4, 2.5_

- [x] 3. Implement palom_align Nextflow process
  - [x] 3.1 Create palom_align process in modules/registration.nf
    - Define process with same input/output signature as ashlar process
    - Configure container from module specification
    - Set up publishDir for registration/ output
    - Set up publishDir for qc/provenance/ logs
    - Add when clause using Flow.doirun('registration', mcp.workflow)
    - _Requirements: 3.1, 3.2, 6.1, 6.2, 6.4, 6.5_
  
  - [x] 3.2 Write process script block
    - Create ome_cycles and registration directories
    - Build command to invoke register_akoya_palom.py with correct arguments
    - Pass module options using Opts.moduleOpts(module, mcp)
    - Generate versions.yml output with palom version
    - _Requirements: 3.2, 6.3_

- [x] 4. Update registration workflow to support engine selection
  - [x] 4.1 Add engine selection logic to registration workflow
    - Read registration-engine parameter from mcp.workflow
    - Default to 'ashlar' if parameter not specified
    - Add conditional branching: if engine == 'palom' vs engine == 'ashlar'
    - Call palom_align process when PALOM selected
    - Call ashlar process when ASHLAR selected (existing code)
    - _Requirements: 1.1, 1.2_
  
  - [x] 4.2 Add engine validation
    - Validate engine parameter is either 'ashlar' or 'palom'
    - Throw clear error message if invalid engine specified
    - _Requirements: 1.3, 1.4_
  
  - [x] 4.3 Unify output channels
    - Assign palom_align.out.img or ashlar.out.img to common registered variable
    - Emit registered channel from workflow
    - Ensure downstream modules receive identical channel structure
    - _Requirements: 3.1, 3.2_

- [x] 5. Enhance register_akoya_palom.py script for production use
  - [x] 5.1 Add robust error handling
    - Wrap coarse_register_affine in try-except with clear error message
    - Add try-except for constrain_shifts with fallback to unconstrained
    - Validate cycle index is in valid range before processing
    - Validate channel indices exist in input images
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 5.2 Ensure metadata preservation
    - Extract pixel_size from reference reader at level 0
    - Pass pixel_size to write_pyramidal_ometiff without scaling
    - Set PhysicalSizeX, PhysicalSizeY, and units in OME metadata
    - Verify axes specification is "CYX"
    - _Requirements: 3.4, 3.5_
  
  - [x] 5.3 Implement pyramidal output with correct compression
    - Use build_pyramid function to generate 2x downsampled levels
    - Write full-resolution level 0 with OME metadata
    - Write reduced-resolution levels as subIFDs
    - Apply zlib compression by default (configurable via --compression)
    - Use 512x512 tile size for all levels
    - _Requirements: 3.3, 3.5, 3.6_
  
  - [x] 5.4 Add input file discovery and sorting
    - Use pathlib.Path.glob to find files matching pattern
    - Sort files alphabetically to establish consistent cycle order
    - Raise clear error if no files found
    - Print discovered files with cycle indices for user verification
    - _Requirements: 5.1, 5.2_
  
  - [x] 5.5 Implement channel selection and concatenation
    - Parse cycle-channels specification into mapping dict
    - For each cycle, select specified channels or keep all if not specified
    - Concatenate registered cycles along channel axis (axis=0)
    - Maintain cycle order in final concatenated output
    - _Requirements: 4.4, 5.5_

- [x] 6. Create Dockerfile for PALOM container
  - [x] 6.1 Write Dockerfile with base image and dependencies
    - Use continuumio/miniconda3:latest as base
    - Install conda packages: python=3.10, tifffile, dask, numpy, scikit-image, zarr
    - Install palom[all] via pip
    - Clean conda cache to reduce image size
    - _Requirements: 2.1_
  
  - [x] 6.2 Add registration script to container
    - Copy register_akoya_palom.py to /usr/local/bin/
    - Set executable permissions with chmod +x
    - Set WORKDIR to /work
    - Set ENTRYPOINT to /bin/bash
    - _Requirements: 2.2_

- [-] 7. Build and publish PALOM container
  - [x] 7.1 Build container locally and test
    - Run docker build command
    - Test container can execute register_akoya_palom.py --help
    - Verify palom package is importable
    - Check container size is reasonable (<2GB)
    - _Requirements: 2.3_
  
  - [x] 7.2 Tag and push container to registry
    - Tag with semantic version (e.g., 1.0.0)
    - Push to labsyspharm/palom-mcmicro or ghcr.io/labsyspharm/palom-mcmicro
    - Update version in config/defaults.yml to match pushed tag
    - _Requirements: 2.3, 2.4_

- [x] 8. Integration testing with MCMICRO pipeline
  - [x] 8.1 Test PALOM registration with sample data
    - Create test params.yml with registration-engine: palom
    - Run MCMICRO on exemplar-001 or similar dataset
    - Verify output file created in registration/ directory
    - Check output is pyramidal OME-TIFF with correct metadata
    - _Requirements: 1.1, 3.1, 3.2, 3.3, 3.4_
  
  - [x] 8.2 Test backward compatibility with ASHLAR
    - Run MCMICRO without registration-engine parameter
    - Verify ASHLAR is used by default
    - Confirm existing workflows unchanged
    - _Requirements: 1.2_
  
  - [x] 8.3 Test downstream module compatibility
    - Run full MCMICRO pipeline with PALOM registration
    - Verify segmentation module processes PALOM output successfully
    - Verify quantification module produces expected tables
    - Check visualization module can render PALOM output
    - _Requirements: 3.1, 3.2_
  
  - [x] 8.4 Test error handling
    - Test with invalid registration-engine value
    - Test with invalid cycle index
    - Test with invalid channel specification
    - Verify clear error messages in all cases
    - _Requirements: 1.4, 8.1, 8.2, 8.4, 8.5_
  
  - [x] 8.5 Test PALOM-specific options
    - Test with custom --ref-index value
    - Test with --cycle-channels specification
    - Test with different --compression options
    - Verify options are correctly passed through Opts.moduleOpts
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ]* 9. Create documentation
  - [ ]* 9.1 Write user guide for PALOM registration
    - Document how to enable PALOM via registration-engine parameter
    - Explain PALOM vs ASHLAR differences and use cases
    - Provide example parameter configurations
    - Document all PALOM-specific options
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ]* 9.2 Add troubleshooting guide
    - Document common PALOM registration issues
    - Provide solutions for insufficient keypoints error
    - Explain how to interpret PALOM log output
    - Add FAQ section for PALOM-specific questions
    - _Requirements: 7.5_
  
  - [ ]* 9.3 Update MCMICRO main documentation
    - Add PALOM to list of registration modules
    - Update registration section with engine selection info
    - Add PALOM to module overview diagram
    - Update parameter reference with registration-engine
    - _Requirements: 7.1, 7.2_

- [ ]* 10. Performance optimization and validation
  - [ ]* 10.1 Benchmark PALOM vs ASHLAR performance
    - Run both engines on identical test datasets
    - Measure execution time, memory usage, output size
    - Document performance characteristics
    - _Requirements: 3.5, 3.6_
  
  - [ ]* 10.2 Optimize PALOM parameters for common use cases
    - Test different thumbnail sizes for coarse alignment
    - Evaluate pyramid level selection for registration quality
    - Determine optimal compression settings
    - Document recommended settings for different data types
    - _Requirements: 4.1, 4.2, 4.3_

# Requirements Document

## Introduction

This specification defines the integration of PALOM (Piecewise Alignment for Large-scale Optical Microscopy) as a first-class registration module within the MCMICRO pipeline. Currently, MCMICRO uses ASHLAR as the sole registration engine for stitching and aligning multi-cycle tissue imaging data. This feature will enable users to choose PALOM as an alternative registration engine, particularly beneficial for Akoya Phenocycler data where PALOM has demonstrated superior performance in handling pre-stitched, multi-cycle OME-TIFF images.

The integration will maintain full compatibility with MCMICRO's existing workflow architecture, allowing PALOM to produce identical output formats and metadata as ASHLAR, ensuring seamless downstream processing through segmentation, quantification, and visualization modules.

## Glossary

- **MCMICRO**: A modular, end-to-end pipeline for processing multiplexed whole-slide imaging data
- **PALOM**: Piecewise Alignment for Large-scale Optical Microscopy - a Python-based registration tool
- **ASHLAR**: Alignment by Simultaneous Harmonization of Layer/Adjacency Registration - the current default registration module
- **Registration Module**: A MCMICRO module responsible for stitching and aligning multi-cycle imaging data
- **OME-TIFF**: Open Microscopy Environment Tagged Image File Format - a standardized format for microscopy images
- **Pyramidal TIFF**: A multi-resolution TIFF file containing the full-resolution image plus downsampled versions
- **Container**: A Docker or Singularity containerized environment for running module code
- **Nextflow Process**: A computational task definition in the Nextflow workflow language
- **Module Specification**: Configuration defining a module's container, version, and execution parameters
- **Workflow Parameter**: User-configurable setting that controls pipeline behavior
- **Channel Selection**: The ability to specify which image channels to use for registration and which to retain in output
- **Pixel Size Metadata**: Physical dimensions (in micrometers) of image pixels stored in OME-TIFF metadata

## Requirements

### Requirement 1

**User Story:** As a MCMICRO user, I want to select PALOM as my registration engine instead of ASHLAR, so that I can leverage PALOM's superior alignment capabilities for my Akoya Phenocycler data.

#### Acceptance Criteria

1. WHEN THE User specifies `registration.engine: palom` in the workflow parameters, THE MCMICRO Pipeline SHALL execute the PALOM registration module instead of ASHLAR.
2. WHEN THE User specifies `registration.engine: ashlar` or omits the registration engine parameter, THE MCMICRO Pipeline SHALL execute the ASHLAR registration module as the default behavior.
3. THE MCMICRO Pipeline SHALL validate the registration engine parameter value against the allowed values of "ashlar" and "palom".
4. IF THE User specifies an invalid registration engine value, THEN THE MCMICRO Pipeline SHALL terminate with a clear error message indicating the valid options.

### Requirement 2

**User Story:** As a MCMICRO developer, I want PALOM packaged as a containerized module following MCMICRO conventions, so that it integrates seamlessly with the existing module architecture.

#### Acceptance Criteria

1. THE PALOM Container SHALL include the palom Python package with all required dependencies (tifffile, dask, numpy, scikit-image).
2. THE PALOM Container SHALL include the register_akoya_palom.py script as an executable at a standard path.
3. THE PALOM Container SHALL be published to a container registry accessible to MCMICRO users.
4. THE Module Specification SHALL define the PALOM module in config/defaults.yml with container name, version, and command structure matching MCMICRO conventions.
5. THE Module Specification SHALL support user-configurable options through the options.palom parameter.

### Requirement 3

**User Story:** As a MCMICRO user, I want PALOM to produce output files identical in format and location to ASHLAR, so that downstream segmentation and quantification modules work without modification.

#### Acceptance Criteria

1. THE PALOM Module SHALL write the registered image to the registration/ directory within the project folder.
2. THE PALOM Module SHALL produce a pyramidal OME-TIFF file with the naming pattern `{sample_name}.ome.tif`.
3. THE PALOM Module SHALL include multiple pyramid levels in the output OME-TIFF with 2x downsampling between levels.
4. THE PALOM Module SHALL preserve the original pixel size metadata from the reference cycle in all pyramid levels.
5. THE PALOM Module SHALL use zlib compression by default for all pyramid levels to balance file size and compatibility.
6. THE PALOM Module SHALL write tiled TIFF data with 512x512 pixel tiles for efficient random access.

### Requirement 4

**User Story:** As a MCMICRO user, I want to configure PALOM-specific registration parameters, so that I can optimize alignment quality for my specific imaging data.

#### Acceptance Criteria

1. THE PALOM Module SHALL accept a reference cycle index parameter to specify which cycle serves as the alignment reference.
2. THE PALOM Module SHALL accept reference channel and moving channel parameters to specify which channels are used for computing alignment transformations.
3. THE PALOM Module SHALL accept a pyramid level parameter to control whether registration is performed at full resolution or a downsampled level.
4. THE PALOM Module SHALL accept a cycle-channels parameter to specify which channels from each cycle are retained in the final output.
5. THE PALOM Module SHALL provide sensible default values for all parameters (ref-index: 0, ref-channel: 0, moving-channel: 0, level: 0).

### Requirement 5

**User Story:** As a MCMICRO user, I want PALOM to handle pre-stitched multi-cycle OME-TIFF files, so that I can register Akoya Phenocycler data that has already been stitched by the instrument software.

#### Acceptance Criteria

1. WHEN THE User places pre-stitched per-cycle OME-TIFF files in the raw/ directory, THE PALOM Module SHALL detect and process these files.
2. THE PALOM Module SHALL sort input files alphabetically to establish a consistent cycle ordering.
3. THE PALOM Module SHALL read multi-channel OME-TIFF files and extract specified channels for registration.
4. THE PALOM Module SHALL apply feature-based affine registration followed by local block-wise alignment to each moving cycle.
5. THE PALOM Module SHALL concatenate all registered cycles along the channel axis to produce a single multi-channel output image.

### Requirement 6

**User Story:** As a MCMICRO developer, I want the PALOM module to follow Nextflow best practices, so that it maintains consistency with other MCMICRO modules and supports provenance tracking.

#### Acceptance Criteria

1. THE PALOM Nextflow Process SHALL publish output images to the registration/ directory using Nextflow's publishDir directive.
2. THE PALOM Nextflow Process SHALL publish command scripts and logs to the qc/provenance/ directory for reproducibility.
3. THE PALOM Nextflow Process SHALL emit a versions.yml file containing the palom package version.
4. THE PALOM Nextflow Process SHALL use the module specification from mcp.modules['registration'] to determine container and options.
5. THE PALOM Nextflow Process SHALL only execute when Flow.doirun('registration', mcp.workflow) returns true.

### Requirement 7

**User Story:** As a MCMICRO user, I want clear documentation on when to use PALOM versus ASHLAR, so that I can choose the appropriate registration engine for my data type.

#### Acceptance Criteria

1. THE Documentation SHALL describe the differences between PALOM and ASHLAR registration approaches.
2. THE Documentation SHALL provide guidance on which registration engine is recommended for different imaging platforms (Akoya Phenocycler, CyCIF, etc.).
3. THE Documentation SHALL include example parameter configurations for common PALOM use cases.
4. THE Documentation SHALL explain how to interpret PALOM-specific parameters and their effects on registration quality.
5. THE Documentation SHALL provide troubleshooting guidance for common PALOM registration issues.

### Requirement 8

**User Story:** As a MCMICRO user, I want PALOM to handle registration failures gracefully, so that I receive clear error messages when alignment cannot be completed.

#### Acceptance Criteria

1. IF THE PALOM Module cannot find sufficient keypoints for coarse alignment, THEN THE Module SHALL terminate with an error message indicating insufficient image features.
2. IF THE PALOM Module encounters invalid input file formats, THEN THE Module SHALL terminate with an error message specifying the expected format.
3. IF THE PALOM Module fails during block-wise shift computation, THEN THE Module SHALL attempt to proceed with unconstrained shifts and log a warning.
4. THE PALOM Module SHALL validate that all specified channel indices exist in the input images before processing.
5. THE PALOM Module SHALL validate that the reference cycle index is within the range of available cycles.

# Design Document: PALOM Registration Module Integration

## Overview

This design document describes the integration of PALOM (Piecewise Alignment for Large-scale Optical Microscopy) as an alternative registration engine within the MCMICRO pipeline. The integration follows MCMICRO's modular architecture, allowing users to select between ASHLAR (default) and PALOM registration engines through workflow parameters.

The design maintains backward compatibility with existing MCMICRO workflows while introducing a new configuration parameter `registration.engine` that controls which registration module executes. Both engines produce identical output formats (pyramidal OME-TIFF files in the `registration/` directory), ensuring seamless integration with downstream segmentation, quantification, and visualization modules.

### Key Design Principles

1. **Minimal Disruption**: Existing ASHLAR-based workflows continue to work without modification
2. **Output Compatibility**: PALOM produces byte-for-byte compatible output formats with ASHLAR
3. **Configuration Consistency**: PALOM follows the same parameter structure as other MCMICRO modules
4. **Container Isolation**: PALOM runs in its own container with all dependencies bundled
5. **Provenance Tracking**: All execution artifacts are logged for reproducibility

## Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     MCMICRO Pipeline                         │
│                                                              │
│  ┌────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │ Raw Images │───▶│ Registration     │───▶│ Segmentation│ │
│  │  (raw/)    │    │  (registration/) │    │             │ │
│  └────────────┘    └──────────────────┘    └─────────────┘ │
│                             │                                │
│                             ▼                                │
│                    ┌─────────────────┐                      │
│                    │ Engine Selector │                      │
│                    │ (main.nf)       │                      │
│                    └────────┬────────┘                      │
│                             │                                │
│              ┌──────────────┴──────────────┐                │
│              ▼                              ▼                │
│     ┌────────────────┐            ┌────────────────┐        │
│     │ ASHLAR Process │            │ PALOM Process  │        │
│     │ (default)      │            │ (new)          │        │
│     └────────────────┘            └────────────────┘        │
│              │                              │                │
│              └──────────────┬───────────────┘                │
│                             ▼                                │
│                    {sample}.ome.tif                          │
│                    (pyramidal, tiled)                        │
└─────────────────────────────────────────────────────────────┘
```

### Module Architecture

The PALOM integration consists of four main components:

1. **Container Image**: Docker/Singularity container with PALOM and dependencies
2. **Nextflow Process**: `palom_align` process in `modules/registration.nf`
3. **Registration Script**: `register_akoya_palom.py` Python script
4. **Configuration**: Module specification in `config/defaults.yml`

## Components and Interfaces

### 1. Container Image

**Purpose**: Provide an isolated, reproducible environment for PALOM execution.

**Base Image**: `continuumio/miniconda3:latest`

**Dependencies**:
- Python 3.10
- palom[all] (via pip)
- tifffile 2023.7.10
- dask
- numpy
- scikit-image 0.21
- zarr 2.14.2

**Dockerfile Structure**:
```dockerfile
FROM continuumio/miniconda3:latest

# Install conda dependencies
RUN conda install -y -c conda-forge \
    python=3.10 \
    tifffile=2023.7.10 \
    dask \
    numpy \
    scikit-image=0.21 \
    zarr=2.14.2 \
    && conda clean -afy

# Install palom via pip
RUN pip install --no-cache-dir "palom[all]"

# Copy registration script
COPY register_akoya_palom.py /usr/local/bin/register_akoya_palom.py
RUN chmod +x /usr/local/bin/register_akoya_palom.py

# Set working directory
WORKDIR /work

ENTRYPOINT ["/bin/bash"]
```

**Container Registry**: `labsyspharm/palom-mcmicro` or `ghcr.io/labsyspharm/palom-mcmicro`

**Versioning**: Follow semantic versioning (e.g., `1.0.0`, `1.0.1`)

### 2. Nextflow Process: palom_align

**Location**: `modules/registration.nf`

**Process Definition**:

```groovy
process palom_align {
    container "${params.contPfx}${module.container}:${module.version}"
    publishDir "${params.in}/registration", mode: 'copy', pattern: '*.ome.tif'
    
    // Provenance
    publishDir "${Flow.QC(params.in, 'provenance')}", mode: 'copy',
      pattern: '.command.{sh,log}',
      saveAs: {fn -> fn.replace('.command', "${module.name}")}
    
    input:
      val mcp
      val module
      val sampleName
      path lraw       // Staged files
      val lrelPath    // Relative paths for script
      path lffp       // Flat-field (unused by PALOM, for compatibility)
      path ldfp       // Dark-field (unused by PALOM, for compatibility)

    output:
      path "*.ome.tif", emit: img
      tuple path('.command.sh'), path('.command.log')
      path "versions.yml", emit: versions

    when: Flow.doirun('registration', mcp.workflow)
    
    script:
    def imgs = lrelPath.collect{ Util.escapeForShell(it) }.join(" ")
    def opts = Opts.moduleOpts(module, mcp)
    """
    # Create working directories
    mkdir -p ome_cycles registration
    
    # Run PALOM registration
    python /usr/local/bin/register_akoya_palom.py \\
      --input-dir . \\
      --pattern "*.{ome.tiff,ome.tif}" \\
      --output ${sampleName}.ome.tif \\
      ${opts}
    
    # Record versions
    cat <<-END_VERSIONS > versions.yml
    "${module.name}":
        palom: \$(python -c 'import palom; print(palom.__version__)')
        python: \$(python --version | sed 's/Python //g')
    END_VERSIONS
    """
}
```

**Interface Contract**:
- **Inputs**: Same as `ashlar` process for compatibility
  - `mcp`: MCMICRO parameters
  - `module`: Module specification
  - `sampleName`: Sample identifier
  - `lraw`: Staged raw image files
  - `lrelPath`: Relative paths to images
  - `lffp`, `ldfp`: Illumination profiles (ignored by PALOM)
- **Outputs**:
  - `*.ome.tif`: Registered pyramidal OME-TIFF
  - Command provenance files
  - Version information

### 3. Registration Script: register_akoya_palom.py

**Location**: Embedded in container at `/usr/local/bin/register_akoya_palom.py`

**Command-Line Interface**:

```
python register_akoya_palom.py \
  --input-dir <directory> \
  --pattern <glob_pattern> \
  --output <output_path> \
  [--ref-index <int>] \
  [--ref-channel <int>] \
  [--moving-channel <int>] \
  [--level <int>] \
  [--cycle-channels <spec>] \
  [--thumbnail-size <int>] \
  [--max-pyramid-levels <int>] \
  [--min-size-for-next-level <int>] \
  [--tile-size <int>] \
  [--compression <none|zlib|lzw>]
```

**Key Functions**:

1. **parse_args()**: Parse command-line arguments
2. **parse_cycle_channels()**: Parse channel selection specification
3. **build_pyramid()**: Generate multi-resolution pyramid levels
4. **write_pyramidal_ometiff()**: Write pyramidal OME-TIFF with metadata
5. **main()**: Orchestrate registration workflow

**Registration Workflow**:

```
1. Discover and sort input cycle files
2. Load reference cycle (specified by --ref-index)
3. Extract reference registration channel
4. For each moving cycle:
   a. Load moving cycle
   b. Extract moving registration channel
   c. Compute coarse affine alignment (feature-based)
   d. Compute fine block-wise shifts
   e. Apply transformations to all channels
   f. Select specified channels for output
5. Concatenate all cycles along channel axis
6. Build pyramid with 2x downsampling
7. Write pyramidal OME-TIFF with metadata
```

**Metadata Preservation**:
- Pixel size (PhysicalSizeX, PhysicalSizeY) from reference cycle
- Units (µm)
- Axes specification (CYX)
- Channel count and ordering

### 4. Configuration Updates

**config/defaults.yml** - Add PALOM module specification:

```yaml
workflow:
  start-at: registration
  stop-at: quantification
  # ... existing parameters ...
  registration-engine: ashlar  # NEW: default to ashlar

options:
  ashlar: -m 30
  palom: --level 0 --ref-index 0  # NEW: PALOM default options

modules:
  registration:
    # Existing ASHLAR spec (unchanged)
    name: ashlar
    container: labsyspharm/ashlar
    version: 1.17.0
  registration-palom:  # NEW: PALOM spec
    name: palom
    container: labsyspharm/palom-mcmicro
    version: 1.0.0
```

**config/schema.yml** - Add registration-engine parameter:

```yaml
workflow:
  - sample-name
  - start-at
  - stop-at
  # ... existing parameters ...
  - registration-engine  # NEW
```

### 5. Workflow Integration

**modules/registration.nf** - Updated workflow:

```groovy
workflow registration {
    take:
      mcp
      raw
      ffp
      dfp

    main:
      rawst = raw.toSortedList{a, b -> a[0] <=> b[0]}.transpose()
      sampleName = file(params.in).name

      // Determine which registration engine to use
      def engine = mcp.workflow['registration-engine'] ?: 'ashlar'
      
      if (engine == 'palom') {
        // Use PALOM module specification
        palom_align(
          mcp,
          mcp.modules['registration-palom'],
          sampleName,
          rawst.first(),
          rawst.last(),
          ffp.toSortedList{a, b -> a.getName() <=> b.getName()},
          dfp.toSortedList{a, b -> a.getName() <=> b.getName()}
        )
        registered = palom_align.out.img
      } else if (engine == 'ashlar') {
        // Use ASHLAR (existing code)
        ashlar(
          mcp,
          mcp.modules['registration'],
          sampleName,
          rawst.first(),
          rawst.last(),
          ffp.toSortedList{a, b -> a.getName() <=> b.getName()},
          dfp.toSortedList{a, b -> a.getName() <=> b.getName()}
        )
        registered = ashlar.out.img
      } else {
        error "Unknown registration engine: ${engine}. Valid options: ashlar, palom"
      }

    emit:
      registered
}
```

## Data Models

### Input Data Model

**Raw Image Files**:
- Format: OME-TIFF (`.ome.tif`, `.ome.tiff`)
- Organization: One file per cycle
- Naming: Alphabetically sortable (e.g., `c1.ome.tiff`, `c2.ome.tiff`)
- Structure: Multi-channel, single Z-plane, pyramidal or flat
- Location: `{project}/raw/`

**Cycle Structure**:
```
Cycle File (OME-TIFF)
├── Channel 0 (e.g., DAPI)
├── Channel 1 (e.g., Marker 1)
├── Channel 2 (e.g., Marker 2)
└── Channel N
```

### Output Data Model

**Registered Image**:
- Format: Pyramidal OME-TIFF
- Filename: `{sample_name}.ome.tif`
- Location: `{project}/registration/`
- Structure:
  ```
  OME-TIFF File
  ├── Level 0 (Full Resolution)
  │   ├── Channel 0 (Cycle 0, Channel X)
  │   ├── Channel 1 (Cycle 0, Channel Y)
  │   ├── Channel 2 (Cycle 1, Channel X)
  │   └── Channel N
  ├── Level 1 (2x downsampled)
  ├── Level 2 (4x downsampled)
  └── Level N
  ```

**Metadata**:
```yaml
OME-XML Metadata:
  PhysicalSizeX: <value_from_reference>
  PhysicalSizeY: <value_from_reference>
  PhysicalSizeXUnit: µm
  PhysicalSizeYUnit: µm
  Axes: CYX
  Channels: <concatenated_from_all_cycles>
  
TIFF Tags:
  TileWidth: 512
  TileHeight: 512
  Compression: zlib (default)
  BigTIFF: true
  SubIFDs: <pyramid_levels - 1>
```

### Configuration Data Model

**User Configuration** (`params.yml`):
```yaml
workflow:
  registration-engine: palom  # or 'ashlar'
  
options:
  palom: >
    --ref-index 0
    --ref-channel 0
    --moving-channel 0
    --level 0
    --cycle-channels "0:0,1;1:0,2"
```

**Module Specification** (internal):
```yaml
registration-palom:
  name: palom
  container: labsyspharm/palom-mcmicro
  version: 1.0.0
```

## Error Handling

### Error Categories and Responses

#### 1. Configuration Errors

**Invalid Registration Engine**:
```groovy
if (!(engine in ['ashlar', 'palom'])) {
    error "Unknown registration engine: ${engine}. Valid options: ashlar, palom"
}
```

**Missing Required Parameters**:
- Handled by argparse in Python script
- Returns clear error message with usage information

#### 2. Input Validation Errors

**No Input Files Found**:
```python
if not files:
    raise FileNotFoundError(
        f"No files found in {input_dir} matching {args.pattern}"
    )
```

**Invalid Cycle Index**:
```python
if not (0 <= args.ref_index < len(files)):
    raise ValueError(
        f"ref-index {args.ref_index} is out of range for {len(files)} files."
    )
```

**Invalid Channel Specification**:
```python
if idx not in range(n_files):
    raise ValueError(
        f"cycle index {idx} in --cycle-channels is out of range [0, {n_files-1}]."
    )
```

#### 3. Registration Errors

**Insufficient Keypoints**:
```python
try:
    aligner.coarse_register_affine(n_keypoints=4000)
except Exception as e:
    print(f"ERROR: Coarse registration failed. "
          f"Insufficient image features for alignment. "
          f"Details: {repr(e)}")
    sys.exit(1)
```

**Block Shift Computation Failure**:
```python
try:
    aligner.constrain_shifts()
except Exception as e:
    print(f"WARNING: constrain_shifts failed "
          f"(likely no valid block shifts). "
          f"Proceeding with unconstrained shifts. "
          f"Error: {repr(e)}")
    # Continue with unconstrained shifts
```

#### 4. Output Errors

**Write Permission Issues**:
- Handled by Nextflow's publishDir mechanism
- Fails with clear error if output directory not writable

**Disk Space Issues**:
- Python will raise `OSError` if insufficient disk space
- Error message includes file path and required space

### Error Logging

All errors are logged to:
1. **Nextflow log**: `.nextflow.log`
2. **Process log**: `{project}/qc/provenance/palom.log`
3. **Standard error**: Captured by Nextflow

## Testing Strategy

### Unit Tests

**Test Scope**: Individual Python functions in `register_akoya_palom.py`

**Test Cases**:
1. `test_parse_cycle_channels()`: Validate channel specification parsing
2. `test_build_pyramid()`: Verify pyramid generation with correct dimensions
3. `test_write_pyramidal_ometiff()`: Confirm metadata preservation
4. `test_parse_args()`: Validate argument parsing and defaults

**Test Framework**: pytest

**Location**: `tests/unit/test_palom_script.py`

### Integration Tests

**Test Scope**: End-to-end PALOM module execution within MCMICRO

**Test Cases**:

1. **Basic Registration**:
   - Input: 2 cycles, 3 channels each
   - Expected: Single OME-TIFF with 6 channels
   - Validation: File exists, correct dimensions, metadata preserved

2. **Channel Selection**:
   - Input: 2 cycles with `--cycle-channels "0:0,1;1:0"`
   - Expected: Output with 3 channels (not 6)
   - Validation: Correct channel count

3. **Pyramid Generation**:
   - Input: Large image (>10k x 10k pixels)
   - Expected: Multiple pyramid levels
   - Validation: SubIFDs present, correct downsampling factors

4. **Error Handling**:
   - Input: Invalid cycle index
   - Expected: Clear error message, non-zero exit code
   - Validation: Error message contains expected text

**Test Framework**: Nextflow test framework + pytest

**Location**: `tests/integration/test_palom_module.nf`

### Comparison Tests

**Test Scope**: Validate PALOM output compatibility with downstream modules

**Test Cases**:

1. **Segmentation Compatibility**:
   - Run MCMICRO with PALOM registration
   - Run segmentation on PALOM output
   - Validation: Segmentation completes successfully

2. **Quantification Compatibility**:
   - Run full pipeline with PALOM
   - Validation: Quantification tables generated correctly

3. **Visualization Compatibility**:
   - Generate Minerva story from PALOM output
   - Validation: Visualization renders correctly

**Test Data**: Exemplar datasets (e.g., exemplar-001, exemplar-002)

### Performance Tests

**Test Scope**: Validate PALOM performance characteristics

**Metrics**:
1. **Execution Time**: Compare PALOM vs ASHLAR on identical inputs
2. **Memory Usage**: Peak memory consumption during registration
3. **Output Size**: Compressed file size with different compression options

**Test Cases**:
1. Small dataset (2 cycles, 2k x 2k pixels)
2. Medium dataset (5 cycles, 10k x 10k pixels)
3. Large dataset (10 cycles, 20k x 20k pixels)

### Validation Criteria

**All tests must pass**:
- Exit code 0 for successful runs
- Expected output files present
- Metadata validation (pixel size, channel count)
- No errors in logs

**Performance benchmarks**:
- PALOM execution time < 2x ASHLAR time (for comparable datasets)
- Memory usage < 32GB for typical datasets
- Output file size reasonable (< 2x uncompressed size with zlib)

## Implementation Notes

### Pixel Size Preservation

Critical requirement: PALOM must preserve the exact pixel size from the reference cycle, regardless of the pyramid level used for registration.

```python
# Read pixel size from reference at level 0
pixel_size = float(ref_reader.pixel_size)  # e.g., 0.44 µm

# Use this value for ALL pyramid levels in output
metadata = {
    "PhysicalSizeX": pixel_size,  # NOT scaled by level_downsamples
    "PhysicalSizeY": pixel_size,
    "PhysicalSizeXUnit": "µm",
    "PhysicalSizeYUnit": "µm",
}
```

### Compression Strategy

Default to `zlib` compression for balance between file size and compatibility:
- **zlib**: Good compression, widely supported, moderate speed
- **lzw**: Less compression, faster, universal support
- **none**: No compression, fastest, largest files

Users can override via `--palom-opts "--compression lzw"`.

### Channel Concatenation Order

Channels are concatenated in cycle order, with channels from each cycle appearing consecutively:

```
Output Channel Order:
[Cycle0_Ch0, Cycle0_Ch1, ..., Cycle1_Ch0, Cycle1_Ch1, ..., CycleN_ChM]
```

This matches the expected behavior for downstream MCMICRO modules.

### Backward Compatibility

The integration maintains full backward compatibility:
- Existing workflows without `registration-engine` parameter use ASHLAR (default)
- ASHLAR module specification unchanged
- No changes to downstream modules required
- Existing parameter files continue to work

### Future Enhancements

Potential future improvements (out of scope for initial implementation):

1. **Auto-detection**: Automatically select PALOM for pre-stitched Akoya data
2. **Hybrid Mode**: Use PALOM for alignment, ASHLAR for stitching
3. **Quality Metrics**: Report alignment quality scores
4. **Parallel Processing**: Register multiple samples concurrently
5. **GPU Acceleration**: Leverage GPU for feature detection and transformation

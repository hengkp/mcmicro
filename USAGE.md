# Using PALOM with Official MCMICRO

You can now use the official `labsyspharm/mcmicro` pipeline with the custom `hengkp/palom:v2` container by providing a params file.

## Quick Start

```bash
# Run official MCMICRO with PALOM registration
nextflow run labsyspharm/mcmicro \
  --in /path/to/your/data \
  -params-file params.yml
```

## What's in params.yml?

The `params.yml` file is a complete copy of MCMICRO's default configuration with the key change:

```yaml
workflow:
  registration-engine: palom  # Use PALOM instead of ASHLAR

modules:
  registration-palom:
    name: palom
    container: hengkp/palom  # Custom container
    version: 1.0.2           # Latest version
```

All other settings match the official MCMICRO defaults, so you can modify any parameter as needed.

In this fork, an active registration stage automatically switches PALOM to ASHLAR
with a warning when discovered raw inputs include non-OME-TIFF files (such as
`.rcpnl`) or use a multi-file format. OME-TIFF-only inputs keep PALOM. An active
background subtraction stage is skipped with a warning if `markers.csv` lacks
`background`, or lacks `exposure` while any `background` value is non-empty;
`remove` is optional. Both adjustments are recorded in `qc/params.yml`.

## Channel display colours

Add an optional `color` column (or `colour`) to the project's `markers.csv` to
choose channel colours in PALOM registration and background-subtracted OME-TIFFs,
including the image opened in QuPath. Accepted values are `#RRGGBB`, `RRGGBB`, or
`red`, `green`, `blue`, `yellow`, `cyan`, `magenta`, `white`, `gray`, `grey`,
`orange`, `purple`, `pink`. Case and surrounding whitespace are ignored. Invalid
values stop the workflow at launch, even when background subtraction is off.

An explicit colour overrides the defaults. With an empty or absent colour,
names starting with DAPI or Hoechst get blue; other channels use red, green,
yellow, cyan, magenta, then hues around the wheel, skipping pure blue. Only
channels using this palette advance it.

```csv
cycle,marker_name,background,exposure,remove,color
1,DAPI1,,100,FALSE,
1,CD3,,100,FALSE,#00FF00
1,CD20,,100,FALSE,magenta
1,PanCK,,100,FALSE,
```

## Full Example

```bash
# Download example data
nextflow run labsyspharm/mcmicro/exemplar.nf --name exemplar-001

# Run with PALOM registration
nextflow run labsyspharm/mcmicro \
  --in exemplar-001 \
  -params-file params.yml
```

## Custom Options

You can add more options to `params.yml`:

```yaml
workflow:
  registration-engine: palom
  start-at: registration
  stop-at: quantification

options:
  palom: --level 0 --ref-index 0 --max-pyramid-levels 2

modules:
  registration-palom:
    name: palom
    container: hengkp/palom
    version: 1.0.2
```

## Benefits

- ✅ Use official MCMICRO (always up-to-date)
- ✅ No need to maintain a fork
- ✅ Just share `params.yml` with collaborators
- ✅ Works on any machine (Docker pulls `hengkp/palom:v2` automatically)

## Docker Hub

The container is publicly available at:
- https://hub.docker.com/r/hengkp/palom

Supports both `linux/amd64` and `linux/arm64` platforms.

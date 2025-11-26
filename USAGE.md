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

# PALOM Registration Setup

This MCMICRO fork is configured to use the pre-built `hengkp/palom:v2` Docker container for image registration.

## Configuration

The pipeline uses PALOM as the registration engine with the following settings in `config/defaults.yml`:

```yaml
workflow:
  registration-engine: palom

modules:
  registration-palom:
    name: palom
    container: hengkp/palom
    version: 1.0.2
```

## Usage

Run MCMICRO with PALOM registration:

```bash
nextflow run labsyspharm/mcmicro --in /path/to/data
```

The pipeline will automatically use the `hengkp/palom:v2` container from Docker Hub.

## Memory-Efficient Registration

The registration uses `register_akoya_palom_v2.py`, which processes channels one at a time to minimize memory usage. This allows registration of large multi-cycle images within Docker's memory constraints.

## Custom Options

Adjust PALOM options in `config/defaults.yml`:

```yaml
options:
  palom: --level 0 --ref-index 0 --max-pyramid-levels 2
```

See `register_akoya_palom_v2.py --help` for all available options.

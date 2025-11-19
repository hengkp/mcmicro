# PALOM Container for MCMICRO

This directory contains the Docker container definition for the PALOM registration module in MCMICRO.

## Contents

- `Dockerfile` - Container definition with conda environment and palom package
- `register_akoya_palom.py` - Python script for PALOM registration
- `build-palom-container.sh` - Helper script to build and tag the container
- `.dockerignore` - Files to exclude from Docker build context

## Building the Container

### Prerequisites

- Docker installed and running
- Docker daemon accessible

### Build Command

```bash
# Build with default version (1.0.0)
./build-palom-container.sh

# Build with specific version
./build-palom-container.sh 1.0.1

# Build with custom registry
./build-palom-container.sh 1.0.0 ghcr.io/labsyspharm/palom-mcmicro
```

Or manually:

```bash
docker build -t labsyspharm/palom-mcmicro:1.0.0 .
```

## Testing the Container

### Test 1: Verify container builds successfully

```bash
docker build -t palom-mcmicro:test .
```

Expected: Build completes without errors.

### Test 2: Verify script is accessible

```bash
docker run --rm palom-mcmicro:test python /usr/local/bin/register_akoya_palom.py --help
```

Expected: Help message displays with all command-line options.

### Test 3: Verify palom package is installed

```bash
docker run --rm palom-mcmicro:test python -c "import palom; print(palom.__version__)"
```

Expected: Prints palom version number.

### Test 4: Check container size

```bash
docker images palom-mcmicro:test
```

Expected: Container size should be reasonable (<2GB).

## Container Specifications

### Base Image
- `continuumio/miniconda3:latest`

### Python Dependencies
- python=3.10
- tifffile=2023.7.10
- dask
- numpy
- scikit-image=0.21
- zarr=2.14.2
- palom[all] (via pip)

### Script Location
- `/usr/local/bin/register_akoya_palom.py`

### Working Directory
- `/work`

### Entrypoint
- `/bin/bash`

## Publishing the Container

After successful testing:

```bash
# Tag with version
docker tag palom-mcmicro:test labsyspharm/palom-mcmicro:1.0.0
docker tag palom-mcmicro:test labsyspharm/palom-mcmicro:latest

# Push to registry
docker push labsyspharm/palom-mcmicro:1.0.0
docker push labsyspharm/palom-mcmicro:latest
```

## Usage in MCMICRO

Once published, the container is referenced in `config/defaults.yml`:

```yaml
modules:
  registration-palom:
    name: palom
    container: labsyspharm/palom-mcmicro
    version: 1.0.0
```

## Troubleshooting

### Docker daemon not running

If you see "Cannot connect to the Docker daemon", start Docker Desktop or the Docker daemon:

```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

### Build fails with conda errors

Ensure you have a stable internet connection. Conda may need to download packages.

### Script not executable

The Dockerfile includes `chmod +x` to make the script executable. If issues persist, verify the COPY command succeeded.

## Requirements Satisfied

This container implementation satisfies the following requirements from the spec:

- **Requirement 2.1**: Container includes palom package with all dependencies
- **Requirement 2.2**: Container includes register_akoya_palom.py at standard path
- **Requirement 2.3**: Container can be built and published to registry

# PALOM Container Deployment Guide

This guide covers the steps to tag and push the PALOM container to a registry.

## Prerequisites

1. **Docker installed and running**
   ```bash
   docker --version
   docker info
   ```

2. **Registry authentication**
   
   For Docker Hub (labsyspharm):
   ```bash
   docker login
   # Enter your Docker Hub credentials
   ```
   
   For GitHub Container Registry (ghcr.io):
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

3. **Built PALOM container**
   If not already built, run:
   ```bash
   ./build-palom-container.sh 1.0.0 labsyspharm/palom-mcmicro
   ```

## Deployment Steps

### Option 1: Using the Push Script (Recommended)

The automated script handles tagging and pushing:

```bash
# Push to Docker Hub (default)
./push-palom-container.sh 1.0.0 labsyspharm/palom-mcmicro

# Or push to GitHub Container Registry
./push-palom-container.sh 1.0.0 ghcr.io/labsyspharm/palom-mcmicro
```

The script will:
1. Check if Docker is running
2. Build the container if needed
3. Tag with semantic version (1.0.0) and latest
4. Prompt for confirmation before pushing
5. Push both version tag and latest tag

### Option 2: Manual Steps

If you prefer manual control:

```bash
# 1. Build the container (if not already built)
docker build -t labsyspharm/palom-mcmicro:1.0.0 .

# 2. Tag with latest
docker tag labsyspharm/palom-mcmicro:1.0.0 labsyspharm/palom-mcmicro:latest

# 3. Verify tags
docker images | grep palom

# 4. Push version tag
docker push labsyspharm/palom-mcmicro:1.0.0

# 5. Push latest tag
docker push labsyspharm/palom-mcmicro:latest
```

## Registry Options

### Docker Hub (labsyspharm)
- **Registry**: `labsyspharm/palom-mcmicro`
- **URL**: https://hub.docker.com/r/labsyspharm/palom-mcmicro
- **Public**: Yes (recommended for open-source)

### GitHub Container Registry (ghcr.io)
- **Registry**: `ghcr.io/labsyspharm/palom-mcmicro`
- **URL**: https://github.com/labsyspharm/mcmicro/pkgs/container/palom-mcmicro
- **Public**: Configurable

## Verification

After pushing, verify the container is accessible:

```bash
# Pull from registry
docker pull labsyspharm/palom-mcmicro:1.0.0

# Test the container
docker run --rm labsyspharm/palom-mcmicro:1.0.0 \
  python /usr/local/bin/register_akoya_palom.py --help

# Check palom version
docker run --rm labsyspharm/palom-mcmicro:1.0.0 \
  python -c "import palom; print(palom.__version__)"
```

## Configuration Update

The version in `config/defaults.yml` is already set correctly:

```yaml
modules:
  registration-palom:
    name: palom
    container: labsyspharm/palom-mcmicro
    version: 1.0.0
```

**No changes needed** - the version matches the pushed tag.

## Troubleshooting

### Docker daemon not running
```
Error: Cannot connect to the Docker daemon
```
**Solution**: Start Docker Desktop or Docker daemon

### Authentication failed
```
Error: unauthorized: authentication required
```
**Solution**: Run `docker login` with valid credentials

### Image not found locally
```
Error: No such image
```
**Solution**: Build the container first using `./build-palom-container.sh`

### Push denied
```
Error: denied: requested access to the resource is denied
```
**Solution**: Ensure you have push permissions to the registry

## Next Steps

After successful deployment:

1. ✅ Container tagged with version 1.0.0
2. ✅ Container pushed to registry
3. ✅ Config file version verified (1.0.0)
4. Test the container from registry in MCMICRO pipeline
5. Update documentation with registry information
6. Commit and push configuration changes

## Version Management

For future releases:

```bash
# Update version in config/defaults.yml
# Then build and push with new version
./push-palom-container.sh 1.1.0 labsyspharm/palom-mcmicro
```

Follow semantic versioning:
- **Major** (2.0.0): Breaking changes
- **Minor** (1.1.0): New features, backward compatible
- **Patch** (1.0.1): Bug fixes, backward compatible

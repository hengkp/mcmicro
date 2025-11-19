# Quick Deployment Commands

## Current Status
- ✅ Dockerfile created
- ✅ Registration script (register_akoya_palom.py) ready
- ✅ Config file (config/defaults.yml) updated with version 1.0.0
- ⏳ Container needs to be tagged and pushed to registry

## Prerequisites Check

```bash
# Verify deployment readiness
./verify-palom-deployment.sh
```

## Deployment Commands

### Step 1: Start Docker
Ensure Docker Desktop is running or start the Docker daemon.

### Step 2: Login to Registry

**For Docker Hub:**
```bash
docker login
# Enter username and password when prompted
```

**For GitHub Container Registry:**
```bash
export GITHUB_TOKEN=your_token_here
echo $GITHUB_TOKEN | docker login ghcr.io -u your_username --password-stdin
```

### Step 3: Build Container (if not already built)

```bash
./build-palom-container.sh 1.0.0 labsyspharm/palom-mcmicro
```

### Step 4: Tag and Push

**Option A: Using automated script (recommended)**
```bash
./push-palom-container.sh 1.0.0 labsyspharm/palom-mcmicro
```

**Option B: Manual commands**
```bash
# Tag the container
docker tag labsyspharm/palom-mcmicro:latest labsyspharm/palom-mcmicro:1.0.0

# Push version tag
docker push labsyspharm/palom-mcmicro:1.0.0

# Push latest tag
docker push labsyspharm/palom-mcmicro:latest
```

### Step 5: Verify Deployment

```bash
# Pull from registry to verify
docker pull labsyspharm/palom-mcmicro:1.0.0

# Test the container
docker run --rm labsyspharm/palom-mcmicro:1.0.0 \
  python /usr/local/bin/register_akoya_palom.py --help
```

## Alternative Registry (GitHub Container Registry)

If using ghcr.io instead:

```bash
# Build and tag
./build-palom-container.sh 1.0.0 ghcr.io/labsyspharm/palom-mcmicro

# Push
./push-palom-container.sh 1.0.0 ghcr.io/labsyspharm/palom-mcmicro

# Update config/defaults.yml
# Change: container: ghcr.io/labsyspharm/palom-mcmicro
```

## Configuration Verification

The configuration is already correct in `config/defaults.yml`:

```yaml
modules:
  registration-palom:
    name: palom
    container: labsyspharm/palom-mcmicro
    version: 1.0.0
```

✅ **No changes needed** - version matches the tag (1.0.0)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Docker not running | Start Docker Desktop |
| Authentication failed | Run `docker login` |
| Image not found | Run `./build-palom-container.sh` first |
| Push denied | Check registry permissions |
| Wrong version | Update `config/defaults.yml` |

## Post-Deployment

After successful push:
1. ✅ Verify container is accessible from registry
2. ✅ Test container in MCMICRO pipeline
3. ✅ Commit configuration changes
4. ✅ Update documentation
5. ✅ Mark task 7.2 as complete

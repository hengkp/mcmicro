# Why Two Registration Modules?

## Question
Why does MCMICRO use `registration-palom` module instead of just changing the `registration` module from `labsyspharm/ashlar` to `hengkp/palom`?

## Answer

MCMICRO uses **two separate module definitions** because ASHLAR and PALOM are fundamentally different tools:

### Module Structure

```yaml
modules:
  registration:              # ASHLAR (default)
    name: ashlar
    container: labsyspharm/ashlar
    version: 1.17.0
    
  registration-palom:        # PALOM (alternative)
    name: palom
    container: hengkp/palom
    version: 1.0.2
```

### Why They're Separate

1. **Different Commands**
   - ASHLAR: `ashlar <images> -m 30 -o output.ome.tif`
   - PALOM: `python /usr/local/bin/register_akoya_palom_v2.py --input-dir . --output output.ome.tif`

2. **Different Inputs**
   - ASHLAR: Takes raw image tiles
   - PALOM: Takes pre-stitched OME-TIFF cycles + optional markers.csv

3. **Different Parameters**
   - ASHLAR: `-m` (max shift), `--ffp`, `--dfp` (illumination profiles)
   - PALOM: `--level`, `--ref-index`, `--max-pyramid-levels`

4. **Different Use Cases**
   - ASHLAR: Stitching + registration of raw tiles
   - PALOM: Registration of pre-stitched multi-cycle images

### How It Works

The workflow checks the `registration-engine` parameter:

```groovy
def engine = mcp.workflow['registration-engine'] ?: 'ashlar'

if (engine == 'palom') {
  palom(mcp, mcp.modules['registration-palom'], ...)
} else {
  ashlar(mcp, mcp.modules['registration'], ...)
}
```

### Configuration

To use PALOM, set in `params.yml`:

```yaml
workflow:
  registration-engine: palom  # Switch from ashlar to palom

modules:
  registration-palom:         # Configure PALOM module
    container: hengkp/palom
    version: 1.0.2
```

## Summary

You **cannot** just replace `registration` module with `hengkp/palom` because:
- The Nextflow process expects different commands
- The container has different scripts
- The workflow logic routes to different processes based on `registration-engine`

This design allows MCMICRO to support multiple registration tools while keeping each tool's specific requirements isolated.

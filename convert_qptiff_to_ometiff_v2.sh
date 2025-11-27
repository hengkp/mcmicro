#!/bin/bash
set -euo pipefail

################### CONFIG ###################

# Path to bfconvert
BFCONVERT="/Users/heng/opt/bftools/bfconvert"

# Input/output dirs
INPUT_DIR="/Users/heng/Dropbox/Macbook Pro/Projects/Spatial project/CyCIF (NY&Folk)/QPTIFF for Alignment/raw_qptiff"
OUTPUT_DIR="../raw"

# Parallelism: 2 is usually safe for 4-core / 16 GB on 10+ GB images
PARALLEL_JOBS=2

# Pyramid settings (ALWAYS ON)
# scale=4 and limited levels → fewer resampling / writes but still QuPath-friendly
PYRAMID_SCALE=4
PYRAMID_RESOLUTIONS=5

# Larger tiles = fewer I/O ops (still OK on 16 GB RAM)
TILE_X=2048
TILE_Y=2048

# Compression:
#  - "LZW"  : good speed, moderate size
#  - "Uncompressed" : fastest, but huge files
#  - "zlib" : smallest, but slowest
COMPRESSION="LZW"

# Optional: only use one channel (0-based) if you ever want DAPI-only files
CHANNEL_INDEX=""

################# END CONFIG #################

cd "$INPUT_DIR"
mkdir -p "$OUTPUT_DIR"

convert_one() {
    local f="$1"
    local base
    base=$(basename "$f" .qptiff)
    local out="${OUTPUT_DIR}/${base}.ome.tiff"

    echo "Converting $f -> $out"

    local opts=(
        -nolookup
        -pyramid-scale "${PYRAMID_SCALE}"
        -pyramid-resolutions "${PYRAMID_RESOLUTIONS}"
        -tilex "${TILE_X}" -tiley "${TILE_Y}"
        -compression "${COMPRESSION}"
        -bigtiff
    )

    # If you ever want nuclei-only to speed things up:
    if [[ -n "${CHANNEL_INDEX}" ]]; then
        opts+=(-channel "${CHANNEL_INDEX}")
    fi

    "$BFCONVERT" "${opts[@]}" "$f" "$out"

    if [[ $? -eq 0 ]]; then
        echo "✓ Successfully converted $f"
    else
        echo "✗ Failed to convert $f"
    fi
}

export BFCONVERT OUTPUT_DIR PYRAMID_SCALE PYRAMID_RESOLUTIONS TILE_X TILE_Y COMPRESSION CHANNEL_INDEX
export -f convert_one

echo "Starting conversion in $INPUT_DIR"
echo "Output to $OUTPUT_DIR"
echo "Pyramids: scale=${PYRAMID_SCALE}, levels=${PYRAMID_RESOLUTIONS}"
echo "Tiles: ${TILE_X}x${TILE_Y}, compression=${COMPRESSION}, parallel jobs=${PARALLEL_JOBS}"

if command -v parallel >/dev/null 2>&1; then
    echo "GNU parallel found – running with ${PARALLEL_JOBS} jobs"
    find . -maxdepth 1 -name 'c*.qptiff' -print0 \
        | parallel -0 -j "${PARALLEL_JOBS}" convert_one {}
else
    echo "GNU parallel not found – using xargs with ${PARALLEL_JOBS} jobs"
    find . -maxdepth 1 -name 'c*.qptiff' -print0 \
        | xargs -0 -n 1 -P "${PARALLEL_JOBS}" bash -c 'convert_one "$@"' _
fi

echo ""
echo "Conversion complete. Checking output files:"
ls -lh "${OUTPUT_DIR}/"*.ome.tiff

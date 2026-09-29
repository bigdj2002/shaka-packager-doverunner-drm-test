#!/usr/bin/env sh
set -euo pipefail

INPUT=${1:?Usage: $0 <input-file> [mp4|fmp4]}
FORMAT=${2:-mp4} # mp4 or fmp4
BASE_OUTDIR="../abr-avc-video"
LEVEL_IDC="5.2" # 4K60 requires level 5.2 (use 5.1 for <=4K30)
FPS="${FPS:-60000/1001}"
GOP="${GOP:-360}"

case "$FORMAT" in
  mp4)
    OUTDIR="${BASE_OUTDIR}-mp4"
    MOVFLAGS="+faststart"
    FRAG_OPTS=""
    ;;
  fmp4)
    OUTDIR="${BASE_OUTDIR}-fmp4"
    MOVFLAGS="+faststart+dash+frag_keyframe+separate_moof"
    FRAG_OPTS="-frag_duration 6000000 -min_frag_duration 6000000"
    ;;
  *)
    echo "Unsupported format: $FORMAT (use mp4 or fmp4)"
    exit 1
    ;;
esac

mkdir -p "$OUTDIR"

encode() {
  local scale=$1
  local bv=$2
  local maxrate=$3
  local bufsize=$4
  local outfile=$5

  ffmpeg -y -i "$INPUT" -pix_fmt yuv420p -vsync cfr -r "$FPS" -c:v libx264 -preset slow -profile:v high -level:v "$LEVEL_IDC" \
    -vf "scale=${scale}:-2" -b:v "$bv" -maxrate "$maxrate" -bufsize "$bufsize" \
    -g "$GOP" -keyint_min "$GOP" -sc_threshold 0 \
    -movflags "$MOVFLAGS" $FRAG_OPTS \
    -c:a aac -b:a 128k -ac 2 "$OUTDIR/$outfile"
}

# Ladder aligned with AVC ladder (1920/1280/960/854/640/384)
encode 1920 6000k 6300k 12000k "output_avc_1920.mp4"
encode 1280 4000k 4200k 8000k "output_avc_1280.mp4"
encode 960  2000k 2100k 4000k "output_avc_960.mp4"
encode 854  1500k 1600k 3000k "output_avc_854.mp4"
encode 640   750k  800k 1500k "output_avc_640.mp4"
encode 384   370k  400k  800k "output_avc_384.mp4"

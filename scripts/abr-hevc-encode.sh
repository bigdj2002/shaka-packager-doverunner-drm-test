#!/usr/bin/env bash
set -euo pipefail

INPUT=${1:?Usage: $0 <input-file> [mp4|fmp4]}
FORMAT=${2:-mp4} # mp4 or fmp4
BASE_OUTDIR="../abr-hevc-video"
FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
LEVEL_IDC="5.2" # 4K60 requires level 5.2 (use 5.1 for <=4K30)
TIER="high"
X265_PARAMS="high-tier=1"
FPS="${FPS:-60000/1001}"
GOP="${GOP:-360}"

case "$FORMAT" in
  mp4)
    OUTDIR="${OUTPUT_DIR:-${BASE_OUTDIR}-mp4}"
    MOVFLAGS="+faststart"
    FRAG_OPTS=""
    ;;
  fmp4)
    OUTDIR="${OUTPUT_DIR:-${BASE_OUTDIR}-fmp4}"
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

  if [ "${SKIP_EXISTING:-0}" = "1" ] && [ -s "$OUTDIR/$outfile" ]; then
    echo "Skipping existing output: $OUTDIR/$outfile"
    return
  fi

  "$FFMPEG_BIN" -y -i "$INPUT" -pix_fmt yuv420p -vsync cfr -r "$FPS" -c:v libx265 -preset slow \
    -profile:v main -level:v "$LEVEL_IDC" -x265-params "$X265_PARAMS" \
    -vf "scale=${scale}:-2" -b:v "$bv" -maxrate "$maxrate" -bufsize "$bufsize" \
    -g "$GOP" -keyint_min "$GOP" -sc_threshold 0 \
    -movflags "$MOVFLAGS" $FRAG_OPTS \
    -c:a aac -b:a 128k -ac 2 "$OUTDIR/$outfile"
}

encode 3840 12000k 12600k 24000k "output_hevc_3840.mp4"
encode 2560  8000k  8400k 16000k "output_hevc_2560.mp4"
encode 1920  6000k  6300k 12000k "output_hevc_1920.mp4"
encode 1280  4000k  4200k  8000k "output_hevc_1280.mp4"
encode 854   1500k  1600k  3000k "output_hevc_854.mp4"
encode 640    750k   800k  1500k "output_hevc_640.mp4"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RENDITION_DIR="${RENDITION_DIR_HEVC:-${SCRIPT_DIR}/../mc-abr-hevc-video-mp4-remux}"
FALLBACK_INPUT="${RENDITION_DIR}/output_hevc_3840.mp4"
OUTPUT_ROOT_NON_DRM="${SCRIPT_DIR}/packaging-test/shaka/non-drm"
OUTPUT_ROOT_DRM="${SCRIPT_DIR}/packaging-test/shaka/drm"
COMMAND_LOG="${SCRIPT_DIR}/shaka_command.abr-hevc-package-playready-dash.log"
PROFILE="hevc_cmaf"

ENABLE_DRM=0
if [ "${1-}" = "--drm" ]; then
  ENABLE_DRM=1
  shift
fi

ENCRYPT_SCOPE="${ENCRYPT_SCOPE:-both}"

ENCRYPTION_SCHEME_ARG=""
if [ -n "${ENCRYPTION_SCHEME-}" ]; then
  ENCRYPTION_SCHEME_ARG="--encryption_scheme ${ENCRYPTION_SCHEME}"
fi

if [ "${ENABLE_DRM}" -eq 1 ]; then
  ENC_TOKEN="${ENC_TOKEN:?Please set ENC_TOKEN (see .env.example)}"
  CONTENT_ID="${CONTENT_ID:?Please set CONTENT_ID (see .env.example)}"
  OUTPUT_ROOT="${OUTPUT_ROOT_DRM}"
  python3 "${SCRIPT_DIR}/doverunner-integration-script.py" \
    --enable_drm \
    --enc_token "${ENC_TOKEN:?set ENC_TOKEN}" \
    --content_id "${CONTENT_ID:?set CONTENT_ID}" \
    --drm_type "playready" \
    --encrypt_scope "${ENCRYPT_SCOPE}" \
    --input "${FALLBACK_INPUT}" \
    --output_root "${OUTPUT_ROOT}" \
    --command_log "${COMMAND_LOG}" \
    --profile "${PROFILE}" \
    --output_format "dash" \
    ${ENCRYPTION_SCHEME_ARG} \
    --rendition_dir "${RENDITION_DIR}" \
    "$@"
else
  OUTPUT_ROOT="${OUTPUT_ROOT_NON_DRM}"
  python3 "${SCRIPT_DIR}/doverunner-integration-script.py" \
    --input "${FALLBACK_INPUT}" \
    --output_root "${OUTPUT_ROOT}" \
    --command_log "${COMMAND_LOG}" \
    --profile "${PROFILE}" \
    --output_format "dash" \
    ${ENCRYPTION_SCHEME_ARG} \
    --rendition_dir "${RENDITION_DIR}" \
    "$@"
fi

python3 "${SCRIPT_DIR}/scripts/relativize-dash-mpd.py" "${OUTPUT_ROOT}/hevc/dash/stream.mpd"

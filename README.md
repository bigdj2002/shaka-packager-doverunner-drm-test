# Shaka Packager Integration Sample

Shell scripts and a Python helper for ABR encoding, remuxing, and DRM packaging using [Shaka Packager](https://github.com/shaka-project/shaka-packager) and [DoveRunner](https://docs.doverunner.com) CPIX API.

---

## Repository Structure

```
.
├── scripts/
│   ├── abr-avc-encode.sh                  # FFmpeg AVC (H.264) ABR ladder encode
│   ├── abr-hevc-encode.sh                 # FFmpeg HEVC (H.265) ABR ladder encode
│   ├── abr-avc-remux.sh                   # Remux AVC MP4s to reset PTS/DTS
│   ├── abr-hevc-remux.sh                  # Remux HEVC MP4s to reset PTS/DTS
│   ├── abr-avc-package-fairplay-hls.sh    # Shaka package → AVC  / FairPlay  / HLS
│   ├── abr-avc-package-widevine-dash.sh   # Shaka package → AVC  / Widevine  / DASH
│   ├── abr-avc-package-playready-dash.sh  # Shaka package → AVC  / PlayReady / DASH
│   ├── abr-hevc-package-cmaf.sh           # Shaka package → HEVC / FairPlay  / CMAF
│   ├── abr-hevc-package-widevine-dash.sh  # Shaka package → HEVC / Widevine  / DASH
│   ├── abr-hevc-package-playready-dash.sh # Shaka package → HEVC / PlayReady / DASH
│   ├── abr-avc-segment-rename.sh          # Rewrite segment URLs in AVC manifests
│   ├── abr-hevc-segment-rename.sh         # Rewrite segment URLs in HEVC manifests
│   └── upload-shaka-to-s3.sh              # Upload packaged output to S3
├── cpix-api-client/                       # DoveRunner CPIX client (git submodule)
├── packaging-test/                        # Local packaging output (git-ignored)
├── doverunner-integration-script.py       # Python wrapper that calls Shaka Packager
├── rewrite_manifest_urls.py               # URL rewrite utility for manifests
├── packager-osx-arm64                     # Shaka Packager binary (macOS ARM)
├── .env.example                           # Environment variable template
└── .gitignore
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.6+ | |
| FFmpeg | any recent | for encode/remux scripts |
| Shaka Packager | v3.2.0+ | binary included (`packager-osx-arm64`) |
| AWS CLI | any | only for `upload-shaka-to-s3.sh` |

The DoveRunner CPIX API client is included as a Git submodule at `cpix-api-client/`. If you already cloned this repository without submodules, initialize it with:

```sh
git submodule update --init --recursive
```

---

## Setup

1. **Clone this repository**

   ```sh
   git clone --recurse-submodules https://github.coupang.net/dowon14/shaka-packager-integration-sample.git
   cd shaka-packager-integration-sample
   ```

2. **Configure environment variables**

   ```sh
   cp .env.example .env
   # Edit .env and fill in ENC_TOKEN and CONTENT_ID
   source .env
   ```

3. **Make scripts executable**

   ```sh
   chmod +x scripts/*.sh
   ```

---

## Workflow

The typical end-to-end flow is:

```
Encode (FFmpeg)  →  Remux (FFmpeg)  →  Package (Shaka)  →  Upload (S3)
```

### 1. Encode — ABR Ladder

```sh
# AVC (H.264) — outputs to ../abr-avc-video-mp4/
./scripts/abr-avc-encode.sh <input-file> [mp4|fmp4]

# HEVC (H.265) — outputs to ../abr-hevc-video-mp4/
./scripts/abr-hevc-encode.sh <input-file> [mp4|fmp4]
```

Default resolutions:

| Codec | Resolutions |
|-------|-------------|
| AVC   | 1920 / 1280 / 960 / 854 / 640 / 384 |
| HEVC  | 3840 / 2560 / 1920 / 1280 / 854 / 640 |

### 2. Remux — Reset PTS/DTS

```sh
./scripts/abr-avc-remux.sh   # reads ../mc-abr-avc-video-mp4/ → ../mc-abr-avc-video-mp4-remux/
./scripts/abr-hevc-remux.sh  # reads ../mc-abr-hevc-video-mp4/ → ../mc-abr-hevc-video-mp4-remux/
```

Override source/destination with env vars:

```sh
SRC_DIR=/path/to/src DST_DIR=/path/to/dst ./scripts/abr-avc-remux.sh
```

### 3. Package — Shaka Packager + DRM

Each packaging script accepts an optional `--drm` flag. Without it, content is packaged without encryption (non-DRM).

**DRM support matrix:**

| Script | Codec | DRM | Format | Default Scheme |
|--------|-------|-----|--------|---------------|
| `abr-avc-package-fairplay-hls.sh` | AVC | FairPlay | HLS | `cbcs` |
| `abr-avc-package-widevine-dash.sh` | AVC | Widevine | DASH | `cenc` |
| `abr-avc-package-playready-dash.sh` | AVC | PlayReady | DASH | `cenc` |
| `abr-hevc-package-cmaf.sh` | HEVC | FairPlay | CMAF | `cbcs` |
| `abr-hevc-package-widevine-dash.sh` | HEVC | Widevine | DASH | `cenc` |
| `abr-hevc-package-playready-dash.sh` | HEVC | PlayReady | DASH | `cenc` |

```sh
# AVC
./scripts/abr-avc-package-fairplay-hls.sh [--drm]
./scripts/abr-avc-package-widevine-dash.sh [--drm]
./scripts/abr-avc-package-playready-dash.sh [--drm]

# HEVC
./scripts/abr-hevc-package-cmaf.sh [--drm]
./scripts/abr-hevc-package-widevine-dash.sh [--drm]
./scripts/abr-hevc-package-playready-dash.sh [--drm]
```

Output is written to:

```
packaging-test/shaka/
├── non-drm/
│   ├── avc/
│   │   ├── hls/
│   │   └── dash/
│   └── hevc/
│       ├── cmaf/
│       └── dash/
└── drm/
    ├── avc/
    │   ├── hls/
    │   └── dash/
    └── hevc/
        ├── cmaf/
        └── dash/
```

> `packaging-test/` is git-ignored — local only, never committed.

**Environment variables for packaging scripts:**

| Variable | Required | Description |
|----------|----------|-------------|
| `ENC_TOKEN` | Yes (DRM only) | DoveRunner KMS encryption token |
| `CONTENT_ID` | Yes (DRM only) | Content ID for DRM key request |
| `PROFILE` | No | Packaging profile (`avc_ts`, `hevc_cmaf`; script defaults apply) |
| `ENCRYPT_SCOPE` | No | `both` (default), `video`, or `audio` |
| `ENCRYPTION_SCHEME` | No | `cenc`, `cbc1`, `cens`, or `cbcs` |
| `DRM_TYPE` | No | Overrides DRM type (e.g. `widevine`, `fairplay`) |
| `HLS_BASE_URL` | No | Base URL prepended to HLS segment paths |
| `EMIT_DASH` | No | Set to `1` to also emit DASH alongside CMAF |
| `RENDITION_DIR_AVC` | No | Custom path to remuxed AVC MP4s |
| `RENDITION_DIR_HEVC` | No | Custom path to remuxed HEVC MP4s |

**PlayReady encryption scheme notes:**

- `cenc` (CTR): PlayReady 2.0+ — broadest device compatibility (Xbox One, smart TVs, Windows)
- `cbcs` (CBC): PlayReady 4.0+ only — use when FairPlay multi-DRM packaging is also required

```sh
# Override encryption scheme example
ENCRYPTION_SCHEME=cbcs ./scripts/abr-hevc-package-playready-dash.sh --drm
```

### 4. Rewrite Manifest URLs

After packaging, replace local absolute paths in manifests with CDN URLs:

```sh
./scripts/abr-avc-segment-rename.sh
./scripts/abr-hevc-segment-rename.sh
```

Override defaults via env vars:

```sh
OLD="https://old.host/path/,https://old.host/path2/" \
NEW="https://cdn.example.com/path/,https://cdn.example.com/path2/" \
./scripts/abr-avc-segment-rename.sh
```

### 5. Upload to S3

```sh
./scripts/upload-shaka-to-s3.sh [src-dir] [s3-destination]

# Example
./scripts/upload-shaka-to-s3.sh packaging-test/shaka s3://your-bucket/your-prefix/
```

---

## Python Integration Script

`doverunner-integration-script.py` is the core wrapper that:

1. Requests DRM keys from DoveRunner KMS via CPIX API
2. Builds and executes the Shaka Packager command with encryption flags

```sh
python3 doverunner-integration-script.py \
  --enc_token "$ENC_TOKEN" \
  --content_id "$CONTENT_ID" \
  --drm_type widevine,playready \
  'in=video.mp4,stream=video,init_segment=out/video/init.mp4,segment_template=out/video/$Number$.m4s' \
  'in=video.mp4,stream=audio,init_segment=out/audio/init.mp4,segment_template=out/audio/$Number$.m4s' \
  --generate_static_live_mpd \
  --mpd_output out/stream.mpd \
  --clear_lead 0
```

**Key arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--enc_token` | Yes | KMS token for CPIX API |
| `--content_id` | Yes | Content ID |
| `--drm_type` | Yes | Comma-separated: `widevine`, `playready`, `fairplay` |
| `--encryption_scheme` | No | `cenc` (default), `cbc1`, `cens`, `cbcs` |
| `--track_type` | No | `all_tracks` (default), `audio`, `sd`, `hd`, `uhd1`, `uhd2` |

All other arguments are passed directly to Shaka Packager.

---

## References

- [DoveRunner CPIX API Docs](https://docs.doverunner.com/content-security/multi-drm/packaging/cpix-api/)
- [DoveRunner CPIX API Client](https://github.com/doverunner/cpix-api-client)
- [Shaka Packager](https://github.com/shaka-project/shaka-packager)
- [Shaka Packager Releases](https://github.com/shaka-project/shaka-packager/releases/tag/v3.2.0)

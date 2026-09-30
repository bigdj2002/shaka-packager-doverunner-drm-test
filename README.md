# Shaka Packager DoveRunner DRM Test

An AVC/HEVC adaptive bitrate packaging test using FFmpeg, Shaka Packager, and DoveRunner CPIX. The included wrappers produce clear or PlayReady encrypted DASH output. This repository also contains a CPIX client and a playback license token sample as Git submodules.

## What is included

| Path | Purpose |
| --- | --- |
| `scripts/abr-avc-encode.sh`, `scripts/abr-hevc-encode.sh` | Encode six MP4 renditions with FFmpeg. |
| `scripts/abr-avc-package-playready-dash.sh`, `scripts/abr-hevc-package-playready-dash.sh` | Package the renditions as clear or PlayReady DASH. |
| `doverunner-integration-script.py` | Build Shaka Packager commands and, in DRM mode, request keys through CPIX. |
| `scripts/relativize-dash-mpd.py` | Convert local segment paths in a DASH manifest to relative paths; the packaging wrappers run it automatically. |
| `scripts/serve-dash.py` | Serve DRM output locally at `http://127.0.0.1:8765`. |
| `cpix-api-client/` | [CPIX client fork](https://github.com/bigdj2002/cpix-api-client) used by the packaging script. |
| `drm-license-token-sample-python/` | [License token sample fork](https://github.com/bigdj2002/drm-license-token-sample-python) for playback tests. |

## Requirements

- Python 3.10 or newer and the `requests` package for the CPIX client.
- FFmpeg with `libx264` and/or `libx265` for encoding.
- A Shaka Packager executable. Set `PACKAGER_BIN` to its path; the fallback path is `./packager-osx-arm64`, which is **not included** in this repository.
- A DoveRunner KMS encryption token and content ID for DRM packaging. Clear packaging does not require them.

```bash
git clone --recurse-submodules https://github.com/bigdj2002/shaka-packager-doverunner-drm-test.git
cd shaka-packager-doverunner-drm-test
python3 -m pip install requests
export PACKAGER_BIN=/absolute/path/to/packager
```

For an existing clone, run `git submodule update --init --recursive`. The playback license token sample uses separate credentials and dependencies; see its own README. Its license token is different from the KMS `ENC_TOKEN` used for packaging.

## Quick start: AVC DASH

Run these commands from the repository root, replacing `input.mp4` with your source file:

```bash
OUTPUT_DIR="$PWD/packaging-test/input/avc" ./scripts/abr-avc-encode.sh input.mp4
RENDITION_DIR_AVC="$PWD/packaging-test/input/avc" ./scripts/abr-avc-package-playready-dash.sh
```

The clear DASH manifest is written to `packaging-test/shaka/non-drm/avc/dash/stream.mpd`.

For PlayReady encryption, export your DoveRunner values and put `--drm` **first** in the wrapper arguments:

```bash
export ENC_TOKEN=your-kms-encryption-token
export CONTENT_ID=your-content-id
RENDITION_DIR_AVC="$PWD/packaging-test/input/avc" ./scripts/abr-avc-package-playready-dash.sh --drm
```

The encrypted manifest is written to `packaging-test/shaka/drm/avc/dash/stream.mpd`. The default DASH encryption scheme is `cenc`; set `ENCRYPTION_SCHEME=cbcs` before the packaging command if needed.

## HEVC DASH

```bash
OUTPUT_DIR="$PWD/packaging-test/input/hevc" ./scripts/abr-hevc-encode.sh input.mp4
RENDITION_DIR_HEVC="$PWD/packaging-test/input/hevc" ./scripts/abr-hevc-package-playready-dash.sh

# With the ENC_TOKEN and CONTENT_ID environment variables set:
RENDITION_DIR_HEVC="$PWD/packaging-test/input/hevc" ./scripts/abr-hevc-package-playready-dash.sh --drm
```

The HEVC manifests are at `packaging-test/shaka/{non-drm,drm}/hevc/dash/stream.mpd`. The encoder defaults to 60,000/1,001 fps and a 360-frame GOP. Set `FFMPEG_BIN`, `FPS`, `GOP`, or `OUTPUT_DIR` to override encoder defaults. The HEVC encoder also accepts `SKIP_EXISTING=1` to reuse nonempty rendition files.

## Packaging options

| Variable | Effect |
| --- | --- |
| `RENDITION_DIR_AVC`, `RENDITION_DIR_HEVC` | Directory containing `output_avc_<width>.mp4` or `output_hevc_<width>.mp4`. The wrappers otherwise look for sibling `../mc-abr-*-video-mp4-remux` directories. |
| `ENC_TOKEN`, `CONTENT_ID` | Required with `--drm`; provided to the DoveRunner KMS request. |
| `ENCRYPT_SCOPE` | `both` (default), `video`, or `audio`. Also controls which tracks the wrapper includes in clear mode. |
| `ENCRYPTION_SCHEME` | Optional `cenc`, `cbc1`, `cens`, or `cbcs` override. |
| `PROFILE` | Optional AVC profile override; AVC defaults to `avc_ts`. The HEVC wrapper uses `hevc_cmaf`. |
| `PACKAGER_BIN` | Path to the Shaka Packager executable. |

The Python integration script also accepts `--input`, `--rendition_dir`, `--output_root`, `--output_format`, `--profile`, `--emit_dash`, and DRM options. Run `python3 doverunner-integration-script.py --help` for its current argument list. The wrappers forward additional arguments to it after their optional `--drm` flag.

Packaging writes to `packaging-test/` and a `shaka_command*.log` file. These paths and `.env` are Git-ignored. The command log redacts key and IV arguments.

## Local playback check

After DRM packaging, start the local file server:

```bash
python3 scripts/serve-dash.py
```

The manifests are available at `http://127.0.0.1:8765/avc/dash/stream.mpd` and `http://127.0.0.1:8765/hevc/dash/stream.mpd`. The server reads only from `packaging-test/shaka/drm/`; a compatible player still needs a valid PlayReady license token and license configuration. See `drm-license-token-sample-python/README.md` for token generation.

## Test environment note

The CPIX client fork currently disables TLS certificate verification for its KMS request. Restore certificate verification before using this code outside a controlled test environment.

## References

- [DoveRunner CPIX documentation](https://docs.doverunner.com/content-security/multi-drm/packaging/cpix-api/)
- [Shaka Packager](https://github.com/shaka-project/shaka-packager)
- [Additional packaging notes](docs/doverunner-shaka-migration-poc.md)

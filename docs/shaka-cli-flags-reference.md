# CLI flags reference (packager / mpd_generator)

This document lists command-line flags defined in the codebase (via `ABSL_FLAG(...)`) and where they are validated/applied.

## Notes

- `packager` parses flags in `packager/app/packager_main.cc` using `absl::ParseCommandLine(argc, argv)`.
- Most flags are *applied* in `packager/app/packager_main.cc` in `GetPackagingParams()` by reading values via `absl::GetFlag(FLAGS_<name>)`.
- Some arguments are **not** `--flags`, but **stream descriptor parameters** (positional args like `input=...` / `stream=...` / `output=...`). These are documented in the `kUsage` string in `packager/app/packager_main.cc` and parsed by `ParseStreamDescriptor(...)` in `packager/app/stream_descriptor.*`.

---

# packager

## General / behavior

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--dump_stream_info` | bool | `false` | Dump demuxed stream info and exit. |
| `--licenses` | bool | `false` | Print bundled licenses and exit. |
| `--quiet` | bool | `false` | Suppress INFO logs (raise log level to WARNING). |
| `--use_fake_clock_for_muxer` | bool | `false` | Use a fake clock so muxed creation/mod times become 0 (testing). |
| `--test_packager_version` | string | `""` | Inject a fake packager version (testing only). |
| `--single_threaded` | bool | `false` | Force single-threaded packaging. |

## Chunking / muxing

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--temp_dir` | string | `""` | Temp directory for intermediate files (single_segment flows). |
| `--segment_duration` | double | `6.0` | Target segment duration (seconds). If single file, acts as subsegment duration. |
| `--fragment_duration` | double | `0` | Target fragment duration (seconds); should not exceed segment duration. |
| `--segment_sap_aligned` | bool | `true` | Force segments to start on access points. |
| `--fragment_sap_aligned` | bool | `true` | Force fragments to start on access points (implies segment SAP aligned). |
| `--start_segment_number` | int64 | `1` | Initial segment number (DASH SegmentTemplate/HLS segment name). |
| `--clear_lead` | double | `5.0` | Clear lead duration when encryption is enabled; rounded to full segments. |
| `--generate_sidx_in_media_segments` | bool | `true` | Insert `sidx` boxes in media segments (required for DASH on-demand w/o segment template). |
| `--mp4_include_pssh_in_stream` | bool | `true` | Include PSSH boxes inside encrypted MP4 streams. |
| `--transport_stream_timestamp_offset_ms` | int32 | `100` | Positive offset to avoid negative TS timestamps. |
| `--default_text_zero_bias_ms` | int32 | `0` | Bias threshold for assuming text stream starts at zero (pads if earlier than threshold). |

## DASH / MPD

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--mpd_output` | string | `""` | Output MPD file path. |
| `--base_urls` | string | `""` | Comma-separated BaseURLs to add under `<MPD>`. |
| `--min_buffer_time` | double | `2.0` | Common duration for Representation data rate (seconds). |
| `--minimum_update_period` | double | `5.0` | How often players should refresh dynamic MPD (seconds). |
| `--suggested_presentation_delay` | double | `0.0` | Presentation delay to add (seconds) for dynamic MPD. |
| `--utc_timings` | string | `""` | Comma-separated `schemeIdUri=value` pairs for UTCTiming. |
| `--generate_static_live_mpd` | bool | `false` | Force static MPD when segment_template is present. |
| `--generate_dash_if_iop_compliant_mpd` | bool | `true` | Best-effort DASH-IF IOP compliance. |
| `--allow_approximate_segment_timeline` | bool | `false` | Treat near-equal segment durations as equal to reduce SegmentTimeline size (ignored with `$Time$`). |
| `--allow_codec_switching` | bool | `false` | Allow adaptive switching between different codecs (same media type/lang/container). |
| `--include_mspr_pro_for_playready` | bool | `true` | Add PlayReady `<mspr:pro>` alongside `<cenc:pssh>`. |
| `--dash_force_segment_list` | bool | `false` | Use SegmentList instead of SegmentBase (helps when refs > sidx limit). |
| `--low_latency_dash_mode` | bool | `false` | Enable LL-DASH behavior (reduced latency). |
| `--output_media_info` | bool | `false` | Emit human-readable `.media_info` next to outputs. |

## HLS

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--hls_master_playlist_output` | string | `""` | Master playlist output path (required for HLS output). |
| `--hls_base_url` | string | `""` | Base URL prefix for playlists and media. |
| `--hls_key_uri` | string | `""` | Key URI for identity/Apple key formats. |
| `--hls_playlist_type` | string | `"VOD"` | `VOD` / `EVENT` / `LIVE`; sets EXT-X-PLAYLIST-TYPE (omitted for LIVE). |
| `--hls_media_sequence_number` | int32 | `0` | Initial EXT-X-MEDIA-SEQUENCE (helps continuity across restarts). |
| `--hls_start_time_offset` | optional<double> | `nullopt` | EXT-X-START offset; positive = from start, negative = from end. |
| `--create_session_keys` | bool | `false` | Emit EXT-X-SESSION-KEY for offline playback. |
| `--add_program_date_time` | bool | `false` | Add EXT-X-PROGRAM-DATE-TIME based on wall clock. |

## Manifest common (DASH + HLS)

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--time_shift_buffer_depth` | double | `1800.0` | Live buffer depth (seconds). |
| `--preserved_segments_outside_live_window` | uint64 | `50` | Keep this many segments beyond live window before pruning. |
| `--default_language` | string | `""` | Preferred default language for audio/text (sets DASH Role main or HLS DEFAULT=YES). |
| `--default_text_language` | string | `""` | Overrides default language for text tracks only. |
| `--force_cl_index` | bool | `true` | Preserve CLI stream order as track order. |

## DRM selection / protection systems

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--protection_systems` | string | `""` | Comma-separated DRM systems to generate (common, widevine, playready, fairplay, marlin). |

## Crypto common (encryption enabled)

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--protection_scheme` | string | `"cenc"` | Protection scheme: cenc, cbc1, cbcs, cens. |
| `--crypt_byte_block` | int32 | `1` | Encrypted blocks in pattern (applies to cbcs/cens). |
| `--skip_byte_block` | int32 | `9` | Unencrypted blocks in pattern (applies to cbcs/cens). |
| `--vp9_subsample_encryption` | bool | `true` | Enable VP9 subsample encryption. |
| `--playready_extra_header_data` | string | `""` | Extra XML to embed in PlayReady headers. |

## Widevine

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--enable_widevine_encryption` | bool | `false` | Use Widevine key server for encryption. |
| `--enable_widevine_decryption` | bool | `false` | Use Widevine license server/proxy for decryption. |
| `--key_server_url` | string | `""` | Widevine key/license server URL (required with enc/dec). |
| `--content_id` | hex bytes | empty | Content ID (hex); required for encryption. |
| `--policy` | string | `""` | Stored policy name for rights (optional). |
| `--group_id` | hex bytes | empty | License group ID (hex). |
| `--enable_entitlement_license` | bool | `false` | Request entitlement license. |
| `--signer` | string | `""` | Signer name (typically required when using signing keys). |
| `--aes_signing_key` | hex bytes | empty | AES signing key (needs `--aes_signing_iv`, exclusive with RSA). |
| `--aes_signing_iv` | hex bytes | empty | AES signing IV. |
| `--rsa_signing_key_path` | string | `""` | PKCS#1 RSA private key path (exclusive with AES signing). |
| `--crypto_period_duration` | int32 | `0` | Crypto period duration (seconds); >0 enables key rotation. |
| `--max_sd_pixels` | int32 | `768*576` | Upper bound for SD classification (used in label function). |
| `--max_hd_pixels` | int32 | `1920*1080` | Upper bound for HD classification. |
| `--max_uhd1_pixels` | int32 | `4096*2160` | Upper bound for UHD1 classification. |

## Raw key

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--enable_raw_key_encryption` | bool | `false` | Enable encryption with raw keys from CLI. |
| `--enable_raw_key_decryption` | bool | `false` | Enable decryption with raw keys from CLI. |
| `--keys` | string | `""` | `label=<drm_label>:key_id=<hex>:key=<hex>[, ...]` (preferred). |
| `--key_id` | hex bytes | empty | Deprecated single key_id (used only if `--keys` empty). |
| `--key` | hex bytes | empty | Deprecated single key (used only if `--keys` empty). |
| `--iv` | hex bytes | empty | IV (8 or 16 bytes) for raw-key encryption; optional/testing. |
| `--pssh` | hex bytes | empty | PSSH boxes (hex) to embed; optional. |
| `--enable_fixed_key_encryption` | bool | `false` | Alias (deprecated) → maps to `--enable_raw_key_encryption`. |
| `--enable_fixed_key_decryption` | bool | `false` | Alias (deprecated) → maps to `--enable_raw_key_decryption`. |

## PlayReady key server

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--enable_playready_encryption` | bool | `false` | Use PlayReady packaging server for encryption. |
| `--playready_server_url` | string | `""` | PlayReady packaging server URL (required with enable flag). |
| `--program_identifier` | string | `""` | Program identifier for PlayReady request. |

## Ad cue markers

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--ad_cues` | string | `""` | Ad cue markers `start[,duration][;start[,duration]]...` (seconds). |

## Deprecated / retired (ignored)

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--profile` | string | `""` | Deprecated; ignored. |
| `--single_segment` | bool | `true` | Deprecated; ignored. |
| `--webm_subsample_encryption` | bool | `true` | Deprecated; ignored (use `--vp9_subsample_encryption`). |
| `--availability_time_offset` | double | `0` | Deprecated; ignored (use `--suggested_presentation_delay`). |
| `--playready_key_id` | string | `""` | Deprecated; ignored. |
| `--playready_key` | string | `""` | Deprecated; ignored. |
| `--mp4_use_decoding_timestamp_in_timeline` | bool | `false` | Deprecated; ignored. |
| `--num_subsegments_per_sidx` | int32 | `0` | Deprecated; ignored (use `--generate_sidx_in_media_segments`). |
| `--generate_widevine_pssh` | bool | `false` | Deprecated; ignored (use `--protection_systems`). |
| `--generate_playready_pssh` | bool | `false` | Deprecated; ignored (use `--protection_systems`). |
| `--generate_common_pssh` | bool | `false` | Deprecated; ignored (use `--protection_systems`). |
| `--generate_static_mpd` | bool | `false` | Deprecated; ignored (use `--generate_static_live_mpd`). |

---

# mpd_generator

`mpd_generator` parses flags in `packager/app/mpd_generator.cc`.

| Flag | Type | Default | Description |
|---|---|---:|---|
| `--licenses` | bool | `false` | Print bundled licenses and exit. |
| `--test_packager_version` | string | `""` | Inject fake packager version (testing). |
| `--input` | string | `""` | Comma-separated MediaInfo text files (required). |
| `--output` | string | `""` | Output MPD file (required). |
| `--base_urls` | string | `""` | Comma-separated BaseURLs to add under `<MPD>`. |

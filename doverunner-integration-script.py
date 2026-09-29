from __future__ import annotations

import sys
import os
import subprocess
import argparse
import base64
import shlex
import re
from pathlib import Path

# Add the path of cpix-api-client to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
client_path = os.path.join(current_dir, 'cpix-api-client', 'python', 'src')
sys.path.append(client_path)

# Ensure correct packager binary for Mac environment
PACKAGER_BIN = str(Path(current_dir) / 'packager-osx-arm64')

from cpix_client import CpixClient
from drm_type import DrmType
from encryption_scheme import EncryptionScheme
from track_type import TrackType

FAIRPLAY_PSSH = "00000020707373680000000029701FE43CC74A348C5BAE90C7439A4700000000"
# DoveRunner KMS URL
KMS_URL = "https://drm-kms.doverunner.com/v2/cpix/pallycon/getKey/"

# AVC/H.264 ladder (TS/HLS, DASH fMP4)
AVC_VIDEO_LADDER = [
    {"label": "video-1920", "bandwidth": 6000000},
    {"label": "video-1280", "bandwidth": 4000000},
    {"label": "video-960",  "bandwidth": 2000000},
    {"label": "video-854",  "bandwidth": 1500000},
    {"label": "video-640",  "bandwidth": 750000},
    {"label": "video-384",  "bandwidth": 370000},
]

# HEVC/H.265 ladder (CMAF/DASH)
HEVC_VIDEO_LADDER = [
    {"label": "video-3840", "bandwidth": 12000000},
    {"label": "video-2560", "bandwidth": 8000000},
    {"label": "video-1920", "bandwidth": 6000000},
    {"label": "video-1280", "bandwidth": 4000000},
    {"label": "video-854",  "bandwidth": 2000000},
    {"label": "video-640",  "bandwidth": 1200000},
]

MEDIA_CONVERT_AUDIO_PRESET = {
    "label": "audio-2ch-128k",
    "bandwidth": 128000,
    "language": "ko",
}


class CustomArgumentParser(argparse.ArgumentParser):
    def format_usage(self):
        return "usage: %(prog)s [options] [Shaka options]\n\n" % {'prog': self.prog}

    def format_help(self):
        help_text = super().format_help()
        usage_line = self.format_usage()

        description_start = help_text.find(self.description)
        if description_start != -1:
            # Replace everything before the description with the custom usage line
            modified_help = usage_line + help_text[description_start:]
        else:
            modified_help = help_text.replace(help_text.split('\n')[0], usage_line.strip())

        return modified_help


def parse_arguments():
    parser = CustomArgumentParser(description="Sample script for integrating DoveRunner CPIX with Shaka packager")
    default_input = os.path.join(current_dir, "sample.mp4")
    default_output_root = os.path.join(current_dir, "packaging-test", "shaka", "non-drm")
    default_command_log = str(Path(current_dir) / "shaka_command.log")

    # DRM Group
    drm_group = parser.add_argument_group("DRM")
    drm_group.add_argument("--enable_drm", action="store_true", help="Enable DRM.")
    drm_group.add_argument("--enc_token", required=False, help="KMS token used for CPIX API communication with KMS")
    drm_group.add_argument("--content_id", required=False, help="Content ID")
    drm_group.add_argument("--drm_type", required=False, help="DRM Type(s) separated by comma.")
    drm_group.add_argument(
        "--encrypt_scope",
        default="both",
        choices=["audio", "video", "both"],
        help="Choose encryption target: audio, video, or both.",
    )

    # Packaging Group
    packaging_group = parser.add_argument_group("Packaging")
    packaging_group.add_argument("--profile", default="avc_ts", help="Packaging profile.")
    packaging_group.add_argument("--output_format", default="hls", choices=["hls", "dash", "cmaf"], help="Output format.")
    packaging_group.add_argument("--emit_dash", action="store_true", help="When output_format=cmaf, also generate a separate dash/ output (MPD + segments).")
    packaging_group.add_argument("--encryption_scheme", required=False, choices=["cenc", "cbc1", "cens", "cbcs"], help="Encryption scheme override.")

    # I/O Group
    io_group = parser.add_argument_group("I/O")
    io_group.add_argument("--input", default=default_input, help="Input file.")
    io_group.add_argument("--output_root", default=default_output_root, help="Output root directory.")
    io_group.add_argument("--rendition_dir", required=False, help="Directory containing per-rendition inputs.")
    io_group.add_argument("--command_log", default=default_command_log, help="File path to write command log.")

    # Parse args for DoveRunner first
    args, remaining = parser.parse_known_args()

    # Add args for Shaka packager to shaka_args
    args.shaka_args = remaining

    return args


def _encrypt_scope_to_tracks(scope: str) -> tuple[TrackType, list[str]]:
    """
    Map user-facing encrypt_scope to TrackType flags and human-readable labels.
    """
    scope = scope.lower()
    if scope == "audio":
        return TrackType.AUDIO, ["AUDIO"]
    if scope == "video":
        return TrackType.SD | TrackType.HD | TrackType.UHD1 | TrackType.UHD2, ["SD", "HD", "UHD1", "UHD2"]
    if scope == "both":
        return (
            TrackType.AUDIO | TrackType.SD | TrackType.HD | TrackType.UHD1 | TrackType.UHD2,
            ["AUDIO", "SD", "HD", "UHD1", "UHD2"],
        )
    raise ValueError(f"Unsupported encrypt_scope: {scope}")


def parse_flag_enum(enum_class, value_str):
    values = [v.strip().upper() for v in value_str.split(',')]
    result = enum_class(0)
    for value in values:
        if value not in enum_class.__members__:
            raise ValueError(f"Invalid {enum_class.__name__}: {value}")
        result |= enum_class[value]
    return result


def uuid_to_hex(uuid_string):
    return uuid_string.replace('-', '')


def base64_to_hex(base64_string):
    return base64.b64decode(base64_string).hex()


def _extract_hls_playlist_paths(shaka_args: list[str]) -> list[Path]:
    paths: set[Path] = set()
    i = 0
    while i < len(shaka_args):
        arg = shaka_args[i]
        if arg == "--hls_master_playlist_output" and i + 1 < len(shaka_args):
            paths.add(Path(shaka_args[i + 1]))
            i += 2
            continue

        if arg.startswith("--"):
            i += 1
            continue

        for part in arg.split(","):
            if part.startswith("playlist_name="):
                value = part.split("=", 1)[1]
                if value:
                    paths.add(Path(value))
        i += 1

    return sorted(paths)


def _rewrite_hls_master_playlist_to_absolute(master_path: Path) -> None:
    if not master_path.exists() or not master_path.is_file():
        return

    base_dir = master_path.parent.resolve()
    raw = master_path.read_text(encoding="utf-8")
    lines = raw.splitlines(True)

    def _abspath(rel: str) -> str:
        return str((base_dir / rel).resolve())

    def _should_rewrite_uri(uri: str) -> bool:
        if not uri:
            return False
        if uri.startswith("/"):
            return False
        if "://" in uri:
            return False
        return True

    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if 'URI="' in line:
                try:
                    prefix, rest = line.split('URI="', 1)
                    uri, suffix = rest.split('"', 1)
                    if _should_rewrite_uri(uri):
                        out.append(prefix + 'URI="' + _abspath(uri) + '"' + suffix)
                    else:
                        out.append(line)
                except Exception:
                    out.append(line)
            else:
                out.append(line)
            continue

        if _should_rewrite_uri(stripped):
            out.append(_abspath(stripped) + ("\n" if not line.endswith("\n") else "\n"))
            continue

        out.append(line)

    master_path.write_text("".join(out), encoding="utf-8")


def _rewrite_mpd_paths_to_absolute(mpd_path: Path) -> None:
    if not mpd_path.exists() or not mpd_path.is_file():
        return

    base_dir = mpd_path.parent.resolve()
    content = mpd_path.read_text(encoding="utf-8")

    def _abspath(rel: str) -> str:
        return str((base_dir / rel).resolve())

    def _rewrite_attr(text: str, attr: str) -> str:
        # Replace attr="value" where value is a relative path.
        pattern = re.compile(rf'{attr}="([^"]+)"')

        def repl(m: re.Match) -> str:
            value = m.group(1)
            if not value or value.startswith("/") or "://" in value:
                return m.group(0)
            return f'{attr}="{_abspath(value)}"'

        return pattern.sub(repl, text)

    updated = content
    updated = _rewrite_attr(updated, "initialization")
    updated = _rewrite_attr(updated, "media")

    if updated != content:
        mpd_path.write_text(updated, encoding="utf-8")


def _inject_iv_into_hls_playlists(playlist_paths: list[Path], iv_hex: str) -> None:
    iv_attr = f"IV=0x{iv_hex.upper()}"
    for playlist_path in playlist_paths:
        try:
            content = playlist_path.read_text(encoding="utf-8")
        except Exception:
            continue

        changed = False
        new_lines: list[str] = []
        for line in content.splitlines(keepends=True):
            if line.startswith("#EXT-X-KEY:") and "METHOD=SAMPLE-AES" in line and "IV=" not in line:
                stripped = line.rstrip("\r\n")
                line = f"{stripped},{iv_attr}\n"
                changed = True
            new_lines.append(line)

        if changed:
            try:
                playlist_path.write_text("".join(new_lines), encoding="utf-8")
            except Exception:
                pass


# --- New Helper Functions for Packaging Logic ---

def _score_rendition_candidate(path: Path) -> int:
    stem = path.stem
    if stem.startswith("output_"):
        parts = stem.split("_")
        if parts and parts[-1].isdigit():
            return int(parts[-1])
    if stem.startswith("video-"):
        res = stem.split("-", 1)[1]
        if res.isdigit():
            return int(res)
    return -1


def _pick_default_source_from_renditions(root: Path) -> Path | None:
    candidates = []
    for ext in ["mp4", "mxf", "mov", "mkv", "ts"]:
        candidates.extend(sorted(root.glob(f"output_*_*.{ext}")))
        candidates.extend(sorted(root.glob(f"video-*.{ext}")))

    if not candidates:
        return None
    return max(candidates, key=_score_rendition_candidate)


def _resolve_input_for_label(source_path: Path, rendition_root: Path | None, label: str) -> Path:
    if not rendition_root:
        return source_path

    candidates = []
    for ext in ["mp4", "mxf", "mov", "mkv", "ts"]:
        cand = rendition_root / f"{label}.{ext}"
        if cand.exists():
            return cand

        candidates.extend(rendition_root.glob(f"{label}.*"))

        if label.startswith("video-"):
            res = label.split("-", 1)[1]
            alt_avc = rendition_root / f"output_avc_{res}.{ext}"
            if alt_avc.exists():
                return alt_avc
            candidates.extend(rendition_root.glob(f"output_avc_{res}.*"))

            alt_hevc = rendition_root / f"output_hevc_{res}.{ext}"
            if alt_hevc.exists():
                return alt_hevc
            candidates.extend(rendition_root.glob(f"output_hevc_{res}.*"))

        if label.startswith("audio-"):
            alt_audio = rendition_root / f"audio.{ext}"
            if alt_audio.exists():
                return alt_audio
            candidates.extend(rendition_root.glob("audio.*"))

    if candidates:
        return candidates[0]

    audio_candidates = sorted(rendition_root.glob("audio.*"))
    if audio_candidates:
        return audio_candidates[0]

    if label.startswith("audio-") and source_path.exists() and source_path.is_file():
        return source_path

    any_candidates = []
    for ext in ["mp4", "mxf", "mov", "mkv", "ts"]:
        any_candidates.extend(sorted(rendition_root.glob(f"*.{ext}")))
    if any_candidates:
        return any_candidates[0]

    raise FileNotFoundError(f"Rendition file for '{label}' not found in {rendition_root}")


def _pick_encryption_scheme(output_format: str, drm_types_value, override_value: str | None) -> EncryptionScheme:
    if override_value:
        return EncryptionScheme[override_value.strip().upper()]

    if output_format == "dash":
        return EncryptionScheme.CENC
    if output_format == "hls":
        return EncryptionScheme.CBCS
    return EncryptionScheme.CBCS


def _pick_container(output_format: str) -> tuple[str, bool]:
    if output_format == "hls":
        return "ts", True
    if output_format == "dash":
        return "fmp4", False
    return "fmp4", False


def _segment_names(profile: str, container: str, label: str, kind: str, output_format: str = "hls") -> tuple[str | None, str]:
    if profile == "hevc_cmaf":
        if output_format == "dash":
            return f"{label}init.mp4", f"{label}_$Number%09d$.m4s"
        if kind == "video":
            return f"{label}init.cmfv", f"{label}_$Number%09d$.cmfv"
        return f"{label}init.cmfa", f"{label}_$Number%09d$.cmfa"

    if container == "ts":
        return None, f"{label}_$Number%05d$.ts"
    return f"{label}init.mp4", f"{label}_$Number%05d$.m4s"


def _build_stream_descriptor(
    *,
    input_path: Path,
    stream_kind: str,
    bandwidth: int,
    init_segment: Path | None,
    segment_template: Path,
    playlist_path: Path | None,
    language: str | None,
    drm_label: str | None,
) -> str:
    parts = [
        f"in={input_path}",
        f"stream={stream_kind}",
        f"bandwidth={bandwidth}",
    ]

    if language:
        parts.append(f"language={language}")
    if init_segment is not None:
        parts.append(f"init_segment={init_segment}")

    parts.append(f"segment_template={segment_template}")

    if playlist_path is not None:
        parts.append(f"playlist_name={playlist_path}")
    if drm_label is not None:
        parts.append(f"drm_label={drm_label}")
    return ",".join(parts)


def _bucket_for_label(label: str) -> str:
    """
    Map rendition label (e.g., video-1920) to a DRM bucket label expected by KMS (SD/HD/UHD1/UHD2).
    """
    try:
        res_part = label.split("-", 1)[1]
        res = int(res_part)
    except Exception:
        # Fallback to HD if parsing fails
        return "HD"

    if res >= 3500:
        return "UHD2"
    if res >= 2300:
        return "UHD1"
    if res >= 1100:
        return "HD"
    return "SD"


def _pick_video_ladder(profile: str):
    return HEVC_VIDEO_LADDER if profile.startswith("hevc") else AVC_VIDEO_LADDER


def build_packaging_commands(
    source_file,
    output_root,
    segment_length=6,
    clear_lead=0,
    profile="avc_ts",
    ts_segment_format=False,
    container="fmp4",
    output_format="hls",
    rendition_dir=None,
    encrypt_scope="video",
):
    source_path = Path(source_file).resolve()
    rendition_root = Path(rendition_dir).resolve() if rendition_dir else None

    if not source_path.exists():
        if rendition_root:
            picked = _pick_default_source_from_renditions(rendition_root)
            source_path = picked if picked else rendition_root
        else:
            raise FileNotFoundError(f"Template input file not found: {source_path}")

    # Determine include flags based on output_format
    include_hls = output_format in ["hls", "cmaf"]
    include_dash = output_format == "dash" or (output_format == "cmaf" and profile == "hevc_cmaf")
    is_cmaf = output_format == "cmaf" or profile == "hevc_cmaf"
    is_hevc_cmaf = profile == "hevc_cmaf"

    # Map profile to output dir name to align with mediaconvert layout (avc/hevc under root)
    base_dir = "avc" if profile.startswith("avc") else "hevc" if profile.startswith("hevc") else profile
    output_base = Path(output_root).resolve() / base_dir

    if is_hevc_cmaf:
        if output_format == "dash":
            cmaf_root = output_base / "dash"
            hls_root = cmaf_root
            dash_manifest = cmaf_root / "stream.mpd"
        else:
            cmaf_root = output_base / "cmaf"
            hls_root = cmaf_root
            dash_manifest = (cmaf_root / "stream.mpd") if include_dash else None
    elif is_cmaf:
        cmaf_root = output_base / "cmaf"
        hls_root = cmaf_root
        dash_manifest = (output_base / "dash" / "stream.mpd") if include_dash else None
    else:  # "avc_ts"
        hls_root = output_base / "hls"
        dash_root = output_base / "dash"
        cmaf_root = hls_root if include_hls else dash_root
        dash_manifest = dash_root / "stream.mpd" if include_dash else None

    cmaf_root.mkdir(parents=True, exist_ok=True)
    if include_hls:
        hls_root.mkdir(parents=True, exist_ok=True)
    if include_dash:
        dash_manifest.parent.mkdir(parents=True, exist_ok=True)

    shaka_args = []
    extra_global_flags = []

    # DASH VOD: emit static MPD
    if include_dash:
        extra_global_flags.extend(["--generate_static_live_mpd"])

    include_video = encrypt_scope in ("video", "both")
    include_audio = encrypt_scope in ("audio", "both")

    if include_video:
        video_ladder = _pick_video_ladder(profile)
        for track in video_ladder:
            if (not is_cmaf) and output_format == "hls":
                # AVC HLS: place rendition folders under hls/
                track_dir = hls_root / track["label"]
            elif (not is_cmaf) and output_format == "dash":
                # AVC DASH: place rendition folders under dash/
                track_dir = dash_root / track["label"]
            else:
                # CMAF/HEVC: use cmaf_root
                track_dir = cmaf_root / track["label"]
            track_dir.mkdir(parents=True, exist_ok=True)
            if include_hls:
                if is_hevc_cmaf and output_format != "dash":
                    playlist_path = (Path(track["label"]) / f"{track['label']}.m3u8")
                else:
                    playlist_path = (track_dir / f"{track['label']}.m3u8")
            else:
                playlist_path = None

            init_name, seg_template = _segment_names(profile, container, track["label"], "video", output_format=output_format)
            init_segment = (track_dir / init_name) if init_name else None
            seg_path = track_dir / seg_template
            drm_bucket = _bucket_for_label(track["label"]) if include_video else None
            shaka_args.append(
                _build_stream_descriptor(
                    input_path=_resolve_input_for_label(source_path, rendition_root, track["label"]),
                    stream_kind="video",
                    bandwidth=track["bandwidth"],
                    init_segment=init_segment,
                    segment_template=seg_path,
                    playlist_path=playlist_path,
                    language=None,
                    drm_label=drm_bucket,
                )
            )

    if include_audio:
        audio = MEDIA_CONVERT_AUDIO_PRESET
        if (not is_cmaf) and output_format == "hls":
            # AVC HLS: place audio folder under hls/
            audio_dir = hls_root / audio["label"]
        elif (not is_cmaf) and output_format == "dash":
            # AVC DASH: place audio folder under dash/
            audio_dir = dash_root / audio["label"]
        else:
            # CMAF/HEVC: use cmaf_root
            audio_dir = cmaf_root / audio["label"]
        audio_dir.mkdir(parents=True, exist_ok=True)
        if include_hls:
            if is_hevc_cmaf and output_format != "dash":
                audio_playlist = (Path(audio["label"]) / f"{audio['label']}.m3u8")
            else:
                audio_playlist = (audio_dir / f"{audio['label']}.m3u8")
        else:
            audio_playlist = None

        init_name, seg_template = _segment_names(profile, container, audio["label"], "audio", output_format=output_format)
        init_segment = (audio_dir / init_name) if init_name else None
        seg_path = audio_dir / seg_template
        audio_drm_label = "AUDIO" if include_audio else None
        shaka_args.append(
            _build_stream_descriptor(
                input_path=_resolve_input_for_label(source_path, rendition_root, audio["label"]),
                stream_kind="audio",
                bandwidth=audio["bandwidth"],
                init_segment=init_segment,
                segment_template=seg_path,
                playlist_path=audio_playlist,
                language=audio["language"],
                drm_label=audio_drm_label,
            )
        )

    if include_dash:
        shaka_args.extend(["--mpd_output", str(dash_manifest)])
    if include_hls:
        shaka_args.extend(["--hls_master_playlist_output", str(hls_root / "master.m3u8")])
        shaka_args.extend(["--hls_playlist_type", "VOD"])

    shaka_args.extend(["--segment_duration", str(segment_length)])
    if include_hls:
        shaka_args.extend(["--clear_lead", str(clear_lead)])

    shaka_args.extend(extra_global_flags)

    return shaka_args

# --------------------------------------------------------

# Get key information using the CPIX client module
def get_key_info(enc_token, content_id, drm_types, encryption_scheme, track_types):
    kms_url_with_token = f"{KMS_URL}{enc_token}"
    client = CpixClient(kms_url_with_token)
    try:
        if TrackType.ALL_TRACKS in track_types:
            track_types = TrackType.ALL_TRACKS  # single key

        content_key_info = client.get_content_key_info_from_doverunner_kms(
            content_id,
            drm_types,
            encryption_scheme,
            track_types
        )
        return content_key_info
    except Exception as e:
        print(f"Failed to get key information: {e}")
        print(f"Error type: {type(e).__name__}")
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                print(f"Response status: {getattr(resp, 'status_code', 'unknown')}")
                print(f"Response text: {getattr(resp, 'text', '')}")
            except Exception:
                pass
        return None


def run_shaka_packager(content_key_info, shaka_args, drm_types, encryption_scheme, track_types, track_types_as_labels, drm_enabled, is_ts_container=False, command_log_path=None):
    command = [PACKAGER_BIN]

    if drm_enabled:
        if not content_key_info or not content_key_info.multidrm_infos:
            print("No valid key information.")
            return

        keys = []
        pssh = set()
        iv = None
        protection_systems = []
        hls_key_uri = None
        single_kid = None
        single_key = None

        force_single_key_for_hls_ts = bool(is_ts_container and drm_types and (DrmType.FAIRPLAY in drm_types))
        key_infos = content_key_info.multidrm_infos
        if force_single_key_for_hls_ts:
            # HLS-TS + FairPlay is forced to single-key encryption for stability.
            preferred = next((k for k in key_infos if getattr(k, "fairplay_hls_key_uri", None)), None)
            key_infos = [preferred or key_infos[0]]

        for key_info in key_infos:
            # Matches the label value and track type entered by the user.
            if force_single_key_for_hls_ts:
                label = ""
            else:
                label = "" if TrackType.ALL_TRACKS in track_types \
                    else next((track_label
                               for track_label in track_types_as_labels if track_label.upper() == key_info.track_type), "")
            kid = uuid_to_hex(key_info.key_id)
            key = base64_to_hex(key_info.key)
            if force_single_key_for_hls_ts:
                single_kid = kid
                single_key = key
            else:
                keys.append(f"label={label}:key_id={kid}:key={key}")

            if iv is None and key_info.iv:
                iv = base64_to_hex(key_info.iv)

            if DrmType.WIDEVINE in drm_types and key_info.widevine_pssh:
                pssh.add(base64_to_hex(key_info.widevine_pssh))
                if "widevine" not in protection_systems:
                    protection_systems.append("widevine")
            if DrmType.PLAYREADY in drm_types and key_info.playready_pssh:
                pssh.add(base64_to_hex(key_info.playready_pssh))
                if "playready" not in protection_systems:
                    protection_systems.append("playready")
            if DrmType.FAIRPLAY in drm_types:
                pssh.add(FAIRPLAY_PSSH)
                if not hls_key_uri and getattr(key_info, "fairplay_hls_key_uri", None):
                    hls_key_uri = key_info.fairplay_hls_key_uri

        command.append("--enable_raw_key_encryption")
        if force_single_key_for_hls_ts:
            if not single_kid or not single_key:
                print("No valid single key material.")
                return
            command.extend(["--key_id", single_kid, "--key", single_key])
        else:
            command.extend(["--keys", ','.join(keys)])

        # Remove drm_label from args if only using default key (ALL_TRACKS)
        if force_single_key_for_hls_ts or all(k.startswith("label=:") for k in keys):
            sanitized = []
            for arg in shaka_args:
                if arg.startswith("--"):
                    sanitized.append(arg)
                    continue
                parts = [p for p in arg.split(",") if not p.startswith("drm_label=")]
                sanitized.append(",".join(parts))
            shaka_args = sanitized

        if is_ts_container and DrmType.FAIRPLAY in drm_types:
            print("Using Sample-AES encryption for HLS-TS with FairPlay")
        else:
            command.extend(["--protection_scheme", encryption_scheme.name.lower()])

        # Apply hls_key_uri for single-key FairPlay.
        if DrmType.FAIRPLAY in drm_types and hls_key_uri and (force_single_key_for_hls_ts or len(keys) == 1):
            command.extend(["--hls_key_uri", hls_key_uri])

        if iv and DrmType.FAIRPLAY in drm_types:
            command.extend(["--iv", iv])

        if pssh and not is_ts_container:
            command.extend(["--pssh", ''.join(pssh)])

        if drm_enabled and drm_types and (DrmType.FAIRPLAY in drm_types) and is_ts_container:
            # For HLS-TS FairPlay, explicitly set protection_systems=fairplay so that packager
            # emits KEYFORMAT=com.apple.streamingkeydelivery instead of KEYFORMAT=identity.
            if "fairplay" not in protection_systems:
                protection_systems.append("fairplay")

        if protection_systems:
            command.extend(["--protection_systems", ','.join(protection_systems)])

    else:
        print("DRM is disabled; running Shaka Packager without encryption flags.")

    # Add all remaining shaka_args to the command
    command.extend(shaka_args)

    try:
        printable = " \\\n   ".join(shlex.quote(arg) for arg in command)
        if command_log_path:
            with open(command_log_path, "a", encoding="utf-8") as f:
                f.write("[shaka] full command:\n")
                f.write(f"  {printable}\n")

        hls_work_dir = None
        if "--hls_master_playlist_output" in shaka_args:
            try:
                idx = shaka_args.index("--hls_master_playlist_output")
                if idx + 1 < len(shaka_args):
                    hls_work_dir = str(Path(shaka_args[idx + 1]).resolve().parent)
            except Exception:
                hls_work_dir = None

        subprocess.run(command, check=True, cwd=hls_work_dir)

        if "--hls_master_playlist_output" in shaka_args:
            try:
                idx = shaka_args.index("--hls_master_playlist_output")
                if idx + 1 < len(shaka_args):
                    master = Path(shaka_args[idx + 1])
                    if hls_work_dir and not master.is_absolute():
                        master = (Path(hls_work_dir) / master).resolve()
                    _rewrite_hls_master_playlist_to_absolute(master)
            except Exception:
                pass

        if "--mpd_output" in shaka_args:
            try:
                idx = shaka_args.index("--mpd_output")
                if idx + 1 < len(shaka_args):
                    mpd = Path(shaka_args[idx + 1])
                    if hls_work_dir and not mpd.is_absolute():
                        mpd = (Path(hls_work_dir) / mpd).resolve()
                    _rewrite_mpd_paths_to_absolute(mpd)
            except Exception:
                pass

        if is_ts_container and drm_enabled and drm_types and (DrmType.FAIRPLAY in drm_types) and iv:
            playlist_paths = _extract_hls_playlist_paths(shaka_args)
            if hls_work_dir:
                base_dir = Path(hls_work_dir)
                resolved = [(p if p.is_absolute() else (base_dir / p)).resolve() for p in playlist_paths]
            else:
                resolved = playlist_paths
            _inject_iv_into_hls_playlists(resolved, iv)

        print("Packaging complete.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running Shaka Packager")
        # print(f"An error occurred while running Shaka Packager: {e}")


if __name__ == "__main__":
    args = parse_arguments()

    drm_enabled = args.enable_drm
    drm_types = None
    track_types = TrackType.ALL_TRACKS
    encryption_scheme = EncryptionScheme.CENC
    key_info = None
    key_info_dash = None

    effective_encrypt_scope = args.encrypt_scope

    if drm_enabled:
        missing = [flag for flag in ["enc_token", "content_id", "drm_type"] if not getattr(args, flag)]
        if missing:
            print(f"Missing required arguments for DRM mode: {', '.join(missing)}")
            sys.exit(1)

        try:
            drm_types = parse_flag_enum(DrmType, args.drm_type.upper())
            track_types, track_types_as_labels = _encrypt_scope_to_tracks(effective_encrypt_scope)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        encryption_scheme = _pick_encryption_scheme(args.output_format, drm_types, args.encryption_scheme)
        encryption_scheme_dash = _pick_encryption_scheme("dash", drm_types, args.encryption_scheme)

        kms_url = KMS_URL.format(enc_token=args.enc_token) if "{enc_token}" in KMS_URL else f"{KMS_URL}{args.enc_token}"
        client = CpixClient(kms_url)
        try:
            if TrackType.ALL_TRACKS in track_types:
                track_types = TrackType.ALL_TRACKS
            key_info = client.get_content_key_info_from_doverunner_kms(
                args.content_id,
                drm_types,
                encryption_scheme,
                track_types
            )

            if args.output_format == "cmaf" and args.emit_dash:
                key_info_dash = client.get_content_key_info_from_doverunner_kms(
                    args.content_id,
                    drm_types,
                    encryption_scheme_dash,
                    track_types
                )
        except Exception as e:
            print(f"Failed to get key information: {e}")
            print(f"Error type: {type(e).__name__}")
            key_info = None
        if not key_info:
            print("Failed to get key information. Exit the program.")
            sys.exit(1)
    else:
        key_info = None
        track_types_as_labels = []

    if args.command_log:
        with open(args.command_log, "w", encoding="utf-8") as _:
            pass

    container, is_ts = _pick_container(args.output_format)

    # Primary output
    generated_shaka_args = build_packaging_commands(
        args.input,
        args.output_root,
        ts_segment_format=is_ts,
        container=container,
        output_format=args.output_format,
        rendition_dir=args.rendition_dir,
        profile=args.profile,
        encrypt_scope=effective_encrypt_scope,
    )
    final_shaka_args = generated_shaka_args + args.shaka_args
    run_shaka_packager(
        key_info,
        final_shaka_args,
        drm_types,
        encryption_scheme,
        track_types,
        track_types_as_labels,
        drm_enabled,
        is_ts_container=is_ts,
        command_log_path=args.command_log,
    )

    # Optional separate DASH output (MediaConvert-like layout)
    if args.output_format == "cmaf" and args.emit_dash:
        dash_args = build_packaging_commands(
            args.input,
            args.output_root,
            ts_segment_format=False,
            container="fmp4",
            output_format="dash",
            rendition_dir=args.rendition_dir,
            profile=args.profile,
            encrypt_scope=effective_encrypt_scope,
        )
        run_shaka_packager(
            key_info_dash,
            dash_args,
            drm_types,
            _pick_encryption_scheme("dash", drm_types, args.encryption_scheme),
            track_types,
            track_types_as_labels,
            drm_enabled,
            is_ts_container=False,
            command_log_path=args.command_log,
        )

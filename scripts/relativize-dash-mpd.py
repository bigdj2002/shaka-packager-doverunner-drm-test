#!/usr/bin/env python3
"""Make a Shaka Packager DASH manifest portable to an HTTP origin."""

import re
import sys
from pathlib import Path


def relativize(mpd_path: Path) -> None:
    mpd_path = mpd_path.resolve()
    prefix = str(mpd_path.parent) + "/"
    original = mpd_path.read_text(encoding="utf-8")
    updated = original

    for attribute in ("initialization", "media"):
        updated = re.sub(
            rf'({attribute}="){re.escape(prefix)}',
            r"\1",
            updated,
        )

    for match in re.finditer(r'(?:initialization|media)="([^"]+)"', updated):
        if match.group(1).startswith(("/", "file://")):
            raise ValueError(f"Absolute segment URL remains in {mpd_path}")

    if updated != original:
        mpd_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        relativize(Path(argument))

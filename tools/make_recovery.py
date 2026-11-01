#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce one experimental stock X50 v1 recovery image. Never flashes a router.

Python 3.9+; standard library only. Only the exact allowlisted TP-Link 1.6.7
image is accepted. Do not generalize this length-field change to other images.
"""

import argparse
import hashlib
import io
from pathlib import Path
import struct
import sys
import urllib.request
import zipfile

SOURCE_URL = (
    "https://static.tp-link.com/upload/firmware/2025/202506/20250604/"
    "X50v1_1.6.7%20Build%2025031412%20Rel.%2048241.zip"
)
ARCHIVE_BYTES = 35_211_174
ARCHIVE_SHA256 = "f810c90d377f7f59ce6a1e9b5e6c52d90f8c3ce6c9bfc7df86a48ce86b4af7e1"
MEMBER_NAME = "X50v1_en_1.6.7 Build 25031412 Rel. 48241_US_EU_JP_CA_up.bin"
SOURCE_BYTES = 37_363_379
SOURCE_SHA256 = "9d7c13c9570531d25fb00cf682ef19f2e6fe5a8509f690d26bfa0a00eae977bc"
CANDIDATE_SHA256 = "0dd441b4dab6027591f0b1d13b4c63d7c820f5580473847a23730140e1e96370"
DECLARED_BYTES = 0x02001814
OUTPUT_NAME = "Deco_X50_V1_1.6.7_legacy_HTTP_recovery_EXPERIMENTAL.bin"


class RecoveryError(ValueError):
    """An input did not match the exact supported image."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_source(data):
    if len(data) != SOURCE_BYTES or sha256(data) != SOURCE_SHA256:
        raise RecoveryError(
            "Unsupported input: expected the unmodified official X50 v1 1.6.7 BIN "
            f"({SOURCE_BYTES} bytes, SHA-256 {SOURCE_SHA256}). No output was written."
        )


def source_from_archive(data):
    if len(data) != ARCHIVE_BYTES or sha256(data) != ARCHIVE_SHA256:
        raise RecoveryError("ZIP does not match the allowlisted official archive.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [item for item in archive.infolist() if item.filename == MEMBER_NAME]
        if len(entries) != 1 or entries[0].file_size != SOURCE_BYTES:
            raise RecoveryError("Unexpected ZIP member or uncompressed size.")
        # Read the exact member into memory; no archive paths are extracted.
        source = archive.read(entries[0])
    validate_source(source)
    return source


def read_source(path):
    size = path.stat().st_size
    if size not in (ARCHIVE_BYTES, SOURCE_BYTES):
        raise RecoveryError("Input size does not match the supported ZIP or BIN.")
    with path.open("rb") as stream:
        data = stream.read(max(ARCHIVE_BYTES, SOURCE_BYTES) + 1)
    if size == ARCHIVE_BYTES:
        return source_from_archive(data)
    validate_source(data)
    return data


def download_source():
    print("Downloading the exact official TP-Link archive over HTTPS...", flush=True)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "deco-x50-v1-recovery"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.geturl().startswith("https://static.tp-link.com/"):
            raise RecoveryError("Unexpected download destination; expected official TP-Link HTTPS.")
        data = response.read(ARCHIVE_BYTES + 1)
    return source_from_archive(data)


def make_candidate(source):
    validate_source(source)
    candidate = struct.pack(">I", DECLARED_BYTES) + source[4:]
    if candidate[4:] != source[4:] or sha256(candidate) != CANDIDATE_SHA256:
        raise RecoveryError("Internal reproducibility check failed; refusing to save.")
    return candidate


def check_candidate(path):
    if path.stat().st_size != SOURCE_BYTES:
        raise RecoveryError("Candidate size mismatch.")
    with path.open("rb") as stream:
        data = stream.read(SOURCE_BYTES + 1)
    if sha256(data) != CANDIDATE_SHA256:
        raise RecoveryError("Candidate SHA-256 mismatch.")
    return data


def save_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also rejects an existing symlink. Never overwrites inputs.
    with path.open("xb") as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--download", action="store_true", help="Fetch the exact official ZIP")
    inputs.add_argument("--input", type=Path, help="Use the exact official ZIP or extracted BIN")
    inputs.add_argument("--check", type=Path, help="Check an existing candidate; write nothing")
    parser.add_argument("--output", type=Path, default=Path("artifacts") / OUTPUT_NAME)
    args = parser.parse_args(argv)
    try:
        if args.check is not None:
            check_candidate(args.check)
            print("Candidate matches the reproducible reference exactly.")
        else:
            if args.output.exists() or args.output.is_symlink():
                raise RecoveryError(f"Output already exists: {args.output}. Choose a new path.")
            source = download_source() if args.download else read_source(args.input)
            candidate = make_candidate(source)
            save_new(args.output, candidate)
            print(f"Created: {args.output}")
            print("Only offsets 1, 2 and 3 changed; every byte from offset 4 is preserved.")
        print(f"Size: {SOURCE_BYTES} bytes")
        print(f"SHA-256: {CANDIDATE_SHA256}")
        print("EXPERIMENTAL stock recovery image; read README.md before using it.")
        print("This tool does not contact or flash a router.")
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

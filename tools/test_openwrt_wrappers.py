#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Local experiment: wrap an existing OpenWrt UBI in a Deco stock container.

All output images are internal negative test inputs, not installable firmware.
Runs a host-only GPL-loader harness with all hardware operations stubbed out.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
EXPECTED_PAYLOAD_HASH = "82b8dd525b40a7974c58b563a4f98cd7d405548b0df6bfdbeb21c48b27da5c52"
TABLE, DATA, LIMIT = 0x1014, 0x1814, 0x2001814

spec = importlib.util.spec_from_file_location("deco_inspect", BASE / "tools/analyze_deco_firmware.py")
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


def update_outer_md5(data):
    # The common tplink-safeloader salt, as used by the published repack script.
    # The inspected recovery never uses this field for signature verification.
    salt = bytes.fromhex("7a2b15ed9b98596de504ab44ac2a9f4e")
    data[4:20] = hashlib.md5(salt + data[20:]).digest()


def compact(original, ubi, table, proud=False):
    header = bytearray(original[:DATA])
    struct.pack_into(">I", header, TABLE, len(ubi))
    body = bytearray(ubi)
    for i, entry in enumerate(table["partitions"]):
        old_base, size = entry["absolute_base"], entry["size"]
        new_base = len(body)
        body += original[old_base:old_base + size]
        struct.pack_into(">I", header, TABLE + 12 + i * 44 + 32, new_base)
    data = header + body
    struct.pack_into(">I", data, 0, len(data))
    if proud:
        data[0x1C:0x1E] = b"Pr"
    update_outer_md5(data)
    return data


def run_case(name, data, expected_pass, output_dir, parsed=None):
    path = output_dir / (name + ".test-input")
    path.write_bytes(data)
    result = subprocess.run(
        [str(BASE / "host_harness/check_recovery"), str(path)],
        capture_output=True, text=True,
    )
    (output_dir / (name + ".log")).write_text(result.stdout + result.stderr)
    actual_pass = result.returncode == 0
    if actual_pass != expected_pass:
        raise RuntimeError("Unexpected result in " + name)
    summary = re.search(r"HARNESS_RESULT (.+)", result.stdout)
    evidence = {
        "case": name, "bytes": len(data), "declared_bytes": struct.unpack_from(">I", data)[0],
        "sha256": hashlib.sha256(data).hexdigest(), "rsa_valid": inspector.verify(bytes(data))[0],
        "accepted_by_host_loader": actual_pass, "loader_summary": summary.group(1) if summary else None,
        "signature_error": "Verify sig error!" in result.stdout,
        "format_table_parsed": parsed is not None,
        "scope": "Local host harness; no physical router connected or flashed",
    }
    if not expected_pass and ("write_calls=0" not in result.stdout or "erase_calls=0" not in result.stdout):
        raise RuntimeError("Rejected input unexpectedly reached a hardware stub")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--openwrt", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=BASE / "artifacts/openwrt-negative-tests")
    args = parser.parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=False)
    original = args.stock.read_bytes()
    ubi = args.openwrt.read_bytes()
    if hashlib.sha256(original).hexdigest() != "9d7c13c9570531d25fb00cf682ef19f2e6fe5a8509f690d26bfa0a00eae977bc":
        raise RuntimeError("Stock 1.6.7 carrier digest mismatch")
    if hashlib.sha256(ubi).hexdigest() != EXPECTED_PAYLOAD_HASH:
        raise RuntimeError("OpenWrt release digest mismatch")
    if ubi[:4] != b"UBI#" or len(ubi) % (128 * 1024):
        raise RuntimeError("Unexpected OpenWrt UBI geometry")
    if not inspector.verify(original)[0]:
        raise RuntimeError("Invalid original carrier")
    table = inspector.parse_table(original)

    control = bytearray(original)
    struct.pack_into(">I", control, 0, LIMIT)
    cloud = compact(original, ubi, table)
    proud = compact(original, ubi, table, proud=True)
    cloud_table = inspector.parse_table(cloud)
    proud_table = inspector.parse_table(proud)
    if cloud_table["root_size"] != len(ubi) or proud_table["root_size"] != len(ubi):
        raise RuntimeError("Incorrect rewritten rootfs length")
    if bytes(cloud[DATA:DATA + len(ubi)]) != ubi:
        raise RuntimeError("Wrapped OpenWrt changed unexpectedly")

    padded = bytearray(original)
    padded[DATA:DATA + table["root_size"]] = ubi + b"\xFF" * (table["root_size"] - len(ubi))
    struct.pack_into(">I", padded, 0, LIMIT)
    update_outer_md5(padded)
    padded_table = inspector.parse_table(padded)

    appended = bytearray(control) + ubi
    update_outer_md5(appended)

    results = [
        run_case("stock_167_length_only_CONTROL", control, True, output_dir, inspector.parse_table(control)),
        run_case("openwrt_compact_cloud_md5_fixed", cloud, False, output_dir, cloud_table),
        run_case("openwrt_compact_proud_md5_fixed", proud, False, output_dir, proud_table),
        run_case("openwrt_padded_stock_table_length_clamped", padded, False, output_dir, padded_table),
        run_case("stock_signed_prefix_openwrt_appended", appended, False, output_dir, inspector.parse_table(appended)),
    ]
    report = {
        "openwrt_sha256": EXPECTED_PAYLOAD_HASH,
        "openwrt_bytes": len(ubi), "carrier_sha256": hashlib.sha256(original).hexdigest(),
        "hardware_tested": False, "results": results,
    }
    (output_dir / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

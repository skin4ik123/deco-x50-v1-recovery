#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Inspect TP-Link Deco firmware offline. Never connects to or flashes a router.

Requires Python 3 and cryptography. Public keys/format are documented in TP-Link
GPL nvrammanager and sidhantgoel/tplink_decrypt. Offsets target the X50 v1 format.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY_1024 = b"""-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC01mXkVkLWgx8iRZkDuMC8zlNJ
jAwj1QHhlpJrrRFHztHK4FVtoxn+uFP43/odevO8qziynnkkLaHu3wD1/q+2qCmL
1VDtIRU3NQD7wbI2yhvbieqU0KEJ6rA3rQXrSOJp4Vh1JowAvjNlnAFWGEOUmTmZ
k7gGCSY1xZBDwhCX/QIDAQAB
-----END PUBLIC KEY-----"""
KEY_2048 = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtsejiMPOKuh/OQ9/MKiJ
RQsHk0/UtzfrNFUKto2PTIgg8sjS5hRHRRnHqQmi5bOB3LI4VeoREAOaAqsxky69
lEcGd4H2zGH74c0EZI5jn/eOsxPJkf9E4GlIlezKle6K93u7WZWMnsl4Azgsolkr
hUwa1ViUmQyEmAcN+n3DFvggHvBfZi3uszXyOxCtdcLWsbZzm8Sb2gq7WhHiefO7
oi5n72uGUp4QxnXidG5d8IzCHIPtvh209zJzvWRroAhgn1FLRY0Vaba17ZjO5CkK
GLpzINVZQuCOOLVlEmngwAYAFjh1TIkIVw3qZrxWqvPjcViiy9WUXmMuJPBKHcOh
nQIDAQAB
-----END PUBLIC KEY-----"""
SIG_OFFSET = 0x130
TABLE_OFFSET = 0x1014
DATA_OFFSET = 0x1814


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify(data):
    if len(data) < DATA_OFFSET:
        return False, {"reason": "too short for this container format"}
    version = data[0x112]
    if version not in (1, 2):
        return False, {"reason": "unknown signature version", "version": version}
    sig_len = 256 if version == 2 else 128
    signature = data[SIG_OFFSET:SIG_OFFSET + sig_len][::-1]
    message = bytearray(data[20:])
    message[SIG_OFFSET - 20:SIG_OFFSET - 20 + sig_len] = bytes(sig_len)
    key = serialization.load_pem_public_key(KEY_2048 if version == 2 else KEY_1024)
    try:
        if version == 1:
            # GPL rsaVerifySign computes SHA-1 over the MD5 digest of this region.
            key.verify(signature, hashlib.md5(message).digest(), padding.PKCS1v15(), hashes.SHA1())
        else:
            key.verify(signature, bytes(message), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=222), hashes.SHA256())
    except (InvalidSignature, ValueError):
        return False, {"version": version, "signature_bytes": sig_len}
    return True, {"version": version, "signature_bytes": sig_len}


def decrypt_verified(data):
    """Decrypt only after a valid RSA-2048/PSS signature has been checked."""
    if not verify(data)[0]:
        raise ValueError("Refusing to decrypt an image with an invalid signature")
    if data[0x112] != 2:
        return data
    key = serialization.load_pem_public_key(KEY_2048).public_numbers()
    signature = int.from_bytes(data[SIG_OFFSET:SIG_OFFSET + 256], "little")
    em = pow(signature, key.e, key.n).to_bytes(256, "big")
    if em[-1] != 0xBC:
        raise ValueError("Unexpected PSS trailer")
    masked_db, digest = em[:223], em[223:255]
    mask = b"".join(hashlib.sha256(digest + i.to_bytes(4, "big")).digest() for i in range(7))[:223]
    db = bytearray(a ^ b for a, b in zip(masked_db, mask))
    db[0] &= 0x7F
    if db[0] != 1:
        raise ValueError("Unexpected PSS salt encoding")
    salt = bytes(db[1:])
    start = SIG_OFFSET + 256
    end = start + ((len(data) - start) // 16) * 16
    decryptor = Cipher(algorithms.AES(salt[:16]), modes.CBC(salt[16:32])).decryptor()
    return data[:start] + decryptor.update(data[start:end]) + decryptor.finalize() + data[end:]


def parse_table(data):
    root_size, count, is_manu = struct.unpack_from(">III", data, TABLE_OFFSET)
    if count > 32 or root_size < 64 or DATA_OFFSET + root_size > len(data):
        raise ValueError("Not a supported plaintext upgrade table")
    partitions = []
    previous_end = root_size
    for index in range(count):
        pos = TABLE_OFFSET + 12 + 44 * index
        name = data[pos:pos + 32].split(b"\0", 1)[0].decode("ascii")
        base, size, kind = struct.unpack_from(">III", data, pos + 32)
        if base != previous_end or DATA_OFFSET + base + size > len(data):
            raise ValueError("Partition bounds or contiguous-layout check failed")
        previous_end = base + size
        raw = data[DATA_OFFSET + base:DATA_OFFSET + base + size]
        partitions.append({"name": name, "relative_base": base, "absolute_base": DATA_OFFSET + base,
                           "size": size, "content_type": kind, "sha256": sha256(raw),
                           "text": raw.decode("utf-8", errors="replace").rstrip("\0")})
    return {"table_offset": TABLE_OFFSET, "ubi_offset": DATA_OFFSET, "root_size": root_size,
            "isManu": is_manu, "partition_count": count, "partitions": partitions}


def extract_ubi(ubi, out_dir):
    """Read the 128-KiB PEB / 2-KiB page UBI layout used by Deco X50 v1."""
    peb_size = 128 * 1024
    if len(ubi) % peb_size:
        raise ValueError("Root UBI length is not a whole number of erase blocks")
    volumes, names = {}, {}
    for pos in range(0, len(ubi), peb_size):
        block = ubi[pos:pos + peb_size]
        if block[:4] != b"UBI#":
            continue
        vid_offset, data_offset = struct.unpack_from(">II", block, 16)
        if not (64 <= vid_offset < data_offset < peb_size):
            raise ValueError("Invalid UBI header offsets")
        vid = block[vid_offset:vid_offset + 64]
        if vid[:4] != b"UBI!":
            continue
        vol_id, lnum = struct.unpack_from(">II", vid, 8)
        seq = struct.unpack_from(">Q", vid, 40)[0]
        raw = block[data_offset:]
        if vol_id == 0x7FFFEFFF:
            for i in range(min(128, len(raw) // 172)):
                record = raw[172 * i:172 * (i + 1)]
                reserved = struct.unpack_from(">I", record)[0]
                length = struct.unpack_from(">H", record, 14)[0]
                if reserved and 0 < length <= 127:
                    names[i] = record[16:16 + length].decode("ascii")
            continue
        if vol_id >= 128:
            continue
        key = (vol_id, lnum)
        if key not in volumes or seq > volumes[key][0]:
            volumes[key] = (seq, raw)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for vol_id in sorted({key[0] for key in volumes}):
        parts = sorted((lnum, raw) for (vid, lnum), (_, raw) in volumes.items() if vid == vol_id)
        if [i for i, _ in parts] != list(range(len(parts))):
            raise ValueError("Missing logical block in UBI volume")
        raw = b"".join(raw for _, raw in parts)
        name = names.get(vol_id, f"volume-{vol_id}")
        if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("Unsafe volume name")
        target = out_dir / (name + ".bin")
        target.write_bytes(raw)
        outputs.append({"name": name, "volume_id": vol_id, "bytes": len(raw), "sha256": sha256(raw), "path": str(target)})
    return outputs


def inspect(path, extract_dir=None):
    data = path.read_bytes()
    valid, signature = verify(data)
    result = {"file": str(path), "bytes": len(data), "sha256": sha256(data),
              "declared_bytes": struct.unpack_from(">I", data)[0] if len(data) >= 4 else None,
              "signature_valid": valid, "signature": signature,
              "scope": "offline verification with published keys; not a test on a physical router"}
    if not valid:
        return result
    plain = decrypt_verified(data)
    try:
        table = parse_table(plain)
    except (ValueError, struct.error, UnicodeDecodeError) as exc:
        result["parse_error"] = str(exc)
        return result
    result["upgrade_table"] = table
    result["payload_was_encrypted"] = plain != data
    if extract_dir is not None:
        extract_dir.mkdir(parents=True, exist_ok=True)
        ubi = plain[DATA_OFFSET:DATA_OFFSET + table["root_size"]]
        (extract_dir / "rootfs.ubi").write_bytes(ubi)
        result["volumes"] = extract_ubi(ubi, extract_dir / "volumes")
    return result


def mutation_controls(path):
    data = path.read_bytes()
    if not verify(data)[0]:
        raise ValueError("Mutation controls require a genuine valid image")
    cases = [("original", None), ("Cloud_to_Proud", (0x1C, b"Pr")),
             ("one_payload_bit_changed", (DATA_OFFSET + 0x1000, bytes([data[DATA_OFFSET + 0x1000] ^ 1])))]
    outputs = []
    for name, change in cases:
        modified = bytearray(data)
        if change is not None:
            offset, replacement = change
            modified[offset:offset + len(replacement)] = replacement
        outputs.append({"case": name, "signature_valid": verify(bytes(modified))[0]})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path)
    parser.add_argument("--extract", type=Path, help="Write verified UBI/volumes into this local directory")
    parser.add_argument("--mutation-controls", action="store_true", help="Verify in-memory mutations; writes no modified firmware")
    args = parser.parse_args()
    result = inspect(args.firmware, args.extract)
    if args.mutation_controls:
        result["mutation_controls"] = mutation_controls(args.firmware)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

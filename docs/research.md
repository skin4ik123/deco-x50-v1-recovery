# Source analysis

Analysis date: 2026-11-01. Findings below describe the published source and tested files, not an independently dumped device bootloader.

## Sources and provenance

Two official TP-Link archives were compared:

- [GPL_X55.tar.gz, 2022-06-02](https://static.tp-link.com/upload/gpl-code/2022/202206/20220602/GPL_X55.tar.gz), member prefix `GPL_X55/qca/src/u-boot-2016/`.
- [GPL_x55.tar.gz, 2023-02-23](https://static.tp-link.com/upload/gpl-code/2023/202302/20230223/GPL_x55.tar.gz), member prefix `11.4/qca/src/u-boot-2016/`.

`lib/nvrammanager/nm_fwup.c` is byte-identical between these archives: SHA-256 `463da6ba465e4216abf497822e3d55fc9426fa44d6f5c4a0c5a7a85ea783d6e6`. The unmodified copy is in [host_harness/nm_fwup.c](../host_harness/nm_fwup.c).

`lib/uip/httpd.c` is also identical: SHA-256 `1c9d9069dda305bf00574776e9f97afcc4a268d9ad456f6809dabf9b866da900`. Archive URLs, sizes and hashes are in [source_manifest.json](../evidence/source_manifest.json).

## HTTP call path and signature

`httpd.c:554`, `handle_update`, calls `nm_upgradeFirmware(upload_buffer, actual_received_bytes)`. In `nm_fwup.c:473` the loader:

1. Reads the external big-endian `filesize` field at offset 0.
2. Checks that it is between the minimum and `IMAGE_SIZE_MAX`, and no larger than the actual buffer.
3. Unconditionally calls `handle_fw_cloud` to verify the RSA signature.
4. Parses the signed upgrade table and reaches the OS-slot write routine.

The legacy maximum is `0x02001814`, or 33,560,596 bytes. The actual 1.6.7 BIN is 37,363,379 bytes, so its original declared size is rejected.

`handle_fw_cloud` at line 448 zeroes the 128-byte signature field at `0x130`, computes MD5 over **the actual upload from `0x14` to its end**, then verifies the signature using the fixed RSA-1024 public key. The vendor RSA routine uses SHA-1 over that MD5 digest, PKCS#1 v1.5, and a little-endian stored signature. The Python inspector and OpenSSL harness reproduce this verification.

The first 20 bytes are outside this signed region: a four-byte declared size and a 16-byte outer MD5 field. Changing the declared size leaves RSA valid. Replacing UBI, changing the table or `isManu`, switching Cloud/Proud, or appending bytes does not.

## Container layout

| Offset | Field |
|---|---|
| `0x0000` | Declared length, four-byte big endian |
| `0x0004` | Outer MD5, 16 bytes |
| `0x0014` | Signed region begins; `fw-type:Cloud` in examined originals |
| `0x0112` | Signature-format version in examined originals |
| `0x0130` | Stored signature: 128 bytes for old format, 256 for new format |
| `0x1014` | Upgrade table: rootSize, entry count, isManu, metadata entries |
| `0x1814` | UBI system image begins |

Table scalar fields are 32-bit big endian. An entry is 44 bytes: name[32], relative base, length, content type. Bases are relative to `0x1814`. The actual support-list and soft-version upload data are text; the inspector does not discard an assumed eight-byte prefix.

In the newer encrypted format, these table offsets apply to decrypted bytes. Successfully verifying/decrypting that format offline does not make it accepted by the old loader.

## The length-only candidate

The builder allows exactly one original BIN by full size and SHA-256. It replaces bytes `[0:4]` with big-endian `0x02001814`. For this input only offsets 1, 2 and 3 actually change. Everything from offset 4 to the real end is identical to the vendor image. The outer MD5 is left untouched; the examined loader does not use it as an independent authorization check.

`nm_writeRootToMtd` at line 189 uses the signed `rootSize` and the selected OS partition size. The 1.6.7 root UBI is 37,355,520 bytes. In the harness it fits the assumed 44,040,192-byte (42 MiB) slot, so the full UBI reaches the mock write. It is not truncated to the smaller external declared size.

The harness uses the published X50 v1 layout assumption: root slots at `0x640000` and `0x3040000`, each `0x2a00000` bytes. This is not a readout of the owner's hardware. No inference about physical bad blocks or actual NAND capacity follows from a mock write.

## Investigated firmware

All seven original signatures below were verified offline using the published public keys.

| Original BIN | Bytes | Signature | Encrypted payload | isManu |
|---|---:|---|---|---:|
| X55 v1 1.2.2 Build 230301 | 32,250,712 | RSA-1024 | No | 0 |
| X50 ISP-US v1 2.1.0 Build 20260829 | 32,774,773 | RSA-1024 | No | 0 |
| X50 v1 1.3.1 Build 230824 | 38,542,282 | RSA-1024 | No | 0 |
| X50 v1 1.5.5 Build 240718 | 36,314,803 | RSA-1024 | No | 0 |
| X50 v1 1.6.7 Build 25031412 | 37,363,379 | RSA-1024 | No | 0 |
| X50 v1 1.8.0 Build 25102213 | 37,625,536 | RSA-2048/PSS | AES | 0 |
| X50 v1 1.11.1 Build 26081714 | 37,887,728 | RSA-2048/PSS | AES | 0 |

Changing the declared size of 1.8.0 does not help its different signature pass the legacy RSA-1024 code. The builder intentionally does not offer a general-purpose patch option for arbitrary versions.

## Bootloop and reset findings

The motivating report concerned EU X50 v1 units that entered a bootloop after the official ISP-US 2.1.0 update. The vendor's X55 1.2.2 recovery image uploaded, but the bootloop reportedly remained. After the experimental 1.6.7 trial, an owner reported a red LED. A complete boot/reset/setup success has not yet been established.

Several source observations explain why a successfully accepted upload alone is insufficient:

- `nm_upgradeFwupFile`, line 391, erases `runtime_data` only if `isManu` is nonzero (line 403). All seven files have zero. Positive host traces show `config_erase_calls=0`. Incompatible retained data is a hypothesis for the bootloop, not an established cause.
- In extracted stock ISP 2.1.0 and recovery 1.2.2, `/etc/rc.button/reset` exits unless `/tmp/done_boot` exists. It is created by the late startup script. A crash before then can prevent the normal reset handler from acting.
- The stock preinit failsafe hook registration is commented out in those images. The mere presence of OpenWrt-like failsafe files does not establish a working button entry method.
- HTTP recovery's GET `/reset` handler at `httpd.c:330` issues a fixed U-Boot reboot command. It is not a factory-reset/configuration erase endpoint.
- Examined boot logic does not establish an automatic switch to the other OS slot after a kernel hang. Repeated power cycling is not a confirmed fallback method.
- The recovery writer changes an OS slot and boot index, not APPSBL/ART. This statement is limited to that function; stock operating-system behavior after boot was not exhaustively audited.

The ISP image's signed support-list includes X50 `1.0.0` EU (`special_id:45550000`). Its `fdt@mp03.3` DTB matches the recovery image. Therefore the ISP-US filename alone does not establish a region mismatch as the cause.

The support-list checker is hardware dependent. In these host tests the downstream checker stub is not reached (`support_stub_calls=0`); if it is reached, the shim fails closed. The harness does **not** establish full model/region compatibility on real hardware.

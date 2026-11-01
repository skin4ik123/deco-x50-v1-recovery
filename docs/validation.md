# Validation and reproduction

## What was established

| Test in the original loader host harness | Result |
|---|---|
| Original X55 1.2.2 | RSA valid, mock OS write |
| Same image, Cloud/Proud changed | RSA failure; no erase/write |
| Same image, one UBI bit changed | RSA failure; no erase/write |
| Same image, isManu changed | RSA failure; no erase/write |
| Original X50 1.6.7 | Declared-size rejection; no erase/write |
| X50 1.6.7, only declared length changed | RSA valid, full 37,355,520-byte UBI reaches mock write |
| Length-only candidate, one UBI bit changed | RSA failure; no erase/write |
| Original ISP-US 2.1.0 | RSA valid, mock OS write |
| Original X50 1.8.0 | Declared-size rejection |
| X50 1.8.0, declared length changed | RSA failure; no erase/write |
| Four OpenWrt wrappers | RSA failure; no erase/write |

The saved candidate itself was separately executed through the harness. Its log is [candidate_host_harness.log](../evidence/candidate_host_harness.log). [host_harness_results.json](../evidence/host_harness_results.json) and [openwrt_wrap_results.json](../evidence/openwrt_wrap_results.json) contain the original positive/negative traces and summaries.

The packaged tools were checked again before publication: all eight builder tests passed, the HTTPS download reproduced the reference candidate, both signatures verified, the original C source compiled, and the OpenWrt experiment reproduced the recorded results exactly. See [publication_validation.json](../evidence/publication_validation.json).

These tests do not touch hardware. All NAND erase/write and environment operations are inert `MOCK_*` logs. The OS slot size is an assumption. Hardware support checks, real NAND behavior, booting the kernel, factory reset and Internet access are not established by this harness.

## Device recovery report

**2026-11-01: successful recovery confirmed by the device owner** for the reported EU X50 v1.0 bootloop case using the modified stock 1.6.7 image through U-Boot HTTP recovery. The earlier red-LED observation has been superseded by the owner's confirmation of successful recovery. See [hardware_recovery_report.json](../evidence/hardware_recovery_report.json).

This is an owner-reported hardware outcome, separate from the host tests above. It does not establish compatibility with other hardware revisions or bootloaders, or a general recovery success rate.

## Builder checks

Python 3.9+ is sufficient for the builder and its tests:

```sh
python3 -m unittest discover -s tests -v
```

Four fail-closed tests run without firmware. To include four integration tests, set `DECO_STOCK_BIN` to the exact original 1.6.7 BIN extracted from the vendor ZIP:

```sh
DECO_STOCK_BIN=/absolute/path/to/original.bin python3 -m unittest discover -s tests -v
```

These check the expected candidate hash, changed-byte set, source preservation, corrupt-input rejection, already-patched rejection, existing-file/symlink protection, and corruption detection after a CLI round trip. Firmware is not committed to Git.

The `--download` route also checks the official archive's hash and exact member before reading the BIN into memory. It does not extract arbitrary paths from ZIPs.

## Independent signature inspection

The optional inspector requires `cryptography`; it is not needed by the builder:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-analysis.txt
python3 tools/analyze_deco_firmware.py /path/to/original.bin --mutation-controls
python3 tools/analyze_deco_firmware.py artifacts/Deco_X50_V1_1.6.7_legacy_HTTP_recovery_EXPERIMENTAL.bin
```

The original and candidate should both show `signature_valid: true`; changing the payload or Cloud/Proud should show false. `--extract DIRECTORY` writes verified UBI/volumes locally. It is an offline analysis tool; no router connection or flash command is implemented.

## Original C loader harness

On Linux, install a C compiler, make and OpenSSL development headers using your normal OS package manager. Then:

```sh
make -C host_harness
host_harness/check_recovery /path/to/original-1.6.7.bin
host_harness/check_recovery /path/to/original-1.6.7.bin --clamp
host_harness/check_recovery /path/to/original-1.6.7.bin --clamp --flip
host_harness/check_recovery artifacts/Deco_X50_V1_1.6.7_legacy_HTTP_recovery_EXPERIMENTAL.bin
```

Expected exit codes: 2, 0, 2, 0. The successful trace must include `HARNESS_RSA_VALID=1`, `written_bytes=37355520`, and `config_erase_calls=0`. `--clamp` changes only the in-memory external length; `--flip` corrupts one in-memory UBI byte. Additional negative controls are `--proud` and `--manu`.

The harness compiles the byte-identical vendor `nm_fwup.c`. Compatibility headers and `driver.c` supply host types, OpenSSL verification, mock partition metadata and logging stubs. Hardware-dependent support-list validation is not emulated; the checker stub rejects if reached.

Original analysis environment: Python 3.12.14, cryptography 50.0.2, OpenSSL 3.5.8, Linux. See [verification_environment.txt](../evidence/verification_environment.txt). Broader Python and operating-system compatibility has not been exhaustively tested.

# Deco X50 v1 legacy HTTP recovery

[Русская инструкция](README.ru.md)

Recovery tools and source analysis for an ordinary **TP-Link Deco X50 hardware v1** that still exposes U-Boot HTTP recovery, but will not boot after an update. The image builder reproduces a stock **1.6.7 Build 25031412 Rel. 48241** candidate by changing only an unsigned length field. All signed firmware content is preserved.

**Status, 2026-11-01: successful recovery confirmed by the device owner.** The owner confirmed that recovery with the modified stock 1.6.7 image succeeded in the reported EU X50 v1.0 bootloop case. The image also passes the original published loader code in host tests with inert flash stubs. See the [hardware recovery report](evidence/hardware_recovery_report.json). This result applies to the reported case; compatibility with other hardware or bootloaders is not established.

**Post-recovery progress, 2026-11-01:** on the tested EU v1.0 unit, an owner-authenticated session was used to execute a fixed command as `uid=0(root) gid=0(root)` without UART. The owner also completed and verified backups of **13 critical flash partitions (15.75 MiB)**. The temporary web cache was restored and checked after the probes. **OpenWrt has not been installed by this route.** See the [progress report](docs/progress-2026-11-01.md) and [structured results](evidence/post_recovery_progress.json).

## Scope

- Intended research target: ordinary X50 v1, specifically the EU v1.0 case that motivated this investigation, with the legacy HTTP loader represented in the 2022/2023 GPL sources.
- No compatibility claim for v1.2, v1.3, v2, v3, PoE, Outdoor, 4G/5G, or other models. The signed support list includes X50 `1.0.0` EU; that is not a substitute for checking the installed hardware and bootloader.
- Intended entry point: an already working U-Boot recovery page at `http://192.168.0.1`. Do not use this candidate as a normal app/web updater image.
- It does not bypass RSA verification or install OpenWrt. The payload remains genuine TP-Link stock firmware.
- The examined loader writes an OS slot and boot index. This image has `isManu=0`, so that loader does not clear `runtime_data`.

At the time of the recovery experiment, the installed bootloader had not been compared with the published source. Later owner-run diagnostics confirmed two 42 MiB OS partitions, and the bootloader partition was included in the owner's private critical backup. Its implementation has not been independently compared byte for byte with the source used in the harness. Another loader could handle the altered length differently. Flashing can leave the device unusable; use this only if you accept that experimental scope.

## Download the ready-to-upload firmware

The [latest recovery release](https://github.com/skin4ik123/deco-x50-v1-recovery/releases/latest) includes **`Deco_X50_V1_1.6.7_TPLink_HTTP_Recovery.bin`**, its SHA-256 and instructions. Select the BIN under **Assets**. It is byte-identical to the reproducible candidate below and the image in the owner-confirmed recovery case.

Upload through **U-Boot HTTP recovery at `192.168.0.1`**, for the reported **Deco X50 EU V1.0** case. The installed system version is **TP-Link 1.6.7**; the project release number identifies the recovery package.

## Build the exact candidate yourself

Download this repository's source ZIP and extract it, or clone it. With Python **3.9+**, run from the repository folder:

```sh
python3 tools/make_recovery.py --download
```

On Windows, use `py -3` in place of `python3`. The builder uses only Python's standard library, downloads the exact official ZIP over HTTPS, verifies both ZIP and BIN SHA-256, then creates:

```text
artifacts/Deco_X50_V1_1.6.7_legacy_HTTP_recovery_EXPERIMENTAL.bin
```

If automatic download is unavailable, download the [official 1.6.7 ZIP](https://static.tp-link.com/upload/firmware/2025/202506/20250604/X50v1_1.6.7%20Build%2025031412%20Rel.%2048241.zip) yourself:

```sh
python3 tools/make_recovery.py --input "/path/to/official.zip"
```

The exact original BIN is also accepted. Other files, altered inputs and already patched inputs are rejected. Existing output files are never overwritten. The tool never connects to a router or flashes anything.

| Check | Value |
|---|---|
| Actual candidate size | 37,363,379 bytes; not truncated |
| Original BIN SHA-256 | `9d7c13c9570531d25fb00cf682ef19f2e6fe5a8509f690d26bfa0a00eae977bc` |
| Candidate SHA-256 | `0dd441b4dab6027591f0b1d13b4c63d7c820f5580473847a23730140e1e96370` |
| Original declared size | 37,363,379 |
| Candidate declared size | 33,560,596 (`0x02001814`) |
| Changed byte offsets, zero based | 1, 2, 3; every byte from offset 4 is identical |

Check an existing candidate without generating another one:

```sh
python3 tools/make_recovery.py --check artifacts/Deco_X50_V1_1.6.7_legacy_HTTP_recovery_EXPERIMENTAL.bin
```

## Recovery procedure

Start with [TP-Link's official recovery instructions](https://www.tp-link.com/ca/support/faq/2958/). TP-Link specifies the X55 v1 1.2.2 recovery image first for X50/X55 v1. This project investigates the case where that image uploads but bootloop persists.

For the experimental candidate, use the same HTTP recovery entry procedure: connect one unit directly by Ethernet, set the PC to `192.168.0.2/24`, hold Reset while powering on, then open `http://192.168.0.1`. Upload the generated BIN and wait for the page to report completion. Do not interrupt a write. Reboot afterward if required by the recovery procedure.

If stock firmware starts, a normal factory reset erases settings: press Reset for one second and release, then wait about two minutes. [The X50 guide](https://www.tp-link.com/uk/document/27326/?app=wifi-toolkit) describes pulsing blue as ready for setup and solid green as connected. A red LED requires further checking. Restore the PC's usual DHCP settings afterward.

If recovery rejects the image or the unit continues cycling, record the exact message. The owner-confirmed success in the reported case does not guarantee recovery of every device. This project has no established automatic configuration erase or power-cycle fallback method.

## Why it can help

In the examined loader, the size check uses the first four bytes, while RSA verification covers the actual upload from offset `0x14` to its real end. The system write length comes from the signed upgrade table. Consequently, this one length-field edit lets stock 1.6.7 pass the old 32 MiB payload limit without changing the signature or system image.

The 1.6.7 UBI is 37,355,520 bytes and fits the 42 MiB OS slot used in the harness; later device diagnostics confirmed that slot size on the tested unit. Whether another stock firmware can boot with retained data is a device-level question; it is not established by the host test.

See [the source analysis](docs/research.md), [test results and reproduction](docs/validation.md), and [machine-readable evidence](evidence/).

## OpenWrt

Four locally constructed OpenWrt wrappers were rejected by the original loader's RSA check with zero erase/write calls; the stock length-only control passed. Replacing the payload, changing Cloud/Proud or appending a UBI does not preserve the signature. See [the negative experiment](docs/openwrt.md). Refer to [Oein's X50 v1 port](https://github.com/Oein/Deco-X50-Firmware-Unpack/blob/main/openwrt/README.md) for that separate installation route.

## Contributing results

Issues with exact hardware revision, starting firmware, recovery response and observed boot/reset/setup result are useful. Include the candidate SHA-256. Omit MAC addresses, serial numbers, account information, passwords and configuration backups. Please distinguish an LED observation from a complete recovery.

## License and credits

Project additions are GPL-2.0-or-later; original TP-Link/U-Boot source retains its notices and upstream licensing. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md). The Git tree contains reproduction tools and evidence; ready-to-upload recovery images are published separately as release assets. Vendor firmware is not relicensed under the project's license. This is an independent project, not an official TP-Link release.

# Attribution and licensing

Project tools and documentation were prepared from a recovery investigation with the device owner and assistance from ChatGPT/Codex. Project additions are available under GPL-2.0-or-later. No claim is made to vendor firmware ownership or an official vendor endorsement.

## TP-Link / U-Boot

The following files in `host_harness/` are unmodified copies from the official TP-Link X55 GPL archive:

- `nm_fwup.c`
- `nm_fwup.h`
- `nm_lib.h`
- `nm_api.h`
- `sysProductInfo.h`

Their original copyright and authorship notices are preserved, including Shenzhen TP-LINK Technologies Co. Ltd. and Meng Qing. Upstream U-Boot is copyrighted by Wolfgang Denk and its other contributors. The original licensing explanation is preserved as `host_harness/UPSTREAM-LICENSE-README`; the GNU GPL version 2 text is included in `LICENSE` and `host_harness/GPL-2.0.txt`. Original files retain their upstream terms; this project does not expand their licensing grants.

Source: [TP-Link GPL archive, 2022-06-02](https://static.tp-link.com/upload/gpl-code/2022/202206/20220602/GPL_X55.tar.gz). Matching upgrade and HTTP source was also checked in the [2023-02-23 archive](https://static.tp-link.com/upload/gpl-code/2023/202302/20230223/GPL_x55.tar.gz). Exact archive and source hashes are in `evidence/source_manifest.json`.

`driver.c`, `common.h`, the small host compatibility headers and the Makefile are analysis additions under GPL-2.0-or-later. They substitute inert logs for flash/environment operations and use the installed OpenSSL library for verification. OpenSSL is a separate system dependency and is not bundled here.

## Prior research and documentation

- [Oein/Deco-X50-Firmware-Unpack](https://github.com/Oein/Deco-X50-Firmware-Unpack), including its X50 v1 OpenWrt work, documentation and release assets. The exact OpenWrt asset is attributed in `docs/openwrt.md`; no OpenWrt binary is bundled.
- [sidhantgoel/tplink_decrypt](https://github.com/sidhantgoel/tplink_decrypt) documents the vendor RSA/AES container format and published public keys used in the independent inspector. These are public verification keys, not private signing keys.
- [kuncy7/openwrt-ax55-v1](https://github.com/kuncy7/openwrt-ax55-v1/blob/master/FINDINGS.md), related AX55 research consulted as background. X50 conclusions here were checked against its own official source and firmware files.
- [TP-Link recovery FAQ](https://www.tp-link.com/ca/support/faq/2958/) and [X50 setup guide](https://www.tp-link.com/uk/document/27326/?app=wifi-toolkit) for the normal recovery entry and LED/reset reference.

The builder downloads firmware directly from TP-Link and verifies the recorded archive and BIN hashes. The Git tree contains reproduction tools and evidence. At the device owner's request, ready-to-upload recovery BINs are also distributed as separate GitHub release assets. The stock firmware's copyright and licensing remain with its respective owners; the project's GPL license does not relicense vendor firmware. Release assets identify the exact stock base and checksum.

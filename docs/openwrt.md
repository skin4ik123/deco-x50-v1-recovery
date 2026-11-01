# Why the stock candidate does not install OpenWrt

The length field is outside the signed region. The UBI payload and upgrade table are inside it. Preserving an official signature while replacing the operating system does not work in the examined loader.

A real X50 v1 OpenWrt UBI from [Oein's prerelease `deco-x50-v1-r37324.2`](https://github.com/Oein/Deco-X50-Firmware-Unpack/releases/tag/deco-x50-v1-r37324.2) was used for local negative tests. Asset: `openwrt-qualcommax-ipq50xx-tplink_deco-x50-v1-squashfs-factory.ubi`; 14,155,776 bytes; SHA-256 `82b8dd525b40a7974c58b563a4f98cd7d405548b0df6bfdbeb21c48b27da5c52`. The factory UBI and kernel FIT target were inspected before the experiment.

| Constructed local input | RSA | Host loader |
|---|---|---|
| Stock 1.6.7 with length change only, control | Valid | Reaches mock write |
| Compact OpenWrt replacement; metadata and outer MD5 updated | Invalid | Rejects before erase/write |
| Same replacement with Cloud/Proud change | Invalid | Rejects before erase/write |
| OpenWrt padded to stock UBI size; declared length changed | Invalid | Rejects before erase/write |
| Original stock prefix plus appended OpenWrt UBI | Invalid | Rejects before erase/write |

All four changed containers passed the local table-format parser but failed cryptographic verification. Results and generated input hashes are in [openwrt_wrap_results.json](../evidence/openwrt_wrap_results.json). No such wrapper was flashed to a physical router. Invalid test inputs are not distributed as firmware.

To reproduce the negative experiment, obtain that exact OpenWrt asset, the exact original stock 1.6.7 BIN and the optional Python dependencies. Build the host harness, then run:

```sh
python3 tools/test_openwrt_wrappers.py --stock /path/to/original-1.6.7.bin --openwrt /path/to/factory.ubi
```

It writes local negative test inputs and logs under `artifacts/openwrt-negative-tests/`, then runs only the inert host harness. These inputs are for verification, not installation.

The tested limitation is specific: these wrappers do not pass this published HTTP recovery loader. It is not proof that every possible installation approach is impossible. [Oein's port documentation](https://github.com/Oein/Deco-X50-Firmware-Unpack/blob/main/openwrt/README.md) describes its separate installation route; this project does not add a verified no-UART OpenWrt method.

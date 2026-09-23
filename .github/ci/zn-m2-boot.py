#!/usr/bin/env python3
"""Build ZN M2 and NN6000 v2 without WiFi.

Both kernels stay on the default gzip FitImage. This script does not change
compression, flash size, or RAM size.
"""

import re
import sys
from pathlib import Path

WIFI_PACKAGES = (
    "kmod-ath11k-ahb",
    "kmod-ath11k",
    "ath11k-firmware-ipq6018",
    "wpad-openssl",
)

ROOT = Path(__file__).resolve().parents[2]


def strip_wifi_defaults(path: Path) -> None:
    text = path.read_text()
    pattern = r"(?<![\w-])(?:%s)(?![\w-])" % "|".join(map(re.escape, WIFI_PACKAGES))
    updated = re.sub(pattern, "", text)
    if updated == text:
        sys.exit(f"no WiFi defaults found in {path}")
    if "nss-firmware-ipq6018" not in updated and "nss-firmware-ipq6018" in text:
        sys.exit(f"refusing to drop NSS firmware from {path}")
    path.write_text(updated)


def drop_zn_m2_wifi(path: Path) -> None:
    text = path.read_text()
    matches = list(re.finditer(r"(?ms)^define Device/zn_m2\n.*?^endef$", text))
    if len(matches) != 1:
        sys.exit(f"expected one Device/zn_m2 block, found {len(matches)}")
    block = matches[0].group()
    if "\t$(call Device/FitImage)\n" not in block or "FitImageLzma" in block:
        sys.exit("ZN M2 kernel is not the default gzip FIT")
    if "\t$(call Device/UbiFit)\n" not in block:
        sys.exit("ZN M2 lost its UBI layout")
    if "DEVICE_PACKAGES" in block:
        sys.exit("ZN M2 already sets DEVICE_PACKAGES; review the removal list")
    removal = (
        "\tDEVICE_PACKAGES := -kmod-ath11k-ahb -ath11k-firmware-ipq6018 \\\n"
        "\t\t-wpad-openssl -ipq-wifi-zn_m2\n"
    )
    block = block[: -len("endef")] + removal + "endef"
    path.write_text(text[: matches[0].start()] + block + text[matches[0].end() :])


def drop_nn6000_wifi(path: Path) -> None:
    text = path.read_text()
    old = "\tDEVICE_PACKAGES := ipq-wifi-link_nn6000 kmod-fs-f2fs f2fs-tools\n"
    new = (
        "\tDEVICE_PACKAGES := kmod-fs-f2fs f2fs-tools \\\n"
        "\t\t-kmod-ath11k-ahb -ath11k-firmware-ipq6018 -wpad-openssl \\\n"
        "\t\t-ipq-wifi-link_nn6000\n"
    )
    if text.count(old) != 1:
        sys.exit("unexpected NN6000 DEVICE_PACKAGES line")
    block = re.search(r"(?ms)^define Device/link_nn6000-v1\n.*?^endef$", text)
    if not block or "\t$(call Device/FitImage)\n" not in block.group() or "FitImageLzma" in block.group():
        sys.exit("NN6000 kernel is not the default gzip FIT")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    qualcommax = ROOT / "target/linux/qualcommax"
    if not (qualcommax / "image/Makefile").is_file():
        sys.exit(f"LEDE tree not found at {ROOT}")
    strip_wifi_defaults(qualcommax / "Makefile")
    strip_wifi_defaults(qualcommax / "ipq60xx/target.mk")
    drop_zn_m2_wifi(qualcommax / "image/ipq60xx.mk")
    drop_nn6000_wifi(qualcommax / "image/ipq60xx.mk")
    print("ZN M2 and NN6000 v2: WiFi packages removed, kernel FIT stays gzip")


if __name__ == "__main__":
    main()

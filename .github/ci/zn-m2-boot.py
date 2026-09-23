#!/usr/bin/env python3
"""Drop ZN M2 WiFi packages and compress its FIT with LZMA.

This script does not set flash or RAM size. The board has 128MB NAND;
the partition size is read from SMEM. RAM size is filled in by U-Boot.
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


def switch_zn_m2_to_lzma(path: Path) -> None:
    text = path.read_text()
    matches = list(re.finditer(r"(?ms)^define Device/zn_m2\n.*?^endef$", text))
    if len(matches) != 1:
        sys.exit(f"expected one Device/zn_m2 block, found {len(matches)}")
    block = matches[0].group()
    gzip = "\t$(call Device/FitImage)\n"
    lzma = "\t$(call Device/FitImageLzma)\n"
    ubi = "\t$(call Device/UbiFit)\n"
    if gzip not in block or ubi not in block:
        sys.exit("ZN M2 no longer uses LEDE's FitImage + UbiFit NAND layout")
    if lzma not in block:
        block = block.replace(gzip, lzma, 1)
    removal = (
        "\tDEVICE_PACKAGES := -kmod-ath11k-ahb -ath11k-firmware-ipq6018 \\\n"
        "\t\t-wpad-openssl -ipq-wifi-zn_m2\n"
    )
    if "DEVICE_PACKAGES" in block:
        sys.exit("ZN M2 already sets DEVICE_PACKAGES; review the removal list")
    block = block[: -len("endef")] + removal + "endef"
    path.write_text(text[: matches[0].start()] + block + text[matches[0].end() :])


def main() -> None:
    qualcommax = ROOT / "target/linux/qualcommax"
    if not (qualcommax / "image/Makefile").is_file():
        sys.exit(f"LEDE tree not found at {ROOT}")
    if "define Device/FitImageLzma\n" not in (qualcommax / "image/Makefile").read_text():
        sys.exit("this LEDE tree has no FitImageLzma recipe")
    strip_wifi_defaults(qualcommax / "Makefile")
    strip_wifi_defaults(qualcommax / "ipq60xx/target.mk")
    switch_zn_m2_to_lzma(qualcommax / "image/ipq60xx.mk")
    print("ZN M2: WiFi defaults removed, FIT is LZMA")


if __name__ == "__main__":
    main()

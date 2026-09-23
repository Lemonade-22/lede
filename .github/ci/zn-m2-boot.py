#!/usr/bin/env python3
"""Make LEDE's ZN M2 image boot on the 256MB NAND unit.

OpenWRT-CI_Self does this in Scripts/ZN-M2-WIFI-NO.py against VIKINGYFY's
tree (Device/nand-common plus ipq6018-nowifi.dtsi). LEDE inlines
FitImage+UbiFit and reserves 40MiB for Q6 in ipq6018-256m.dtsi, so the same
result has to be applied to those files instead of copied verbatim.
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


def shrink_q6(path: Path) -> None:
    text = path.read_text()
    old = "\treg = <0x0 0x4ab00000 0x0 0x2800000>;"
    new = "\treg = <0x0 0x4ab00000 0x0 0x1000000>;"
    if text.count(old) != 1:
        sys.exit("unexpected Q6 reservation in ipq6018-256m.dtsi")
    path.write_text(text.replace(old, new, 1))


def main() -> None:
    qualcommax = ROOT / "target/linux/qualcommax"
    if not (qualcommax / "image/Makefile").is_file():
        sys.exit(f"LEDE tree not found at {ROOT}")
    if "define Device/FitImageLzma\n" not in (qualcommax / "image/Makefile").read_text():
        sys.exit("this LEDE tree has no FitImageLzma recipe")
    strip_wifi_defaults(qualcommax / "Makefile")
    strip_wifi_defaults(qualcommax / "ipq60xx/target.mk")
    switch_zn_m2_to_lzma(qualcommax / "image/ipq60xx.mk")
    shrink_q6(qualcommax / "files/arch/arm64/boot/dts/qcom/ipq6018-256m.dtsi")
    print("ZN M2: WiFi defaults removed, Q6 reservation is 16MiB, FIT is LZMA")


if __name__ == "__main__":
    main()

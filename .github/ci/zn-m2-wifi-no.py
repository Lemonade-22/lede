#!/usr/bin/env python3
"""ZN-M2 WIFI-NO build customization; run only from its dedicated workflow."""
import json
import re
import sys
from pathlib import Path

def wireless(name):
    return bool(re.match(
        r"^(?:kmod-(?:ath|cfg80211|mac80211|rfkill|mt76|mt79|rt2|rtw|rtl8|rtl9|brcm|b43|lib80211|wl(?:-|$))"
        r"|(?:ath|mt76|mt79|rtl8|rtl9|brcm).*firmware"
        r"|ipq-wifi-|wpad(?:-|$)|hostapd(?:-|$)|wpa-(?:supplicant|cli)"
        r"|iw(?:-|$)|iwinfo$|libiwinfo(?:[0-9]|-|$)|rpcd-mod-iwinfo$"
        r"|wireless-(?:regdb|tools)|wifi-scripts$|ucode-mod-nl80211$"
        r"|wifischedule$|usteer$|dawn$|relayd$|luci-proto-relay$|aircrack|airmon|horst$|wavemon$"
        r"|luci-(?:app|i18n)-(?:wifi|wlan|wireless|wifischedule|wifihistory|wifidog|repeater|travelmate|usteer|dawn))", name))

def prepare():
    for name in ("Makefile", "ipq60xx/target.mk"):
        path = Path("target/linux/qualcommax") / name
        text = path.read_text()
        text = re.sub(r"(?<![\w-])(?:kmod-ath11k-ahb|wpad-openssl|ath11k-firmware-ipq6018)(?![\w-])", "", text)
        path.write_text(text)
    # Retain LuCI's wired pages; remove their optional iwinfo runtime dependencies.
    for name in ("luci-mod-network", "luci-mod-status"):
        path = Path("feeds/luci/modules") / name / "Makefile"
        text = path.read_text()
        text = re.sub(r"\+(?:libiwinfo|rpcd-mod-iwinfo)(?![\w-])", "", text)
        path.write_text(text)
    modules = Path("feeds/luci/modules")
    removed = []
    for path in modules.glob("*/root/usr/share/luci/menu.d/*.json"):
        data = json.loads(path.read_text())
        keys = [key for key, value in data.items()
                if "wireless" in key or "wireless" in value.get("action", {}).get("path", "")]
        for key in keys:
            del data[key]
            removed.append(key)
        if keys:
            path.write_text(json.dumps(data, indent=2) + "\n")
    for relative in (
        "luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js",
        "luci-mod-network/root/usr/share/ucitrack/luci-mod-network-wireless.json",
        "luci-mod-status/htdocs/luci-static/resources/view/status/wireless.js",
        "luci-mod-status/htdocs/luci-static/resources/view/status/include/60_wifi.js",
        "luci-mod-dashboard/htdocs/luci-static/resources/view/dashboard/include/30_wifi.js",
    ):
        path = modules / relative
        if path.exists():
            path.unlink()
            removed.append(relative)
    if not removed:
        raise SystemExit("No wireless LuCI pages found; review the feed layout")
    # LEDE enables WiFi in the shared ipq6018-cmiot.dtsi. Override this board only.
    path = Path("target/linux/qualcommax/files/arch/arm64/boot/dts/qcom/ipq6018-m2.dts")
    text = path.read_text()
    updated, count = re.subn(
        r'(&wifi\s*\{\s*)status = "okay";',
        r'\1status = "disabled";',
        text,
        count=1,
    )
    if count == 0:
        updated, count = re.subn(
            r'(&wifi\s*\{)',
            r'\1\n\tstatus = "disabled";',
            text,
            count=1,
        )
    if count != 1:
        raise SystemExit("Expected one ZN-M2 WiFi node")
    path.write_text(updated)
    print("Removed wireless UI entries:", *removed, sep="\n")

def configure():
    # Use actual package metadata, including feed packages; do not invent symbols.
    # Feeds may embed GBK in descriptions; only package names are consumed.
    packages = re.findall(
        r"^Package: (.+)$",
        Path("tmp/.packageinfo").read_text(encoding="utf-8", errors="replace"),
        re.M,
    )
    blocked = sorted(name for name in packages if wireless(name))
    if not {"kmod-ath11k-ahb", "wpad-openssl", "ath11k-firmware-ipq6018"} <= set(blocked):
        raise SystemExit("Expected wireless packages missing from package metadata")
    path = Path(".config")
    text = re.sub(r"^(?:CONFIG_PACKAGE_([^=]+)=[ymn]|# CONFIG_PACKAGE_(.+) is not set)\n",
                  lambda m: "" if wireless(m[1] or m[2]) else m[0], path.read_text(), flags=re.M)
    path.write_text(text + "\n" + "".join(f"# CONFIG_PACKAGE_{name} is not set\n" for name in blocked))
    Path("artifact/buildinfo/wifi-no-packages.txt").write_text("\n".join(blocked) + "\n")

def verify(manifest=False):
    if manifest:
        paths = list(Path("bin/targets/qualcommax/ipq60xx").glob("*zn_m2*.manifest"))
        if not paths:
            raise SystemExit("ZN-M2 package manifest missing")
        names = {line.split()[0] for path in paths for line in path.read_text().splitlines() if line.strip()}
    else:
        names = set(re.findall(r"^CONFIG_PACKAGE_(.+)=[ym]$", Path(".config").read_text(), re.M))
    bad = sorted(name for name in names if wireless(name))
    if bad:
        raise SystemExit("Wireless packages remain: " + ", ".join(bad))
    required = {"kmod-qca-nss-dp", "kmod-qca-nss-drv", "nss-firmware-ipq6018", "luci-mod-network"}
    if not required <= names:
        raise SystemExit("Required wired packages missing: " + ", ".join(sorted(required - names)))
    print("WIFI-NO verified: no wireless packages; wired NSS and LuCI retained")

if __name__ == "__main__":
    {"prepare": prepare, "configure": configure, "verify": verify,
     "manifest": lambda: verify(True)}[sys.argv[1]]()

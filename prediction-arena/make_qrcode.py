"""Generate the on-site QR code from the notebook's CURRENT LAN IP.

Run this AFTER connecting to the venue Wi-Fi / starting the hotspot, because
the IP changes with the network. Output: qrcode.png next to this script.
"""
from __future__ import annotations

import socket
from pathlib import Path

import segno

ROOT = Path(__file__).resolve().parent
PORT = 5000


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ip = lan_ip()
    url = f"http://{ip}:{PORT}/"
    out = ROOT / "qrcode.png"
    segno.make(url, error="m").save(
        out, scale=10, border=3, dark="#0f1420", light="#ffffff"
    )
    print("=" * 60)
    print(f"  QR code -> {out}")
    print(f"  URL     -> {url}")
    print(f"  Board   -> http://{ip}:{PORT}/dashboard")
    print("  Print the PNG or show it on screen; phones scan to join.")
    print("  If the venue Wi-Fi isolates clients, use a hotspot instead.")
    print("=" * 60)


if __name__ == "__main__":
    main()

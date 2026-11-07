"""Generate the on-site QR code for the local H5 game.

The QR encodes ONLY the entry URL. Changing the code or the question bank does
NOT change the QR; only a changed IP / port / path requires regeneration.

Outputs (next to this script, prefix set by --name):
  <name>.png                 screen / projector use (small)
  <name>_print_300dpi.png    300 dpi, 8.5 x 8.5 cm print master (--print)
  <name>_A4_print.png        A4 @ 300 dpi sheet with the QR at exact 8.5 cm (--print)

The print master is exactly 1004 x 1004 px = 8.5 cm x 8.5 cm at 300 dpi
(8.5 / 2.54 * 300 = 1003.94), with a >= 4-module quiet zone, pure black on
white, and integer-pixel modules so the printed code stays crisp.

Examples:
  python make_qrcode.py --print
      -> current LAN IP (re-run after changing Wi-Fi)
  python make_qrcode.py --print --url http://192.168.137.1:5000/ --name qrcode_hotspot
      -> stable Windows Mobile Hotspot IP, print once and reuse forever
"""
from __future__ import annotations

import argparse
import io
import socket
from pathlib import Path
from urllib.parse import urlparse

import segno
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PORT = 5000

DPI = 300
SIZE_CM = 8.5
SIZE_PX = round(SIZE_CM / 2.54 * DPI)  # 1004 px
BORDER = 4  # QR spec minimum quiet zone, in modules

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _centered(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill, width: int):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


def make_screen(url: str, stem: str) -> Path:
    out = ROOT / f"{stem}.png"
    segno.make(url, error="q").save(
        out, scale=10, border=BORDER, dark="#000000", light="#ffffff"
    )
    return out


def make_print_master(url: str, stem: str):
    """Return (path, modules, total_modules, pixel_scale)."""
    qr = segno.make(url, error="h")
    modules = len(qr.matrix)                 # rows, without quiet zone
    total = modules + 2 * BORDER
    scale = max(1, SIZE_PX // total)         # integer px per module

    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=BORDER,
            dark="#000000", light="#ffffff")
    buf.seek(0)
    tile = Image.open(buf).convert("RGB")

    canvas = Image.new("RGB", (SIZE_PX, SIZE_PX), "white")
    offset = (SIZE_PX - tile.width) // 2    # extra white margin, still >= 4 modules
    canvas.paste(tile, (offset, offset))

    out = ROOT / f"{stem}_print_300dpi.png"
    canvas.save(out, dpi=(DPI, DPI))
    return out, modules, total, scale


def make_a4_sheet(url: str, master_path: Path, stem: str, hint: str) -> Path:
    w = round(21.0 / 2.54 * DPI)     # 2480
    h = round(29.7 / 2.54 * DPI)     # 3508
    sheet = Image.new("RGB", (w, h), "white")
    master = Image.open(master_path).convert("RGB")

    y = round(3.0 / 2.54 * DPI)      # 3 cm from top
    sheet.paste(master, ((w - SIZE_PX) // 2, y))

    draw = ImageDraw.Draw(sheet)
    cursor = y + SIZE_PX + round(1.4 / 2.54 * DPI)
    _centered(draw, cursor, "扫码参与 · 概率预测互动", _font(96), (17, 24, 39), w)
    cursor += round(1.9 / 2.54 * DPI)
    _centered(draw, cursor, hint, _font(58), (75, 85, 99), w)
    cursor += round(1.5 / 2.54 * DPI)
    _centered(draw, cursor, "若打不开，请用手机浏览器输入下方网址", _font(46), (110, 118, 130), w)
    cursor += round(1.4 / 2.54 * DPI)
    _centered(draw, cursor, url, _font(52), (17, 24, 39), w)

    out = ROOT / f"{stem}_A4_print.png"
    sheet.save(out, dpi=(DPI, DPI))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true",
                    help="also write the 300 dpi 8.5 cm print master and A4 sheet")
    ap.add_argument("--url", default=None,
                    help="override the encoded URL (e.g. a fixed hotspot or public IP)")
    ap.add_argument("--name", default="qrcode",
                    help="output filename prefix, so different URLs do not overwrite")
    ap.add_argument("--hint", default="请连接与现场笔记本相同的 WiFi",
                    help="second line of text on the A4 sheet")
    args = ap.parse_args()

    ip = lan_ip()
    url = args.url or f"http://{ip}:{PORT}/"
    parts = urlparse(url)
    board = f"{parts.scheme}://{parts.netloc}/dashboard"

    screen = make_screen(url, args.name)
    print("=" * 66)
    print(f"  URL      -> {url}")
    print(f"  Screen   -> {screen.name}")
    print(f"  Board    -> {board}")

    if args.print:
        master, modules, total, scale = make_print_master(url, args.name)
        a4 = make_a4_sheet(url, master, args.name, args.hint)
        print(f"  Print    -> {master.name}  ({SIZE_PX} x {SIZE_PX} px @ {DPI} dpi"
              f" = {SIZE_CM} x {SIZE_CM} cm)")
        print(f"             QR {modules} modules, quiet zone {BORDER}, "
              f"{scale} px/module (integer, crisp)")
        print(f"  A4 sheet -> {a4.name}  (A4 @ {DPI} dpi, QR at exact {SIZE_CM} cm)")

    print("  NOTE: the QR encodes the URL only. Code / question-bank changes do")
    print("        NOT affect it; regenerate only when IP, port or path changes.")
    print("=" * 66)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор обложки и иконки ядра PocketVGM (пиксель-арт «звуковые чипы»).

Формат картинок Analogue Pocket (выяснен по стоковым файлам):
16 бит на пиксель little-endian, используется только младший байт (серый
0-255, 0 = чёрный/прозрачный фон), буфер хранит картинку, повёрнутую на 90°
по часовой стрелке (т.е. encode: display.transpose(ROTATE_90) построчно).

Пишет: Platforms/_images/pocketvgm.bin (521x165) и Cores/<ядро>/icon.bin
(36x36) + PNG-превью рядом (в git не кладутся).
"""

import os
import re
import struct
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "core", "pkg", "pocket")
CORE_DIR = "M4chanic.PocketVGM"
FONT_RS = os.path.join(ROOT, "core", "lang", "rust", "examples", "player", "src", "font.rs")

BRIGHT, MID, DIM, BODY = 230, 140, 70, 40


def load_font():
    """FONT8X8 из font.rs плеера: 96 глифов с ASCII 32, LSB — левый пиксель."""
    text = open(FONT_RS, encoding="utf-8").read()
    rows = re.findall(r"\[((?:0x[0-9A-Fa-f]{2},?\s*){8})\]", text)
    font = [[int(b, 16) for b in re.findall(r"0x[0-9A-Fa-f]{2}", r)] for r in rows]
    assert len(font) == 96, len(font)
    return font


FONT = load_font()


def draw_text(px, x, y, s, color, scale=1):
    for ch in s:
        glyph = FONT[max(0, min(95, ord(ch) - 32))]
        for gy, row in enumerate(glyph):
            for gx in range(8):
                if row >> gx & 1:
                    for sy in range(scale):
                        for sx in range(scale):
                            px[x + gx * scale + sx, y + gy * scale + sy] = color
        x += 8 * scale


def rect(px, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px[x, y] = color


def frame(px, x0, y0, x1, y1, color):
    rect(px, x0, y0, x1, y0, color)
    rect(px, x0, y1, x1, y1, color)
    rect(px, x0, y0, x0, y1, color)
    rect(px, x1, y0, x1, y1, color)


def dip_chip(px, x, y, w, h, label):
    """DIP-корпус сверху: тело с рамкой, ключ-выемка слева, ножки сверху/снизу."""
    for lx in range(x + 6, x + w - 4, 10):  # ножки
        rect(px, lx, y - 4, lx + 2, y - 1, MID)
        rect(px, lx, y + h + 1, lx + 2, y + h + 4, MID)
    rect(px, x, y, x + w, y + h, BODY)
    frame(px, x, y, x + w, y + h, BRIGHT)
    rect(px, x, y + h // 2 - 3, x + 2, y + h // 2 + 3, 0)  # ключ
    frame(px, x, y + h // 2 - 3, x + 2, y + h // 2 + 3, BRIGHT)
    tw = len(label) * 8
    draw_text(px, x + (w - tw) // 2 + 2, y + (h - 7) // 2, label, BRIGHT)


def square_wave(px, x0, x1, ybase, amp, period, color):
    """Меандр толщиной 2px."""
    level = -1
    x = x0
    while x < x1:
        xe = min(x + period // 2, x1)
        y = ybase + amp * level
        rect(px, x, y, xe, y + 1, color)         # полка
        if xe < x1:
            ylo, yhi = sorted((ybase - amp, ybase + amp))
            rect(px, xe, ylo, xe + 1, yhi + 1, color)  # фронт
        level = -level
        x = xe
    # sync: маленький «нотный» акцент не нужен — чистый меандр


def encode(img, path):
    buf = img.transpose(Image.ROTATE_90)
    vals = list(buf.getdata())
    with open(path, "wb") as f:
        f.write(struct.pack("<%dH" % len(vals), *vals))
    print("записан %s (%d байт)" % (path, len(vals) * 2))


def make_platform(preview_dir):
    im = Image.new("L", (521, 165), 0)
    px = im.load()
    draw_text(px, 24, 30, "Pocket", MID, 3)
    draw_text(px, 24 + 6 * 24, 30, "VGM", BRIGHT, 3)
    draw_text(px, 26, 62, "VGM NSF GBS SID MIDI", MID)
    square_wave(px, 24, 285, 120, 16, 28, BRIGHT)
    dip_chip(px, 318, 16, 92, 26, "YM2151")
    dip_chip(px, 352, 68, 92, 26, "2A03")
    dip_chip(px, 318, 120, 92, 26, "SID6581")
    im.save(os.path.join(preview_dir, "platform_preview.png"))
    encode(im, os.path.join(PKG, "Platforms", "_images", "pocketvgm.bin"))


def make_icon(preview_dir):
    im = Image.new("L", (36, 36), 0)
    px = im.load()
    x, y, w, h = 5, 8, 25, 19
    for lx in range(x + 3, x + w - 2, 6):
        rect(px, lx, y - 3, lx + 1, y - 1, MID)
        rect(px, lx, y + h + 1, lx + 1, y + h + 3, MID)
    rect(px, x, y, x + w, y + h, BODY)
    frame(px, x, y, x + w, y + h, BRIGHT)
    rect(px, x, y + h // 2 - 2, x + 1, y + h // 2 + 2, 0)
    draw_text(px, x + 5, y + (h - 7) // 2, "M4", BRIGHT)
    im.save(os.path.join(preview_dir, "icon_preview.png"))
    encode(im, os.path.join(PKG, "Cores", CORE_DIR, "icon.bin"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    make_platform(out)
    make_icon(out)

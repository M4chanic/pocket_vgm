#!/usr/bin/env python3
"""Конвертер VGM (Mega Drive: YM2612 + SN76489) -> GYM с заголовком GYMX.

GYM квантует время кадрами 1/60 с; внутрикадровые задержки VGM теряются.
Файлы с data-блоками (стриминг DAC, команды 0x67/0x80-0x8F) не поддерживаются.

Использование: vgm2gym.py in.vgm out.gym "Название" "Игра" [loop_frame]
"""
import gzip
import sys

FRAME = 735  # сэмплов 44.1 кГц на кадр 60 Гц


def convert(data, title, game, loop_frame=0):
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    assert data[:4] == b'Vgm ', 'не VGM'
    ver = int.from_bytes(data[8:12], 'little')
    if ver >= 0x150:
        off = int.from_bytes(data[0x34:0x38], 'little')
        pos = 0x34 + off if off else 0x40
    else:
        pos = 0x40

    body = bytearray()
    acc = 0

    def wait(n):
        nonlocal acc
        acc += n
        while acc >= FRAME:
            body.append(0x00)
            acc -= FRAME

    while pos < len(data):
        c = data[pos]
        if c == 0x66:
            break
        elif c == 0x52:
            body += bytes([0x01, data[pos + 1], data[pos + 2]])
            pos += 3
        elif c == 0x53:
            body += bytes([0x02, data[pos + 1], data[pos + 2]])
            pos += 3
        elif c == 0x50:
            body += bytes([0x03, data[pos + 1]])
            pos += 2
        elif c == 0x61:
            wait(int.from_bytes(data[pos + 1:pos + 3], 'little'))
            pos += 3
        elif c == 0x62:
            wait(735)
            pos += 1
        elif c == 0x63:
            wait(882)
            pos += 1
        elif 0x70 <= c <= 0x7F:
            wait((c & 0xF) + 1)
            pos += 1
        elif c == 0x4F:      # GG-стерео — в GYM некуда
            pos += 2
        elif c == 0x67 or 0x80 <= c <= 0x8F:
            raise SystemExit('VGM использует data-блоки DAC — GYM так не умеет')
        else:
            raise SystemExit(f'неизвестная команда VGM {c:#04x} @ {pos:#x}')

    def pad32(s):
        b = s.encode('ascii', 'replace')[:31]
        return b + b'\0' * (32 - len(b))

    hdr = bytearray(428)
    hdr[0:4] = b'GYMX'
    hdr[4:36] = pad32(title)
    hdr[36:68] = pad32(game)
    hdr[420:424] = loop_frame.to_bytes(4, 'little')
    hdr[424:428] = (0).to_bytes(4, 'little')   # без сжатия
    return bytes(hdr) + bytes(body)


if __name__ == '__main__':
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    with open(sys.argv[1], 'rb') as f:
        raw = f.read()
    loop = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    out = convert(raw, sys.argv[3], sys.argv[4], loop)
    with open(sys.argv[2], 'wb') as f:
        f.write(out)
    print(f'{sys.argv[2]}: {len(out)} байт')

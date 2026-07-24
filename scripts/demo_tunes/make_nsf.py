#!/usr/bin/env python3
"""Генерация демо-NSF: «Коробейники» (рус. народная, PD), аранжировка своя (CC0).

Плеер: pulse1 — мелодия, треугольник — бас. Поток нот: [dur, lo, hi]*,
dur=0 — зациклиться на начало потока. hi с битом 7 — пауза.
"""
import sys
from asm6502 import Asm, note_hz

CPU = 1789773.0


def pulse_period(hz):
    return round(CPU / (16 * hz)) - 1


def tri_period(hz):
    # треугольник звучит октавой ниже при том же периоде
    return round(CPU / (32 * hz)) - 1


Q, E = 30, 15  # четверть и восьмая в кадрах (60 Гц, 120 BPM)


def stream(notes, period_fn):
    out = bytearray()
    for name, dur in notes:
        assert 0 < dur < 256
        if name is None:
            out += bytes([dur, 0, 0x80])
        else:
            p = period_fn(note_hz(name))
            assert 0 < p < 0x800, f'{name}: период {p:#x}'
            out += bytes([dur, p & 0xFF, p >> 8])
    out.append(0)  # маркер цикла
    return out


# Мелодия (ля минор), две фразы куплета
MELODY = [
    ('E5', Q), ('B4', E), ('C5', E), ('D5', Q), ('C5', E), ('B4', E),
    ('A4', Q), ('A4', E), ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', Q + E), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', Q), (None, Q),
    ('D5', Q + E), ('F5', E), ('A5', Q), ('G5', E), ('F5', E),
    ('E5', Q + E), ('C5', E), ('E5', Q), ('D5', E), ('C5', E),
    ('B4', Q), ('B4', E), ('C5', E), ('D5', Q), ('E5', Q),
    ('C5', Q), ('A4', Q), ('A4', Q), (None, Q),
]

# Бас: корень такта восьмыми «бум-пауза», гармония Am/E/Am/Am | Dm/Am/E/Am
BASS_ROOTS = ['A2', 'E2', 'A2', 'A2', 'D2', 'A2', 'E2', 'A2']
BASS = []
for root in BASS_ROOTS:
    for _ in range(4):  # 4 доли такта
        BASS.append((root, E))
        BASS.append((None, E))

mel_len = sum(d for _, d in MELODY)
bass_len = sum(d for _, d in BASS)
assert mel_len == bass_len, f'мелодия {mel_len} != бас {bass_len} кадров'

a = Asm(0x8000)
# точки входа
a.op('JMP', 'abs', 'init')
a.op('JMP', 'abs', 'play')

a.label('init')
a.op('LDA', 'imm', 0x0F); a.op('STA', 'abs', 0x4015)   # включить каналы
a.op('LDA', 'imm', 0x08); a.op('STA', 'abs', 0x4001)   # свип выключен
a.op('LDA', 'imm', 0xB0); a.op('STA', 'abs', 0x4000)   # pulse1 тихо
a.op('LDA', 'imm', 0x80); a.op('STA', 'abs', 0x4008)   # треугольник заглушен
a.op('LDA', 'imm', 0x30); a.op('STA', 'abs', 0x400C)   # шум тихо
for ptr, lab in ((0x10, 'mel'), (0x14, 'bass')):
    a.op('LDA', 'imm', '<' + lab); a.op('STA', 'zp', ptr)
    a.op('LDA', 'imm', '>' + lab); a.op('STA', 'zp', ptr + 1)
a.op('LDA', 'imm', 1)
a.op('STA', 'zp', 0x12)  # счётчик мелодии
a.op('STA', 'zp', 0x16)  # счётчик баса
a.op('RTS')

a.label('play')
# --- мелодия ---
a.op('DEC', 'zp', 0x12)
a.op('BNE', 'rel', 'do_bass')
a.op('LDY', 'imm', 0)
a.op('LDA', 'indy', 0x10)
a.op('BNE', 'rel', 'm_ok')
a.op('LDA', 'imm', '<mel'); a.op('STA', 'zp', 0x10)
a.op('LDA', 'imm', '>mel'); a.op('STA', 'zp', 0x11)
a.op('LDA', 'indy', 0x10)
a.label('m_ok')
a.op('STA', 'zp', 0x12)
a.op('INY')
a.op('LDA', 'indy', 0x10); a.op('STA', 'abs', 0x4002)
a.op('INY')
a.op('LDA', 'indy', 0x10)
a.op('BMI', 'rel', 'm_rest')
a.op('STA', 'abs', 0x4003)
a.op('LDA', 'imm', 0xBC)   # duty 50%, громкость 12
a.op('STA', 'abs', 0x4000)
a.op('JMP', 'abs', 'm_adv')
a.label('m_rest')
a.op('LDA', 'imm', 0xB0)
a.op('STA', 'abs', 0x4000)
a.label('m_adv')
a.op('CLC')
a.op('LDA', 'zp', 0x10); a.op('ADC', 'imm', 3); a.op('STA', 'zp', 0x10)
a.op('LDA', 'zp', 0x11); a.op('ADC', 'imm', 0); a.op('STA', 'zp', 0x11)
# --- бас ---
a.label('do_bass')
a.op('DEC', 'zp', 0x16)
a.op('BNE', 'rel', 'done')
a.op('LDY', 'imm', 0)
a.op('LDA', 'indy', 0x14)
a.op('BNE', 'rel', 'b_ok')
a.op('LDA', 'imm', '<bass'); a.op('STA', 'zp', 0x14)
a.op('LDA', 'imm', '>bass'); a.op('STA', 'zp', 0x15)
a.op('LDA', 'indy', 0x14)
a.label('b_ok')
a.op('STA', 'zp', 0x16)
a.op('INY')
a.op('LDA', 'indy', 0x14); a.op('STA', 'abs', 0x400A)
a.op('INY')
a.op('LDA', 'indy', 0x14)
a.op('BMI', 'rel', 'b_rest')
a.op('STA', 'abs', 0x400B)
a.op('LDA', 'imm', 0xFF)   # линейный счётчик всегда открыт
a.op('STA', 'abs', 0x4008)
a.op('JMP', 'abs', 'b_adv')
a.label('b_rest')
a.op('LDA', 'imm', 0x80)
a.op('STA', 'abs', 0x4008)
a.label('b_adv')
a.op('CLC')
a.op('LDA', 'zp', 0x14); a.op('ADC', 'imm', 3); a.op('STA', 'zp', 0x14)
a.op('LDA', 'zp', 0x15); a.op('ADC', 'imm', 0); a.op('STA', 'zp', 0x15)
a.label('done')
a.op('RTS')

a.label('mel')
a.data(stream(MELODY, pulse_period))
a.label('bass')
a.data(stream(BASS, tri_period))

code = a.assemble()


def pad32(s):
    b = s.encode('ascii')[:31]
    return b + b'\0' * (32 - len(b))


hdr = bytearray(0x80)
hdr[0:5] = b'NESM\x1a'
hdr[5] = 1                       # версия
hdr[6] = 1                       # песен
hdr[7] = 1                       # стартовая
hdr[0x08:0x0A] = (0x8000).to_bytes(2, 'little')            # load
hdr[0x0A:0x0C] = a.labels['init'].to_bytes(2, 'little')    # init
hdr[0x0C:0x0E] = a.labels['play'].to_bytes(2, 'little')    # play
hdr[0x0E:0x2E] = pad32('Korobeiniki (m4pocket demo)')
hdr[0x2E:0x4E] = pad32('trad. rus., arr. M4chanic')
hdr[0x4E:0x6E] = pad32('CC0 / public domain')
hdr[0x6E:0x70] = (16666).to_bytes(2, 'little')             # NTSC-период

out = sys.argv[1] if len(sys.argv) > 1 else 'korobeiniki.nsf'
with open(out, 'wb') as f:
    f.write(bytes(hdr) + code)
print(f'{out}: {len(code)} байт кода+данных, INIT={a.labels["init"]:#x}, '
      f'PLAY={a.labels["play"]:#x}, мелодия {mel_len} кадров '
      f'({mel_len / 60:.1f} с на цикл)')

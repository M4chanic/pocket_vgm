#!/usr/bin/env python3
"""Генерация демо-GBS: «Ода к радости» (Бетховен, PD), аранжировка своя (CC0).

SM83-плеер: канал 1 (пульс) — мелодия, канал 2 (пульс) — бас.
Поток нот: [dur, lo, hi]*, dur=0 — цикл, hi=0xFF — пауза.
Без HALT и прерываний: PLAY дёргает хост-плеер по тику (TAC=0 → vblank-темп).
"""
import sys
from asm6502 import note_hz

LOAD = 0x0400
RAM = 0xC000        # mel_ptr lo/hi, mel_cnt, bass_ptr lo/hi, bass_cnt


def gb_freq(hz):
    x = 2048 - round(131072 / hz)
    assert 0 <= x < 2048
    return x


Q, E = 30, 15
QD, H = Q + E, 60


def stream(notes):
    out = bytearray()
    for name, dur in notes:
        assert 0 < dur < 256
        if name is None:
            out += bytes([dur, 0, 0xFF])
        else:
            x = gb_freq(note_hz(name))
            out += bytes([dur, x & 0xFF, x >> 8])
    out.append(0)
    return out


MELODY = [
    ('E5', Q), ('E5', Q), ('F5', Q), ('G5', Q),
    ('G5', Q), ('F5', Q), ('E5', Q), ('D5', Q),
    ('C5', Q), ('C5', Q), ('D5', Q), ('E5', Q),
    ('E5', QD), ('D5', E), ('D5', H),
    ('E5', Q), ('E5', Q), ('F5', Q), ('G5', Q),
    ('G5', Q), ('F5', Q), ('E5', Q), ('D5', Q),
    ('C5', Q), ('C5', Q), ('D5', Q), ('E5', Q),
    ('D5', QD), ('C5', E), ('C5', H),
]

BASS_BARS = [
    ['C3', 'G3', 'C3', 'G3'], ['G2', 'G3', 'G2', 'G3'],
    ['C3', 'G3', 'C3', 'G3'], ['G2', 'G3', 'C3', 'C4'],
    ['C3', 'G3', 'C3', 'G3'], ['G2', 'G3', 'G2', 'G3'],
    ['C3', 'G3', 'C3', 'G3'], ['G2', 'G3', 'C3', 'C4'],
]
BASS = [(n, Q) for bar in BASS_BARS for n in bar]

mel_len = sum(d for _, d in MELODY)
bass_len = sum(d for _, d in BASS)
assert mel_len == bass_len, f'мелодия {mel_len} != бас {bass_len}'

# --- мини-ассемблер SM83 (двухпроходный) ---
items = []          # (тип, аргументы)
labels = {}


def emit(*b):
    items.append(('b', b))


def label(name):
    items.append(('l', name))


def jr_nz(target):
    items.append(('jrnz', target))


def a16(target):    # два байта адреса метки (после первого прохода)
    items.append(('a16', target))


def size(it):
    return {'b': len(it[1]), 'l': 0, 'jrnz': 2, 'a16': 2}[it[0]]


def assemble():
    pc = LOAD
    for it in items:
        if it[0] == 'l':
            labels[it[1]] = pc
        else:
            pc += size(it)
    out = bytearray()
    pc = LOAD
    for it in items:
        if it[0] == 'l':
            continue
        if it[0] == 'b':
            out += bytes(v & 0xFF for v in it[1])
        elif it[0] == 'jrnz':
            off = labels[it[1]] - (pc + 2)
            assert -128 <= off <= 127
            out += bytes([0x20, off & 0xFF])
        elif it[0] == 'a16':
            out += labels[it[1]].to_bytes(2, 'little')
        pc += size(it)
    return out


def track(base, ptr, cnt, stream_lab, env, skip_lab):
    """Шаг одного трека: base — LDH-смещение NRx1 ($FF00+base+1 и т.д.)."""
    emit(0xFA, cnt & 0xFF, cnt >> 8)        # LD A,(cnt)
    emit(0x3D)                              # DEC A
    emit(0xEA, cnt & 0xFF, cnt >> 8)        # LD (cnt),A
    jr_nz(skip_lab)
    emit(0xFA, ptr & 0xFF, ptr >> 8)        # LD A,(ptr)
    emit(0x6F)                              # LD L,A
    emit(0xFA, (ptr + 1) & 0xFF, (ptr + 1) >> 8)
    emit(0x67)                              # LD H,A
    emit(0x2A)                              # LD A,(HL+)  dur
    emit(0xB7)                              # OR A
    jr_nz(stream_lab + '_ok')
    emit(0x21); a16(stream_lab)             # LD HL,stream
    emit(0x2A)                              # LD A,(HL+)
    label(stream_lab + '_ok')
    emit(0xEA, cnt & 0xFF, cnt >> 8)        # LD (cnt),A
    emit(0x2A)                              # LD A,(HL+)  lo
    emit(0xE0, base + 3)                    # LDH (NRx3),A
    emit(0x2A)                              # LD A,(HL+)  hi
    emit(0xFE, 0xFF)                        # CP 0xFF (пауза?)
    emit(0x28, 0x0C)                        # JR Z,+12 -> rest
    emit(0x47)                              # LD B,A (hi на потом)
    emit(0x3E, env)                         # env ДО триггера
    emit(0xE0, base + 2)                    # LDH (NRx2),A
    emit(0x78)                              # LD A,B
    emit(0xF6, 0x80)                        # OR 0x80 (trigger)
    emit(0xE0, base + 4)                    # LDH (NRx4),A
    emit(0x18, 0x04)                        # JR +4 (мимо rest)
    # rest: env=0 (глушим)
    emit(0x3E, 0x00)
    emit(0xE0, base + 2)                    # LDH (NRx2),A
    # ptr обратно в RAM
    emit(0x7D)                              # LD A,L
    emit(0xEA, ptr & 0xFF, ptr >> 8)
    emit(0x7C)                              # LD A,H
    emit(0xEA, (ptr + 1) & 0xFF, (ptr + 1) >> 8)
    label(skip_lab)


# INIT
label('init')
emit(0x3E, 0x80); emit(0xE0, 0x26)          # NR52: звук вкл
emit(0x3E, 0xFF); emit(0xE0, 0x25)          # NR51: оба канала в оба уха
emit(0x3E, 0x77); emit(0xE0, 0x24)          # NR50: громкость
emit(0x3E, 0x80); emit(0xE0, 0x11)          # NR11: duty 50%
emit(0x3E, 0x80); emit(0xE0, 0x16)          # NR21: duty 50%
emit(0x3E, 0x00); emit(0xE0, 0x12); emit(0xE0, 0x17)  # env тихо
for ptr, lab in ((RAM, 'mel'), (RAM + 3, 'bass')):
    emit(0x21); a16(lab)                    # LD HL,stream
    emit(0x7D); emit(0xEA, ptr & 0xFF, ptr >> 8)
    emit(0x7C); emit(0xEA, (ptr + 1) & 0xFF, (ptr + 1) >> 8)
emit(0x3E, 0x01)
emit(0xEA, (RAM + 2) & 0xFF, (RAM + 2) >> 8)
emit(0xEA, (RAM + 5) & 0xFF, (RAM + 5) >> 8)
emit(0xC9)                                  # RET

# PLAY
label('play')
track(0x10, RAM, RAM + 2, 'mel', 0xC2, 'sk1')
track(0x15, RAM + 3, RAM + 5, 'bass', 0x92, 'sk2')
emit(0xC9)                                  # RET

label('mel')
items.append(('b', tuple(stream(MELODY))))
label('bass')
items.append(('b', tuple(stream(BASS))))

code = assemble()


def pad32(s):
    b = s.encode('ascii')[:31]
    return b + b'\0' * (32 - len(b))


hdr = bytearray(112)
hdr[0:3] = b'GBS'
hdr[3] = 1                                  # версия
hdr[4] = 1                                  # песен
hdr[5] = 1                                  # первая
hdr[6:8] = LOAD.to_bytes(2, 'little')
hdr[8:10] = labels['init'].to_bytes(2, 'little')
hdr[10:12] = labels['play'].to_bytes(2, 'little')
hdr[12:14] = (0xFFFE).to_bytes(2, 'little')  # SP
hdr[14] = 0                                 # TMA
hdr[15] = 0                                 # TAC: vblank
hdr[16:48] = pad32('Ode to Joy (m4pocket demo)')
hdr[48:80] = pad32('Beethoven, arr. M4chanic')
hdr[80:112] = pad32('CC0 / public domain')

out = sys.argv[1] if len(sys.argv) > 1 else 'ode_to_joy.gbs'
with open(out, 'wb') as f:
    f.write(bytes(hdr) + code)
print(f'{out}: {len(code)} байт, INIT={labels["init"]:#x}, PLAY={labels["play"]:#x}, '
      f'цикл {mel_len} кадров ({mel_len / 59.7:.1f} с)')

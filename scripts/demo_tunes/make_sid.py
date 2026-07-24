#!/usr/bin/env python3
"""Генерация демо-SID (PSID v2): «Greensleeves» (англ. народная, PD),
аранжировка своя (CC0).

Голос 1 — пила (мелодия), голос 2 — пульс (бас). Поток нот как в make_nsf:
[dur, lo, hi]*, dur=0 — цикл, hi=0 — пауза. За 2 кадра до конца ноты мелодии
снимается gate (иначе повторные ноты сливаются).
"""
import sys
from asm6502 import Asm, note_hz

PAL = 985248.0


def sid_freq(hz):
    v = round(hz * 16777216 / PAL)
    assert 0 < v < 0x10000
    return v


Q, E = 24, 12          # четверть и восьмая (50 Гц, 6/8 ~ темп 125 на восьмую)
QD = Q + E             # четверть с точкой


def stream(notes):
    out = bytearray()
    for name, dur in notes:
        assert 0 < dur < 256
        if name is None:
            out += bytes([dur, 0, 0])
        else:
            f = sid_freq(note_hz(name))
            assert f >> 8, f'{name}: hi-байт 0'
            out += bytes([dur, f & 0xFF, f >> 8])
    out.append(0)
    return out


# Куплет в ля миноре, упрощённая ровная ритмика
MELODY = [
    ('A4', E),
    ('C5', Q), ('D5', E), ('E5', Q), ('F5', E), ('E5', Q), ('D5', E),
    ('B4', Q), ('G4', E), ('A4', Q), ('B4', E), ('C5', Q), ('A4', E),
    ('A4', Q), ('G#4', E), ('A4', Q), ('B4', E), ('G#4', Q), ('E4', E),
    ('A4', Q), ('C5', E), ('E5', Q), ('F5', E), ('E5', Q), ('D5', E),
    ('B4', Q), ('G4', E), ('A4', Q), ('B4', E), ('C5', Q), ('B4', E),
    ('A4', Q), ('G#4', E), ('A4', QD), ('A4', QD), (None, E),
]

# Бас: гармония долями по четверти с точкой
BASS_ROOTS = ['A2', 'A2', 'C3', 'G2', 'A2', 'A2', 'E2', 'E2', 'A2',
              'A2', 'C3', 'G2', 'A2', 'E2', 'A2', 'A2', 'E2', 'A2']
BASS = [(None, E)] + [(r, QD) for r in BASS_ROOTS] + [(None, E)]

mel_len = sum(d for _, d in MELODY)
bass_len = sum(d for _, d in BASS)
assert mel_len == bass_len, f'мелодия {mel_len} != бас {bass_len} кадров'

SAW, PULSE = 0x20, 0x40

a = Asm(0x1000)
a.op('JMP', 'abs', 'init')
a.op('JMP', 'abs', 'play')

a.label('init')
a.op('LDA', 'imm', 0x0F); a.op('STA', 'abs', 0xD418)   # громкость, фильтр выкл.
a.op('LDA', 'imm', 0x08); a.op('STA', 'abs', 0xD405)   # v1 A=0 D=8
a.op('LDA', 'imm', 0xA8); a.op('STA', 'abs', 0xD406)   # v1 S=10 R=8
a.op('LDA', 'imm', 0x0A); a.op('STA', 'abs', 0xD40C)   # v2 A=0 D=10
a.op('LDA', 'imm', 0x88); a.op('STA', 'abs', 0xD40D)   # v2 S=8 R=8
a.op('LDA', 'imm', 0x08); a.op('STA', 'abs', 0xD40A)   # v2 ширина пульса $0800
a.op('LDA', 'imm', 0x00); a.op('STA', 'abs', 0xD409)
for ptr, lab in ((0x10, 'mel'), (0x14, 'bass')):
    a.op('LDA', 'imm', '<' + lab); a.op('STA', 'zp', ptr)
    a.op('LDA', 'imm', '>' + lab); a.op('STA', 'zp', ptr + 1)
a.op('LDA', 'imm', 1)
a.op('STA', 'zp', 0x12)
a.op('STA', 'zp', 0x16)
a.op('RTS')

a.label('play')
# --- мелодия (голос 1) ---
a.op('DEC', 'zp', 0x12)
a.op('BEQ', 'rel', 'm_next')
a.op('LDA', 'zp', 0x12)
a.op('CMP', 'imm', 2)                 # хвост ноты: снять gate
a.op('BNE', 'rel', 'do_bass')
a.op('LDA', 'imm', SAW)
a.op('STA', 'abs', 0xD404)
a.op('JMP', 'abs', 'do_bass')
a.label('m_next')
a.op('LDY', 'imm', 0)
a.op('LDA', 'indy', 0x10)
a.op('BNE', 'rel', 'm_ok')
a.op('LDA', 'imm', '<mel'); a.op('STA', 'zp', 0x10)
a.op('LDA', 'imm', '>mel'); a.op('STA', 'zp', 0x11)
a.op('LDA', 'indy', 0x10)
a.label('m_ok')
a.op('STA', 'zp', 0x12)
a.op('INY')
a.op('LDA', 'indy', 0x10); a.op('STA', 'abs', 0xD400)
a.op('INY')
a.op('LDA', 'indy', 0x10)
a.op('BEQ', 'rel', 'm_rest')
a.op('STA', 'abs', 0xD401)
a.op('LDA', 'imm', SAW | 1)           # gate on
a.op('STA', 'abs', 0xD404)
a.op('JMP', 'abs', 'm_adv')
a.label('m_rest')
a.op('LDA', 'imm', SAW)
a.op('STA', 'abs', 0xD404)
a.label('m_adv')
a.op('CLC')
a.op('LDA', 'zp', 0x10); a.op('ADC', 'imm', 3); a.op('STA', 'zp', 0x10)
a.op('LDA', 'zp', 0x11); a.op('ADC', 'imm', 0); a.op('STA', 'zp', 0x11)
# --- бас (голос 2) ---
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
a.op('LDA', 'indy', 0x14); a.op('STA', 'abs', 0xD407)
a.op('INY')
a.op('LDA', 'indy', 0x14)
a.op('BEQ', 'rel', 'b_rest')
a.op('STA', 'abs', 0xD408)
a.op('LDA', 'imm', PULSE | 1)
a.op('STA', 'abs', 0xD40B)
a.op('JMP', 'abs', 'b_adv')
a.label('b_rest')
a.op('LDA', 'imm', PULSE)
a.op('STA', 'abs', 0xD40B)
a.label('b_adv')
a.op('CLC')
a.op('LDA', 'zp', 0x14); a.op('ADC', 'imm', 3); a.op('STA', 'zp', 0x14)
a.op('LDA', 'zp', 0x15); a.op('ADC', 'imm', 0); a.op('STA', 'zp', 0x15)
a.label('done')
a.op('RTS')

a.label('mel')
a.data(stream(MELODY))
a.label('bass')
a.data(stream(BASS))

code = a.assemble()


def pad32(s):
    b = s.encode('ascii')[:31]
    return b + b'\0' * (32 - len(b))


hdr = bytearray(0x7C)
hdr[0:4] = b'PSID'
hdr[4:6] = (2).to_bytes(2, 'big')       # версия
hdr[6:8] = (0x7C).to_bytes(2, 'big')    # dataOffset
hdr[8:10] = (0).to_bytes(2, 'big')      # load: первые 2 байта данных
hdr[10:12] = a.labels['init'].to_bytes(2, 'big')
hdr[12:14] = a.labels['play'].to_bytes(2, 'big')
hdr[14:16] = (1).to_bytes(2, 'big')     # песен
hdr[16:18] = (1).to_bytes(2, 'big')     # стартовая
hdr[18:22] = (0).to_bytes(4, 'big')     # speed: VBI
hdr[0x16:0x36] = pad32('Greensleeves (m4pocket demo)')
hdr[0x36:0x56] = pad32('trad. eng., arr. M4chanic')
hdr[0x56:0x76] = pad32('2026 CC0 / public domain')
hdr[0x76:0x78] = ((1 << 2) | (1 << 4)).to_bytes(2, 'big')  # PAL, 6581

out = sys.argv[1] if len(sys.argv) > 1 else 'greensleeves.sid'
with open(out, 'wb') as f:
    f.write(bytes(hdr) + (0x1000).to_bytes(2, 'little') + code)
print(f'{out}: {len(code)} байт, INIT={a.labels["init"]:#x}, '
      f'PLAY={a.labels["play"]:#x}, цикл {mel_len} кадров ({mel_len / 50:.1f} с)')

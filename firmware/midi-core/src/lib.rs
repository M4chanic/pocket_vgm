//! MIDI (SMF 0/1) -> поток команд chipbox для OPL3.
//!
//! Синтезатор General MIDI на 18 двухоператорных каналах OPL3, патчи —
//! GENMIDI-лумп (Freedoom, BSD-3). Выход — слова секвенсора: 0xC — запись
//! OPL3, 0x8 — ожидание в тиках 1/44100 c. Тайминг исполняет железо.

#![cfg_attr(not(any(test, feature = "std")), no_std)]

extern crate alloc;

use alloc::vec::Vec;

pub const OP_OPL3: u32 = 0xC000_0000;
pub const OP_WAIT: u32 = 0x8000_0000;
pub const TICK_RATE: f64 = 44100.0;

static GENMIDI: &[u8] = include_bytes!("../genmidi.lmp");

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    BadMagic,
    TooShort,
    BadTrack,
    NoGenmidi,
}

// ---------------------------------------------------------------------
// GENMIDI: 175 инструментов по 36 байт после "#OPL_II#"
// (0-127 мелодические GM, 128-174 перкуссия для нот 35-81)

#[derive(Clone, Copy)]
struct GmOp {
    trem: u8,   // AM/VIB/EG/KSR/MULT
    attack: u8, // attack/decay
    sustain: u8,
    wave: u8,
    ksl: u8,
    level: u8,
}

#[derive(Clone, Copy)]
struct GmVoice {
    modu: GmOp,
    feedback: u8,
    car: GmOp,
    base_note_off: i16,
}

#[derive(Clone, Copy)]
struct GmInstr {
    fixed_note: u8, // 0 = обычный
    voice: GmVoice,
}

fn gm_op(d: &[u8]) -> GmOp {
    GmOp { trem: d[0], attack: d[1], sustain: d[2], wave: d[3], ksl: d[4], level: d[5] }
}

fn gm_instr(idx: usize) -> Option<GmInstr> {
    let base = 8 + idx * 36;
    let d = GENMIDI.get(base..base + 36)?;
    let v = &d[4..20]; // первый голос
    Some(GmInstr {
        fixed_note: d[3],
        voice: GmVoice {
            modu: gm_op(&v[0..6]),
            feedback: v[6],
            car: gm_op(&v[7..13]),
            base_note_off: i16::from_le_bytes([v[14], v[15]]),
        },
    })
}

// ---------------------------------------------------------------------
// Частоты: F-num/block. Таблица F-num для нот 0-11 при block 1
// (частота OPL3 = 49716 Гц): fnum = f * 2^(20-block) / 49716.

const FNUM_OCT: [u16; 12] = [345, 365, 387, 410, 435, 460, 488, 517, 547, 580, 615, 651];

fn note_to_fnum_block(note: i32, bend_cents: i32) -> (u16, u8) {
    // нота с подстройкой в центах; берём базу и сдвигаем октавами
    let mut n = note * 100 + bend_cents;
    if n < 0 {
        n = 0;
    }
    let semi = (n / 100) as usize;
    let frac = (n % 100) as u32;
    let (mut oct, idx) = ((semi / 12) as i32 - 1, semi % 12);
    // интерполяция между соседними F-num (грубая, 1/100 полутона)
    let f0 = FNUM_OCT[idx] as u32;
    let f1 = if idx == 11 { FNUM_OCT[0] as u32 * 2 } else { FNUM_OCT[idx + 1] as u32 };
    let mut fnum = (f0 + (f1 - f0) * frac / 100) as u32;
    while oct < 0 {
        fnum /= 2;
        oct += 1;
    }
    while oct > 7 {
        fnum *= 2;
        oct -= 1;
    }
    while fnum > 1023 && oct < 7 {
        fnum /= 2;
        oct += 1;
    }
    if fnum > 1023 {
        fnum = 1023;
    }
    (fnum as u16, oct as u8)
}

// ---------------------------------------------------------------------
// Синтезатор

// 9: в железе OPL3 урезан до одного банка (OPL2-объём) ради площади FPGA
const NUM_VOICES: usize = 9;
const OP_OFF: [u8; 9] = [0x00, 0x01, 0x02, 0x08, 0x09, 0x0A, 0x10, 0x11, 0x12];

#[derive(Clone, Copy, Default)]
struct Voice {
    active: bool,
    midi_ch: u8,
    note: u8,
    instr: u16, // 0xFFFF = не загружен
    age: u32,
}

#[derive(Clone, Copy)]
struct MidiCh {
    program: u8,
    volume: u8,
    pan: u8,
    bend: i32, // в центах, +-200
}

impl Default for MidiCh {
    fn default() -> Self {
        MidiCh { program: 0, volume: 100, pan: 64, bend: 0 }
    }
}

pub struct Synth {
    out: Vec<u32>,
    voices: [Voice; NUM_VOICES],
    chans: [MidiCh; 16],
    clock: u32,
}

impl Synth {
    fn new() -> Synth {
        let mut s = Synth {
            out: Vec::new(),
            voices: [Voice { instr: 0xFFFF, ..Default::default() }; NUM_VOICES],
            chans: [MidiCh::default(); 16],
            clock: 0,
        };
        s.wr(1, 0x05, 0x01); // OPL3 mode
        s.wr(0, 0x01, 0x00);
        s.wr(0, 0xBD, 0x00); // без ритм-режима
        for v in 0..NUM_VOICES {
            let (bank, ch) = (v / 9, v % 9);
            s.wr(bank as u8, 0xC0 + ch as u8, 0x30); // L+R
        }
        s
    }

    fn wr(&mut self, bank: u8, reg: u8, val: u8) {
        self.out.push(OP_OPL3 | (bank as u32) << 16 | (reg as u32) << 8 | val as u32);
    }

    fn wait(&mut self, ticks: u32) {
        let mut t = ticks;
        while t > 0 {
            let n = t.min(0xFF_FFFF);
            self.out.push(OP_WAIT | n);
            t -= n;
        }
    }

    fn op_regs(v: usize) -> (u8, u8, u8) {
        let (bank, ch) = (v / 9, v % 9);
        (bank as u8, OP_OFF[ch], ch as u8)
    }

    fn load_patch(&mut self, v: usize, instr: u16) {
        let Some(gi) = gm_instr(instr as usize) else { return };
        let (bank, op, ch) = Self::op_regs(v);
        let gv = gi.voice;
        for (slot, o) in [(op, gv.modu), (op + 3, gv.car)] {
            self.wr(bank, 0x20 + slot, o.trem);
            self.wr(bank, 0x40 + slot, o.ksl & 0xC0 | o.level & 0x3F);
            self.wr(bank, 0x60 + slot, o.attack);
            self.wr(bank, 0x80 + slot, o.sustain);
            self.wr(bank, 0xE0 + slot, o.wave & 7);
        }
        self.wr(bank, 0xC0 + ch, gv.feedback & 0x0F | 0x30);
        self.voices[v].instr = instr;
    }

    fn key(&mut self, v: usize, on: bool) {
        let mc = self.voices[v].midi_ch as usize;
        let instr = self.voices[v].instr;
        let gi = gm_instr(instr as usize);
        let (bank, _, ch) = Self::op_regs(v);
        if on {
            let mut note = self.voices[v].note as i32;
            if let Some(gi) = &gi {
                if gi.fixed_note != 0 {
                    note = gi.fixed_note as i32;
                }
                note += gi.voice.base_note_off as i32;
            }
            let (fnum, block) = note_to_fnum_block(note, self.chans[mc].bend);
            self.wr(bank, 0xA0 + ch, (fnum & 0xFF) as u8);
            self.wr(bank, 0xB0 + ch, 0x20 | block << 2 | (fnum >> 8) as u8);
        } else {
            self.wr(bank, 0xB0 + ch, 0x00);
        }
    }

    fn carrier_level(&mut self, v: usize, vel: u8) {
        let mc = self.voices[v].midi_ch as usize;
        let Some(gi) = gm_instr(self.voices[v].instr as usize) else { return };
        let (bank, op, _) = Self::op_regs(v);
        // затухание = уровень патча + (тише от velocity и cc7)
        let att = gi.voice.car.level as u32 & 0x3F;
        let vel_att = (127 - vel.min(127) as u32) / 4;
        let vol_att = (127 - self.chans[mc].volume.min(127) as u32) / 4;
        let tl = (att + vel_att + vol_att).min(63) as u8;
        self.wr(bank, 0x40 + op + 3, gi.voice.car.ksl & 0xC0 | tl);
    }

    fn pan_bits(pan: u8) -> u8 {
        if pan < 43 {
            0x10
        } else if pan > 85 {
            0x20
        } else {
            0x30
        }
    }

    fn note_on(&mut self, mc: u8, note: u8, vel: u8) {
        if vel == 0 {
            self.note_off(mc, note);
            return;
        }
        let instr: u16 = if mc == 9 {
            if !(35..=81).contains(&note) {
                return;
            }
            128 + (note as u16 - 35)
        } else {
            self.chans[mc as usize].program as u16
        };
        // выбор голоса: свободный либо самый старый
        let v = (0..NUM_VOICES)
            .find(|&i| !self.voices[i].active)
            .unwrap_or_else(|| {
                (0..NUM_VOICES).min_by_key(|&i| self.voices[i].age).unwrap()
            });
        self.clock += 1;
        if self.voices[v].active {
            self.key(v, false);
        }
        self.voices[v] = Voice { active: true, midi_ch: mc, note, instr: self.voices[v].instr, age: self.clock };
        if self.voices[v].instr != instr {
            self.load_patch(v, instr);
        }
        let gi = gm_instr(instr as usize);
        let (bank, _, ch) = Self::op_regs(v);
        let fb = gi.map(|g| g.voice.feedback & 0x0F).unwrap_or(0);
        self.wr(bank, 0xC0 + ch, fb | Self::pan_bits(self.chans[mc as usize].pan));
        self.carrier_level(v, vel);
        self.key(v, true);
    }

    fn note_off(&mut self, mc: u8, note: u8) {
        for v in 0..NUM_VOICES {
            if self.voices[v].active && self.voices[v].midi_ch == mc && self.voices[v].note == note {
                self.voices[v].active = false;
                self.key(v, false);
            }
        }
    }

    fn all_off(&mut self, mc: u8) {
        for v in 0..NUM_VOICES {
            if self.voices[v].active && self.voices[v].midi_ch == mc {
                self.voices[v].active = false;
                self.key(v, false);
            }
        }
    }

    fn bend(&mut self, mc: u8, value14: i32) {
        self.chans[mc as usize].bend = (value14 - 8192) * 200 / 8192;
        for v in 0..NUM_VOICES {
            if self.voices[v].active && self.voices[v].midi_ch == mc {
                self.key(v, true); // перезапись частоты (key уже установлен)
            }
        }
    }
}

// ---------------------------------------------------------------------
// SMF

fn rd_vlq(d: &[u8], pos: &mut usize) -> Option<u32> {
    let mut v: u32 = 0;
    for _ in 0..4 {
        let b = *d.get(*pos)?;
        *pos += 1;
        v = v << 7 | (b & 0x7F) as u32;
        if b & 0x80 == 0 {
            return Some(v);
        }
    }
    Some(v)
}

struct TrackEvent {
    tick: u64,
    order: u32,
    data: [u8; 3],
    len: u8,
    tempo: u32, // 0 = не темп-событие
}

/// Конвертация SMF -> поток команд chipbox.
pub fn midi_to_commands(data: &[u8]) -> Result<Vec<u32>, Error> {
    if data.len() < 14 || &data[0..4] != b"MThd" {
        return Err(Error::BadMagic);
    }
    let ntrks = u16::from_be_bytes([data[10], data[11]]) as usize;
    let division = u16::from_be_bytes([data[12], data[13]]);
    if division & 0x8000 != 0 {
        return Err(Error::BadTrack); // SMPTE-тайминг не поддержан
    }
    let division = division.max(1) as f64;

    // разобрать все треки в абсолютных тиках
    let mut events: Vec<TrackEvent> = Vec::new();
    let mut pos = 14;
    let mut order: u32 = 0;
    for _ in 0..ntrks {
        while pos + 8 <= data.len() && &data[pos..pos + 4] != b"MTrk" {
            let l = u32::from_be_bytes([data[pos+4], data[pos+5], data[pos+6], data[pos+7]]) as usize;
            pos += 8 + l;
        }
        if pos + 8 > data.len() {
            break;
        }
        let len = u32::from_be_bytes([data[pos+4], data[pos+5], data[pos+6], data[pos+7]]) as usize;
        let mut p = pos + 8;
        let end = (p + len).min(data.len());
        pos = p + len;

        let mut tick: u64 = 0;
        let mut running: u8 = 0;
        while p < end {
            let delta = rd_vlq(data, &mut p).ok_or(Error::BadTrack)?;
            tick += delta as u64;
            let mut status = *data.get(p).ok_or(Error::BadTrack)?;
            if status & 0x80 != 0 {
                p += 1;
                if status < 0xF0 {
                    running = status;
                }
            } else {
                status = running;
            }
            match status & 0xF0 {
                0x80 | 0x90 | 0xA0 | 0xB0 | 0xE0 => {
                    let a = *data.get(p).ok_or(Error::BadTrack)?;
                    let b = *data.get(p + 1).ok_or(Error::BadTrack)?;
                    p += 2;
                    events.push(TrackEvent {
                        tick, order, data: [status, a, b], len: 3, tempo: 0,
                    });
                }
                0xC0 | 0xD0 => {
                    let a = *data.get(p).ok_or(Error::BadTrack)?;
                    p += 1;
                    events.push(TrackEvent { tick, order, data: [status, a, 0], len: 2, tempo: 0 });
                }
                0xF0 => match status {
                    0xFF => {
                        let mt = *data.get(p).ok_or(Error::BadTrack)?;
                        p += 1;
                        let l = rd_vlq(data, &mut p).ok_or(Error::BadTrack)? as usize;
                        if mt == 0x51 && l == 3 {
                            let t = u32::from_be_bytes([0, data[p], data[p+1], data[p+2]]);
                            events.push(TrackEvent { tick, order, data: [0, 0, 0], len: 0, tempo: t });
                        }
                        p += l;
                    }
                    0xF0 | 0xF7 => {
                        let l = rd_vlq(data, &mut p).ok_or(Error::BadTrack)? as usize;
                        p += l;
                    }
                    _ => {}
                },
                _ => return Err(Error::BadTrack),
            }
            order += 1;
        }
    }

    events.sort_by_key(|e| (e.tick, e.order));

    let mut synth = Synth::new();
    let mut tempo: f64 = 500_000.0; // мкс на четверть
    let mut last_tick: u64 = 0;
    let mut frac: f64 = 0.0;

    for ev in &events {
        let dt = (ev.tick - last_tick) as f64;
        last_tick = ev.tick;
        if dt > 0.0 {
            let samples = dt * tempo / division / 1_000_000.0 * TICK_RATE + frac;
            let whole = samples as u64;
            frac = samples - whole as f64;
            if whole > 0 {
                synth.wait(whole as u32);
            }
        }
        if ev.tempo != 0 {
            tempo = ev.tempo as f64;
            continue;
        }
        let mc = ev.data[0] & 0x0F;
        match ev.data[0] & 0xF0 {
            0x90 => synth.note_on(mc, ev.data[1], ev.data[2]),
            0x80 => synth.note_off(mc, ev.data[1]),
            0xB0 => match ev.data[1] {
                7 => {
                    synth.chans[mc as usize].volume = ev.data[2];
                }
                10 => {
                    synth.chans[mc as usize].pan = ev.data[2];
                }
                120 | 123 => synth.all_off(mc),
                _ => {}
            },
            0xC0 => {
                synth.chans[mc as usize].program = ev.data[1] & 0x7F;
            }
            0xE0 => synth.bend(mc, (ev.data[1] as i32) | (ev.data[2] as i32) << 7),
            _ => {}
        }
    }
    // хвост: пауза и все ноты долой
    synth.wait(TICK_RATE as u32);
    for v in 0..NUM_VOICES {
        if synth.voices[v].active {
            synth.key(v, false);
        }
    }
    Ok(synth.out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vlq(v: u32) -> Vec<u8> {
        if v < 128 { alloc::vec![v as u8] } else { alloc::vec![(v >> 7) as u8 | 0x80, (v & 0x7F) as u8] }
    }

    fn synth_midi() -> Vec<u8> {
        // формат 0, division 96: C4 on, пауза, off, D4 on/off
        let mut trk: Vec<u8> = Vec::new();
        trk.extend([0, 0xC0, 0x00]); // program 0
        trk.extend([0, 0x90, 60, 100]);
        trk.extend(vlq(96));
        trk.extend([0x80, 60, 0]);
        trk.extend(vlq(96));
        trk.extend([0x90, 62, 100]);
        trk.extend(vlq(96));
        trk.extend([0x80, 62, 0]);
        trk.extend([0, 0xFF, 0x2F, 0]);
        let mut d = alloc::vec![];
        d.extend(b"MThd");
        d.extend(6u32.to_be_bytes());
        d.extend(0u16.to_be_bytes());
        d.extend(1u16.to_be_bytes());
        d.extend(96u16.to_be_bytes());
        d.extend(b"MTrk");
        d.extend((trk.len() as u32).to_be_bytes());
        d.extend(&trk);
        d
    }

    #[test]
    fn converts_notes_and_waits() {
        let cmds = midi_to_commands(&synth_midi()).unwrap();
        let waits: u64 = cmds.iter().filter(|&&c| c & 0xF000_0000 == OP_WAIT)
            .map(|&c| (c & 0xFF_FFFF) as u64).sum();
        // 3 паузы по четверти (96 тиков = 0.5 c) + хвост 1 c = 2.5 c
        assert!((waits as f64 - 44100.0 * 2.5).abs() < 10.0, "waits={waits}");
        let keyons = cmds.iter().filter(|&&c| c & 0xF000_0000 == OP_OPL3
            && (c >> 8) as u8 & 0xF0 == 0xB0 && c & 0x20 != 0).count();
        assert_eq!(keyons, 2);
        let keyoffs = cmds.iter().filter(|&&c| c & 0xF000_0000 == OP_OPL3
            && (c >> 8) as u8 & 0xF0 == 0xB0 && c & 0x20 == 0).count();
        assert!(keyoffs >= 2);
    }

    #[test]
    fn genmidi_present() {
        assert_eq!(&GENMIDI[0..8], b"#OPL_II#");
        assert!(gm_instr(0).is_some());
        assert!(gm_instr(174).is_some());
    }
}

# Demo — freely licensed music for PocketVGM

This folder is placed on the SD card together with the core. Everything here
is freely redistributable; sources and licenses are listed below.

## Sega (VGM / VGZ / GYM)

| File | Source | License |
|---|---|---|
| Town, House of the Rising Sun, Mad Bossa (.vgm/.vgz) | [Free VGMs](https://github.com/jerellsworth/free_vgms) by Safety Stoat Studios | CC0 |
| Bicycle Games (.gym) | same pack, converted with `scripts/vgm2gym.py` | CC0 |

"House of the Rising Sun" is a traditional song (PD) in a CC0 arrangement.

## Nintendo (NSF / GBS)

| File | Content | License |
|---|---|---|
| Korobeiniki (.nsf) | Russian folk tune, own arrangement, generator `scripts/demo_tunes/make_nsf.py` | CC0 |
| Ode to Joy (.gbs) | Beethoven (PD), own arrangement, generator `scripts/demo_tunes/make_gbs.py` | CC0 |

## Computer (MID / SID)

| File | Content | License |
|---|---|---|
| Bach — Prelude in C BWV 846 (.mid) | [Mutopia Project](https://www.mutopiaproject.org/) | Public Domain |
| Greensleeves (.sid) | English folk tune, own arrangement, generator `scripts/demo_tunes/make_sid.py` | CC0 |

The demo tunes (.nsf/.gbs/.sid) are tiny purpose-built players (6502/SM83)
assembled by the generators in `scripts/demo_tunes/`; verified through RTL
simulation (`chipbox_tb --nsffile/--gbsfile/--sidfile`).

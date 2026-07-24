// vgmplay-sim: проигрывает .vgm/.vgz через RTL jt51 (Verilator) и пишет WAV.
// Пока поддержан только YM2151; команды остальных чипов пропускаются по спецификации VGM.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <zlib.h>
#include "Vjt51.h"
#include "verilated.h"

static std::vector<uint8_t> read_maybe_gz(const char* path) {
    gzFile f = gzopen(path, "rb");
    if (!f) { fprintf(stderr, "не открыть %s\n", path); exit(1); }
    std::vector<uint8_t> out;
    uint8_t buf[65536];
    int n;
    while ((n = gzread(f, buf, sizeof buf)) > 0) out.insert(out.end(), buf, buf + n);
    gzclose(f);
    return out;
}

static uint32_t rd32(const std::vector<uint8_t>& d, size_t off) {
    return d[off] | d[off+1] << 8 | d[off+2] << 16 | (uint32_t)d[off+3] << 24;
}

struct Sim {
    Vjt51 top;
    uint64_t cycle = 0;
    uint8_t last_sample = 0;
    std::vector<int16_t> pcm;   // L,R interleaved

    Sim() {
        top.rst = 1; top.cen = 1; top.cen_p1 = 0;
        top.cs_n = 1; top.wr_n = 1; top.a0 = 0; top.din = 0;
        for (int i = 0; i < 32; i++) step();
        top.rst = 0;
    }
    void step() {
        top.cen_p1 = cycle & 1;
        top.clk = 0; top.eval();
        top.clk = 1; top.eval();
        if (top.sample && !last_sample) {
            pcm.push_back((int16_t)top.xleft);
            pcm.push_back((int16_t)top.xright);
        }
        last_sample = top.sample;
        cycle++;
    }
    void wait_ready() {   // ждём снятия busy-флага (бит 7 статуса)
        top.cs_n = 0; top.wr_n = 1;
        for (int i = 0; i < 4096 && (top.dout & 0x80); i++) step();
        top.cs_n = 1;
    }
    void write(uint8_t a0, uint8_t val) {
        wait_ready();
        top.a0 = a0; top.din = val; top.cs_n = 0; top.wr_n = 0;
        step();
        top.cs_n = 1; top.wr_n = 1;
        step();
    }
    void reg_write(uint8_t reg, uint8_t val) { write(0, reg); write(1, val); }
};

static void write_wav(const char* path, const std::vector<int16_t>& pcm, uint32_t rate) {
    FILE* f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "не открыть %s на запись\n", path); exit(1); }
    uint32_t dlen = pcm.size() * 2, riff = 36 + dlen, byterate = rate * 4;
    uint16_t fmt16[] = {1, 2}, block[] = {4, 16};
    fwrite("RIFF", 4, 1, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 8, 1, f);
    uint32_t fmtlen = 16; fwrite(&fmtlen, 4, 1, f);
    fwrite(fmt16, 4, 1, f); fwrite(&rate, 4, 1, f); fwrite(&byterate, 4, 1, f);
    fwrite(block, 4, 1, f);
    fwrite("data", 4, 1, f); fwrite(&dlen, 4, 1, f);
    fwrite(pcm.data(), 2, pcm.size(), f);
    fclose(f);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const char* in = nullptr; const char* out = "out.wav";
    double max_seconds = 0;   // 0 = до конца (без лупа)
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) max_seconds = atof(argv[++i]);
        else in = argv[i];
    }
    if (!in) { fprintf(stderr, "usage: vgmplay <file.vgm|.vgz> [-o out.wav] [-t seconds]\n"); return 1; }

    std::vector<uint8_t> d = read_maybe_gz(in);
    if (d.size() < 0x40 || memcmp(d.data(), "Vgm ", 4)) { fprintf(stderr, "не VGM\n"); return 1; }
    uint32_t version = rd32(d, 0x08);
    uint32_t ym_clk = rd32(d, 0x30) & 0x3FFFFFFF;
    size_t pos = (version >= 0x150) ? 0x34 + rd32(d, 0x34) : 0x40;
    if (!ym_clk) { fprintf(stderr, "в файле нет YM2151\n"); return 1; }
    fprintf(stderr, "VGM v%x.%02x, YM2151 @ %u Hz, данные с 0x%zx\n",
            version >> 8, version & 0xFF, ym_clk, pos);

    Sim sim;
    const double cycles_per_tick = ym_clk / 44100.0;   // тик VGM = 1/44100 c
    double target = 0;
    uint64_t total_ticks = 0, skipped = 0;
    uint64_t max_cycles = max_seconds > 0 ? (uint64_t)(max_seconds * ym_clk) : UINT64_MAX;

    auto wait_ticks = [&](uint32_t n) {
        total_ticks += n;
        target += n * cycles_per_tick;
        while (sim.cycle < target && sim.cycle < max_cycles) sim.step();
    };

    while (pos < d.size() && sim.cycle < max_cycles) {
        uint8_t cmd = d[pos++];
        if (cmd == 0x54) { uint8_t r = d[pos], v = d[pos+1]; pos += 2; sim.reg_write(r, v); }
        else if (cmd == 0x61) { wait_ticks(d[pos] | d[pos+1] << 8); pos += 2; }
        else if (cmd == 0x62) wait_ticks(735);
        else if (cmd == 0x63) wait_ticks(882);
        else if ((cmd & 0xF0) == 0x70) wait_ticks((cmd & 15) + 1);
        else if (cmd == 0x66) break;                                  // конец
        else if (cmd == 0x67) { pos += 2; uint32_t len = rd32(d, pos) & 0x7FFFFFFF; pos += 4 + len; skipped++; }
        else if (cmd == 0x4F || cmd == 0x50) { pos += 1; skipped++; } // PSG
        else if (cmd >= 0x51 && cmd <= 0x5F) { pos += 2; skipped++; } // другие FM-чипы
        else if (cmd == 0x68) { pos += 11; skipped++; }               // PCM RAM write
        else if ((cmd & 0xF0) == 0x80) skipped++;                     // YM2612 DAC+wait
        else if (cmd >= 0x90 && cmd <= 0x95) {                        // DAC stream
            static const int len[] = {4, 4, 5, 10, 1, 4};
            pos += len[cmd - 0x90]; skipped++;
        }
        else if (cmd >= 0xA0 && cmd <= 0xBF) { pos += 2; skipped++; } // AY, NES APU, OKIM6258 и пр.
        else if (cmd >= 0xC0 && cmd <= 0xDF) { pos += 3; skipped++; }
        else if (cmd >= 0xE0) { pos += 4; skipped++; }
        else { fprintf(stderr, "неизвестная команда 0x%02x @0x%zx\n", cmd, pos - 1); return 1; }
    }

    // фактическая частота сэмплов jt51 = clk/64 (sample raте = phi1/32, phi1 = clk/2)
    uint32_t rate = (uint32_t)((double)sim.pcm.size() / 2 / (sim.cycle / (double)ym_clk) + 0.5);
    write_wav(out, sim.pcm, rate);
    fprintf(stderr, "готово: %.1f c музыки, %zu сэмплов @ %u Гц, пропущено чужих команд: %lu → %s\n",
            total_ticks / 44100.0, sim.pcm.size() / 2, rate, (unsigned long)skipped, out);
    return 0;
}

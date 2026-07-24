#include <cstdio>
#include <cstdint>
#include "Vsid_top.h"
#include "verilated.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Vsid_top t;
    t.reset = 1; t.clk = 0; t.ce_1m = 0; t.cs = 0; t.we = 0;
    t.fc_offset_l = 0; t.pot_x_l = 0xFF; t.pot_y_l = 0xFF; t.ext_in_l = 0;
    t.fc_offset_r = 0; t.pot_x_r = 0xFF; t.pot_y_r = 0xFF; t.ext_in_r = 0;
    t.filter_en = 1; t.mode = 0; t.cfg = 0;
    t.ld_clk = 0; t.ld_addr = 0; t.ld_data = 0; t.ld_wr = 0;

    uint32_t phase = 0; const uint32_t inc = (uint32_t)(985248.0/8e6*4294967296.0);
    auto step = [&]() {
        uint64_t p = (uint64_t)phase + inc; t.ce_1m = p >> 32; phase = (uint32_t)p;
        t.clk = 0; t.eval(); t.clk = 1; t.eval();
    };
    for (int i = 0; i < 64; i++) step();
    t.reset = 0;
    auto wr = [&](int a, int d) { t.cs = 1; t.we = 1; t.addr = a; t.data_in = d; step(); t.cs = 0; t.we = 0; step(); };
    // голос 3 — чтобы читать osc3/env3
    wr(0x0E, 0x45); wr(0x0F, 0x1D);  // freq v3
    wr(0x13, 0x00); wr(0x14, 0xF0);  // AD, SR v3
    wr(0x18, 0x0F);                  // volume
    wr(0x12, 0x21);                  // saw + gate v3
    int mn = 0, mx = 0;
    for (int i = 0; i < 4000000; i++) {
        step();
        int a = ((int32_t)(t.audio_l << 14)) >> 14;
        if (a < mn) mn = a; if (a > mx) mx = a;
        if (i % 500000 == 0) {
            t.cs = 1; t.we = 0; t.addr = 0x1B; step(); step();
            int osc3 = t.data_out;
            t.addr = 0x1C; step(); step();
            int env3 = t.data_out;
            t.cs = 0;
            printf("i=%d audio=%d osc3=%02x env3=%02x\n", i, a, osc3, env3);
        }
    }
    printf("min=%d max=%d\n", mn, mx);
    return 0;
}

// Заглушка eReg_SavestateV (оригинал — VHDL в bus_savestates.vhd
// NES_MiSTer). Сейвстейты в m4pocket не используются: регистр всегда
// отдаёт значение по умолчанию, шина чтения — ноль. Порты позиционно
// совместимы с инстансами в apu.sv.
module eReg_SavestateV #(
    parameter [9:0] Adr = 0,
    parameter [63:0] def_value = 0
) (
    input wire clk,
    input wire [63:0] BUS_Din,
    input wire [9:0] BUS_Adr,
    input wire BUS_wren,
    input wire BUS_rst,
    output wire [63:0] BUS_Dout,
    input wire [63:0] Din,
    output wire [63:0] Dout
);

  assign BUS_Dout = 64'd0;
  assign Dout = def_value;

endmodule

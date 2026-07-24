package regs_savestates;

	localparam [9:0] SSREG_INDEX_CPU_1    = 10'd0;   parameter [63:0] SSREG_DEFAULT_CPU_1    = 64'hE064000000000000; // warning: defined new with same values in T65.vhd, as file is VHDL
	localparam [9:0] SSREG_INDEX_CPU_2    = 10'd1;   parameter [63:0] SSREG_DEFAULT_CPU_2    = 64'h0000012000000001; // warning: defined new with same values in T65.vhd, as file is VHDL
	localparam [9:0] SSREG_INDEX_CPU_3    = 10'd2;   parameter [63:0] SSREG_DEFAULT_CPU_3    = 64'h0000000000000000; // warning: defined new with same values in T65.vhd, as file is VHDL

	localparam [9:0] SSREG_INDEX_PPU_1    = 10'd4;   parameter [63:0] SSREG_DEFAULT_PPU_1    = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_PPU_2    = 10'd5;   parameter [63:0] SSREG_DEFAULT_PPU_2    = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_CLOCKGEN = 10'd6;   parameter [63:0] SSREG_DEFAULT_CLOCKGEN = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_PAL0     = 10'd7;   parameter [63:0] SSREG_DEFAULT_PAL0     = 64'h0008000900080000;
	localparam [9:0] SSREG_INDEX_PAL1     = 10'd8;   parameter [63:0] SSREG_DEFAULT_PAL1     = 64'h203A040100100201;
	localparam [9:0] SSREG_INDEX_PAL2     = 10'd9;   parameter [63:0] SSREG_DEFAULT_PAL2     = 64'h2C00003404080200;
	localparam [9:0] SSREG_INDEX_PAL3     = 10'd10;  localparam [63:0] SSREG_DEFAULT_PAL3     = 64'h080214032C240D01;
	localparam [9:0] SSREG_INDEX_LOOPY    = 10'd11;  localparam [63:0] SSREG_DEFAULT_LOOPY    = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_OAMEVAL  = 10'd12;  localparam [63:0] SSREG_DEFAULT_OAMEVAL  = 64'h00000000000001FF;

	localparam [9:0] SSREG_INDEX_APU_TOP  = 10'd16;  localparam [63:0] SSREG_DEFAULT_APU_TOP  = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_APU_DMC1 = 10'd17;  localparam [63:0] SSREG_DEFAULT_APU_DMC1 = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_APU_DMC2 = 10'd18;  localparam [63:0] SSREG_DEFAULT_APU_DMC2 = 64'h0000000000000000;
	localparam [9:0] SSREG_INDEX_APU_FCT  = 10'd19;  localparam [63:0] SSREG_DEFAULT_APU_FCT  = 64'h0000000000007FFF;

	localparam [9:0] SSREG_INDEX_TOP      = 10'd24;  localparam [63:0] SSREG_DEFAULT_TOP      = 64'h0000000000000000;

	localparam [9:0] SSREG_INDEX_EXT      = 10'd28;  localparam [63:0] SSREG_DEFAULT_EXT      = 64'h0000000000000000;

	// mapper savestates can be used by multiple mappers, only active mapper outputs. default values for mappers are defined local!
	localparam [9:0] SSREG_INDEX_MAP1     = 10'd32;
	localparam [9:0] SSREG_INDEX_MAP2     = 10'd33;
	localparam [9:0] SSREG_INDEX_MAP3     = 10'd34;
	localparam [9:0] SSREG_INDEX_MAP4     = 10'd35;
	localparam [9:0] SSREG_INDEX_MAP5     = 10'd36;
	localparam [9:0] SSREG_INDEX_MAP6     = 10'd37;

	// additional modules for mappers in hierachy level 2
	localparam [9:0] SSREG_INDEX_L2MAP1   = 10'd40;

	// additional modules for mapper sound modules
	localparam [9:0] SSREG_INDEX_SNDMAP1  = 10'd48;
	localparam [9:0] SSREG_INDEX_SNDMAP2  = 10'd49;
	localparam [9:0] SSREG_INDEX_SNDMAP3  = 10'd50;
	localparam [9:0] SSREG_INDEX_SNDMAP4  = 10'd51;
	localparam [9:0] SSREG_INDEX_SNDMAP5  = 10'd52;

endpackage
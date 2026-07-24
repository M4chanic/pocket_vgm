#
# user core constraints
#
# put your clock groups in here as well as any net assignments
#

# Fix complaining about this net acting as a clock. Only used for JTAG, and this is not the correct period
create_clock -period 10MHz -name altera_reserved_tck [get_ports { altera_reserved_tck }]

# Регистровые клоки chipbox: GB (~4.19 МГц) и OPL3 (~12.727 МГц).
# Делители дробные (фазовые аккумуляторы), поэтому не generated clock, а
# консервативный период с запасом. CDC в/из этих доменов — тогглы и afifo
# по построению, поэтому домены объявлены асинхронными группами ниже.
create_clock -period 200.000 -name gb_clk  [get_registers {*|chipbox:chipbox|gb_clk_r}]
create_clock -period 70.000  -name opl_clk [get_registers {*|chipbox:chipbox|opl_clk_r}]

set_clock_groups -asynchronous \
 -group { bridge_spiclk } \
 -group { clk_74a } \
 -group { clk_74b } \
 -group { altera_reserved_tck } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk \
          ic|mp1|mf_pllbase_inst|altera_pll_i|general[1].gpll~PLL_OUTPUT_COUNTER|divclk \
          ic|mp1|mf_pllbase_inst|altera_pll_i|general[3].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[2].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|mp1|mf_pllbase_inst|altera_pll_i|general[4].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { ic|audio|audio_pll|mf_audio_pll_inst|altera_pll_i|general[0].gpll~PLL_OUTPUT_COUNTER|divclk \
          ic|audio|audio_pll|mf_audio_pll_inst|altera_pll_i|general[1].gpll~PLL_OUTPUT_COUNTER|divclk } \
 -group { gb_clk } \
 -group { opl_clk }


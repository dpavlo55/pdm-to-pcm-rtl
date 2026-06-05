create_clock -name clk -period 20 [get_ports clk]

# ============================================================
# CIC Decimation Filter Multicycle Path Constraints
# N=3, R=32, M=1
#
# Works with SYNTH_KEEP_HIERARCHY_MODULES: ["cic"] in config.json
# which preserves the cic module hierarchy so register names
# survive synthesis.
# ============================================================

# Comb delay registers (comb_0_dly_0, comb_1_dly_0, comb_2_dly_0)
set_multicycle_path -setup 32 -to [get_cells -hierarchical *comb_*_dly_0_reg*]
set_multicycle_path -hold  31 -to [get_cells -hierarchical *comb_*_dly_0_reg*]

`ifndef PDM_TO_PCM_REG_DEFS_SVH
`define PDM_TO_PCM_REG_DEFS_SVH

localparam REGS_DATA_WIDTH    = 8;
localparam REGS_MIN_ADDR_WIDTH = 3;
localparam REGS_SIZE           = 'h6;

typedef struct packed { logic [4:0] test; logic [1:0] divider; logic enable; } pdm_to_pcm_reg__control__out_t;
typedef struct packed { logic [7:0] value; } pdm_to_pcm_reg__control_low__out_t;
typedef struct packed { logic [7:0] value; } pdm_to_pcm_reg__control_high__out_t;
typedef struct packed { logic [7:0] high; logic [7:0] low; } pdm_to_pcm_reg__nco_control__out_t;

typedef struct packed {
    pdm_to_pcm_reg__control__out_t control;
    pdm_to_pcm_reg__control_low__out_t control_low;
    pdm_to_pcm_reg__control_high__out_t control_high;
    pdm_to_pcm_reg__nco_control__out_t nco_control;
} pdm_to_pcm_reg__out_t;

`endif // PDM_TO_PCM_REG_DEFS_SVH

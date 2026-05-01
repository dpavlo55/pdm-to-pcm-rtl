`ifndef PDM_TO_PCM_REG_DEFS_SVH
`define PDM_TO_PCM_REG_DEFS_SVH

localparam REGS_DATA_WIDTH    = 8;
localparam REGS_MIN_ADDR_WIDTH = 4;
localparam REGS_SIZE           = 'h5;

typedef struct packed { logic enable; } pdm_to_pcm_reg__control__out_t;
typedef struct packed { logic [7:0] high; logic [7:0] low; } pdm_to_pcm_reg__nco_control__out_t;

typedef struct packed {
    pdm_to_pcm_reg__control__out_t control;
    pdm_to_pcm_reg__nco_control__out_t nco_control;
} pdm_to_pcm_reg__out_t;

typedef struct packed { logic [7:0] value_msb; logic [7:0] value_lsb; } pdm_to_pcm_reg__data_right__in_t;
typedef struct packed { logic [7:0] value_msb; logic [7:0] value_lsb; } pdm_to_pcm_reg__data_left__in_t;

typedef struct packed {
    pdm_to_pcm_reg__data_right__in_t data_right;
    pdm_to_pcm_reg__data_left__in_t data_left;
} pdm_to_pcm_reg__in_t;

`endif // PDM_TO_PCM_REG_DEFS_SVH

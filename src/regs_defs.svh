`ifndef PDM_TO_PCM_REG_DEFS_SVH
`define PDM_TO_PCM_REG_DEFS_SVH

localparam REGS_DATA_WIDTH    = 8;
localparam REGS_MIN_ADDR_WIDTH = 2;
localparam REGS_SIZE           = 'h4;

typedef struct packed { logic [4:0] test; logic [1:0] divider; logic enable; } pdm_to_pcm_reg__control__out_t;
typedef struct packed { logic [7:0] test; } pdm_to_pcm_reg__test_reg__out_t;

typedef struct packed {
    pdm_to_pcm_reg__control__out_t control;
    pdm_to_pcm_reg__test_reg__out_t test_reg;
} pdm_to_pcm_reg__out_t;

`endif // PDM_TO_PCM_REG_DEFS_SVH

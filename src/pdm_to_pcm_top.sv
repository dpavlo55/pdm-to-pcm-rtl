`include "regs_defs.svh"

module pdm_to_pcm_top
    (
        input logic clk,
        input logic rst_n,

        input logic pdm_in,
        input logic pdm_in_valid,

        // SPI interface
        input logic spi_sck,
        input logic spi_mosi,
        output logic spi_miso,
        input logic spi_cs_n,

        output pdm_to_pcm_reg__out_t hwif_out
    );

    logic [7:0] mosi_data;
    logic mosi_data_valid;

    logic [7:0] miso_data;
    logic miso_data_valid;

    logic s_cpuif_req;
    logic s_cpuif_req_is_wr;
    logic [2:0] s_cpuif_addr;
    logic [7:0] s_cpuif_wr_data;
    logic s_cpuif_wr_ack;
    logic [7:0] s_cpuif_rd_data;
    logic s_cpuif_rd_ack;

    spi spi_inst (
        .clk   (clk),
        .rst_n (rst_n),

        // SPI interface
        .sck   (spi_sck),
        .mosi  (spi_mosi),
        .miso  (spi_miso),
        .cs_n  (spi_cs_n),

        .mosi_data       (mosi_data),
        .mosi_data_valid (mosi_data_valid),

        .miso_data       (miso_data),
        .miso_data_valid (miso_data_valid)
    );

    spi_to_regs_adapter spi_to_regs_adapter_inst (
        .clk   (clk),
        .rst_n (rst_n),

        .mosi_data          (mosi_data),
        .mosi_data_valid    (mosi_data_valid),

        .miso_data          (miso_data),
        .miso_data_valid    (miso_data_valid),

        .cpuif_req          (s_cpuif_req),
        .cpuif_req_is_wr    (s_cpuif_req_is_wr),
        .cpuif_addr         (s_cpuif_addr),
        .cpuif_wr_data      (s_cpuif_wr_data),
        .cpuif_wr_ack       (s_cpuif_wr_ack),
        .cpuif_rd_data      (s_cpuif_rd_data),
        .cpuif_rd_ack       (s_cpuif_rd_ack)
    );

    regs regs_inst (
        .clk   (clk),
        .rst_n (rst_n),

        .s_cpuif_req       (s_cpuif_req),
        .s_cpuif_req_is_wr (s_cpuif_req_is_wr),
        .s_cpuif_addr      (s_cpuif_addr),
        .s_cpuif_wr_data   (s_cpuif_wr_data),
        .s_cpuif_wr_ack    (s_cpuif_wr_ack),
        .s_cpuif_rd_data   (s_cpuif_rd_data),
        .s_cpuif_rd_ack    (s_cpuif_rd_ack),

        .hwif_out          (hwif_out)
    );

    logic [15:0] step;
    assign step = {hwif_out.control_high.value, hwif_out.control_low.value};

    pdm_clk_gen pdm_clk_gen_inst (
        .clk   (clk),
        .rst_n (rst_n),
        .enable (hwif_out.control.enable),
        .step (step),
        .pdm_clk (),
        .pdm_valid ()
    );

    cic #(
        .PIPELINE_ENABLE (1'b0)
    ) cic_inst (
        .clk (clk),
        .rst_n (rst_n),
        .sig_in (pdm_in),
        .sig_in_valid (pdm_in_valid),
        .sig_out (),  // not connected to anything in this top-level module
        .sig_out_valid ()
    );

endmodule : pdm_to_pcm_top
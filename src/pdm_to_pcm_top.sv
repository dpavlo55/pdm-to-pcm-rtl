`include "regs_defs.svh"

module pdm_to_pcm_top
    (
        input logic clk,
        input logic rst_n,

        output logic pdm_clk,
        input logic pdm_data,

        // SPI interface
        input logic spi_sck,
        input logic spi_mosi,
        output logic spi_miso,
        input logic spi_cs_n,

        // I2S output
        output logic i2s_bclk,
        output logic i2s_lrclk,
        output logic i2s_sdata
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

    logic [15:0] step;
    logic pdm_clk_re;
    logic pdm_clk_fe;
    logic [0:0] pdm_data_left;
    logic pdm_data_left_valid;
    logic [0:0] pdm_data_right;
    logic pdm_data_right_valid;
    logic [7:0] cic_data_left;
    logic cic_data_left_valid;
    logic [7:0] cic_data_right;
    logic cic_data_right_valid;

    pdm_to_pcm_reg__out_t hwif_out;
    pdm_to_pcm_reg__in_t hwif_in;

    spi spi_inst (
        .clk             (clk),
        .rst_n           (rst_n),

        // SPI interface
        .sck             (spi_sck),
        .mosi            (spi_mosi),
        .miso            (spi_miso),
        .cs_n            (spi_cs_n),

        .mosi_data       (mosi_data),
        .mosi_data_valid (mosi_data_valid),

        .miso_data       (miso_data),
        .miso_data_valid (miso_data_valid)
    );

    spi_to_regs_adapter spi_to_regs_adapter_inst (
        .clk             (clk),
        .rst_n           (rst_n),

        .mosi_data       (mosi_data),
        .mosi_data_valid (mosi_data_valid),

        .miso_data       (miso_data),
        .miso_data_valid (miso_data_valid),

        .cpuif_req       (s_cpuif_req),
        .cpuif_req_is_wr (s_cpuif_req_is_wr),
        .cpuif_addr      (s_cpuif_addr),
        .cpuif_wr_data   (s_cpuif_wr_data),
        .cpuif_wr_ack    (s_cpuif_wr_ack),
        .cpuif_rd_data   (s_cpuif_rd_data),
        .cpuif_rd_ack    (s_cpuif_rd_ack)
    );

    regs regs_inst (
        .clk               (clk),
        .rst_n             (rst_n),

        .s_cpuif_req       (s_cpuif_req),
        .s_cpuif_req_is_wr (s_cpuif_req_is_wr),
        .s_cpuif_addr      (s_cpuif_addr),
        .s_cpuif_wr_data   (s_cpuif_wr_data),
        .s_cpuif_wr_ack    (s_cpuif_wr_ack),
        .s_cpuif_rd_data   (s_cpuif_rd_data),
        .s_cpuif_rd_ack    (s_cpuif_rd_ack),

        .hwif_out          (hwif_out),
        .hwif_in           (hwif_in)
    );

    assign step = {hwif_out.nco_control.high, hwif_out.nco_control.low};

    pdm_clk_gen pdm_clk_gen_inst (
        .clk        (clk),
        .rst_n      (rst_n),
        .enable     (hwif_out.control.enable),
        .step       (step),
        .pdm_clk    (pdm_clk),
        .pdm_clk_re (pdm_clk_re),
        .pdm_clk_fe (pdm_clk_fe)
    );

    pdm_sampler pdm_sampler_inst (
        .clk                  (clk),
        .rst_n                (rst_n),
        .pdm_clk_re           (pdm_clk_re),
        .pdm_clk_fe           (pdm_clk_fe),
        .pdm_data             (pdm_data),
        .pdm_data_left        (pdm_data_left),
        .pdm_data_left_valid  (pdm_data_left_valid),
        .pdm_data_right       (pdm_data_right),
        .pdm_data_right_valid (pdm_data_right_valid)
    );

    //cic cic_left_inst (
    //    .clk           (clk),
    //    .rst_n         (rst_n),
    //    .sig_in        (pdm_data_left),
    //    .sig_in_valid  (pdm_data_left_valid),
    //    .sig_out       (cic_data_left),
    //    .sig_out_valid (cic_data_left_valid)
    //);

    assign hwif_in.data_left.value = cic_data_left;

    //cic cic_right_inst (
    //    .clk           (clk),
    //    .rst_n         (rst_n),
    //    .sig_in        (pdm_data_right),
    //    .sig_in_valid  (pdm_data_right_valid),
    //    .sig_out       (cic_data_right),
    //    .sig_out_valid (cic_data_right_valid)
    //);

    assign hwif_in.data_right.value = cic_data_right;

    cic_dual_folded cic_dual_folded_inst (
        .clk                 (clk),
        .rst_n               (rst_n),
        .sig_in_left         (pdm_data_left),
        .sig_in_right        (pdm_data_right),
        .sig_in_valid        (pdm_data_right_valid),
        .sig_out_right       (cic_data_right),
        .sig_out_left        (cic_data_left),
        .sig_out_right_valid (cic_data_right_valid),
        .sig_out_left_valid  (cic_data_left_valid)
    );

    i2s i2s_inst (
        .clk              (clk),
        .rst_n            (rst_n),

        .data_left        (cic_data_left),
        .data_left_valid  (cic_data_left_valid),
        .data_right       (cic_data_right),
        .data_right_valid (cic_data_right_valid),

        .pdm_clk          (pdm_clk),
        .pdm_clk_re       (pdm_clk_re),
        .pdm_clk_fe       (pdm_clk_fe),

        .bclk             (i2s_bclk),
        .lrclk            (i2s_lrclk),
        .sdata            (i2s_sdata)
    );

endmodule : pdm_to_pcm_top
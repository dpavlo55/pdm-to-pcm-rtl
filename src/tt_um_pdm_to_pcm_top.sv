`include "regs_defs.svh"

module tt_um_pdm_to_pcm_top
    (
        input logic clk,
        input logic rst_n,

        input logic pdm_in,

        // SPI interface
        input logic spi_sck,
        input logic spi_mosi,
        output logic spi_miso,
        input logic spi_cs_n,

        output pdm_to_pcm_reg__out_t hwif_out
    );

    logic sck_meta, sck;
    logic mosi_meta, mosi;
    logic cs_n_meta, cs_n;
    logic miso;

    logic [7:0] mosi_data;
    logic mosi_data_valid;

    logic [7:0] miso_data;
    logic miso_data_valid;

    logic s_cpuif_req;
    logic s_cpuif_req_is_wr;
    logic [1:0] s_cpuif_addr;
    logic [7:0] s_cpuif_wr_data;
    logic s_cpuif_wr_ack;
    logic [7:0] s_cpuif_rd_data;
    logic s_cpuif_rd_ack;

    assign spi_miso = (cs_n == 1'b0) ? miso : 1'bZ;

    always_ff @(posedge clk) begin
        sck_meta <= spi_sck;
        sck <= sck_meta;
    end

    always_ff @(posedge clk) begin
        mosi_meta <= spi_mosi;
        mosi <= mosi_meta;
    end

    always_ff @(posedge clk) begin
        cs_n_meta <= spi_cs_n;
        cs_n <= cs_n_meta;
    end

    spi spi_inst (
        .clk   (clk),
        .rst_n (rst_n),

        // SPI interface
        .sck   (sck),
        .mosi  (mosi),
        .miso  (miso),
        .cs_n  (cs_n),

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

endmodule : tt_um_pdm_to_pcm_top
module pdm_to_pcm_top
    (
        input logic clk,
        input logic rst_n,

        input logic pdm_in,

        // SPI interface
        input logic spi_clk,
        input logic spi_mosi,
        output logic spi_miso,
        input logic spi_cs_n
    );

    edge_detector #(
        .REG_OUT (1'b0)
    ) pdm_edge_detector (
        .clk (clk),
        .rst_n (rst_n),
        .sig (pdm_in),
        .edge_re (),
        .edge_fe (),
        .edge_rf (spi_miso)
    );

endmodule : pdm_to_pcm_top
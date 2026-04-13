module tt_um_top
    (
        input  wire [7:0] ui_in,    // Dedicated inputs
        output wire [7:0] uo_out,   // Dedicated outputs
        input  wire [7:0] uio_in,   // IOs: Input path
        output wire [7:0] uio_out,  // IOs: Output path
        output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
        input  wire       ena,      // always 1 when the design is powered, so you can ignore it
        input  wire       clk,      // clock
        input  wire       rst_n     // reset_n - low to reset
    );

    logic spi_sck, sck_meta, sck;
    logic spi_mosi, mosi_meta, mosi;
    logic spi_cs_n, cs_n_meta, cs_n;
    logic spi_miso, miso;
    logic pdm_clk, pdm_data;  // pdm_clk is driven by pdm_to_pcm_top (output)

    assign spi_sck = ui_in[0];
    assign spi_mosi = ui_in[1];
    assign spi_cs_n = ui_in[2];
    assign pdm_data = ui_in[3];
    assign uio_out[0] = miso;
    assign uio_out[7:1] = 7'b0;
    assign uio_oe[0] = ~cs_n;  // enable output only when CS is asserted
    assign uio_oe[7:1] = 7'b0;

    assign uo_out[0] = pdm_clk;  // PDM clock output to microphone
    assign uo_out[7:1] = 7'b0;

    assign spi_miso = miso;

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

    pdm_to_pcm_top pdm_to_pcm_top_inst (
        .clk       (clk),
        .rst_n     (rst_n),
        .pdm_clk   (pdm_clk),
        .pdm_data  (pdm_data),
        .spi_sck   (sck),
        .spi_mosi  (mosi),
        .spi_miso  (miso),
        .spi_cs_n  (cs_n)
    );

endmodule : tt_um_top
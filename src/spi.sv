module spi (
    input logic clk,
    input logic rst_n,

    // SPI interface
    input logic sck,
    input logic mosi,
    output logic miso,
    input logic cs_n,

    output logic [7:0] mosi_data,
    output logic mosi_data_valid,

    input logic [7:0] miso_data,
    input logic miso_data_valid
);

    localparam bit [2:0] CNT_MAX = '1;

    logic [7:0] mosi_reg;
    logic [7:0] miso_reg;

    logic sck_re;
    logic sck_fe;
    logic [2:0] sck_cnt;
    logic sck_cnt_ovf;
    logic sck_cnt_ovf_reg;

    assign miso = miso_reg[7];

    edge_detector sck_edge (
        .clk     (clk),
        .sig     (sck),
        .edge_re (sck_re),
        .edge_fe (sck_fe)
    );

    // Framing counts SCK edges; cs_n only enables the MISO driver (tt_um_top).
    wire _unused = cs_n;

    // MOSI processing

    // only read after 8 bits are shifted in, no reset needed
    always_ff @(posedge clk)
        if (sck_re)
            mosi_reg <= {mosi_reg[6:0], mosi};

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sck_cnt <= '0;
        end else if (sck_re) begin
            sck_cnt <= sck_cnt + 1'b1;
        end

    assign sck_cnt_ovf = (sck_cnt == CNT_MAX) && sck_re;

    always_ff @(posedge clk)
        sck_cnt_ovf_reg <= sck_cnt_ovf;

    // stable until the next SCK rising edge
    assign mosi_data = mosi_reg;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            mosi_data_valid <= 1'b0;
        else
            mosi_data_valid <= sck_cnt_ovf_reg;

    // MISO processing
    // Read data is loaded right after the command byte, so the falling edge
    // ending that byte (sck_cnt == 0) must not shift.

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            miso_reg <= '0;
        end else begin
            if (miso_data_valid) begin
                miso_reg <= miso_data;
            end else if (sck_fe && (sck_cnt != '0)) begin
                miso_reg <= {miso_reg[6:0], 1'b0};
            end
        end


endmodule : spi
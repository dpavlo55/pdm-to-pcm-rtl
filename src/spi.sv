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
    logic [7:0] miso_buffer_reg;

    logic sck_re;
    logic sck_fe;
    logic [2:0] sck_cnt;
    logic sck_cnt_ovf;
    logic sck_cnt_ovf_reg;

    assign miso = miso_reg[7];

    edge_detector sck_edge (
        .clk     (clk),
        .rst_n   (rst_n),
        .sig     (sck),
        .edge_re (sck_re),
        .edge_fe (sck_fe),
        .edge_rf ()
    );

    // MOSI processing

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            mosi_reg <= '0;
        end else begin
            if (sck_re) begin
                mosi_reg <= {mosi_reg[6:0], mosi};
            end
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sck_cnt <= '0;
        end else if (sck_re) begin
            sck_cnt <= sck_cnt + 1'b1;
        end

    assign sck_cnt_ovf = (sck_cnt == CNT_MAX) && sck_re;

    always_ff @(posedge clk)
        sck_cnt_ovf_reg <= sck_cnt_ovf;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            mosi_data <= '0;
            mosi_data_valid <= 1'b0;
        end else begin
            mosi_data_valid <= 1'b0;
            if (sck_cnt_ovf_reg) begin
                mosi_data <= mosi_reg;
                mosi_data_valid <= 1'b1;
            end
        end

    // MISO processing

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            miso_buffer_reg <= '0;
        end else begin
            if (miso_data_valid) begin
                miso_buffer_reg <= miso_data;
            end
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            miso_reg <= '0;
        end else begin
            if (sck_fe) begin
                if (sck_cnt == '0) begin
                    miso_reg <= miso_buffer_reg;
                end else begin
                    miso_reg <= {miso_reg[6:0], 1'b0};
                end
            end
        end


endmodule : spi
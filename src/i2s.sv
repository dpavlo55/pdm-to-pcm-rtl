module i2s
    (
        input  logic clk,
        input  logic rst_n,

        // PCM input — signed 16-bit, held stable between valid pulses
        input  logic [15:0] data_left,
        input  logic data_left_valid,
        input  logic [15:0] data_right,
        input  logic data_right_valid,  // unused: both channels update together

        // PDM clock inputs
        input logic pdm_clk,
        input logic pdm_clk_re,
        input logic pdm_clk_fe,

        // I2S outputs
        output logic bclk,
        output logic lrclk,
        output logic sdata
    );

    // LRCLK = 0 -> left channel, LRCLK = 1 -> right channel
    localparam logic LRCLK_LEFT = 1'b0;
    localparam logic LRCLK_RIGHT = 1'b1;

    localparam logic [4:0] BITS_PER_SAMPLE = 5'd16;

    logic data_ready;
    logic ready;

    // word being transmitted, MSB first
    logic [15:0] tx_word;

    logic [4:0] bit_cnt;
    logic lrclk_internal;
    logic [3:0] bit_index;

    // I2S is ready when first data arrives and rising edge is detected on pdm_clk
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            data_ready <= 1'b0;
        end else if (data_left_valid) begin
            data_ready <= 1'b1;
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            ready <= 1'b0;
        end else if (data_ready && pdm_clk_fe) begin
            ready <= 1'b1;
        end

    // bit counter
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            bit_cnt <= 5'd1;
        end else if (ready) begin
            if (pdm_clk_re) begin
                bit_cnt <= bit_cnt - 1'b1;
            end
        end

    assign bit_index = bit_cnt[3:0];
    assign lrclk_internal = ~bit_cnt[4];

    // BCLK generation
    assign bclk = pdm_clk && ready;

    // LRCLK generation
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            lrclk <= LRCLK_RIGHT;
        end else if (ready) begin
            if (pdm_clk_fe) begin
                if (bit_cnt == 5'd0) begin
                    lrclk <= LRCLK_LEFT;
                end else if (bit_cnt == BITS_PER_SAMPLE) begin
                    lrclk <= LRCLK_RIGHT;
                end
            end
        end

    // load the next channel's sample after the current word's LSB, else shift
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            tx_word <= '0;
        end else if (pdm_clk_fe) begin
            if (bit_index == 4'd0) begin
                tx_word <= (lrclk_internal == LRCLK_RIGHT) ? data_left : data_right;
            end else if (ready) begin
                tx_word <= {tx_word[14:0], 1'b0};
            end
        end

    // SDATA generation
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sdata <= 1'b0;
        end else if (ready) begin
            if (pdm_clk_fe) begin
                sdata <= tx_word[15];
            end
        end

    wire _unused = data_right_valid;

endmodule : i2s
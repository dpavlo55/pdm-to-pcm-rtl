module i2s
    (
        input  logic clk,
        input  logic rst_n,

        // PCM input — signed 8-bit, one-cycle valid pulse per sample
        input  logic [15:0] data_left,
        input  logic data_left_valid,
        input  logic [15:0] data_right,
        input  logic data_right_valid,

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

    logic [15:0] reg_data_left_shadow;
    logic [15:0] reg_data_left;
    logic [15:0] reg_data_right_shadow;
    logic [15:0] reg_data_right;

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

    // left shadow register
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            reg_data_left_shadow <= '0;
        end else if (data_left_valid) begin
            reg_data_left_shadow <= data_left;
        end

    // right shadow register
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            reg_data_right_shadow <= '0;
        end else if (data_right_valid) begin
            reg_data_right_shadow <= data_right;
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

    // left data register
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            reg_data_left <= '0;
        end else if (pdm_clk_fe) begin
            if (lrclk_internal == LRCLK_RIGHT && bit_index == 4'd0) begin
                reg_data_left <= reg_data_left_shadow;
            end
        end

    // right data register
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            reg_data_right <= '0;
        end else if (pdm_clk_fe) begin
            if (lrclk_internal == LRCLK_LEFT && bit_index == 4'd0) begin
                reg_data_right <= reg_data_right_shadow;
            end
        end

    // SDATA generation
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sdata <= 1'b0;
        end else if (ready) begin
            if (pdm_clk_fe) begin
                if (lrclk_internal == LRCLK_LEFT) begin
                    sdata <= reg_data_left[bit_index];
                end else begin
                    sdata <= reg_data_right[bit_index];
                end
            end
        end

endmodule : i2s
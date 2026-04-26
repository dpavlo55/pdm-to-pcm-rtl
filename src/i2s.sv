// Philips I2S transmitter — 16-bit stereo, 32-BCLK frame
//
// Frame timing (Philips I2S):
//   BCLK falls → LRCLK and SDATA update
//   BCLK rises → receiver samples SDATA
//   LRCLK = 0 : left channel  (bits 0..15 of the frame)
//   LRCLK = 1 : right channel (bits 16..31 of the frame)
//
// The 8-bit CIC output is MSB-aligned in a 16-bit word, lower byte zero-padded.
// Frame rate tracks the CIC output rate automatically:
//   new samples are latched into holding registers on each valid pulse,
//   and loaded into the shift register at every frame boundary.
//   No explicit rate configuration is needed.

module i2s
    #(
        parameter int BCLK_DIV = 8  // BCLK = clk / BCLK_DIV; must be even and >= 2
    )
    (
        input  logic clk,
        input  logic rst_n,

        // PCM input — signed 8-bit, one-cycle valid pulse per sample
        input  logic [7:0] data_left,
        input  logic data_left_valid,
        input  logic [7:0] data_right,
        input  logic data_right_valid,

        // I2S outputs
        output logic bclk,
        output logic lrclk,
        output logic sdata
    );

    // -------------------------------------------------------------------------
    // BCLK generation
    //   bclk_fe: single sys_clk pulse coinciding with the BCLK falling edge
    // -------------------------------------------------------------------------
    localparam int BCLK_HALF = BCLK_DIV / 2;
    localparam int BCLK_CNT_W = $clog2(BCLK_DIV);

    // Frame geometry
    localparam int WORD_BITS = 16;
    localparam int FRAME_BITS = WORD_BITS * 2;
    localparam int BIT_CNT_W = $clog2(FRAME_BITS);
    localparam logic [BIT_CNT_W-1:0] LAST_BIT = BIT_CNT_W'(FRAME_BITS - 1);
    localparam logic [BIT_CNT_W-1:0] CHANNEL_BOUNDARY = BIT_CNT_W'(WORD_BITS - 1);

    logic [BCLK_CNT_W-1:0] bclk_cnt;
    logic bclk_fe;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            bclk_cnt <= '0;
        else if (bclk_cnt == BCLK_DIV - 1)
            bclk_cnt <= '0;
        else
            bclk_cnt <= bclk_cnt + 1'b1;

    assign bclk_fe = (bclk_cnt == BCLK_HALF - 1);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            bclk <= 1'b1;
        else if (bclk_cnt == BCLK_HALF - 1)
            bclk <= 1'b0;
        else if (bclk_cnt == BCLK_DIV - 1)
            bclk <= 1'b1;

    // -------------------------------------------------------------------------
    // Sample holding registers
    //   Latched on every valid pulse; MSB-aligned, lower 8 bits zero-padded.
    // -------------------------------------------------------------------------
    logic [WORD_BITS-1:0] hold_left, hold_right;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            hold_left <= '0;
        else if (data_left_valid)
            hold_left <= {data_left, 8'h00};

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            hold_right <= '0;
        else if (data_right_valid)
            hold_right <= {data_right, 8'h00};

    // -------------------------------------------------------------------------
    // Frame serializer
    //
    // shift_reg layout after frame load:
    //   shift_reg[FRAME_BITS-1:WORD_BITS] = hold_left  (MSB first)
    //   shift_reg[WORD_BITS-1:0]          = hold_right (MSB first)
    //
    // bit_cnt runs 0..LAST_BIT, incremented on each bclk_fe.
    // At LAST_BIT the serializer stalls until sample_ready is set by
    // data_left_valid, then loads holding registers and starts the next frame.
    // This makes LRCLK track the CIC output rate (f_PDM / R) automatically.
    // lrclk goes high at CHANNEL_BOUNDARY (right channel starts).
    // -------------------------------------------------------------------------
    logic [FRAME_BITS-1:0] shift_reg;
    logic [BIT_CNT_W-1:0] bit_cnt;
    logic sample_ready;

    // Set by data_left_valid pulse, cleared when the frame loads.
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) sample_ready <= 1'b0;
        else if (data_left_valid) sample_ready <= 1'b1;
        else if (bclk_fe && bit_cnt == LAST_BIT && sample_ready) sample_ready <= 1'b0;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= '0;
            bit_cnt <= LAST_BIT;
            lrclk <= 1'b1;
            sdata <= 1'b0;
        end else if (bclk_fe) begin
            sdata <= shift_reg[FRAME_BITS-1];
            if (bit_cnt == LAST_BIT && sample_ready) begin
                // New sample available: load and start next frame
                shift_reg <= {hold_left, hold_right};
                lrclk <= 1'b0;
                bit_cnt <= '0;
            end else if (bit_cnt != LAST_BIT) begin
                shift_reg <= {shift_reg[FRAME_BITS-2:0], 1'b0};
                if (bit_cnt == CHANNEL_BOUNDARY)
                    lrclk <= 1'b1;
                bit_cnt <= bit_cnt + 1'b1;
            end
        end
    end

endmodule : i2s

// =============================================================================
// cic_dual_folded — stereo CIC decimator, N=3, R=32, M=1, 16-bit PCM output
// =============================================================================
// State: 3 integrators + 3 comb delays per channel, held in two 6-word rings
// that rotate by one word every clock. `slot` tracks which word is at the head:
//
//   slot             :   0     1     2     3     4     5
//   integ_ring[0]    :  L.i0  L.i1  L.i2  R.i0  R.i1  R.i2
//   comb_ring[0]     :  R.d0  R.d1  R.d2  L.d0  L.d1  L.d2
//
// A PDM pair is integrated during the rotation after it arrives. On decimation
// pairs the left combs run in slots 3-5 of that rotation and the right combs in
// slots 0-2 of the next one. PDM pairs must be >= 7 clk apart.
//
// Arithmetic (bit-exact with cic16_model.svh): PDM bits are 0/1, so the ideal
// output S is in [0, 32768]. State wraps modulo 2^15; S = 0 and S = 32768 both
// give 0 and are told apart by the newest PDM bit (1 only for S = 32768).
// Output: pcm = 2*S - 32768, saturated to +32767.
// =============================================================================

module cic_dual_folded
    (
        input  logic        clk,
        input  logic        rst_n,
        input  logic [0:0]  sig_in_left,
        input  logic [0:0]  sig_in_right,
        input  logic        sig_in_valid,
        output logic [15:0] sig_out_left,
        output logic [15:0] sig_out_right,
        output logic        sig_out_left_valid,
        output logic        sig_out_right_valid
    );

    localparam int STATE_W = 15;
    localparam logic [4:0] DECIM_MAX = 5'd31;   // R - 1

    //--------------------------------------------------------------------------
    // Ring position and sequencing
    //--------------------------------------------------------------------------
    logic [2:0] slot;                   // word at the ring heads (0..5)
    logic       slot_wrap;              // last slot of a rotation

    logic       pending_valid;          // a PDM pair waits for the next rotation
    logic       pending_decim;          // the waiting pair is a decimation pair
    logic       pending_pdm_left;       // PDM bits of the waiting pair
    logic       pending_pdm_right;
    logic [4:0] decim_cnt;

    logic       integ_active;           // this rotation integrates a pair
    logic       comb_left_active;       // left combs run in slots 3-5
    logic       comb_right_active;      // right combs run in slots 0-2
    logic       active_pdm_left;        // PDM bits of the pair being integrated
    logic       active_pdm_right;
    logic       decim_pdm_right;        // right PDM bit of the decimation pair
    logic       clear_rings;            // first rotation after reset

    assign slot_wrap = (slot == 3'd5);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            slot <= 3'd0;
        else
            slot <= slot_wrap ? 3'd0 : slot + 3'd1;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            pending_valid <= 1'b0;
            pending_decim <= 1'b0;
            decim_cnt     <= '0;
        end else begin
            if (slot_wrap)
                pending_valid <= 1'b0;
            if (sig_in_valid) begin
                pending_valid <= 1'b1;
                pending_decim <= (decim_cnt == DECIM_MAX);
                decim_cnt     <= (decim_cnt == DECIM_MAX) ? 5'd0 : decim_cnt + 5'd1;
            end
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            integ_active      <= 1'b0;
            comb_left_active  <= 1'b0;
            comb_right_active <= 1'b0;
            clear_rings       <= 1'b1;
        end else if (slot_wrap) begin
            integ_active      <= pending_valid;
            comb_left_active  <= pending_valid && pending_decim;
            comb_right_active <= comb_left_active;
            clear_rings       <= 1'b0;
        end

    // written before use, no reset needed
    always_ff @(posedge clk) begin
        if (sig_in_valid) begin
            pending_pdm_left  <= sig_in_left;
            pending_pdm_right <= sig_in_right;
        end
        if (slot_wrap) begin
            active_pdm_left  <= pending_pdm_left;
            active_pdm_right <= pending_pdm_right;
            decim_pdm_right  <= active_pdm_right;
        end
    end

    //--------------------------------------------------------------------------
    // Integrators: head <= head + (first stage ? PDM bit : previous stage)
    // The previous stage's new value is the word just written to the tail.
    // The rings have no reset; zeros are shifted in during clear_rings.
    //--------------------------------------------------------------------------
    logic [STATE_W-1:0] integ_ring [0:5];
    logic               integ_first_stage;
    logic               integ_pdm_bit;
    logic [STATE_W-1:0] integ_addend;
    logic [STATE_W-1:0] integ_sum;

    assign integ_first_stage = (slot == 3'd0) || (slot == 3'd3);
    assign integ_pdm_bit     = slot[0] ? active_pdm_right : active_pdm_left;  // slot 3 / slot 0
    assign integ_addend      = integ_first_stage ? {{(STATE_W-1){1'b0}}, integ_pdm_bit}
                                                 : integ_ring[5];
    assign integ_sum         = integ_ring[0] + integ_addend;

    always_ff @(posedge clk) begin
        for (int i = 0; i < 5; i++) integ_ring[i] <= integ_ring[i+1];
        integ_ring[5] <= clear_rings ? '0 : (integ_active ? integ_sum : integ_ring[0]);
    end

    //--------------------------------------------------------------------------
    // Combs: output = input - delay, delay <= input
    // Stage 0 input is the new i2 (tail of integ_ring), later stages take the
    // previous comb output.
    //--------------------------------------------------------------------------
    logic [STATE_W-1:0] comb_ring [0:5];
    logic               comb_active;
    logic               comb_first_stage;
    logic               comb_last_stage;
    logic [STATE_W-1:0] comb_input;
    logic [STATE_W-1:0] comb_output;
    logic [STATE_W-1:0] comb_prev;

    assign comb_active      = (slot >= 3'd3) ? comb_left_active : comb_right_active;
    assign comb_first_stage = (slot == 3'd0) || (slot == 3'd3);
    assign comb_last_stage  = (slot == 3'd2) || (slot == 3'd5);
    assign comb_input       = comb_first_stage ? integ_ring[5] : comb_prev;
    assign comb_output      = comb_input - comb_ring[0];

    always_ff @(posedge clk) begin
        for (int i = 0; i < 5; i++) comb_ring[i] <= comb_ring[i+1];
        comb_ring[5] <= clear_rings ? '0 : (comb_active ? comb_input : comb_ring[0]);
    end

    // only read right after it is written, no reset needed
    always_ff @(posedge clk)
        comb_prev <= comb_output;

    //--------------------------------------------------------------------------
    // Outputs
    //--------------------------------------------------------------------------
    logic [15:0] pcm;
    logic        newest_pdm_bit;
    logic        saturate;
    logic        left_done;
    logic        right_done;

    assign newest_pdm_bit = slot[2] ? active_pdm_left : decim_pdm_right;  // slot 5 / slot 2
    assign saturate       = (comb_output == '0) && newest_pdm_bit;        // S == 32768
    assign pcm            = saturate ? 16'h7FFF
                                     : {~comb_output[STATE_W-1], comb_output[STATE_W-2:0], 1'b0};
    assign left_done      = comb_active && comb_last_stage && slot[2];
    assign right_done     = comb_active && comb_last_stage && !slot[2];

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            sig_out_left <= '0;
        else if (left_done)
            sig_out_left <= pcm;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            sig_out_right <= '0;
        else if (right_done)
            sig_out_right <= pcm;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sig_out_left_valid  <= 1'b0;
            sig_out_right_valid <= 1'b0;
        end else begin
            sig_out_left_valid  <= left_done;
            sig_out_right_valid <= right_done;
        end

endmodule : cic_dual_folded

// =============================================================================
// cic_dual_folded — area-optimised stereo CIC decimator, 16-bit output
// =============================================================================
//   N = 3 (stages), R = 32 (decimation), M = 1 (differential delay)
//   Bin = 1 (PDM), internal width = 16 bits, Bout = 16 bits (signed PCM)
//
// Architecture
// ------------
// Both channels share a single 16-bit adder. The filter state (3 integrators +
// 3 comb delays per channel = 12 words) lives in two 6-word "carousel" shift
// registers that rotate past the adder, so no read multiplexer tree is needed:
//
//   sr_int  : [L.i0 L.i1 L.i2 R.i0 R.i1 R.i2]   (rotates on integrator steps)
//   sr_comb : [L.d0 L.d1 L.d2 R.d0 R.d1 R.d2]   (rotates on comb steps)
//
// The only extra datapath register is `acc`, which carries the result of the
// previous step into the next one (integrator cascade / comb cascade).
//
// One PDM sample pair (left captured on the rising PDM edge, right on the
// falling edge) is processed when sig_in_valid is seen:
//
//   non-decimation pair :  L.I0 L.I1 L.I2 R.I0 R.I1 R.I2                (6 clk)
//   decimation pair     :  L.I0 L.I1 L.I2 L.C0 L.C1 L.C2
//                          R.I0 R.I1 R.I2 R.C0 R.C1 R.C2               (12 clk)
//
// so sig_in_valid must be at least 13 clk cycles apart (fclk / fPDM >= 13,
// i.e. fPDM <= 3.8 MHz at 50 MHz).
//
// Arithmetic (bit-exact with the reference model cic16_model.svh)
// ----------------------------------------------------------------
// The PDM input is mapped unipolar (1 -> 1, 0 -> 0). The ideal CIC output is
// then S = sum(h[k] * x[n-k]) with 0 <= S <= R^N = 32768, which fits in 16
// unsigned bits, so all integrators / combs may wrap modulo 2^16 (Hogenauer)
// and the final comb still yields S exactly.
//   integrators : i0 += x ; i1 += i0' ; i2 += i1'        (updated values cascade)
//   combs       : c0 = i2 - d0 ; c1 = c0 - d1 ; c2 = c1 - d2 ; d_k <= input_k
// S is mapped to full-scale signed 16-bit PCM:
//   pcm = 2*S - 32768, saturated to +32767 (only for S == 32768).
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

    localparam int W = 16;
    localparam logic [4:0] DEC_MAX = 5'd31;   // R - 1

    //--------------------------------------------------------------------------
    // State
    //--------------------------------------------------------------------------
    logic [W-1:0] sr_int  [0:5];
    logic [W-1:0] sr_comb [0:5];
    logic [W-1:0] acc;

    logic         x_left, x_right;     // captured PDM bits of the current pair
    logic         busy;
    logic         ch;                  // 0 = left, 1 = right
    logic         comb;                // 0 = integrator steps, 1 = comb steps
    logic [1:0]   stage;               // 0..2
    logic         decim;               // current pair is a decimation pair
    logic [4:0]   dec_cnt;

    //--------------------------------------------------------------------------
    // ALU (single shared 16-bit adder)
    //   integrator step : sr_int[0] + opb
    //   comb step       : opb - sr_comb[0] = opb + ~sr_comb[0] + 1
    //--------------------------------------------------------------------------
    logic         first;
    logic [W-1:0] opb;
    logic [W-1:0] opa;
    logic [W-1:0] alu_out;

    assign first   = !comb && (stage == 2'd0);
    assign opb     = first ? {{(W-1){1'b0}}, (ch ? x_right : x_left)} : acc;
    assign opa     = comb ? ~sr_comb[0] : sr_int[0];
    assign alu_out = opb + opa + {{(W-1){1'b0}}, comb};

    // Full-scale signed mapping with saturation: pcm = 2*S - 32768
    // (S[15] set only for S == 32768 -> saturate to +32767)
    logic [W-1:0] pcm;
    assign pcm = alu_out[W-1] ? {1'b0, {(W-1){1'b1}}}
                              : {~alu_out[W-2], alu_out[W-3:0], 1'b0};

    //--------------------------------------------------------------------------
    // Carousels (no reset-value dependency on control; async reset to zero)
    //--------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            for (int i = 0; i < 6; i++) sr_int[i] <= '0;
        end else if (busy && !comb) begin
            for (int i = 0; i < 5; i++) sr_int[i] <= sr_int[i+1];
            sr_int[5] <= alu_out;
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            for (int i = 0; i < 6; i++) sr_comb[i] <= '0;
        end else if (busy && comb) begin
            for (int i = 0; i < 5; i++) sr_comb[i] <= sr_comb[i+1];
            sr_comb[5] <= acc;          // delay <= comb stage input
        end

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            acc <= '0;
        else if (busy)
            acc <= alu_out;

    //--------------------------------------------------------------------------
    // Sequencer
    //--------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            busy    <= 1'b0;
            ch      <= 1'b0;
            comb    <= 1'b0;
            stage   <= 2'd0;
            decim   <= 1'b0;
            dec_cnt <= '0;
            x_left  <= 1'b0;
            x_right <= 1'b0;
        end else if (!busy) begin
            if (sig_in_valid) begin
                busy    <= 1'b1;
                x_left  <= sig_in_left;
                x_right <= sig_in_right;
                decim   <= (dec_cnt == DEC_MAX);
                dec_cnt <= (dec_cnt == DEC_MAX) ? 5'd0 : dec_cnt + 5'd1;
            end
        end else if (stage != 2'd2) begin
            stage <= stage + 2'd1;
        end else begin
            stage <= 2'd0;
            if (!comb && decim) begin
                comb <= 1'b1;
            end else if (!ch) begin
                ch   <= 1'b1;
                comb <= 1'b0;
            end else begin
                busy <= 1'b0;
                ch   <= 1'b0;
                comb <= 1'b0;
            end
        end

    //--------------------------------------------------------------------------
    // Outputs — updated after the last comb stage of each channel
    //--------------------------------------------------------------------------
    logic last_comb;
    assign last_comb = busy && comb && (stage == 2'd2);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            sig_out_left <= '0;
        else if (last_comb && !ch)
            sig_out_left <= pcm;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            sig_out_right <= '0;
        else if (last_comb && ch)
            sig_out_right <= pcm;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            sig_out_left_valid  <= 1'b0;
            sig_out_right_valid <= 1'b0;
        end else begin
            sig_out_left_valid  <= last_comb && !ch;
            sig_out_right_valid <= last_comb && ch;
        end

endmodule : cic_dual_folded

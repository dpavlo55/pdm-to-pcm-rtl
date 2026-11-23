// =============================================================================
// cic_dual_folded — stereo CIC decimator, N=4, R=32, M=1, 16-bit PCM output
// =============================================================================
// Computed in non-recursive form: the CIC impulse response h (125 taps) spans
// four output periods, so each channel keeps four accumulators of different
// age. For sample j (0..31) of a period, the accumulator of age a (0..3) adds
// the PDM bit times h[(3-a)*32 + 31-j] (table below). At j = 31 the age-3
// accumulator is the output and restarts at 0; then every accumulator ages by
// one (`phase` advances).
//
// The eight accumulators sit in a ring that rotates one word per clock; `slot`
// is the word at the head (0-3 left, 4-7 right). A PDM pair waits at most one
// rotation and is accumulated during the next, so pairs must be >= 8 clk apart.
//
// Arithmetic (bit-exact with cic16_model.svh): PDM bits are 0/1 and h sums to
// 2^20, so the ideal output S is in [0, 2^20]. State wraps modulo 2^20; S = 0
// and S = 2^20 both give 0 and are told apart by the newest PDM bit (1 only
// for S = 2^20). Output: pcm = (2*S - 2^20) / 32, saturated to +32767.
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

    localparam int STATE_W = 20;
    localparam int WEIGHT_W = 15;
    localparam logic [4:0] LAST_SAMPLE = 5'd31;   // R - 1

    //--------------------------------------------------------------------------
    // Ring position and sequencing
    //--------------------------------------------------------------------------
    logic [2:0] slot;                   // word at the ring head (0..7)
    logic       slot_wrap;              // last slot of a rotation
    logic       slot_right;             // head word belongs to the right channel

    logic       pending_valid;          // a PDM pair waits for the next rotation
    logic       pending_pdm_left;       // PDM bits of the waiting pair
    logic       pending_pdm_right;
    logic [4:0] sample_cnt;             // position in the decimation period

    logic       accum_active;           // this rotation accumulates a pair
    logic       active_pdm_left;        // PDM bits of the pair being accumulated
    logic       active_pdm_right;
    logic [4:0] active_sample;          // its position in the period
    logic       active_last;            // it is the last sample of the period
    logic [1:0] phase;                  // age of word 0 of each channel
    logic       clear_ring;             // first rotation after reset

    assign slot_wrap  = (slot == 3'd7);
    assign slot_right = slot[2];

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            slot <= 3'd0;
        else
            slot <= slot + 3'd1;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            pending_valid <= 1'b0;
            sample_cnt    <= '0;
        end else begin
            if (slot_wrap)
                pending_valid <= 1'b0;
            if (sig_in_valid) begin
                pending_valid <= 1'b1;
                sample_cnt    <= sample_cnt + 5'd1;
            end
        end

    // sample_cnt has already counted the active pair, and the pending one too
    assign active_sample = sample_cnt - 5'd1 - {4'd0, pending_valid};
    assign active_last   = (active_sample == LAST_SAMPLE);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            accum_active <= 1'b0;
            phase        <= 2'd0;
            clear_ring   <= 1'b1;
        end else if (slot_wrap) begin
            accum_active <= pending_valid;
            clear_ring   <= 1'b0;
            if (accum_active && active_last)
                phase <= phase + 2'd1;
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
        end
    end

    //--------------------------------------------------------------------------
    // Tap weight of the head word
    //--------------------------------------------------------------------------
    logic [1:0]                age;
    logic                      fold;        // ages 2-3 mirror ages 1-0 (h is symmetric)
    logic [5:0]                tap_index;   // j, or 34-j when folded
    logic [1:0][WEIGHT_W-1:0]  weights;     // {age 1, age 0} weights at tap_index
    logic [WEIGHT_W-1:0]       weight;

    assign age       = slot[1:0] + phase;
    assign fold      = age[1];
    assign tap_index = fold ? 6'd34 - {1'b0, active_sample} : {1'b0, active_sample};

    // weight(age, j) = h[(3-age)*32 + 31-j]; h[k] = h[124-k] gives
    // weight(3-a, j) = weight(a, 34-j), so only ages 0 and 1 are tabulated
    always_comb
        case (tap_index)
            6'd0 : weights = {15'd4960 , 15'd0    };
            6'd1 : weights = {15'd5456 , 15'd0    };
            6'd2 : weights = {15'd5984 , 15'd0    };
            6'd3 : weights = {15'd6541 , 15'd1    };
            6'd4 : weights = {15'd7124 , 15'd4    };
            6'd5 : weights = {15'd7730 , 15'd10   };
            6'd6 : weights = {15'd8356 , 15'd20   };
            6'd7 : weights = {15'd8999 , 15'd35   };
            6'd8 : weights = {15'd9656 , 15'd56   };
            6'd9 : weights = {15'd10324, 15'd84   };
            6'd10: weights = {15'd11000, 15'd120  };
            6'd11: weights = {15'd11681, 15'd165  };
            6'd12: weights = {15'd12364, 15'd220  };
            6'd13: weights = {15'd13046, 15'd286  };
            6'd14: weights = {15'd13724, 15'd364  };
            6'd15: weights = {15'd14395, 15'd455  };
            6'd16: weights = {15'd15056, 15'd560  };
            6'd17: weights = {15'd15704, 15'd680  };
            6'd18: weights = {15'd16336, 15'd816  };
            6'd19: weights = {15'd16949, 15'd969  };
            6'd20: weights = {15'd17540, 15'd1140 };
            6'd21: weights = {15'd18106, 15'd1330 };
            6'd22: weights = {15'd18644, 15'd1540 };
            6'd23: weights = {15'd19151, 15'd1771 };
            6'd24: weights = {15'd19624, 15'd2024 };
            6'd25: weights = {15'd20060, 15'd2300 };
            6'd26: weights = {15'd20456, 15'd2600 };
            6'd27: weights = {15'd20809, 15'd2925 };
            6'd28: weights = {15'd21116, 15'd3276 };
            6'd29: weights = {15'd21374, 15'd3654 };
            6'd30: weights = {15'd21580, 15'd4060 };
            6'd31: weights = {15'd21731, 15'd4495 };
            6'd32: weights = {15'd21824, 15'd4960 };
            6'd33: weights = {15'd21856, 15'd5456 };
            6'd34: weights = {15'd21824, 15'd5984 };
            default: weights = 'x;
        endcase

    assign weight = weights[age[0] ^ age[1]];

    //--------------------------------------------------------------------------
    // Accumulator ring: head <= head + PDM bit * weight (+ 0 when idle)
    // The ring has no reset; zeros are shifted in during clear_ring.
    //--------------------------------------------------------------------------
    logic [STATE_W-1:0] accum_ring [0:7];
    logic               pdm_bit;
    logic               add_weight;     // accumulate active and PDM bit is 1
    logic [STATE_W-1:0] accum_sum;
    logic               output_word;    // head is the finished age-3 accumulator

    assign pdm_bit     = slot_right ? active_pdm_right : active_pdm_left;
    assign add_weight  = accum_active && pdm_bit;
    assign accum_sum   = accum_ring[0] + (add_weight ? {{(STATE_W-WEIGHT_W){1'b0}}, weight} : '0);
    assign output_word = accum_active && active_last && (age == 2'd3);

    always_ff @(posedge clk) begin
        for (int i = 0; i < 7; i++) accum_ring[i] <= accum_ring[i+1];
        accum_ring[7] <= (clear_ring || output_word) ? '0 : accum_sum;
    end

    //--------------------------------------------------------------------------
    // Outputs
    //--------------------------------------------------------------------------
    logic [15:0] pcm;
    logic        saturate;
    logic        left_done;
    logic        right_done;

    assign saturate   = (accum_sum == '0) && pdm_bit;                       // S == 2^20
    // when saturating accum_sum is 0, so ORing in the ones gives 16'h7FFF
    assign pcm        = {~(accum_sum[STATE_W-1] || saturate),
                         accum_sum[STATE_W-2:STATE_W-16] | {15{saturate}}};
    assign left_done  = output_word && !slot_right;
    assign right_done = output_word && slot_right;

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

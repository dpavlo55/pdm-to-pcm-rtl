`timescale 1ns/1ps

module cic_comp #(
    parameter int DATA_WIDTH = 24
)(
    input  logic clk,
    input  logic rst_n,
    input  logic signed [DATA_WIDTH-1:0] data_in,
    input  logic valid_in,

    output logic signed [DATA_WIDTH-1:0] data_out,
    output logic valid_out
);

    // Shift register for the 3 taps
    logic signed [DATA_WIDTH-1:0] tap [0:2];
    logic valid_q;

    // Arithmetic paths with expanded widths to prevent overflow during addition
    logic signed [DATA_WIDTH:0]   sum_edges;
    logic signed [DATA_WIDTH+1:0] middle_tap;
    logic signed [DATA_WIDTH+1:0] edge_taps;
    logic signed [DATA_WIDTH+1:0] cfir_out_full;

    // 1. Symmetric Pre-Adders
    assign sum_edges  = signed'(tap[0]) + signed'(tap[2]);

    // 2. Bit-Shift Arithmetic for standard coefficients
    // Tap 1: 1.125 * x = x + (x / 8) -> x + (x >>> 3)
    assign middle_tap = signed'(tap[1]) + (signed'(tap[1]) >>> 3);

    // Taps 0 and 2: -0.0625 * (x0 + x2) = -(sum) / 16 -> -(sum >>> 4)
    assign edge_taps  = -(sum_edges >>> 4);

    // Combine for final result
    assign cfir_out_full = middle_tap + edge_taps;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tap[0] <= '0;
            tap[1] <= '0;
            tap[2] <= '0;
            valid_q <= 1'b0;
            valid_out <= 1'b0;
            data_out <= '0;
        end else begin
            // Shift the samples when new valid data arrives
            if (valid_in) begin
                tap[0] <= data_in;
                tap[1] <= tap[0];
                tap[2] <= tap[1];
            end

            // Delay the valid signal to match calculations
            valid_q <= valid_in;
            valid_out <= valid_q;

            // Register the calculated output
            if (valid_q) begin
                data_out <= DATA_WIDTH'(cfir_out_full);
            end
        end
    end

endmodule

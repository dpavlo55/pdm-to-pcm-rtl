// Rising and falling edge strobes of a signal that is synchronous to clk:
// each strobe is high for the one clock cycle after the edge.
module edge_detector
    (
        input logic clk,
        input logic sig,
        output logic edge_re,
        output logic edge_fe
    );

    logic sig_d;

    always_ff @(posedge clk)
        sig_d <= sig;

    assign edge_re = sig && ~sig_d;
    assign edge_fe = ~sig && sig_d;

endmodule

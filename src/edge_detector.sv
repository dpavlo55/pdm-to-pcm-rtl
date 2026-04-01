module edge_detector
    #(
        parameter bit REG_OUT = 1'b0
    )
    (
        input logic clk,
        input logic rst_n,
        input logic sig,
        output logic edge_re,
        output logic edge_fe,
        output logic edge_rf
    );

    logic sig_d;

    always_ff @(posedge clk)
        sig_d <= sig;

    if (REG_OUT) begin

        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                edge_re <= 1'b0;
                edge_fe <= 1'b0;
                edge_rf <= 1'b0;
            end else begin
                edge_re <= sig && ~sig_d;
                edge_fe <= ~sig && sig_d;
                edge_rf <= sig && ~sig_d || ~sig && sig_d;
            end
        end

    end else begin

        assign edge_re = sig && ~sig_d;
        assign edge_fe = ~sig && sig_d;
        assign edge_rf = sig && ~sig_d || ~sig && sig_d;

    end

endmodule
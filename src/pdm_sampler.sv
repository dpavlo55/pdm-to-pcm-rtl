module pdm_sampler (
    input logic clk,
    input logic rst_n,
    input logic pdm_clk_re,
    input logic pdm_clk_fe,
    input logic pdm_data,
    output logic [0:0] pdm_data_left,
    output logic pdm_data_left_valid,
    output logic [0:0] pdm_data_right,
    output logic pdm_data_right_valid
);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            pdm_data_left <= 1'b0;
            pdm_data_left_valid <= 1'b0;
            pdm_data_right <= 1'b0;
            pdm_data_right_valid <= 1'b0;
        end else if (pdm_clk_re) begin
            pdm_data_left <= pdm_data;
            pdm_data_left_valid <= 1'b1;
        end else if (pdm_clk_fe) begin
            pdm_data_right <= pdm_data;
            pdm_data_right_valid <= 1'b1;
        end else begin
            pdm_data_left_valid <= 1'b0;
            pdm_data_right_valid <= 1'b0;
        end

endmodule : pdm_sampler
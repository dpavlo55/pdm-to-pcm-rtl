module pdm_clk_gen #(
    parameter int N = 16
) (
    input logic clk,
    input logic rst_n,
    input logic enable,
    input logic [N-1:0] step,
    output logic pdm_clk,
    output logic pdm_clk_re,
    output logic pdm_clk_fe
);

    logic [N-1:0] acc;
    logic carry;
    logic pdm_clk_reg;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            {carry, acc} <= '0;
        else if (enable)
            {carry, acc} <= acc + step;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            pdm_clk_reg <= 1'b0;
        else if (carry)
            pdm_clk_reg <= ~pdm_clk_reg;

    always_ff @(posedge clk or negedge rst_n)
        pdm_clk <= pdm_clk_reg;

    edge_detector pdm_clk_edge_inst (
        .clk     (clk),
        .rst_n   (rst_n),
        .sig     (pdm_clk_reg),
        .edge_re (pdm_clk_re),
        .edge_fe (pdm_clk_fe),
        .edge_rf ()
    );

endmodule : pdm_clk_gen
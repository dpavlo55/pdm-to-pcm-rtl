module pdm_clk_gen #(
    parameter int N = 16
) (
    input  logic clk,
    input  logic rst_n,
    input  logic [N-1:0] step,
    output logic pdm_clk,
    output logic pdm_valid
);

    logic [N-1:0] acc;
    logic carry;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            {carry, acc} <= '0;
        else
            {carry, acc} <= acc + step;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            pdm_clk <= 1'b0;
        else if (carry)
            pdm_clk <= ~pdm_clk;

    assign pdm_valid = carry;

endmodule : pdm_clk_gen
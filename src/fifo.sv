module fifo #(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 4
)(
    input  logic                  clk,
    input  logic                  rst_n,
    input  logic                  wr_en,
    input  logic [DATA_WIDTH-1:0] din,
    input  logic                  rd_en,
    output logic [DATA_WIDTH-1:0] dout,
    output logic                  full,
    output logic                  empty
);

    localparam DEPTH = 1 << ADDR_WIDTH;

    logic [DATA_WIDTH-1:0] mem [DEPTH-1:0];
    logic [ADDR_WIDTH:0] wr_ptr;
    logic [ADDR_WIDTH:0] rd_ptr;

    assign empty = (wr_ptr == rd_ptr);
    assign full =
        (wr_ptr[ADDR_WIDTH] != rd_ptr[ADDR_WIDTH]) &&
        (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            wr_ptr <= 0;
        end else if (wr_en && !full) begin
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= din;
            wr_ptr <= wr_ptr + 1;
        end

    assign dout = mem[rd_ptr[ADDR_WIDTH-1:0]];

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            rd_ptr <= 0;
        end else if (rd_en && !empty) begin
            rd_ptr <= rd_ptr + 1;
        end

endmodule
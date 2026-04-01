import regs_pkg::REGS_MIN_ADDR_WIDTH;

module spi_to_regs_adapter (
    input logic clk,
    input logic rst_n,

    input logic [7:0] mosi_data,
    input logic mosi_data_valid,

    output logic [7:0] miso_data,
    output logic miso_data_valid,

    output logic cpuif_req,
    output logic cpuif_req_is_wr,
    output logic [REGS_MIN_ADDR_WIDTH-1:0] cpuif_addr,
    output logic [7:0] cpuif_wr_data,
    output logic [7:0] cpuif_wr_biten,
    input logic cpuif_req_stall_wr,
    input logic cpuif_req_stall_rd,
    input logic cpuif_rd_ack,
    input logic cpuif_rd_err,
    input logic [7:0] cpuif_rd_data,
    input logic cpuif_wr_ack,
    input logic cpuif_wr_err
);

    typedef enum logic [1:0] {
        IDLE,
        WRITE,
        READ,
        WAIT
    } state_t;

    // types
    typedef enum logic [2:0] {
        SPI_READ = 3'b000,
        SPI_WRITE = 3'b001
    } cmd_t;

    state_t state;
    logic [REGS_MIN_ADDR_WIDTH-1:0] addr;

    assign cpuif_wr_biten = '1;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            state <= IDLE;
            cpuif_req <= 1'b0;
            cpuif_req_is_wr <= 1'b0;
            cpuif_addr <= '0;
            cpuif_wr_data <= '0;
            miso_data <= '0;
            miso_data_valid <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    cpuif_req <= 1'b0;
                    miso_data_valid <= 1'b0;
                    if (mosi_data_valid) begin
                        if (mosi_data[7:5] == SPI_WRITE) begin
                            state <= WRITE;
                            cpuif_req_is_wr <= 1'b1;
                            cpuif_addr <= mosi_data[REGS_MIN_ADDR_WIDTH-1:0];
                            cpuif_wr_data <= mosi_data;
                        end else if (mosi_data[7:5] == SPI_READ) begin
                            state <= READ;
                            cpuif_req_is_wr <= 1'b0;
                            cpuif_addr <= mosi_data[REGS_MIN_ADDR_WIDTH-1:0];
                            cpuif_req <= 1'b1;
                        end else begin
                            state <= IDLE; // Invalid command, stay in IDLE
                        end
                    end
                end
                WRITE: begin
                    if (mosi_data_valid) begin
                        state <= IDLE;
                        cpuif_req <= 1'b1;
                        cpuif_wr_data <= mosi_data;
                    end
                end
                READ: begin
                    if (cpuif_rd_ack) begin
                        state <= WAIT;
                        cpuif_req <= 1'b0;
                        miso_data <= cpuif_rd_data;
                        miso_data_valid <= 1'b1;
                    end
                end
                WAIT: begin
                    if (mosi_data_valid) begin
                        state <= IDLE;
                    end
                end
            endcase
        end

endmodule
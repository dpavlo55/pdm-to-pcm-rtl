module spi_to_regs_adapter (
    input logic clk,
    input logic rst_n,

    input logic [7:0] mosi_data,
    input logic mosi_data_valid,

    output logic [7:0] miso_data,
    output logic miso_data_valid,

    output logic cpuif_req,
    output logic cpuif_req_is_wr,
    output logic [2:0] cpuif_addr,
    output logic [7:0] cpuif_wr_data,
    input logic cpuif_wr_ack,
    input logic [7:0] cpuif_rd_data,
    input logic cpuif_rd_ack
);

    // Tracks whether the next valid byte is the cmd/addr byte (0) or data byte (1).
    // Toggles on every mosi_data_valid, since transfers are always exactly 2 bytes.
    logic byte_sel;

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) begin
            byte_sel        <= 1'b0;
            cpuif_req       <= 1'b0;
            cpuif_req_is_wr <= 1'b0;
            cpuif_addr      <= '0;
            cpuif_wr_data   <= '0;
            miso_data       <= '0;
            miso_data_valid <= 1'b0;
        end else begin
            cpuif_req       <= 1'b0;
            miso_data_valid <= 1'b0;

            if (mosi_data_valid) begin
                byte_sel <= ~byte_sel;
                if (!byte_sel) begin
                    // Byte 0: {3'b0, cmd, 1'b0, addr[2:0]}
                    // bit [4] = cmd: 1 for write, 0 for read
                    cpuif_req_is_wr <= mosi_data[4];
                    cpuif_addr      <= mosi_data[2:0];
                    cpuif_req       <= ~mosi_data[4]; // issue read immediately
                end else begin
                    // Byte 1: data - only issue request for writes
                    cpuif_req     <= cpuif_req_is_wr;
                    cpuif_wr_data <= mosi_data;
                end
            end

            if (cpuif_rd_ack) begin
                miso_data       <= cpuif_rd_data;
                miso_data_valid <= 1'b1;
            end
        end

endmodule
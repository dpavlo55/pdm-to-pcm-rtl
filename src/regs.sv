`include "regs_defs.svh"

module regs (
    input  logic clk,
    input  logic rst_n,

    input  logic s_cpuif_req,
    input  logic s_cpuif_req_is_wr,
    input  logic [2:0] s_cpuif_addr,
    input  logic [7:0] s_cpuif_wr_data,
    output logic s_cpuif_rd_ack,
    output logic [7:0] s_cpuif_rd_data,
    output logic s_cpuif_wr_ack,

    input  pdm_to_pcm_reg__in_t hwif_in,

    output pdm_to_pcm_reg__out_t hwif_out
);

    //--------------------------------------------------------------------------
    // Address decode - write-enable strobes
    //--------------------------------------------------------------------------
    logic wr_strobe_control;
    logic wr_strobe_nco_control_w0;
    logic wr_strobe_nco_control_w1;

    assign wr_strobe_control = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h0);
    assign wr_strobe_nco_control_w0 = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h2);
    assign wr_strobe_nco_control_w1 = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h3);

    //--------------------------------------------------------------------------
    // Field storage
    //--------------------------------------------------------------------------
    logic control_enable;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_enable <= 1'h0;
        else if (wr_strobe_control)
            control_enable <= s_cpuif_wr_data[0];

    logic [7:0] nco_control_low;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            nco_control_low <= 8'h0;
        else if (wr_strobe_nco_control_w0)
            nco_control_low <= s_cpuif_wr_data[7:0];

    logic [7:0] nco_control_high;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            nco_control_high <= 8'h0;
        else if (wr_strobe_nco_control_w1)
            nco_control_high <= s_cpuif_wr_data[7:0];

    //--------------------------------------------------------------------------
    // Read mux
    //--------------------------------------------------------------------------
    logic [7:0] rd_data;

    always_comb begin
        rd_data = 8'h0;
        case (s_cpuif_addr)
            3'h0: begin
                rd_data[0] = control_enable;
            end
            3'h2: begin
                rd_data[7:0] = nco_control_low;
            end
            3'h3: begin
                rd_data[7:0] = nco_control_high;
            end
            3'h4: begin
                rd_data[7:0] = hwif_in.data_right.value;
            end
            3'h5: begin
                rd_data[7:0] = hwif_in.data_left.value;
            end
            3'h6: begin
                rd_data[7:0] = 8'hda;
            end
            default: rd_data = {8{1'b0}};
        endcase
    end

    //--------------------------------------------------------------------------
    // Ack / response
    //--------------------------------------------------------------------------
    assign s_cpuif_wr_ack = s_cpuif_req & s_cpuif_req_is_wr;
    assign s_cpuif_rd_ack = s_cpuif_req & ~s_cpuif_req_is_wr;
    assign s_cpuif_rd_data = rd_data;

    //--------------------------------------------------------------------------
    // hwif_out assignments
    //--------------------------------------------------------------------------
    assign hwif_out.control.enable = control_enable;
    assign hwif_out.nco_control.high = nco_control_high;
    assign hwif_out.nco_control.low = nco_control_low;

endmodule : regs

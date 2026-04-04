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

    output pdm_to_pcm_reg__out_t hwif_out
);

    //--------------------------------------------------------------------------
    // Address decode - write-enable strobes
    //--------------------------------------------------------------------------
    logic wr_strobe_control;
    logic wr_strobe_control_low;
    logic wr_strobe_control_high;

    assign wr_strobe_control = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h0);
    assign wr_strobe_control_low = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h3);
    assign wr_strobe_control_high = s_cpuif_req & s_cpuif_req_is_wr & (s_cpuif_addr == 3'h4);

    //--------------------------------------------------------------------------
    // Field storage
    //--------------------------------------------------------------------------
    logic control_enable;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_enable <= 1'h0;
        else if (wr_strobe_control)
            control_enable <= s_cpuif_wr_data[0];

    logic [1:0] control_divider;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_divider <= 2'h0;
        else if (wr_strobe_control)
            control_divider <= s_cpuif_wr_data[2:1];

    logic [4:0] control_test;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_test <= 5'h0;
        else if (wr_strobe_control)
            control_test <= s_cpuif_wr_data[7:3];

    logic [7:0] control_low_value;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_low_value <= 8'h0;
        else if (wr_strobe_control_low)
            control_low_value <= s_cpuif_wr_data[7:0];

    logic [7:0] control_high_value;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            control_high_value <= 8'h0;
        else if (wr_strobe_control_high)
            control_high_value <= s_cpuif_wr_data[7:0];

    //--------------------------------------------------------------------------
    // Read mux
    //--------------------------------------------------------------------------
    logic [7:0] rd_data;

    always_comb begin
        rd_data = 8'h0;
        case (s_cpuif_addr)
            3'h0: begin
                rd_data[0] = control_enable;
                rd_data[2:1] = control_divider;
                rd_data[7:3] = control_test;
            end
            3'h1: begin
                rd_data[7:0] = 8'h0;
            end
            3'h2: begin
                rd_data[7:0] = 8'hda;
            end
            3'h3: begin
                rd_data[7:0] = control_low_value;
            end
            3'h4: begin
                rd_data[7:0] = control_high_value;
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
    assign hwif_out.control.test = control_test;
    assign hwif_out.control.divider = control_divider;
    assign hwif_out.control.enable = control_enable;
    assign hwif_out.control_low.value = control_low_value;
    assign hwif_out.control_high.value = control_high_value;

endmodule : regs

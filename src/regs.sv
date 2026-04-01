`include "regs_defs.svh"

module regs (
    input  logic clk,
    input  logic rst_n,

    input  logic s_cpuif_req,
    input  logic s_cpuif_req_is_wr,
    input  logic [1:0] s_cpuif_addr,
    input  logic [7:0] s_cpuif_wr_data,
    output logic s_cpuif_rd_ack,
    output logic [7:0] s_cpuif_rd_data,
    output logic s_cpuif_wr_ack,

    output pdm_to_pcm_reg__out_t hwif_out
);

    //--------------------------------------------------------------------------
    // Internal CPUIF signals
    //--------------------------------------------------------------------------
    logic cpuif_req;
    logic cpuif_req_is_wr;
    logic [1:0] cpuif_addr;
    logic [7:0] cpuif_wr_data;
    logic cpuif_rd_ack;
    logic [7:0] cpuif_rd_data;
    logic cpuif_wr_ack;

    assign cpuif_req = s_cpuif_req;
    assign cpuif_req_is_wr = s_cpuif_req_is_wr;
    assign cpuif_addr = s_cpuif_addr;
    assign cpuif_wr_data = s_cpuif_wr_data;
    assign s_cpuif_rd_ack = cpuif_rd_ack;
    assign s_cpuif_rd_data = cpuif_rd_data;
    assign s_cpuif_wr_ack = cpuif_wr_ack;

    //--------------------------------------------------------------------------
    // Address decode - write-enable strobes
    //--------------------------------------------------------------------------
    logic wr_strobe_control;
    logic wr_strobe_test_reg;

    always_comb begin
        wr_strobe_control = cpuif_req & cpuif_req_is_wr & (cpuif_addr == 2'h0);
        wr_strobe_test_reg = cpuif_req & cpuif_req_is_wr & (cpuif_addr == 2'h3);
    end

    //--------------------------------------------------------------------------
    // Field storage
    //--------------------------------------------------------------------------
    logic field_control_enable;
    logic next_control_enable;
    logic load_control_enable;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            field_control_enable <= 1'h0;
        else if (load_control_enable)
            field_control_enable <= next_control_enable;

    logic [1:0] field_control_divider;
    logic [1:0] next_control_divider;
    logic load_control_divider;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            field_control_divider <= 2'h0;
        else if (load_control_divider)
            field_control_divider <= next_control_divider;

    logic [4:0] field_control_test;
    logic [4:0] next_control_test;
    logic load_control_test;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            field_control_test <= 5'h0;
        else if (load_control_test)
            field_control_test <= next_control_test;

    logic [7:0] field_test_reg_test;
    logic [7:0] next_test_reg_test;
    logic load_test_reg_test;
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n)
            field_test_reg_test <= 8'h0;
        else if (load_test_reg_test)
            field_test_reg_test <= next_test_reg_test;

    //--------------------------------------------------------------------------
    // Write logic (named signals, no automatic)
    //--------------------------------------------------------------------------
    always_comb begin
        next_control_enable = field_control_enable;
        load_control_enable = 1'b0;
        if (wr_strobe_control) begin
            next_control_enable = cpuif_wr_data[0];
            load_control_enable = 1'b1;
        end
    end

    always_comb begin
        next_control_divider = field_control_divider;
        load_control_divider = 1'b0;
        if (wr_strobe_control) begin
            next_control_divider = cpuif_wr_data[2:1];
            load_control_divider = 1'b1;
        end
    end

    always_comb begin
        next_control_test = field_control_test;
        load_control_test = 1'b0;
        if (wr_strobe_control) begin
            next_control_test = cpuif_wr_data[7:3];
            load_control_test = 1'b1;
        end
    end

    always_comb begin
        next_test_reg_test = field_test_reg_test;
        load_test_reg_test = 1'b0;
        if (wr_strobe_test_reg) begin
            next_test_reg_test = cpuif_wr_data[7:0];
            load_test_reg_test = 1'b1;
        end
    end

    //--------------------------------------------------------------------------
    // Read mux
    //--------------------------------------------------------------------------
    logic [7:0] rd_data_var;

    always_comb begin
        rd_data_var = 8'h0;
        case (cpuif_addr)
            2'h0: begin
                rd_data_var[0] = field_control_enable;
                rd_data_var[2:1] = field_control_divider;
                rd_data_var[7:3] = field_control_test;
            end
            2'h1: begin
                rd_data_var[7:0] = 8'h0;
            end
            2'h2: begin
                rd_data_var[7:0] = 8'hda;
            end
            2'h3: begin
                rd_data_var[7:0] = field_test_reg_test;
            end
            default: rd_data_var = {8{1'b0}};
        endcase
    end

    //--------------------------------------------------------------------------
    // Ack / response
    //--------------------------------------------------------------------------
    assign cpuif_wr_ack  = cpuif_req & cpuif_req_is_wr;
    assign cpuif_rd_ack  = cpuif_req & ~cpuif_req_is_wr;
    assign cpuif_rd_data = rd_data_var;

    //--------------------------------------------------------------------------
    // hwif_out assignments
    //--------------------------------------------------------------------------
    assign hwif_out.control.test = field_control_test;
    assign hwif_out.control.divider = field_control_divider;
    assign hwif_out.control.enable = field_control_enable;
    assign hwif_out.test_reg.test = field_test_reg_test;

endmodule : regs

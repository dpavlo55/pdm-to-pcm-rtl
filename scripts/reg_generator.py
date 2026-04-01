"""
reg_generator.py — Generate Yosys/OpenLane-compatible SystemVerilog register block
from a SystemRDL source file.

Outputs:
  <outdir>/regs_defs.svh  — packed struct typedefs + localparams (no package, include-guard protected)
  <outdir>/regs.sv        — register module (no `automatic`, simplified CPUIF)

Usage:
  python reg_generator.py --rdl <path/to/file.rdl> [--outdir <output_dir>]

When run without arguments defaults to:
  --rdl    ../src/pdm_to_pcm.rdl
  --outdir ../src
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import systemrdl
from systemrdl.rdltypes import AccessType


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FieldModel:
    name: str
    high: int       # MSB bit index in the register
    low: int        # LSB bit index in the register
    sw: AccessType
    hw: AccessType
    reset: int

    @property
    def width(self) -> int:
        return self.high - self.low + 1

    @property
    def hw_accessible(self) -> bool:
        """Field is driven out to hwif_out (hw reads the value)."""
        return self.hw in (AccessType.r, AccessType.rw)

    @property
    def sw_writable(self) -> bool:
        return self.sw in (AccessType.rw, AccessType.w)

    @property
    def sv_type(self) -> str:
        if self.width == 1:
            return "logic"
        return f"logic [{self.width - 1}:0]"


@dataclass
class RegisterModel:
    name: str
    address: int
    data_width: int
    fields: List[FieldModel] = field(default_factory=list)

    @property
    def hw_fields(self) -> List[FieldModel]:
        """Fields exposed on hwif_out, ordered MSB-first."""
        return sorted(
            [f for f in self.fields if f.hw_accessible],
            key=lambda f: f.high,
            reverse=True,
        )

    @property
    def has_hw_fields(self) -> bool:
        return bool(self.hw_fields)


# ---------------------------------------------------------------------------
# RDL parsing
# ---------------------------------------------------------------------------

def parse_rdl(rdl_path: str) -> tuple[str, int, List[RegisterModel]]:
    """
    Compile and elaborate a SystemRDL file.

    Returns:
        (addrmap_name, addr_width, list_of_RegisterModel)
    """
    compiler = systemrdl.RDLCompiler()
    compiler.compile_file(rdl_path)
    root = compiler.elaborate()

    top = root.children()[0]
    addrmap_name: str = top.inst_name

    addr_width = max(1, math.ceil(math.log2(top.size))) if top.size > 1 else 1

    registers: List[RegisterModel] = []
    for reg_node in top.registers():
        reg = RegisterModel(
            name=reg_node.inst_name,
            address=reg_node.raw_absolute_address,
            data_width=reg_node.get_property("regwidth"),
        )
        for field_node in reg_node.fields():
            reg.fields.append(FieldModel(
                name=field_node.inst_name,
                high=field_node.high,
                low=field_node.low,
                sw=field_node.get_property("sw"),
                hw=field_node.get_property("hw"),
                reset=field_node.get_property("reset") or 0,
            ))
        registers.append(reg)

    return addrmap_name, addr_width, registers


# ---------------------------------------------------------------------------
# regs_defs.svh generator
# ---------------------------------------------------------------------------

def _svh_guard_name(addrmap_name: str) -> str:
    return f"{addrmap_name.upper()}_DEFS_SVH"


def generate_svh(addrmap_name: str, addr_width: int, registers: List[RegisterModel]) -> str:
    """Return the full text of regs_defs.svh."""
    data_width = registers[0].data_width if registers else 8
    guard = _svh_guard_name(addrmap_name)
    num_regs = len(registers)

    lines: List[str] = []
    lines += [
        f"`ifndef {guard}",
        f"`define {guard}",
        "",
        f"localparam REGS_DATA_WIDTH    = {data_width};",
        f"localparam REGS_MIN_ADDR_WIDTH = {addr_width};",
        f"localparam REGS_SIZE           = 'h{num_regs:x};",
        "",
    ]

    # Per-register packed struct (only registers that have hw-accessible fields)
    hw_regs = [r for r in registers if r.has_hw_fields]
    for reg in hw_regs:
        struct_name = f"{addrmap_name}__{reg.name}__out_t"
        # Fields listed MSB-first inside packed struct
        field_decls = "; ".join(
            f"{f.sv_type} {f.name}" for f in reg.hw_fields
        )
        lines.append(f"typedef struct packed {{ {field_decls}; }} {struct_name};")

    lines.append("")

    # Top-level output struct
    top_struct_name = f"{addrmap_name}__out_t"
    lines.append(f"typedef struct packed {{")
    for reg in hw_regs:
        member_type = f"{addrmap_name}__{reg.name}__out_t"
        lines.append(f"    {member_type} {reg.name};")
    lines.append(f"}} {top_struct_name};")

    lines += [
        "",
        f"`endif // {guard}",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# regs.sv generator
# ---------------------------------------------------------------------------

def _sig(reg: RegisterModel, f: FieldModel) -> str:
    """Flat storage signal name for a field."""
    return f"field_{reg.name}_{f.name}"


def _next_sig(reg: RegisterModel, f: FieldModel) -> str:
    return f"next_{reg.name}_{f.name}"


def _load_sig(reg: RegisterModel, f: FieldModel) -> str:
    return f"load_{reg.name}_{f.name}"


def _wr_strobe(reg: RegisterModel) -> str:
    return f"wr_strobe_{reg.name}"


def generate_sv(addrmap_name: str, addr_width: int, registers: List[RegisterModel]) -> str:
    """Return the full text of regs.sv."""
    data_width = registers[0].data_width if registers else 8
    top_struct = f"{addrmap_name}__out_t"
    hw_regs = [r for r in registers if r.has_hw_fields]
    rw_fields: List[tuple[RegisterModel, FieldModel]] = [
        (r, f) for r in registers for f in r.fields if f.sw_writable
    ]

    L: List[str] = []

    # --- header ---
    L += [
        '`include "regs_defs.svh"',
        "",
        f"module regs (",
        f"    input  logic clk,",
        f"    input  logic rst_n,",
        f"",
        f"    input  logic s_cpuif_req,",
        f"    input  logic s_cpuif_req_is_wr,",
        f"    input  logic [{addr_width - 1}:0] s_cpuif_addr,",
        f"    input  logic [{data_width - 1}:0] s_cpuif_wr_data,",
        f"    output logic s_cpuif_rd_ack,",
        f"    output logic [{data_width - 1}:0] s_cpuif_rd_data,",
        f"    output logic s_cpuif_wr_ack,",
        f"",
        f"    output {top_struct} hwif_out",
        f");",
        "",
    ]

    # --- internal CPUIF wires ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Internal CPUIF signals",
        "    //--------------------------------------------------------------------------",
        f"    logic cpuif_req;",
        f"    logic cpuif_req_is_wr;",
        f"    logic [{addr_width - 1}:0] cpuif_addr;",
        f"    logic [{data_width - 1}:0] cpuif_wr_data;",
        f"    logic cpuif_rd_ack;",
        f"    logic [{data_width - 1}:0] cpuif_rd_data;",
        f"    logic cpuif_wr_ack;",
        "",
        "    assign cpuif_req = s_cpuif_req;",
        "    assign cpuif_req_is_wr = s_cpuif_req_is_wr;",
        "    assign cpuif_addr = s_cpuif_addr;",
        "    assign cpuif_wr_data = s_cpuif_wr_data;",
        "    assign s_cpuif_rd_ack = cpuif_rd_ack;",
        "    assign s_cpuif_rd_data = cpuif_rd_data;",
        "    assign s_cpuif_wr_ack = cpuif_wr_ack;",
        "",
    ]

    # --- address decode ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Address decode - write-enable strobes",
        "    //--------------------------------------------------------------------------",
    ]
    has_writable_regs = any(
        any(f.sw_writable for f in r.fields) for r in registers
    )
    if has_writable_regs:
        for reg in registers:
            if any(f.sw_writable for f in reg.fields):
                L.append(
                    f"    logic {_wr_strobe(reg)};"
                )
        L.append("")
        L.append("    always_comb begin")
        for reg in registers:
            if any(f.sw_writable for f in reg.fields):
                L.append(
                    f"        {_wr_strobe(reg)} = cpuif_req & cpuif_req_is_wr"
                    f" & (cpuif_addr == {addr_width}'h{reg.address:x});"
                )
        L.append("    end")
        L.append("")

    # --- field storage ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Field storage",
        "    //--------------------------------------------------------------------------",
    ]
    for reg, f in rw_fields:
        reset_val = f"{f.width}'h{f.reset:x}"
        sig = _sig(reg, f)
        next_s = _next_sig(reg, f)
        load_s = _load_sig(reg, f)
        L.append(f"    {f.sv_type} {sig};")
        L.append(f"    {f.sv_type} {next_s};")
        L.append(f"    logic {load_s};")
        L.append(f"    always_ff @(posedge clk or negedge rst_n)")
        L.append(f"        if (!rst_n)")
        L.append(f"            {sig} <= {reset_val};")
        L.append(f"        else if ({load_s})")
        L.append(f"            {sig} <= {next_s};")
        L.append("")

    # --- write logic ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Write logic (named signals, no automatic)",
        "    //--------------------------------------------------------------------------",
    ]
    for reg, f in rw_fields:
        sig = _sig(reg, f)
        next_s = _next_sig(reg, f)
        load_s = _load_sig(reg, f)
        strobe = _wr_strobe(reg)
        bit_slice = f"[{f.high}:{f.low}]" if f.width > 1 else f"[{f.low}]"
        L += [
            f"    always_comb begin",
            f"        {next_s} = {sig};",
            f"        {load_s} = 1'b0;",
            f"        if ({strobe}) begin",
            f"            {next_s} = cpuif_wr_data{bit_slice};",
            f"            {load_s} = 1'b1;",
            f"        end",
            f"    end",
            "",
        ]

    # --- read mux ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Read mux",
        "    //--------------------------------------------------------------------------",
        f"    logic [{data_width - 1}:0] rd_data_var;",
        "",
        "    always_comb begin",
        f"        rd_data_var = {data_width}'h0;",
        f"        case (cpuif_addr)",
    ]
    for reg in registers:
        L.append(f"            {addr_width}'h{reg.address:x}: begin")
        if any(f.sw_writable for f in reg.fields):
            # readable RW fields
            for f in reg.fields:
                if f.sw_writable:
                    bit_slice = f"[{f.high}:{f.low}]" if f.width > 1 else f"[{f.low}]"
                    L.append(f"                rd_data_var{bit_slice} = {_sig(reg, f)};")
        else:
            # RO / constant registers — emit reset value as constant
            # collect fields with non-zero reset
            for f in reg.fields:
                bit_slice = f"[{f.high}:{f.low}]" if f.width > 1 else f"[{f.low}]"
                L.append(f"                rd_data_var{bit_slice} = {f.width}'h{f.reset:x};")
        L.append("            end")
    L += [
        "            default: rd_data_var = {" + str(data_width) + "{1'b0}};",
        "        endcase",
        "    end",
        "",
    ]

    # --- acks ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Ack / response",
        "    //--------------------------------------------------------------------------",
        "    assign cpuif_wr_ack  = cpuif_req & cpuif_req_is_wr;",
        "    assign cpuif_rd_ack  = cpuif_req & ~cpuif_req_is_wr;",
        "    assign cpuif_rd_data = rd_data_var;",
        "",
    ]

    # --- hwif_out ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // hwif_out assignments",
        "    //--------------------------------------------------------------------------",
    ]
    for reg in hw_regs:
        for f in reg.hw_fields:
            L.append(f"    assign hwif_out.{reg.name}.{f.name} = {_sig(reg, f)};")
    L += [
        "",
        "endmodule : regs",
        "",
    ]

    return "\n".join(L)


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Written: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    script_dir = Path(__file__).parent
    default_rdl = str(script_dir / ".." / "src" / "pdm_to_pcm.rdl")
    default_outdir = str(script_dir / ".." / "src")

    parser = argparse.ArgumentParser(
        description="Generate Yosys-compatible regs_defs.svh and regs.sv from a SystemRDL file."
    )
    parser.add_argument("--rdl", default=default_rdl, help="Path to the .rdl source file")
    parser.add_argument("--outdir", default=default_outdir, help="Output directory")
    args = parser.parse_args(argv)

    rdl_path = os.path.realpath(args.rdl)
    outdir = Path(os.path.realpath(args.outdir))

    addrmap_name, addr_width, registers = parse_rdl(rdl_path)

    svh_content = generate_svh(addrmap_name, addr_width, registers)
    sv_content = generate_sv(addrmap_name, addr_width, registers)

    write_file(outdir / "regs_defs.svh", svh_content)
    write_file(outdir / "regs.sv", sv_content)


if __name__ == "__main__":
    main()

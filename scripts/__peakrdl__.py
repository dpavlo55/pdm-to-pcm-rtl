"""
__peakrdl__.py — PeakRDL exporter plugin: regblock-tt

Generates Yosys/OpenLane-compatible register block outputs from a SystemRDL
source file.  Discovered automatically by PeakRDL via peakrdl.toml.

Outputs (written to the directory given by -o):
  regs_defs.svh  — packed struct typedefs + localparams
  regs.sv        — register module with simplified passthrough CPUIF

reg_generator.py is imported unchanged for its data model types and
generator functions; only the elaboration step is performed here (the
AddrmapNode is supplied by the PeakRDL framework).
"""

from __future__ import annotations

import math
import sys
import os
from pathlib import Path
from typing import List, TYPE_CHECKING

from peakrdl.plugins.exporter import ExporterSubcommandPlugin

if TYPE_CHECKING:
    import argparse
    from systemrdl.node import AddrmapNode

# reg_generator.py lives next to this file; ensure it can be imported even
# when this module is imported before python_search_paths is applied.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from reg_generator import (  # noqa: E402
    FieldModel,
    RegisterModel,
    generate_svh,
    write_file,
    _sig,
    _num_words,
    _word_strobe,
    _field_word_idx,
    _field_local_slice,
)


# ---------------------------------------------------------------------------
# Write-buffer helpers
# buf_info maps reg_name -> trigger_reg_name for every register with
# buffer_writes=True.  All logic lives here; reg_generator is unmodified.
# ---------------------------------------------------------------------------

def _buf_is_cross(reg_name: str, trigger_reg_name: str) -> bool:
    """True when the commit trigger lives in a different register."""
    return trigger_reg_name != reg_name


def _buf_needs_shadow(
    reg: RegisterModel,
    trigger_reg_name: str,
    data_width: int,
) -> bool:
    """False only for a single-word self-triggered register (no shadow needed)."""
    if _buf_is_cross(reg.name, trigger_reg_name):
        return True
    return _num_words(reg, data_width) > 1


def _buf_commit_strobe(
    reg: RegisterModel,
    trigger_reg_name: str,
    all_regs: List[RegisterModel],
    data_width: int,
) -> str:
    """Strobe signal that fires the atomic commit of a buffered register."""
    if _buf_is_cross(reg.name, trigger_reg_name):
        trig_reg = next(r for r in all_regs if r.name == trigger_reg_name)
        return _word_strobe(trig_reg, 0, data_width)
    return _word_strobe(reg, 0, data_width)


def _buf_pending_name(reg: RegisterModel) -> str:
    return f"wbuf_{reg.name}_pending"


def _buf_data_name(reg: RegisterModel, word_idx: int) -> str:
    return f"wbuf_{reg.name}_w{word_idx}_data"


# ---------------------------------------------------------------------------
# SV generator (with write-buffer support)
# ---------------------------------------------------------------------------

def _generate_sv(
    addrmap_name: str,
    addr_width: int,
    registers: List[RegisterModel],
    buf_info: dict,
) -> str:
    """Return the full text of regs.sv, adding write-buffer logic where needed."""
    data_width = registers[0].data_width if registers else 8
    top_struct = f"{addrmap_name}__out_t"
    hw_regs = [r for r in registers if r.has_hw_fields]
    rw_fields: List[tuple] = [
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

    # --- address decode ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Address decode - write-enable strobes",
        "    //--------------------------------------------------------------------------",
    ]
    has_writable_regs = any(any(f.sw_writable for f in r.fields) for r in registers)
    if has_writable_regs:
        for reg in registers:
            if any(f.sw_writable for f in reg.fields):
                for w in range(_num_words(reg, data_width)):
                    L.append(f"    logic {_word_strobe(reg, w, data_width)};")
        L.append("")
        for reg in registers:
            if any(f.sw_writable for f in reg.fields):
                for w in range(_num_words(reg, data_width)):
                    word_addr = reg.address + w
                    L.append(
                        f"    assign {_word_strobe(reg, w, data_width)} = s_cpuif_req & s_cpuif_req_is_wr"
                        f" & (s_cpuif_addr == {addr_width}'h{word_addr:x});"
                    )
        L.append("")

    # --- write buffers ---
    buf_regs = [
        r for r in registers
        if r.name in buf_info and _buf_needs_shadow(r, buf_info[r.name], data_width)
    ]
    if buf_regs:
        L += [
            "    //--------------------------------------------------------------------------",
            "    // Write buffers",
            "    //--------------------------------------------------------------------------",
        ]
        for reg in buf_regs:
            trig_name = buf_info[reg.name]
            is_cross = _buf_is_cross(reg.name, trig_name)
            # For same-reg trigger, word 0 is the trigger; shadow the rest.
            # For cross-reg trigger, all words get a shadow.
            buffered_words = [
                w for w in range(_num_words(reg, data_width))
                if is_cross or w != 0
            ]
            commit = _buf_commit_strobe(reg, trig_name, registers, data_width)

            L.append(f"    logic {_buf_pending_name(reg)};")
            for w in buffered_words:
                L.append(f"    logic [{data_width - 1}:0] {_buf_data_name(reg, w)};")
            L.append(f"    always_ff @(posedge clk or negedge rst_n)")
            L.append(f"        if (!rst_n) begin")
            L.append(f"            {_buf_pending_name(reg)} <= 1'b0;")
            for w in buffered_words:
                L.append(f"            {_buf_data_name(reg, w)} <= {data_width}'h0;")
            L.append(f"        end else begin")
            L.append(f"            if ({commit})")
            L.append(f"                {_buf_pending_name(reg)} <= 1'b0;")
            for w in buffered_words:
                L.append(f"            if ({_word_strobe(reg, w, data_width)}) begin")
                L.append(f"                {_buf_data_name(reg, w)} <= s_cpuif_wr_data[{data_width - 1}:0];")
                L.append(f"                {_buf_pending_name(reg)} <= 1'b1;")
                L.append(f"            end")
            L.append(f"        end")
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
        word_idx = _field_word_idx(f, data_width)
        local_slice = _field_local_slice(f, data_width)

        if reg.name in buf_info and _buf_needs_shadow(reg, buf_info[reg.name], data_width):
            trig_name = buf_info[reg.name]
            is_cross = _buf_is_cross(reg.name, trig_name)
            commit = _buf_commit_strobe(reg, trig_name, registers, data_width)
            # word 0 is the trigger word for same-reg; all words buffered for cross-reg
            uses_shadow = is_cross or word_idx != 0
            if uses_shadow:
                strobe = f"{_buf_pending_name(reg)} && {commit}"
                source = f"{_buf_data_name(reg, word_idx)}{local_slice}"
            else:
                strobe = commit
                source = f"s_cpuif_wr_data{local_slice}"
        else:
            strobe = _word_strobe(reg, word_idx, data_width)
            source = f"s_cpuif_wr_data{local_slice}"

        L.append(f"    {f.sv_type} {sig};")
        L.append(f"    always_ff @(posedge clk or negedge rst_n)")
        L.append(f"        if (!rst_n)")
        L.append(f"            {sig} <= {reset_val};")
        L.append(f"        else if ({strobe})")
        L.append(f"            {sig} <= {source};")
        L.append("")

    # --- read mux ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Read mux",
        "    //--------------------------------------------------------------------------",
        f"    logic [{data_width - 1}:0] rd_data;",
        "",
        "    always_comb begin",
        f"        rd_data = {data_width}'h0;",
        f"        case (s_cpuif_addr)",
    ]
    for reg in registers:
        num_words = _num_words(reg, data_width)
        for w in range(num_words):
            word_addr = reg.address + w
            L.append(f"            {addr_width}'h{word_addr:x}: begin")
            word_fields = [f for f in reg.fields if _field_word_idx(f, data_width) == w]
            if any(f.sw_writable for f in reg.fields):
                for f in word_fields:
                    if f.sw_writable:
                        local_slice = _field_local_slice(f, data_width)
                        L.append(f"                rd_data{local_slice} = {_sig(reg, f)};")
            else:
                for f in word_fields:
                    local_slice = _field_local_slice(f, data_width)
                    L.append(f"                rd_data{local_slice} = {f.width}'h{f.reset:x};")
            L.append("            end")
    L += [
        "            default: rd_data = {" + str(data_width) + "{1'b0}};",
        "        endcase",
        "    end",
        "",
    ]

    # --- acks ---
    L += [
        "    //--------------------------------------------------------------------------",
        "    // Ack / response",
        "    //--------------------------------------------------------------------------",
        "    assign s_cpuif_wr_ack = s_cpuif_req & s_cpuif_req_is_wr;",
        "    assign s_cpuif_rd_ack = s_cpuif_req & ~s_cpuif_req_is_wr;",
        "    assign s_cpuif_rd_data = rd_data;",
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
# Model builder
# ---------------------------------------------------------------------------

def _build_model(
    top_node: "AddrmapNode",
) -> tuple:
    """
    Build the data model from an already-elaborated AddrmapNode.

    Returns (addrmap_name, addr_width, registers, buf_info) where
    buf_info maps reg_name -> trigger_reg_name for every buffered register.
    """
    addrmap_name: str = top_node.inst_name
    addr_width = max(1, math.ceil(math.log2(top_node.size))) if top_node.size > 1 else 1

    registers: List[RegisterModel] = []
    buf_info: dict = {}
    for reg_node in top_node.registers():
        buf_writes = bool(reg_node.get_property('buffer_writes') or False)
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
        if buf_writes:
            trig_ref = reg_node.get_property('wbuffer_trigger')
            if trig_ref is not None:
                buf_info[reg.name] = trig_ref.inst_name

    return addrmap_name, addr_width, registers, buf_info


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class RegblockTtExporter(ExporterSubcommandPlugin):
    short_desc = "Generate Yosys/OpenLane-compatible regs_defs.svh + regs.sv"

    def do_export(
        self,
        top_node: "AddrmapNode",
        options: "argparse.Namespace",
    ) -> None:
        outdir = Path(options.output)
        addrmap_name, addr_width, registers, buf_info = _build_model(top_node)
        write_file(outdir / "regs_defs.svh", generate_svh(addrmap_name, addr_width, registers))
        write_file(outdir / "regs.sv", _generate_sv(addrmap_name, addr_width, registers, buf_info))

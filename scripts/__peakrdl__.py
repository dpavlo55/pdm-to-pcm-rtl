"""
__peakrdl__.py — PeakRDL exporter plugin: regblock-tt

Generates Yosys/OpenLane-compatible register block outputs from a SystemRDL
source file.  Discovered automatically by PeakRDL via peakrdl.toml.

Outputs (written to the directory given by -o):
  regs_defs.svh  — packed struct typedefs + localparams
  regs.sv        — register module with simplified passthrough CPUIF

Self-contained: all data model types and generator functions are defined
here. The elaboration step receives an AddrmapNode from the PeakRDL framework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, TYPE_CHECKING

from peakrdl.plugins.exporter import ExporterSubcommandPlugin
from systemrdl.rdltypes import AccessType

if TYPE_CHECKING:
    import argparse
    from systemrdl.node import AddrmapNode


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
    def hw_writable(self) -> bool:
        """Field is driven in from hwif_in (hw writes the value)."""
        return self.hw in (AccessType.w, AccessType.rw)

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
        """Fields exposed on hwif_out (HW reads), ordered MSB-first."""
        return sorted(
            [f for f in self.fields if f.hw_accessible],
            key=lambda f: f.high,
            reverse=True,
        )

    @property
    def has_hw_fields(self) -> bool:
        return bool(self.hw_fields)

    @property
    def hw_in_fields(self) -> List[FieldModel]:
        """Fields driven from hwif_in (HW writes, SW reads), ordered MSB-first."""
        return sorted(
            [f for f in self.fields if f.hw_writable],
            key=lambda f: f.high,
            reverse=True,
        )

    @property
    def has_hw_in_fields(self) -> bool:
        return bool(self.hw_in_fields)


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

    # Per-register packed struct for hwif_out (HW reads, SW writes)
    hw_regs = [r for r in registers if r.has_hw_fields]
    for reg in hw_regs:
        struct_name = f"{addrmap_name}__{reg.name}__out_t"
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

    # Per-register packed struct for hwif_in (HW writes, SW reads)
    hw_in_regs = [r for r in registers if r.has_hw_in_fields]
    if hw_in_regs:
        lines.append("")
        for reg in hw_in_regs:
            struct_name = f"{addrmap_name}__{reg.name}__in_t"
            field_decls = "; ".join(
                f"{f.sv_type} {f.name}" for f in reg.hw_in_fields
            )
            lines.append(f"typedef struct packed {{ {field_decls}; }} {struct_name};")

        lines.append("")

        # Top-level input struct
        top_in_struct_name = f"{addrmap_name}__in_t"
        lines.append(f"typedef struct packed {{")
        for reg in hw_in_regs:
            member_type = f"{addrmap_name}__{reg.name}__in_t"
            lines.append(f"    {member_type} {reg.name};")
        lines.append(f"}} {top_in_struct_name};")

    lines += [
        "",
        f"`endif // {guard}",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Written: {path}")


def _sig(reg: RegisterModel, f: FieldModel) -> str:
    """Flat storage signal name for a field."""
    return f"{reg.name}_{f.name}"


# ---------------------------------------------------------------------------
# Low-level SV helpers
# ---------------------------------------------------------------------------

def _num_words(reg: RegisterModel, data_width: int) -> int:
    return max(1, reg.data_width // data_width)


def _word_strobe(reg: RegisterModel, word_idx: int, data_width: int) -> str:
    if _num_words(reg, data_width) == 1:
        return f"wr_strobe_{reg.name}"
    return f"wr_strobe_{reg.name}_w{word_idx}"


def _field_word_idx(f: FieldModel, data_width: int) -> int:
    return f.low // data_width


def _field_local_slice(f: FieldModel, data_width: int) -> str:
    local_low = f.low % data_width
    local_high = local_low + f.width - 1
    return f"[{local_low}]" if f.width == 1 else f"[{local_high}:{local_low}]"


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
    hw_in_regs = [r for r in registers if r.has_hw_in_fields]
    rw_fields: List[tuple] = [
        (r, f) for r in registers for f in r.fields if f.sw_writable
    ]
    top_in_struct = f"{addrmap_name}__in_t"

    L: List[str] = []

    # --- header ---
    hwif_in_port = (
        [f"    input  {top_in_struct} hwif_in,", f""]
        if hw_in_regs else []
    )
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
        *hwif_in_port,
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
                    if f.hw_writable:
                        L.append(f"                rd_data{local_slice} = hwif_in.{reg.name}.{f.name};")
                    else:
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

from peakrdl_uvm.exporter import UVMExporter

class UvmTtExporter(ExporterSubcommandPlugin):
    short_desc = 'Generate UVM with TT HDLs'
    def add_exporter_arguments(self, arg_group) -> None:
        arg_group.add_argument('--type-style', default='hier')

    def do_export(self, top_node, options) -> None:
        x = UVMExporter(user_template_dir='rtl/scripts/uvm_templates')
        x.export(
            top_node, options.output,
            export_as_package=True,
            reuse_class_definitions=(options.type_style=='lexical'),
            use_uvm_factory=False
        )


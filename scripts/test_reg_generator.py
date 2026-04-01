"""Tests for reg_generator.py"""

import re
import sys
import os
import tempfile
from pathlib import Path

import pytest

# Make the scripts directory importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

from reg_generator import parse_rdl, generate_svh, generate_sv, main

RDL_PATH = str(Path(__file__).parent / ".." / "src" / "pdm_to_pcm.rdl")


# ---------------------------------------------------------------------------
# Phase 1 — RDL parsing
# ---------------------------------------------------------------------------

class TestParseRdl:
    def setup_method(self):
        self.addrmap_name, self.addr_width, self.registers = parse_rdl(RDL_PATH)

    def test_addrmap_name(self):
        assert self.addrmap_name == "pdm_to_pcm_reg"

    def test_addr_width(self):
        assert self.addr_width == 2

    def test_num_registers(self):
        assert len(self.registers) == 4

    def test_register_names(self):
        names = [r.name for r in self.registers]
        assert names == ["control", "data", "id", "test_reg"]

    def test_register_addresses(self):
        addrs = [r.address for r in self.registers]
        assert addrs == [0x0, 0x1, 0x2, 0x3]

    def test_control_fields(self):
        control = self.registers[0]
        field_names = [f.name for f in control.fields]
        assert set(field_names) == {"enable", "divider", "test"}

    def test_control_field_widths(self):
        control = self.registers[0]
        widths = {f.name: f.width for f in control.fields}
        assert widths["enable"] == 1
        assert widths["divider"] == 2
        assert widths["test"] == 5

    def test_control_field_bit_positions(self):
        control = self.registers[0]
        bits = {f.name: (f.high, f.low) for f in control.fields}
        assert bits["enable"] == (0, 0)
        assert bits["divider"] == (2, 1)
        assert bits["test"] == (7, 3)

    def test_control_sw_writable(self):
        from systemrdl.rdltypes import AccessType
        control = self.registers[0]
        for f in control.fields:
            assert f.sw == AccessType.rw

    def test_data_field_hw_na(self):
        from systemrdl.rdltypes import AccessType
        data_reg = self.registers[1]
        assert len(data_reg.fields) == 1
        assert data_reg.fields[0].hw == AccessType.na

    def test_id_field_reset(self):
        id_reg = self.registers[2]
        assert id_reg.fields[0].reset == 0xDA

    def test_hw_accessible_fields(self):
        control = self.registers[0]
        assert all(f.hw_accessible for f in control.fields)
        data_reg = self.registers[1]
        assert not any(f.hw_accessible for f in data_reg.fields)

    def test_sw_writable_fields(self):
        control = self.registers[0]
        assert all(f.sw_writable for f in control.fields)
        data_reg = self.registers[1]
        assert not any(f.sw_writable for f in data_reg.fields)


# ---------------------------------------------------------------------------
# Phase 2 — regs_defs.svh generation
# ---------------------------------------------------------------------------

class TestGenerateSvh:
    def setup_method(self):
        self.addrmap_name, self.addr_width, self.registers = parse_rdl(RDL_PATH)
        self.svh = generate_svh(self.addrmap_name, self.addr_width, self.registers)

    def test_no_package_keyword(self):
        assert "package" not in self.svh

    def test_no_import_keyword(self):
        assert "import" not in self.svh

    def test_include_guard_present(self):
        assert "`ifndef PDM_TO_PCM_REG_DEFS_SVH" in self.svh
        assert "`define PDM_TO_PCM_REG_DEFS_SVH" in self.svh
        assert "`endif" in self.svh

    def test_packed_structs(self):
        matches = re.findall(r"typedef struct packed", self.svh)
        # at least control_out_t + top-level out_t
        assert len(matches) >= 2

    def test_no_unpacked_structs(self):
        # Unpacked would be 'typedef struct {' with no 'packed'
        unpacked = re.findall(r"typedef struct\s*\{", self.svh)
        assert len(unpacked) == 0

    def test_localparams_present(self):
        assert "localparam REGS_DATA_WIDTH" in self.svh
        assert "localparam REGS_MIN_ADDR_WIDTH" in self.svh

    def test_localparam_values(self):
        assert "REGS_DATA_WIDTH    = 8" in self.svh
        assert "REGS_MIN_ADDR_WIDTH = 2" in self.svh

    def test_control_struct_fields(self):
        # Must contain test, divider, enable in the packed struct
        assert "test" in self.svh
        assert "divider" in self.svh
        assert "enable" in self.svh

    def test_hw_na_regs_excluded(self):
        # data and id registers have hw=na fields only — no struct for them
        assert "data__out_t" not in self.svh
        assert "id__out_t" not in self.svh

    def test_top_level_struct_name(self):
        assert "pdm_to_pcm_reg__out_t" in self.svh

    def test_control_struct_name(self):
        assert "pdm_to_pcm_reg__control__out_t" in self.svh

    def test_fields_msb_first_in_struct(self):
        # test (bits 7:3) must appear before enable (bit 0) in the packed struct
        test_pos = self.svh.find("logic [4:0] test")
        enable_pos = self.svh.find("logic enable")
        assert test_pos < enable_pos


# ---------------------------------------------------------------------------
# Phase 3 — regs.sv generation
# ---------------------------------------------------------------------------

class TestGenerateSv:
    def setup_method(self):
        self.addrmap_name, self.addr_width, self.registers = parse_rdl(RDL_PATH)
        self.sv = generate_sv(self.addrmap_name, self.addr_width, self.registers)

    def test_no_automatic_keyword(self):
        # Only allow 'automatic' inside comments
        lines_with_automatic = [
            l for l in self.sv.splitlines()
            if "automatic" in l and not l.lstrip().startswith("//")
        ]
        assert lines_with_automatic == []

    def test_no_stall_ports(self):
        assert "stall" not in self.sv

    def test_no_err_ports(self):
        # 'err' as a port — should not appear in port list
        assert "s_cpuif_rd_err" not in self.sv
        assert "s_cpuif_wr_err" not in self.sv

    def test_no_biten_port(self):
        assert "biten" not in self.sv

    def test_no_import(self):
        assert "import" not in self.sv

    def test_no_package_qualifier(self):
        assert "regs_pkg::" not in self.sv

    def test_includes_defs_header(self):
        assert '`include "regs_defs.svh"' in self.sv

    def test_module_name(self):
        assert "module regs (" in self.sv

    def test_hwif_out_port_present(self):
        assert "hwif_out" in self.sv
        assert "pdm_to_pcm_reg__out_t" in self.sv

    def test_cpuif_ports_present(self):
        assert "s_cpuif_req" in self.sv
        assert "s_cpuif_req_is_wr" in self.sv
        assert "s_cpuif_addr" in self.sv
        assert "s_cpuif_wr_data" in self.sv
        assert "s_cpuif_rd_ack" in self.sv
        assert "s_cpuif_rd_data" in self.sv
        assert "s_cpuif_wr_ack" in self.sv

    def test_field_storage_signals(self):
        assert "control_enable" in self.sv
        assert "control_divider" in self.sv
        assert "control_test" in self.sv

    def test_no_next_load_signals(self):
        assert "next_" not in self.sv
        assert "load_" not in self.sv

    def test_read_mux_has_id_constant(self):
        # ID register reset = 0xDA
        assert "8'hda" in self.sv

    def test_write_ack_logic(self):
        assert "s_cpuif_req & s_cpuif_req_is_wr" in self.sv

    def test_read_ack_logic(self):
        assert "s_cpuif_req & ~s_cpuif_req_is_wr" in self.sv

    def test_hwif_out_assignments(self):
        assert "assign hwif_out.control.test" in self.sv
        assert "assign hwif_out.control.divider" in self.sv
        assert "assign hwif_out.control.enable" in self.sv

    def test_endmodule(self):
        assert "endmodule : regs" in self.sv


# ---------------------------------------------------------------------------
# Phase 4 — CLI / file output
# ---------------------------------------------------------------------------

class TestCli:
    def test_writes_both_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["--rdl", RDL_PATH, "--outdir", tmpdir])
            assert (Path(tmpdir) / "regs_defs.svh").exists()
            assert (Path(tmpdir) / "regs.sv").exists()

    def test_svh_output_no_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["--rdl", RDL_PATH, "--outdir", tmpdir])
            content = (Path(tmpdir) / "regs_defs.svh").read_text()
            assert "package" not in content

    def test_sv_output_no_automatic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main(["--rdl", RDL_PATH, "--outdir", tmpdir])
            content = (Path(tmpdir) / "regs.sv").read_text()
            code_lines = [l for l in content.splitlines() if not l.lstrip().startswith("//")]
            assert not any("automatic" in l for l in code_lines)

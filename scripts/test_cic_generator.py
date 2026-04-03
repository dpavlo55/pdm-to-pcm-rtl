"""Tests for cic_generator.py"""

import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from cic_pruning import compute_cic_params, CicParams, StageParams
from cic_generator import generate_sv, main


# ---------------------------------------------------------------------------
# compute_cic_params
# ---------------------------------------------------------------------------

class TestComputeCicParams:

    def test_n3_r8_bit_growth(self):
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert p.bit_growth == 9

    def test_n3_r8_max_width(self):
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert p.max_width == 10

    def test_n3_r8_trunc_bits(self):
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert p.trunc_bits == 2

    def test_n3_r8_stage_count(self):
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert len(p.stages) == 6  # 2*N

    def test_n3_r8_all_stages_full_width(self):
        """For PDM case all Bj effective = 0 so all stages use max_width=10."""
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert all(s.width == 10 for s in p.stages)

    def test_n4_r25_bit_growth(self):
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        assert p.bit_growth == 19

    def test_n4_r25_max_width(self):
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        assert p.max_width == 35

    def test_n4_r25_trunc_bits(self):
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        assert p.trunc_bits == 19

    def test_n4_r25_stage_count(self):
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        assert len(p.stages) == 8  # 2*N

    def test_n4_r25_integrator_widths(self):
        """Integrator stage widths must match the pruning table (34,29,26,22)."""
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        integ_widths = [s.width for s in p.stages[:4]]
        assert integ_widths == [34, 29, 26, 22]

    def test_n4_r25_comb_widths(self):
        """Comb stage widths must match the pruning table (21,20,19,18)."""
        p = compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16)
        comb_widths = [s.width for s in p.stages[4:]]
        assert comb_widths == [21, 20, 19, 18]

    def test_stage_indices_are_sequential(self):
        p = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        assert [s.index for s in p.stages] == list(range(1, 7))


# ---------------------------------------------------------------------------
# generate_sv — structural checks
# ---------------------------------------------------------------------------

class TestGenerateSv:

    @pytest.fixture(scope="class")
    def sv_n3(self):
        return generate_sv(compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8))

    @pytest.fixture(scope="class")
    def sv_n4(self):
        return generate_sv(compute_cic_params(N=4, R=25, M=1, Bin=16, Bout=16))

    def test_module_declaration_present(self, sv_n3):
        assert "module cic" in sv_n3

    def test_endmodule_label_present(self, sv_n3):
        assert "endmodule : cic" in sv_n3

    def test_pipeline_enable_parameter(self, sv_n3):
        assert "parameter bit PIPELINE_ENABLE" in sv_n3

    def test_sig_in_width_n3(self, sv_n3):
        assert "[0:0] sig_in" in sv_n3  # 1-bit input

    def test_sig_out_width_n3(self, sv_n3):
        assert "[7:0]" in sv_n3  # 8-bit output

    def test_sig_out_width_n4(self, sv_n4):
        assert "[15:0]" in sv_n4  # 16-bit output

    def test_n3_integrator_count(self, sv_n3):
        """There must be exactly N=3 integrator signals."""
        matches = re.findall(r"integ_\d+\s*<=\s*integ_\d+\s*\+", sv_n3)
        assert len(matches) == 3

    def test_n4_integrator_count(self, sv_n4):
        matches = re.findall(r"integ_\d+\s*<=\s*integ_\d+\s*\+", sv_n4)
        assert len(matches) == 4

    def test_n3_comb_delay_count(self, sv_n3):
        """M=1: each of N=3 comb stages has exactly one delay register."""
        matches = re.findall(r"comb_\d+_dly_0\b", sv_n3)
        # signal declaration + always_ff body — at least 3 declarations
        decl = re.findall(r"logic.*comb_\d+_dly_0", sv_n3)
        assert len(decl) == 3

    def test_n3_comb_diff_count(self, sv_n3):
        decl = re.findall(r"logic.*comb_\d+_diff", sv_n3)
        assert len(decl) == 3

    def test_generate_block_present(self, sv_n3):
        assert "generate" in sv_n3
        assert "endgenerate" in sv_n3

    def test_pipeline_enable_branches(self, sv_n3):
        assert "g_comb" in sv_n3
        assert "g_pipe" in sv_n3

    def test_sig_in_valid_port(self, sv_n3):
        assert "input  logic sig_in_valid" in sv_n3

    def test_sig_in_se_declared(self, sv_n3):
        assert "sig_in_se" in sv_n3

    def test_sig_in_se_uses_replication(self, sv_n3):
        """Sign extension must use N'(signed'(sig_in)) form."""
        assert "assign sig_in_se = 10'(signed'(sig_in))" in sv_n3
        assert "[9:0]'(" not in sv_n3

    def test_integrators_are_signed(self, sv_n3):
        assert re.search(r"logic signed \[\d+:\d+\] integ_0", sv_n3)

    def test_comb_signals_are_signed(self, sv_n3):
        assert re.search(r"logic signed \[\d+:\d+\] comb_0_diff", sv_n3)
        assert re.search(r"logic signed \[\d+:\d+\] comb_0_dly_0", sv_n3)

    def test_integrators_gated_by_sig_in_valid(self, sv_n3):
        assert "sig_in_valid" in sv_n3
        # Each integrator always_ff should use sig_in_valid, not free-running
        assert sv_n3.count("else if (sig_in_valid)") >= 3

    def test_dec_cnt_gated_by_sig_in_valid(self, sv_n3):
        assert "dec_cnt" in sv_n3
        assert "else if (sig_in_valid)" in sv_n3

    def test_dec_en_gated_by_sig_in_valid(self, sv_n3):
        assert "sig_in_valid && (dec_cnt" in sv_n3

    def test_dec_en_signal(self, sv_n3):
        assert "dec_en" in sv_n3

    def test_valid_signal(self, sv_n3):
        assert "valid <= 1'b0" in sv_n3
        assert "valid <= dec_en" in sv_n3

    def test_output_truncation_n3(self, sv_n3):
        """sig_out must come from comb_2_diff[9:2] (max_width-1 : trunc_bits)."""
        assert "comb_2_diff[9:2]" in sv_n3

    def test_output_truncation_n4(self, sv_n4):
        """sig_out must come from comb_3_diff[34:19]."""
        assert "comb_3_diff[34:19]" in sv_n4

    def test_no_localparams(self, sv_n3):
        assert "localparam" not in sv_n3

    def test_logic_type_only(self, sv_n3):
        """No reg or wire type declarations should appear."""
        assert not re.search(r"\breg\b", sv_n3)
        assert not re.search(r"\bwire\b", sv_n3)

    def test_rst_n_active_low(self, sv_n3):
        assert "negedge rst_n" in sv_n3
        assert "!rst_n" in sv_n3

    def test_always_ff_used(self, sv_n3):
        assert "always_ff" in sv_n3

    def test_always_comb_used(self, sv_n3):
        assert "always_comb" in sv_n3

    def test_no_manual_edit_notice(self, sv_n3):
        assert "DO NOT EDIT BY HAND" in sv_n3


# ---------------------------------------------------------------------------
# CLI — main() writes file to temp directory
# ---------------------------------------------------------------------------

class TestMain:

    def test_main_writes_cic_sv(self, tmp_path):
        main(["--N", "3", "--R", "8", "--M", "1", "--Bin", "1", "--Bout", "8",
              "--outdir", str(tmp_path)])
        out = tmp_path / "cic.sv"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_main_default_n4(self, tmp_path):
        main(["--N", "4", "--R", "25", "--M", "1", "--Bin", "16", "--Bout", "16",
              "--outdir", str(tmp_path)])
        content = (tmp_path / "cic.sv").read_text()
        assert "assign sig_in_se = 34'(signed'(sig_in))" in content

    def test_main_creates_output_dir(self, tmp_path):
        nested = tmp_path / "new_subdir"
        main(["--outdir", str(nested)])
        assert (nested / "cic.sv").exists()

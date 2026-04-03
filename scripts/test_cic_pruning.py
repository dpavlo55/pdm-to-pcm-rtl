"""Tests that verify calculate_cic_pruning produces the correct output."""

import io
import math
import sys

import pytest

from cic_pruning import calculate_cic_pruning, compute_passband_metrics, compute_cic_params, main


def capture(N: int, R: int, M: int, Bin: int, Bout: int) -> str:
    buf = io.StringIO()
    sys.stdout = buf
    try:
        calculate_cic_pruning(N=N, R=R, M=M, Bin=Bin, Bout=Bout)
    finally:
        sys.stdout = sys.__stdout__
    return buf.getvalue()


def normalize(text: str) -> str:
    """Strip trailing whitespace from each line so table padding doesn't break comparisons."""
    return "\n".join(line.rstrip() for line in text.splitlines())


# ── expected outputs (generated from the original implementation) ─────────────

EXPECTED_N3_R8 = normalize(
    "\nCIC Filter Parameters:\n"
    "    N = 3 (number of stages)\n"
    "    R = 8 (sample rate change)\n"
    "    M = 1 (comb filter differential delay)\n"
    "    Bin = 1 (input bit width)\n"
    "    Bout = 8 (output bit width)\n"
    "\nMax Bit Growth Due To Gain  = 9\n"
    "Max Accumulator Width = 10\n"
    "\n"
    " Stage(j)  |    Bj    |  Accum (adder) width \n"
    "-----------------------------------------------\n"
    "    1      |  0 (-7)  |          10           \n"
    "    2      |  0 (-4)  |          10           \n"
    "    3      |  0 (-3)  |          10           \n"
    "    4      |  0 (-2)  |          10           \n"
    "    5      |  0 (-1)  |          10           \n"
    "    6      |    0     |          10           \n"
    "    7      |    2     |       8 (final)       \n"
    "\n"
)

EXPECTED_N4_R25 = normalize(
    "\nCIC Filter Parameters:\n"
    "    N = 4 (number of stages)\n"
    "    R = 25 (sample rate change)\n"
    "    M = 1 (comb filter differential delay)\n"
    "    Bin = 16 (input bit width)\n"
    "    Bout = 16 (output bit width)\n"
    "\nMax Bit Growth Due To Gain  = 19\n"
    "Max Accumulator Width = 35\n"
    "\n"
    " Stage(j)  |    Bj    |  Accum (adder) width \n"
    "-----------------------------------------------\n"
    "    1      |    1     |          34           \n"
    "    2      |    6     |          29           \n"
    "    3      |    9     |          26           \n"
    "    4      |    13    |          22           \n"
    "    5      |    14    |          21           \n"
    "    6      |    15    |          20           \n"
    "    7      |    16    |          19           \n"
    "    8      |    17    |          18           \n"
    "    9      |    19    |      16 (final)       \n"
    "\n"
)


# ── tests ─────────────────────────────────────────────────────────────────────

class TestCICPruningOutput:
    """Validates that the full printed output is identical to the reference."""

    def test_n3_r8_m1_bin1_bout8(self):
        """3rd-order, R=8 decimation — PDM-to-PCM scenario."""
        assert normalize(capture(N=3, R=8, M=1, Bin=1, Bout=8)) == EXPECTED_N3_R8

    def test_n4_r25_m1_bin16_bout16(self):
        """Classic 4th-order, R=25 decimation — 16-bit audio scenario."""
        assert normalize(capture(N=4, R=25, M=1, Bin=16, Bout=16)) == EXPECTED_N4_R25


class TestCICPruningSpotChecks:
    """Spot-checks specific lines in the output for targeted verification."""

    def test_n3_bit_growth(self):
        out = capture(N=3, R=8, M=1, Bin=1, Bout=8)
        assert "Max Bit Growth Due To Gain  = 9" in out

    def test_n3_max_accumulator_width(self):
        out = capture(N=3, R=8, M=1, Bin=1, Bout=8)
        assert "Max Accumulator Width = 10" in out

    def test_n3_final_stage_bout(self):
        """Final stage must report Bout as the accumulator width."""
        out = capture(N=3, R=8, M=1, Bin=1, Bout=8)
        assert "8 (final)" in out

    def test_n4_bit_growth(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "Max Bit Growth Due To Gain  = 19" in out

    def test_n4_max_accumulator_width(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "Max Accumulator Width = 35" in out

    def test_n4_final_stage_bout(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "16 (final)" in out

    def test_n4_stage_count(self):
        """A 4th-order filter must produce exactly 2*N+1 = 9 stage rows."""
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        stage_rows = [line for line in out.splitlines() if line.strip().startswith(tuple("123456789"))]
        assert len(stage_rows) == 9


# ── CLI tests ─────────────────────────────────────────────────────────────────

def capture_main(argv: list[str]) -> str:
    buf = io.StringIO()
    sys.stdout = buf
    try:
        main(argv)
    finally:
        sys.stdout = sys.__stdout__
    return buf.getvalue()


class TestCICPruningCLI:
    """Validates the argparse CLI entry point."""

    def test_cli_defaults_match_n3_r8(self):
        """Running with no args must produce the N=3,R=8 PDM scenario output."""
        assert normalize(capture_main([])) == EXPECTED_N3_R8

    def test_cli_explicit_n3_r8(self):
        out = capture_main(["--N", "3", "--R", "8", "--M", "1", "--Bin", "1", "--Bout", "8"])
        assert normalize(out) == EXPECTED_N3_R8

    def test_cli_n4_r25(self):
        out = capture_main(["--N", "4", "--R", "25", "--M", "1", "--Bin", "16", "--Bout", "16"])
        assert normalize(out) == EXPECTED_N4_R25

    def test_cli_r_parameter(self):
        out = capture_main(["--N", "3", "--R", "16", "--M", "1", "--Bin", "1", "--Bout", "8"])
        assert "R = 16" in out

    def test_cli_m_parameter(self):
        out = capture_main(["--N", "3", "--R", "8", "--M", "2", "--Bin", "1", "--Bout", "8"])
        assert "M = 2" in out


# ── plot tests ────────────────────────────────────────────────────────────────

class TestCICPruningPlot:
    """Validates the optional --plot argument."""

    def test_plot_flag_accepted(self, monkeypatch):
        """--plot must be accepted without error (plt.show is suppressed)."""
        import matplotlib
        matplotlib.use("Agg")
        monkeypatch.setattr("matplotlib.pyplot.show", lambda: None)
        main(["--plot"])

    def test_plot_flag_with_explicit_params(self, monkeypatch):
        """--plot works together with explicit N/R/M/Bin/Bout arguments."""
        import matplotlib
        matplotlib.use("Agg")
        monkeypatch.setattr("matplotlib.pyplot.show", lambda: None)
        main(["--N", "4", "--R", "25", "--M", "1", "--Bin", "16", "--Bout", "16", "--plot"])

    def test_plot_without_flag_does_not_call_show(self, monkeypatch):
        """Without --plot, plt.show must never be called."""
        show_called = []
        import matplotlib
        matplotlib.use("Agg")
        monkeypatch.setattr("matplotlib.pyplot.show", lambda: show_called.append(True))
        main([])
        assert show_called == []


# ── passband tests ────────────────────────────────────────────────────────────

class TestCICPruningPassband:
    """Validates compute_passband_metrics() and the --passband CLI flag."""

    def _params_n3_r8(self):
        return compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)

    def test_droop_is_negative_db(self):
        droop, _ = compute_passband_metrics(self._params_n3_r8(), passband=0.8)
        assert droop < 0.0

    def test_alias_attenuation_is_positive_db(self):
        _, alias = compute_passband_metrics(self._params_n3_r8(), passband=0.8)
        assert alias > 0.0

    def test_droop_zero_at_dc(self):
        # Very narrow passband (near DC) should have near-zero droop
        droop, _ = compute_passband_metrics(self._params_n3_r8(), passband=0.001)
        assert droop > -0.1

    def test_droop_worsens_with_wider_passband(self):
        p = self._params_n3_r8()
        droop_narrow, _ = compute_passband_metrics(p, passband=0.3)
        droop_wide, _ = compute_passband_metrics(p, passband=0.9)
        assert droop_narrow > droop_wide  # less negative = less droop

    def test_alias_attenuation_improves_with_more_stages(self):
        p_n3 = compute_cic_params(N=3, R=8, M=1, Bin=1, Bout=8)
        p_n5 = compute_cic_params(N=5, R=8, M=1, Bin=1, Bout=8)
        _, alias_n3 = compute_passband_metrics(p_n3, passband=0.8)
        _, alias_n5 = compute_passband_metrics(p_n5, passband=0.8)
        assert alias_n5 > alias_n3

    def test_cli_passband_prints_analysis(self):
        out = capture_main(["--passband", "0.8"])
        assert "Passband Analysis" in out
        assert "Passband droop" in out
        assert "Aliasing band attenuation" in out

    def test_cli_without_passband_no_analysis(self):
        out = capture_main([])
        assert "Passband Analysis" not in out

    def test_cli_passband_values_are_finite(self):
        out = capture_main(["--N", "3", "--R", "8", "--M", "1", "--Bin", "1", "--Bout", "8",
                            "--passband", "0.8"])
        # Both values must end in " dB" and be real numbers
        import re
        matches = re.findall(r"=\s*([-\d.]+)\s*dB", out)
        assert len(matches) == 2
        assert all(math.isfinite(float(v)) for v in matches)

"""Tests that verify calculate_cic_pruning produces the correct output."""

import io
import sys

import pytest

from cic_pruning import calculate_cic_pruning


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
    "\n=== CIC Filter Parameters: N=3, R=8, M=1, Bin=1, Bout=8 ===\n"
    "Max Bit Growth Due To Gain  = 9\n"
    "Max Accumulator Width       = 10\n"
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
    "\n=== CIC Filter Parameters: N=4, R=25, M=1, Bin=16, Bout=16 ===\n"
    "Max Bit Growth Due To Gain  = 19\n"
    "Max Accumulator Width       = 35\n"
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
        assert "Max Accumulator Width       = 10" in out

    def test_n3_final_stage_bout(self):
        """Final stage must report Bout as the accumulator width."""
        out = capture(N=3, R=8, M=1, Bin=1, Bout=8)
        assert "8 (final)" in out

    def test_n4_bit_growth(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "Max Bit Growth Due To Gain  = 19" in out

    def test_n4_max_accumulator_width(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "Max Accumulator Width       = 35" in out

    def test_n4_final_stage_bout(self):
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        assert "16 (final)" in out

    def test_n4_stage_count(self):
        """A 4th-order filter must produce exactly 2*N+1 = 9 stage rows."""
        out = capture(N=4, R=25, M=1, Bin=16, Bout=16)
        stage_rows = [line for line in out.splitlines() if line.strip().startswith(tuple("123456789"))]
        assert len(stage_rows) == 9

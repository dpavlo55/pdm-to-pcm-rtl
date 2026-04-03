"""
pdm_generator.py — Generate a first-order sigma-delta PDM bit-stream for a
sine-wave stimulus and write each sample (0 or 1) on its own line.

Usage:
  python pdm_generator.py [--freq 10000] [--fs 2000000] [--num-samples 20000]
                          [--amp 0.9] [--outdir ../../sim]

Arguments:
  --freq        Sine signal frequency in Hz          (default: 10 000)
  --fs          PDM clock / sample rate in Hz        (default: 2 000 000)
  --num-samples Number of PDM samples to emit        (default: 20 000)
  --amp         Normalised sine amplitude  [0, 1)    (default: 0.9)
  --outdir      Output directory                     (default: ../../sim)
  --outfile     Override the auto-generated filename (default: auto)

The output filename is auto-generated as:
  pdm_<freq_kHz>kHz_<fs_MHz>MHz.txt
e.g.  pdm_10kHz_2MHz.txt
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path


def generate_pdm(freq: float, fs: float, num_samples: int, amp: float) -> list[int]:
    """Return a list of `num_samples` PDM bits for a sine at `freq` Hz.

    Uses first-order sigma-delta modulation:
      err += x[n]
      if err >= 0: output 1, err -= 1
      else:        output 0, err += 1
    """
    if not (0.0 < amp < 1.0):
        raise ValueError(f"amp must be in the open interval (0, 1), got {amp}")
    if freq >= fs / 2:
        raise ValueError(f"freq {freq} Hz must be below Nyquist ({fs / 2} Hz)")

    pdm: list[int] = []
    err = 0.0
    for i in range(num_samples):
        x = amp * math.sin(2.0 * math.pi * freq * i / fs)
        err += x
        if err >= 0.0:
            pdm.append(1)
            err -= 1.0
        else:
            pdm.append(0)
            err += 1.0
    return pdm


def _auto_filename(freq: float, fs: float) -> str:
    """Build a descriptive filename from freq / fs."""
    freq_khz = freq / 1e3
    fs_mhz   = fs   / 1e6

    # Format without unnecessary trailing zeros
    def fmt(v: float) -> str:
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        return s

    return f"pdm_{fmt(freq_khz)}kHz_{fmt(fs_mhz)}MHz.txt"


def main(argv: list[str] | None = None) -> None:
    script_dir = Path(__file__).parent
    default_outdir = str(script_dir / ".." / ".." / "sim")

    parser = argparse.ArgumentParser(
        description="Generate a PDM bit-stream for a sine stimulus (first-order sigma-delta)."
    )
    parser.add_argument("--freq",        type=float, default=10_000,   help="Sine frequency in Hz (default: 10000)")
    parser.add_argument("--fs",          type=float, default=2_000_000, help="PDM sample rate in Hz (default: 2000000)")
    parser.add_argument("--num-samples", type=int,   default=20_000,   help="Number of PDM samples (default: 20000)")
    parser.add_argument("--amp",         type=float, default=0.9,      help="Normalised amplitude 0<amp<1 (default: 0.9)")
    parser.add_argument("--outdir",      default=default_outdir,       help="Output directory (default: ../../sim)")
    parser.add_argument("--outfile",     default=None,                 help="Override output filename")
    args = parser.parse_args(argv)

    pdm_bits = generate_pdm(
        freq=args.freq,
        fs=args.fs,
        num_samples=args.num_samples,
        amp=args.amp,
    )

    filename = args.outfile if args.outfile else _auto_filename(args.freq, args.fs)
    outdir   = Path(os.path.realpath(args.outdir))
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / filename

    out_path.write_text("\n".join(str(b) for b in pdm_bits) + "\n", encoding="utf-8")

    print(f"Written {len(pdm_bits)} PDM samples -> {out_path}")
    print(f"  sine freq   : {args.freq / 1e3:.3f} kHz")
    print(f"  sample rate : {args.fs / 1e6:.3f} MHz")
    print(f"  amplitude   : {args.amp}")
    ones = sum(pdm_bits)
    print(f"  duty cycle  : {100.0 * ones / len(pdm_bits):.1f}%  ({ones}/{len(pdm_bits)} ones)")


if __name__ == "__main__":
    main()

import argparse
import math
from dataclasses import dataclass, field
from typing import List


@dataclass
class StageParams:
    index: int        # 1-based stage index (1 to 2*N)
    bj: int           # effective Bj (0 if raw value was negative)
    width: int        # accumulator width = max_width - bj


@dataclass
class CicParams:
    N: int
    R: int
    M: int
    Bin: int
    Bout: int
    bit_growth: int
    max_width: int
    trunc_bits: int
    stages: List[StageParams] = field(default_factory=list)
    b1_adjusted: bool = False  # True when B1 was forced to 0 (DSPRelated Jan. 2022 update)


def compute_cic_params(N: int, R: int, M: int, Bin: int, Bout: int) -> CicParams:
    """
    Compute Hogenauer pruning parameters for a CIC filter.

    Returns a CicParams dataclass with per-stage widths and global metrics.
    Does not print anything — use calculate_cic_pruning() for display.
    """
    F_sub_j = [0.0] * (2 * N + 1)

    for j in range(N - 1, 0, -1):
        F_sub_j[j - 1] = _compute_integrator_f(j, N, R, M)

    f_comb = [math.sqrt(math.comb(2 * k, k)) for k in range(1, N + 1)]
    F_sub_j[N - 1] = f_comb[N - 2] * math.sqrt(R * M)

    for j in range(2 * N, N, -1):
        F_sub_j[j - 1] = f_comb[2 * N - j]

    F_sub_j[2 * N] = 1.0

    bit_growth = math.ceil(math.log2((R * M) ** N))
    max_width = bit_growth + Bin
    trunc_bits = max_width - Bout

    noise_std_log2 = math.log2(math.sqrt(((2 ** trunc_bits) ** 2) / 12.0))
    half_log2_6_over_n = 0.5 * math.log2(6.0 / N)

    B_sub_j = [
        math.floor(-math.log2(f) + noise_std_log2 + half_log2_6_over_n)
        for f in F_sub_j
    ]

    # Hogenauer B1 fix (DSPRelated Jan. 2022 update):
    # If pruning recommends truncating the input before the first integrator
    # (B1 > 0), set B1 = 0 and push that truncation to the second stage
    # (B2 += 1).  This avoids a 6 dB SNR penalty on the input sequence
    # before any filtering takes place.
    b1_adjusted = False
    if B_sub_j[0] > 0:
        B_sub_j[0] = 0
        B_sub_j[1] += 1
        b1_adjusted = True

    stages: List[StageParams] = []
    for idx, bj_raw in enumerate(B_sub_j[:-1], start=1):
        _, bj_eff = _format_bj(int(bj_raw))
        stages.append(StageParams(index=idx, bj=bj_eff, width=max_width - bj_eff))

    return CicParams(
        N=N, R=R, M=M, Bin=Bin, Bout=Bout,
        bit_growth=bit_growth,
        max_width=max_width,
        trunc_bits=trunc_bits,
        stages=stages,
        b1_adjusted=b1_adjusted,
    )


def _compute_integrator_f(j: int, N: int, R: int, M: int) -> float:
    """Compute F_sub_j for integrator stage j (stages 1 to N-1)."""
    max_k = (R * M - 1) * N + j - 1
    h = [
        sum(
            ((-1) ** L) * math.comb(N, L) * math.comb(N - j + k - R * M * L, k - R * M * L)
            for L in range(k // (R * M) + 1)
        )
        for k in range(max_k + 1)
    ]
    return math.sqrt(sum(x**2 for x in h))


def _format_bj(bj_raw: int) -> tuple[str, int]:
    """Return (display_string, effective_value) for a Bj truncation value."""
    if bj_raw < 0:
        return f"0 ({bj_raw})", 0
    return str(bj_raw), bj_raw


def compute_passband_metrics(params: CicParams, passband: float) -> tuple[float, float]:
    """
    Compute passband droop and worst-case aliasing band attenuation.

    passband: useful bandwidth as a fraction of the output Nyquist frequency
              (0 < passband <= 1, e.g. 0.8 = 80% of output Nyquist)

    Returns (droop_db, alias_attenuation_db):
      droop_db             -- magnitude loss at the passband edge (negative dB)
      alias_attenuation_db -- minimum attenuation across all aliasing bands (positive dB)
    """
    import numpy as np

    N, R, M = params.N, params.R, params.M

    # Passband edge in input-normalized frequency (fraction of input sample rate)
    f_pass = passband * 0.5 / R

    # Normalized CIC magnitude response: DC = 1
    def _H(f: "np.ndarray") -> "np.ndarray":
        f = np.asarray(f, dtype=float)
        f_safe = np.where(np.abs(f) < 1e-12, 1e-12, f)
        return (np.abs(np.sin(np.pi * f_safe * R * M) / np.sin(np.pi * f_safe))) ** N / (R * M) ** N

    # Passband droop: attenuation at the passband edge
    droop_db = float(20.0 * np.log10(max(float(_H(np.array([f_pass]))[0]), 1e-12)))

    # Aliasing bands: for k = 1..R-1, frequencies [k/R - f_pass, k/R + f_pass]
    # clipped to (f_pass, 0.5) to exclude the passband itself.
    # The worst (least attenuated) alias determines the attenuation figure.
    worst_alias_mag = 0.0
    for k in range(1, R):
        f_center = k / R
        f_lo = max(f_center - f_pass, f_pass + 1e-10)
        f_hi = min(f_center + f_pass, 0.5 - 1e-10)
        if f_lo >= f_hi:
            continue
        mags = _H(np.linspace(f_lo, f_hi, 1000))
        worst_alias_mag = max(worst_alias_mag, float(np.max(mags)))

    alias_attenuation_db = -20.0 * np.log10(max(worst_alias_mag, 1e-12))
    return droop_db, alias_attenuation_db


def calculate_cic_pruning(N: int, R: int, M: int, Bin: int, Bout: int, passband: float | None = None) -> None:
    """
    Calculates and prints the Hogenauer pruning table for a CIC filter.
    """
    print(f"\nCIC Filter Parameters:")
    print(f"    N = {N} (number of stages)")
    print(f"    R = {R} (sample rate change)")
    print(f"    M = {M} (comb filter differential delay)")
    print(f"    Bin = {Bin} (input bit width)")
    print(f"    Bout = {Bout} (output bit width)")

    params = compute_cic_params(N, R, M, Bin, Bout)

    # Display Results
    print(f"\nMax Bit Growth Due To Gain  = {params.bit_growth}")
    print(f"Max Accumulator Width = {params.max_width}")
    print("\n" + f"{'Stage(j)':^10} | {'Bj':^8} | {'Accum (adder) width':^21}")
    print("-" * 47)

    # Reconstruct raw Bj for display (bj_raw may be negative before clamping)
    F_sub_j = [0.0] * (2 * N + 1)
    for j in range(N - 1, 0, -1):
        F_sub_j[j - 1] = _compute_integrator_f(j, N, R, M)
    f_comb = [math.sqrt(math.comb(2 * k, k)) for k in range(1, N + 1)]
    F_sub_j[N - 1] = f_comb[N - 2] * math.sqrt(R * M)
    for j in range(2 * N, N, -1):
        F_sub_j[j - 1] = f_comb[2 * N - j]
    F_sub_j[2 * N] = 1.0
    noise_std_log2 = math.log2(math.sqrt(((2 ** params.trunc_bits) ** 2) / 12.0))
    half_log2_6_over_n = 0.5 * math.log2(6.0 / N)
    B_sub_j_raw = [
        math.floor(-math.log2(f) + noise_std_log2 + half_log2_6_over_n)
        for f in F_sub_j
    ]

    # Mirror the B1 fix applied in compute_cic_params for display consistency
    show_b1_adjusted = False
    if B_sub_j_raw[0] > 0:
        B_sub_j_raw[0] = 0
        B_sub_j_raw[1] += 1
        show_b1_adjusted = True

    for stage, bj_raw in enumerate(B_sub_j_raw[:-1], start=1):
        bj_display, bj_effective = _format_bj(int(bj_raw))
        print(f"{stage:^10} | {bj_display:^8} | {params.max_width - bj_effective:^21}")

    # Final output stage
    bj_final_display, _ = _format_bj(int(params.trunc_bits))
    print(f"{2 * N + 1:^10} | {bj_final_display:^8} | {f'{Bout} (final)':^21}")

    if show_b1_adjusted:
        print("Note: B1 was set to 0 and B2 incremented by 1 (see DSPRelated Jan. 2022 update).")
    print()

    if passband is not None:
        droop_db, alias_db = compute_passband_metrics(params, passband)
        f_pass_in = passband * 0.5 / R
        print(f"Passband Analysis (BW = {passband} × output Nyquist = {f_pass_in:.5f} × f_in):")
        print(f"    Passband droop            = {droop_db:.2f} dB")
        print(f"    Aliasing band attenuation = {alias_db:.2f} dB\n")


def plot_frequency_response(params: CicParams, fs: float | None = None, comp: bool = False) -> None:
    """Plot the CIC filter magnitude response (requires matplotlib and numpy)."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        raise ImportError(
            "matplotlib and numpy are required for plotting. "
            "Install with: pip install matplotlib numpy"
        ) from exc

    N, R, M = params.N, params.R, params.M
    fs_scale = fs if fs is not None else 1.0

    # Frequency axis: normalized to input sample rate (0 to 0.5)
    # Small offset avoids sin(0)/0 at DC
    f_norm = np.linspace(1e-6, 0.5, 8000)
    f_plot = f_norm * fs_scale

    # CIC magnitude: |sin(π·f·R·M) / sin(π·f)|^N, normalized by DC gain (R·M)^N
    H_mag = (np.abs(np.sin(np.pi * f_norm * R * M) / np.sin(np.pi * f_norm))) ** N
    H_db = 20 * np.log10(np.maximum(H_mag / (R * M) ** N, 1e-10))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(f_plot, H_db, linewidth=1.5, label='CIC response')

    if comp:
        # CFIR runs at output rate, so its normalized frequency is f_norm * R
        # Transfer function: H_comp(z) = -0.0625 + 1.125*z^-1 - 0.0625*z^-2
        # Amplitude response is |1.125 - 0.125 * cos(2*pi*f_norm*R)|
        H_comp_mag = np.abs(1.125 - 0.125 * np.cos(2 * np.pi * f_norm * R))
        H_comp_db = 20 * np.log10(np.maximum(H_comp_mag, 1e-10))
        H_total_db = H_db + H_comp_db

        ax.plot(f_plot, H_comp_db, linewidth=1.5, linestyle='--', color='orange', label='CFIR response')
        ax.plot(f_plot, H_total_db, linewidth=1.5, color='purple', label='Total (CIC + CFIR)')

    # Output Nyquist: highest frequency preserved after decimation
    f_out_nyq = (0.5 / R) * fs_scale
    nyq_label = f'Output Nyquist (fs/{2 * R})' if fs is not None else f'Output Nyquist (1/{2 * R} · fs_in)'
    ax.axvline(f_out_nyq, color='g', linestyle='--',
               label=nyq_label)

    # Nulls at f = k / (R·M)
    null_freqs = [k / (R * M) * fs_scale for k in range(1, R * M + 1) if k / (R * M) <= 0.5]
    for i, fn in enumerate(null_freqs):
        ax.axvline(fn, color='r', linestyle=':', alpha=0.6,
                   label='Nulls (k/(R·M))' if i == 0 else '_')

    ax.set_title(
        f'CIC Filter Frequency Response — '
        f'N={N}, R={R}, M={M}, Bin={params.Bin}, Bout={params.Bout}'
    )
    xlabel = 'Frequency (Hz)' if fs is not None else 'Normalized frequency (× input sample rate)'
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Magnitude (dB)')
    ax.set_xlim(0, 0.5 * fs_scale)
    ax.set_ylim(bottom=max(float(H_db.min()) - 5, -120))
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def main(argv: list[str] | None = None) -> None:
    """
    Standalone entry point — print the Hogenauer pruning table for a CIC filter.

    Parameters follow standard CIC filter notation:
      N   Number of stages
      R   Sample rate change (decimation ratio)
      M   Comb differential delay (typically 1 or 2)
      Bin Input bit width
      Bout Output bit width
    """
    parser = argparse.ArgumentParser(
        description="Print the Hogenauer pruning table for a CIC decimation filter."
    )
    parser.add_argument("--N",    type=int, default=3,  help="Number of stages (default: 3)")
    parser.add_argument("--R",    type=int, default=8,  help="Decimation ratio (default: 8)")
    parser.add_argument("--M",    type=int, default=1,  help="Comb differential delay, 1 or 2 (default: 1)")
    parser.add_argument("--Bin",  type=int, default=1,  help="Input bit width (default: 1)")
    parser.add_argument("--Bout", type=int, default=8,  help="Output bit width (default: 8)")
    parser.add_argument("--plot", action="store_true", help="Show frequency response plot (requires matplotlib+numpy)")
    parser.add_argument("--passband", type=float, default=None,
                        metavar="BW",
                        help="Useful bandwidth as a fraction of output Nyquist (0 < BW <= 1). "
                             "Prints passband droop and aliasing band attenuation.")
    parser.add_argument("--fs", type=float, default=None,
                        help="Input sampling frequency in Hz (used to scale the plot X-axis up to fs/2)")
    parser.add_argument("--comp", action="store_true", default=False,
                        help="Plot the compensation filter and total response (when --plot is used)")
    args = parser.parse_args(argv)
    calculate_cic_pruning(N=args.N, R=args.R, M=args.M, Bin=args.Bin, Bout=args.Bout, passband=args.passband)
    if args.plot:
        params = compute_cic_params(N=args.N, R=args.R, M=args.M, Bin=args.Bin, Bout=args.Bout)
        plot_frequency_response(params, fs=args.fs, comp=args.comp)


if __name__ == "__main__":
    main()
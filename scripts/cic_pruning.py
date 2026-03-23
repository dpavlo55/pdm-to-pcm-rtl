import math


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


def calculate_cic_pruning(N: int, R: int, M: int, Bin: int, Bout: int) -> None:
    """
    Calculates and prints the Hogenauer pruning table for a CIC filter.
    """
    print(f"\n=== CIC Filter Parameters: N={N}, R={R}, M={M}, Bin={Bin}, Bout={Bout} ===")

    F_sub_j = [0.0] * (2 * N + 1)

    # 1. Find h_sub_j and F_sub_j values for (N-1) cascaded integrators
    for j in range(N - 1, 0, -1):
        F_sub_j[j - 1] = _compute_integrator_f(j, N, R, M)

    # 2. Define F_sub_j values dynamically for N cascaded combs
    f_comb = [math.sqrt(math.comb(2 * k, k)) for k in range(1, N + 1)]

    # 3. Compute F_sub_j for the last integrator stage (Stage N)
    F_sub_j[N - 1] = f_comb[N - 2] * math.sqrt(R * M)

    # 4. Compute F_sub_j for N cascaded filter comb stages
    for j in range(2 * N, N, -1):
        F_sub_j[j - 1] = f_comb[2 * N - j]

    # 5. Define F_sub_j value for the final output register truncation
    F_sub_j[2 * N] = 1.0

    # 6. Calculate Noise Variances and Bit Growth
    bit_growth = math.ceil(math.log2((R * M) ** N))
    max_width = bit_growth + Bin
    truncated_bits = max_width - Bout

    noise_std_log2 = math.log2(math.sqrt(((2 ** truncated_bits) ** 2) / 12.0))
    half_log2_6_over_n = 0.5 * math.log2(6.0 / N)

    # 7. Compute desired B_sub_j vector
    B_sub_j = [
        math.floor(-math.log2(f) + noise_std_log2 + half_log2_6_over_n)
        for f in F_sub_j
    ]

    # Display Results
    print(f"Max Bit Growth Due To Gain  = {bit_growth}")
    print(f"Max Accumulator Width       = {max_width}")
    print("\n" + f"{'Stage(j)':^10} | {'Bj':^8} | {'Accum (adder) width':^21}")
    print("-" * 47)

    for stage, bj_raw in enumerate(B_sub_j[:-1], start=1):
        bj_display, bj_effective = _format_bj(int(bj_raw))
        print(f"{stage:^10} | {bj_display:^8} | {max_width - bj_effective:^21}")

    # Final output stage
    bj_final_display, _ = _format_bj(int(truncated_bits))
    print(f"{2 * N + 1:^10} | {bj_final_display:^8} | {f'{Bout} (final)':^21}\n")


if __name__ == "__main__":
    # Your PDM scenario (3rd Order -> outputs 7 rows)
    calculate_cic_pruning(N=3, R=8, M=1, Bin=1, Bout=8)

    # A classic 4th order filter (4th Order -> outputs 9 rows)
    calculate_cic_pruning(N=4, R=25, M=1, Bin=16, Bout=16)
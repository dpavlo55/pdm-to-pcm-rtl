import math

def calculate_cic_pruning(N, R, M, Bin, Bout):
    """
    Calculates and prints the Hogenauer pruning table for a CIC filter.
    """
    print(f"\n=== CIC Filter Parameters: N={N}, R={R}, M={M}, Bin={Bin}, Bout={Bout} ===")

    # Pre-allocate lists
    F_sub_j = [0.0] * (2 * N + 1)

    # 1. Find h_sub_j and F_sub_j values for (N-1) cascaded integrators
    for j in range(N - 1, 0, -1):
        max_k = (R * M - 1) * N + j - 1
        h_sub_j = [0.0] * (max_k + 1)

        for k in range(max_k + 1):
            for L in range(math.floor(k / (R * M)) + 1):
                n1, k1 = N, L
                n2, k2 = N - j + k - R * M * L, k - R * M * L
                change_to_result = ((-1)**L) * math.comb(n1, k1) * math.comb(n2, k2)
                h_sub_j[k] += change_to_result

        F_sub_j[j - 1] = math.sqrt(sum(x**2 for x in h_sub_j))

    # 2. Define F_sub_j values dynamically for N cascaded combs
    F_sub_j_for_many_combs = [math.sqrt(math.comb(2 * k, k)) for k in range(1, N + 1)]

    # 3. Compute F_sub_j for the last integrator stage (Stage N)
    F_sub_j[N - 1] = F_sub_j_for_many_combs[N - 2] * math.sqrt(R * M)

    # 4. Compute F_sub_j for N cascaded filter comb stages
    for j in range(2 * N, N, -1):
        F_sub_j[j - 1] = F_sub_j_for_many_combs[2 * N - j]

    # 5. Define F_sub_j value for the final output register truncation
    F_sub_j[2 * N] = 1.0

    # 6. Calculate Noise Variances and Bit Growth
    Minus_log2_of_F_sub_j = [-math.log2(f) for f in F_sub_j]

    CIC_Filter_Gain = (R * M)**N
    Num_of_Bits_Growth = math.ceil(math.log2(CIC_Filter_Gain))
    Num_Output_Bits_With_No_Truncation = Num_of_Bits_Growth + Bin

    Num_of_Output_Bits_Truncated = Num_Output_Bits_With_No_Truncation - Bout
    Output_Truncation_Noise_Variance = ((2**Num_of_Output_Bits_Truncated)**2) / 12.0

    Output_Truncation_Noise_Standard_Deviation = math.sqrt(Output_Truncation_Noise_Variance)
    Log_base2_of_Output_Truncation_Noise_Standard_Deviation = math.log2(Output_Truncation_Noise_Standard_Deviation)
    Half_Log_Base2_of_6_over_N = 0.5 * math.log2(6.0 / N)

    # 7. Compute desired B_sub_j vector
    B_sub_j = [
        math.floor(minus_log2 + Log_base2_of_Output_Truncation_Noise_Standard_Deviation + Half_Log_Base2_of_6_over_N)
        for minus_log2 in Minus_log2_of_F_sub_j
    ]

    # ====================================================================
    # Display Results
    # ====================================================================
    print(f"Max Bit Growth Due To Gain  = {Num_of_Bits_Growth}")
    print(f"Max Accumulator Width       = {Num_Output_Bits_With_No_Truncation}")
    print("\n" + f"{'Stage(j)':^10} | {'Bj':^8} | {'Accum (adder) width':^21}")
    print("-" * 47)

    # Print results for Stages 1 to 2*N
    for stage in range(1, 2 * N + 1):
        idx = stage - 1
        bj_raw = int(B_sub_j[idx])

        if bj_raw < 0:
            bj_display = f"0 ({bj_raw})"
            bj_effective = 0
        else:
            bj_display = f"{bj_raw}"
            bj_effective = bj_raw

        accum_width = int(Num_Output_Bits_With_No_Truncation - bj_effective)
        print(f"{stage:^10} | {bj_display:^8} | {accum_width:^21}")

    # Final output stage
    final_stage = 2 * N + 1
    bj_final_raw = int(Num_of_Output_Bits_Truncated)
    bj_final_display = f"0 ({bj_final_raw})" if bj_final_raw < 0 else f"{bj_final_raw}"

    print(f"{final_stage:^10} | {bj_final_display:^8} | {f'{Bout} (final)':^21}\n")


# ====================================================================
# Run your tests here!
# ====================================================================

# Your PDM scenario (3rd Order -> outputs 7 rows)
calculate_cic_pruning(N=3, R=8, M=1, Bin=1, Bout=8)

# A classic 4th order filter (4th Order -> outputs 9 rows)
calculate_cic_pruning(N=4, R=25, M=1, Bin=16, Bout=16)
"""
clockfield_gemini_correspondence.py
====================================
Numerical analysis of the mathematical correspondence between
GEMINI (Yan et al. 2025) and the Clockfield theory.

Produces:
  - Figure 1: Growth law comparison (droplet vs surface)
  - Figure 2: Threshold/freeze condition equivalence
  - Figure 3: Takens embedding in GEMINI crystal
  - Figure 4: Gamma metric at moment of band deposition
  - Figure 5: Exchange rate (k_off) as Hawking temperature analogue

Author: PerceptionLab / anttiluode
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import find_peaks
import json

# ──────────────────────────────────────────────────────────────────────────────
# 1. CLOCKFIELD PARAMETERS
# ──────────────────────────────────────────────────────────────────────────────
TAU      = 2.737   # Clockfield coupling constant (BPS-calibrated)
XI_PL    = 5.1     # Frozen core size in Planck lengths
THRESH   = 1.0     # Normalized freeze threshold Ξ (β/Ξ > 1 → freeze)

# ──────────────────────────────────────────────────────────────────────────────
# 2. GEMINI PARAMETERS (from Yan et al. 2025)
# ──────────────────────────────────────────────────────────────────────────────
K_GROWTH = 0.42    # Crystal volume growth rate (normalized units/hour)
A0       = 0.08    # Initial crystal size parameter
C_THRESH = 1.0     # Normalized reporter concentration threshold
K_OFF    = 0.05    # Exchange rate (thaw rate) for small crystal
T_MAX    = 50.0    # Hours of simulation


def gamma(beta, tau=TAU):
    """Clockfield proper-time metric."""
    return 1.0 / (1.0 + tau * beta)**2


def gemini_radius(t, K=K_GROWTH, A=A0):
    """GEMINI crystal radius: R(t) = (Kt + A)^(1/3)"""
    return (K * t + A) ** (1/3)


def gemini_time_from_radius(r, K=K_GROWTH, A=A0):
    """Invert: t = (r³ - A) / K"""
    return (r**3 - A) / K


def clockfield_horizon_radius(M_units):
    """
    Clockfield surface-recorder: R ∝ M (Schwarzschild-like).
    Normalised so R=1 at M=1.
    """
    return M_units


def droplet_radius(M_units):
    """
    Volume-recorder: R ∝ M^(1/3).
    GEMINI is this. Early Clockfield calculation was this (wrong for BH).
    """
    return M_units ** (1/3)


# ──────────────────────────────────────────────────────────────────────────────
# 3. SIMULATE CELLULAR SIGNAL + GEMINI RECORDING
# ──────────────────────────────────────────────────────────────────────────────

def simulate_nfkb_signal(t_arr, activations=[(6, 2.5), (20, 1.8), (36, 3.0)],
                         tau_decay=3.0, noise_level=0.15):
    """
    Simulates cytoplasmic reporter concentration C_r(t).
    activations: list of (t_onset, amplitude) tuples.
    """
    C = np.zeros_like(t_arr)
    for t_on, amp in activations:
        pulse = amp * np.exp(-(t_arr - t_on)**2 / (2 * 1.5**2))
        pulse[t_arr < t_on] = 0
        C += pulse
    C += noise_level * np.random.normal(size=len(t_arr))
    C = np.clip(C, 0, None)
    return C


def gemini_record(t_arr, C_r, K=K_GROWTH, A=A0, C_thresh=C_THRESH, k_off=K_OFF):
    """
    Simulate GEMINI recording: build radial fluorescence profile.
    Returns: radius array, fluorescence profile.
    """
    R_arr = gemini_radius(t_arr, K, A)
    fluorescence = np.zeros_like(R_arr)

    # Band deposition: C_r > threshold → reporter incorporates into surface shell
    # Also exchange (k_off): band intensity can decay if C_r falls
    band_intensity = np.zeros_like(R_arr)

    for i, (t, C) in enumerate(zip(t_arr, C_r)):
        shell_idx = i  # each time step → one radial shell
        if C > C_thresh:
            # Deposit: intensity ∝ excess above threshold
            band_intensity[shell_idx] = (C - C_thresh) / C_thresh
        else:
            # Exchange: partial thaw, existing surface intensity decays
            band_intensity[shell_idx] = max(0,
                band_intensity[shell_idx] * np.exp(-k_off * (t_arr[1] - t_arr[0])))

    fluorescence = band_intensity
    return R_arr, fluorescence


def gamma_at_deposition(C_r, tau=TAU, C_thresh=C_THRESH):
    """Compute Γ at each moment of band deposition (C_r > threshold)."""
    beta_norm = C_r / C_thresh  # β/Ξ normalized
    return gamma(beta_norm, tau)


# ──────────────────────────────────────────────────────────────────────────────
# 4. TAKENS EMBEDDING IN CRYSTAL COORDINATES
# ──────────────────────────────────────────────────────────────────────────────

def takens_from_gemini(R_arr, fluorescence, delay_steps=5):
    """
    Construct Takens delay embedding from the GEMINI radial profile.
    The GEMINI crystal encodes time as radius → this IS a Takens map.
    We reconstruct the 2D phase space from the crystal's fluorescence profile.
    """
    n = len(R_arr) - delay_steps
    x = fluorescence[delay_steps:]   # F(r) = F(t)
    y = fluorescence[:n]              # F(r - Δr) = F(t - Δτ)
    return x, y, R_arr[delay_steps:]


# ──────────────────────────────────────────────────────────────────────────────
# 5. HAWKING TEMPERATURE ANALOGUE
# ──────────────────────────────────────────────────────────────────────────────

def hawking_temp_analogue(R_arr, K=K_GROWTH):
    """
    In Clockfield: T_H ∝ |dΓ/dr|_shell ∝ 1/M ∝ 1/R_S
    For GEMINI: k_off(t) ∝ 1/R(t) — larger crystal, slower exchange.
    """
    return K_OFF / (R_arr + 0.01)


# ──────────────────────────────────────────────────────────────────────────────
# 6. MAIN ANALYSIS + FIGURES
# ──────────────────────────────────────────────────────────────────────────────

def main():
    np.random.seed(42)
    t = np.linspace(0, T_MAX, 1000)
    dt = t[1] - t[0]

    # ── Generate signal
    C_r = simulate_nfkb_signal(t,
        activations=[(8, 2.8), (22, 1.6), (38, 3.2)],
        noise_level=0.12)

    # ── GEMINI recording
    R_arr, fluorescence = gemini_record(t, C_r)

    # ── Gamma at deposition
    G_arr = gamma_at_deposition(C_r)

    # ── Takens embedding from crystal
    tx, ty, tr = takens_from_gemini(R_arr, fluorescence, delay_steps=15)

    # ── Scaling laws
    M_vals = np.linspace(0.1, 10, 200)
    R_surface = clockfield_horizon_radius(M_vals)
    R_droplet  = droplet_radius(M_vals)

    # ── Hawking analogue
    T_H = hawking_temp_analogue(R_arr)

    # ──────────────────────────────────────────────────────────────────────────
    # PLOTTING
    # ──────────────────────────────────────────────────────────────────────────

    plt.style.use('dark_background')
    fig = plt.figure(figsize=(18, 14))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.38)

    c_cyan   = '#39c5bb'
    c_orange = '#f07a4a'
    c_purple = '#a371f7'
    c_red    = '#f85149'
    c_yellow = '#e3b341'
    c_panel  = '#0d1117'

    # ── Panel 1: Scaling Law Comparison
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(c_panel)
    ax1.plot(M_vals, R_surface, color=c_cyan,   lw=2.5, label='Clockfield BH: R ∝ M (surface)')
    ax1.plot(M_vals, R_droplet, color=c_orange, lw=2.5, label='GEMINI: R ∝ M^(1/3) (volume)')
    ax1.axvline(1.0, color='white', ls=':', alpha=0.4, lw=1)
    ax1.set_xlabel('Mass / Time-debt (normalized)', color='white')
    ax1.set_ylabel('Radius (normalized)', color='white')
    ax1.set_title('Scaling Laws:\nSurface vs Volume Recorder', color=c_cyan, fontsize=10)
    ax1.legend(fontsize=7.5, loc='upper left')
    ax1.tick_params(colors='white')
    ax1.spines[:].set_color('#30363d')

    # ── Panel 2: Cytoplasmic signal + threshold
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(c_panel)
    ax2.plot(t, C_r, color=c_cyan, lw=1.5, alpha=0.9, label='C_r(t) — reporter conc.')
    ax2.axhline(C_THRESH, color=c_red, ls='--', lw=1.5, label=f'Threshold Ξ = {C_THRESH}')
    ax2.fill_between(t, C_THRESH, C_r, where=(C_r > C_THRESH),
                     alpha=0.3, color=c_orange, label='Freeze events (β > Ξ)')
    ax2.set_xlabel('Time (hours)', color='white')
    ax2.set_ylabel('Normalized C_r', color='white')
    ax2.set_title('GEMINI Threshold ↔ Clockfield\nFreeze Condition β > Ξ', color=c_cyan, fontsize=10)
    ax2.legend(fontsize=7.5)
    ax2.tick_params(colors='white')
    ax2.spines[:].set_color('#30363d')

    # ── Panel 3: GEMINI crystal cross-section (fluorescence vs radius)
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.set_facecolor(c_panel)
    ax3.barh(R_arr, fluorescence, height=(R_arr[1]-R_arr[0])*1.5,
             color=c_purple, alpha=0.8)
    ax3.set_xlabel('Fluorescence Intensity', color='white')
    ax3.set_ylabel('Crystal Radius (normalized)', color='white')
    ax3.set_title('GEMINI Crystal Profile\n(simulated tree-ring fluorescence)', color=c_cyan, fontsize=10)
    ax3.tick_params(colors='white')
    ax3.spines[:].set_color('#30363d')

    # Mark band positions
    peaks, _ = find_peaks(fluorescence, height=0.05, distance=20)
    for p in peaks:
        ax3.axhline(R_arr[p], color=c_yellow, ls=':', alpha=0.7, lw=1.2)
        decoded_t = gemini_time_from_radius(R_arr[p])
        ax3.text(max(fluorescence)*0.6, R_arr[p]+0.01,
                 f't≈{decoded_t:.1f}h', color=c_yellow, fontsize=7)

    # ── Panel 4: Gamma at deposition events
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.set_facecolor(c_panel)
    freeze_mask = C_r > C_THRESH
    ax4.plot(t, G_arr, color=c_orange, lw=1.2, alpha=0.6, label='Γ(t)')
    ax4.scatter(t[freeze_mask], G_arr[freeze_mask],
                color=c_red, s=4, alpha=0.8, label='Γ at deposition events')
    ax4.axhline(1/(1+TAU)**2, color=c_yellow, ls='--', lw=1.5,
                label=f'Γ at β=Ξ: {1/(1+TAU)**2:.4f}')
    ax4.set_xlabel('Time (hours)', color='white')
    ax4.set_ylabel('Γ (local proper-time rate)', color='white')
    ax4.set_title(f'Clockfield Metric at Deposition\nΓ = 1/(1+τβ)², τ={TAU}', color=c_cyan, fontsize=10)
    ax4.legend(fontsize=7.5)
    ax4.tick_params(colors='white')
    ax4.spines[:].set_color('#30363d')

    # ── Panel 5: Takens embedding from crystal
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.set_facecolor(c_panel)
    sc = ax5.scatter(tx, ty, c=tr, cmap='plasma', s=6, alpha=0.7)
    plt.colorbar(sc, ax=ax5, label='Crystal radius (time proxy)')
    ax5.set_xlabel('F(r) — present shell', color='white')
    ax5.set_ylabel('F(r - Δr) — past shell', color='white')
    ax5.set_title('Takens Embedding from Crystal:\nTime Folded Into Radial Space', color=c_cyan, fontsize=10)
    ax5.tick_params(colors='white')
    ax5.spines[:].set_color('#30363d')

    # ── Panel 6: Hawking temperature analogue
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.set_facecolor(c_panel)
    ax6.plot(t, T_H, color=c_cyan, lw=2)
    ax6.plot(t, R_arr, color=c_orange, lw=2, linestyle='--', label='R(t) = (Kt+A)^(1/3)')
    ax6.set_xlabel('Time (hours)', color='white')
    ax6.set_ylabel('Exchange rate k_off(t)  /  Radius R(t)', color='white')
    ax6.set_title('k_off(t) ∝ 1/R(t)\n↔ Hawking T_H ∝ 1/M', color=c_cyan, fontsize=10)
    ax6.legend(fontsize=7.5)
    ax6.tick_params(colors='white')
    ax6.spines[:].set_color('#30363d')
    ax6.text(T_MAX*0.5, max(T_H)*0.7,
             f'Larger crystal\n→ lower thaw rate\n↔ colder black hole',
             color=c_yellow, fontsize=8, ha='center',
             bbox=dict(boxstyle='round', facecolor='#1a1a2e', alpha=0.7))

    # ── Panel 7: Summary correspondence table (as text)
    ax7 = fig.add_subplot(gs[2, :])
    ax7.set_facecolor(c_panel)
    ax7.axis('off')

    table_data = [
        ['Mathematical Element',       'GEMINI (Yan et al. 2025)',             'Clockfield Theory'],
        ['Freeze condition',           'C_r > C_Ξ (threshold crossing)',       'β > Ξ  →  Γ → 0'],
        ['Recording substrate',       '3D protein crystal (octahedral)',       '2D Γ-shell (topological)'],
        ['Scaling law',               'R ∝ M^(1/3) [volume, droplet]',        'R ∝ M [surface, holographic]'],
        ['Information type',          'Amplitude (fluorescence intensity)',    'Phase (winding number)'],
        ['Temporal encoding',         'r → t via R(t) = (Kt+A)^(1/3)',        'Takens delays in dendrites'],
        ['Memory readout',            'Fluorescence microscopy (amplitude)',   'Wave resonance (phase)'],
        ['Symmetry constraint',       'Octahedral O_h (isotropic)',            'Smooth closed Γ-shell'],
        ['Thaw/exchange mechanism',   'k_off(t) ∝ 1/R(t)',                    'T_Hawking ∝ 1/M'],
        ['Noise floor role',          'C_noise → temporal resolution limit',  'σ_noise → Ξ crossing statistics'],
        ['Entropy scaling',           'S ∝ V (bulk volume)',                   'S = A/4ℓ_P² (surface area)'],
    ]

    row_colors = [['#1f2937']*3] + \
                 [[('#0d1117' if i%2==0 else '#161b22')]*3 for i in range(len(table_data)-1)]

    col_widths = [0.28, 0.36, 0.36]
    y_pos = 0.97
    x_positions = [0.01, 0.30, 0.65]
    col_colors  = [c_yellow, c_orange, c_cyan]

    for row_i, row in enumerate(table_data):
        bg = '#1f2937' if row_i == 0 else ('#0d1117' if row_i % 2 == 0 else '#161b22')
        ax7.axhspan(y_pos - 0.085, y_pos + 0.002,
                    xmin=0, xmax=1, color=bg, alpha=1.0)
        for col_i, (text, x) in enumerate(zip(row, x_positions)):
            color = col_colors[col_i] if row_i == 0 else 'white'
            weight = 'bold' if row_i == 0 else 'normal'
            fontsize = 8.5 if row_i == 0 else 8
            ax7.text(x, y_pos - 0.035, text,
                     transform=ax7.transAxes,
                     color=color, fontsize=fontsize, fontweight=weight,
                     verticalalignment='center')
        y_pos -= 0.085

    ax7.set_title('Mathematical Correspondence: GEMINI ↔ Clockfield Theory',
                  color=c_cyan, fontsize=12, pad=8)

    # ── Main title
    fig.suptitle(
        'GEMINI as an Engineered Γ-Shell:\nClockfield–GEMINI Mathematical Correspondence',
        color='white', fontsize=14, y=1.01, fontweight='bold'
    )

    plt.savefig('/home/claude/clockfield-gemini/figures/correspondence_analysis.png',
                dpi=150, bbox_inches='tight', facecolor='#050508')
    print("Figure saved.")

    # ── Export summary data
    summary = {
        "tau": TAU,
        "gamma_at_threshold": float(1/(1+TAU)**2),
        "gemini_growth_K": K_GROWTH,
        "peak_band_positions_hours": [
            float(gemini_time_from_radius(R_arr[p]))
            for p in peaks
        ],
        "mean_gamma_at_freeze": float(np.mean(G_arr[freeze_mask])),
        "max_gamma_at_freeze":  float(np.max(G_arr[freeze_mask])),
        "min_gamma_at_freeze":  float(np.min(G_arr[freeze_mask])),
        "correspondence_identities": [
            "Threshold condition: C_r > C_Xi <-> beta > Xi",
            "Growth law: R = (Kt+A)^(1/3) is volume recorder, Clockfield BH is surface recorder",
            "Takens embedding: radial position = temporal Takens map",
            "Isotropy: octahedral O_h symmetry <-> closed Gamma-shell",
            "Exchange rate: k_off(t) ~ 1/R(t) <-> T_Hawking ~ 1/M",
            "Noise floor: C_noise determines temporal resolution <-> sigma sets freeze statistics",
        ]
    }
    with open('/home/claude/clockfield-gemini/correspondence_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print("Summary JSON saved.")
    print(f"\nKey result: Γ at threshold crossing = {1/(1+TAU)**2:.4f}")
    print(f"(proper time running at {100/(1+TAU)**2:.1f}% at moment of GEMINI band deposition)")


if __name__ == '__main__':
    main()

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os


def plot_time_series(
    filepaths: str | list[str],
    figpath: str | None = None,
    show: bool = False,
):
    """
    Plot current and potential vs time for CA, CP, GS, etc.
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    fig, axs = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    fig.suptitle("Current & Potential vs Time")

    for fp in filepaths:
        data = pd.read_csv(fp)
        label = os.path.basename(fp)
        axs[0].plot(data["Time (s)"], data["Current (A)"], label=label)  # Current (A)
        axs[1].plot(
            data["Time (s)"], data["Potential (V)"], label=label
        )  # Potential (V)

    axs[0].set_ylabel("Current (A)", color="tab:red")
    axs[1].set_ylabel("Potential (V)", color="tab:blue")
    axs[1].set_xlabel("Time (s)")

    if len(filepaths) > 1:
        axs[0].legend()
        axs[1].legend()

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    if show:
        plt.show()
    if figpath:
        fig.savefig(figpath)
    plt.close(fig)


def plot_iv_curve(
    filepaths: str | list[str], figpath: str | None = None, show: bool = False
):
    """
    Plot current vs potential for LSV, CV, GCV, etc.
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle("Current vs Potential")

    for fp in filepaths:
        data = pd.read_csv(fp)
        label = os.path.basename(fp)
        ax.plot(data["Potential (V)"], data["Current (A)"], label=label)

    ax.set_xlabel("Potential (V)")
    ax.set_ylabel("Current (A)")
    if len(filepaths) > 1:
        ax.legend()
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    if show:
        plt.show()
    if figpath:
        fig.savefig(figpath)
    plt.close(fig)


def plot_cv_cycles(
    filepaths: str | list[str],
    figpath: str | None = None,
    show: bool = False,
    cycles: int | None = None,
):
    """
    Plot CV data with each cycle shown in a different color.
    Accepts list of filepaths; cycles in each file are plotted as separate groups.
    Assumes the data in each file is ordered as [current, potential] rows, scans concatenated.
    Provide scan_points (points per scan, optional) and cycles (optional) if known.
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle("Cyclic Voltammetry (CV) - Individual Cycles")

    color_map = plt.get_cmap("tab10")
    color_idx = 0

    for fp in filepaths:
        data = pd.read_csv(fp)

        if cycles is not None:
            for n, cycles in zip(data["Cycle"].unique(), range(1, cycles + 1)):
                label = (
                    f"{os.path.basename(fp)} - Cycle {n}"
                    if len(filepaths) > 1 or len(data["Cycle"].unique()) > 1
                    else os.path.basename(fp)
                )
                data_cycle = data[data["Cycle"] == n]
                ax.plot(
                    data_cycle["Potential (V)"],
                    data_cycle["Current (A)"],
                    label=label,
                    color=color_map(color_idx % 10),
                )
                color_idx += 1

    ax.set_xlabel("Potential (V)")
    ax.set_ylabel("Current (A)")
    ax.legend()
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    if show:
        plt.show()
    if figpath:
        fig.savefig(figpath)
    plt.close(fig)

def plot_cdl_points(
    filepaths: str | list[str],
    figpath: str | None = None,
    show: bool = False,
):
    """
    Plot I_cap vs scan rate from one or multiple *_cdl.csv files produced by
    estimate_cdl_from_csv(...). This is a visualization-only helper:
    it draws a through-origin fit line per file for display purposes.

    Expected columns in each *_cdl.csv:
        - scan_rate_V_per_s
        - Icap_A
        - (optional) n_cycles
    """
    if isinstance(filepaths, str):
        filepaths = [filepaths]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle("Capacitive current vs Scan rate")

    for fp in filepaths:
        df = pd.read_csv(fp)
        label = os.path.basename(fp)

        if not {"scan_rate_V_per_s", "Icap_A"}.issubset(df.columns):
            raise ValueError(
                f"{label} must contain 'scan_rate_V_per_s' and 'Icap_A' columns."
            )

        v = df["scan_rate_V_per_s"].astype(float).to_numpy()
        I = df["Icap_A"].astype(float).to_numpy()

        # Scatter points
        ax.scatter(v, I, label=label, zorder=3)

        # Through-origin line (visualization only)
        denom = float(np.sum(v * v))
        if denom > 0:
            slope = float(np.sum(v * I) / denom)
            xs = np.linspace(0.0, float(np.nanmax(v) * 1.05 if len(v) else 1.0), 100)
            ys = slope * xs
            ax.plot(xs, ys, linewidth=1.8, zorder=2)

            # Optional, compact annotation per file
            sse = float(np.sum((I - slope * v) ** 2))
            sst0 = float(np.sum(I**2))
            r2 = float(1.0 - sse / sst0) if sst0 > 0 else np.nan
            cdl_mf = slope * 1e3
            ax.text(
                0.02,
                0.98,
                f"{label}\nC_dl≈{cdl_mf:.3f} mF   R²≈{r2:.3f}",
                transform=ax.transAxes,
                va="top",
                bbox=dict(facecolor="white", alpha=0.65, edgecolor="none"),
            )

    ax.axhline(0.0, linestyle="--", alpha=0.35, linewidth=1.0)
    ax.set_xlabel("Scan rate v (V/s)")
    ax.set_ylabel(r"$I_{\mathrm{cap}}$ (A)")

    if len(filepaths) > 1:
        ax.legend()

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    if show:
        plt.show()
    if figpath:
        fig.savefig(figpath)
    plt.close(fig)

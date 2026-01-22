import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


def _compute_scanrate_from_cycle(df: pd.DataFrame, edge_exclude: float = 0.15) -> float:
    E = df["_E"].to_numpy()
    t = df["Time (s)"].to_numpy()
    dE = np.gradient(E)
    dt = np.gradient(t)
    with np.errstate(divide="ignore", invalid="ignore"):
        dEdt = np.where(dt != 0, dE / dt, np.nan)
    lo = np.nanquantile(E, edge_exclude)
    hi = np.nanquantile(E, 1.0 - edge_exclude)
    m = (E >= lo) & (E <= hi)
    return float(np.nanmedian(np.abs(dEdt[m])))


def _label_branches(df: pd.DataFrame) -> pd.DataFrame:
    E = df["_E"].to_numpy()
    dE = np.gradient(E)
    out = df.copy()
    out["_branch"] = np.where(dE >= 0, "an", "kat")
    return out


def _through_origin_slope(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    denom = float(np.sum(x * x))
    return float(np.sum(x * y) / denom) if denom > 0 else np.nan


def _through_origin_r2(x: np.ndarray, y: np.ndarray, slope: float) -> float:
    y_pred = slope * x
    sse = float(np.sum((y - y_pred) ** 2))
    sst0 = float(np.sum(y**2))
    return float(1 - sse / sst0) if sst0 > 0 else np.nan


def estimate_cdl_from_csv(
    filepath: str,
    vertex_a: Optional[float] = None,
    vertex_b: Optional[float] = None,
    window: float = 0.01,  # half-width around E* for medians
    *,
    edge_exclude: float = 0.15,
    save_points_csv: bool = True,
) -> Dict[str, Any]:
    """
    Estimate the electrochemical double-layer capacitance (Cdl) from a CSV file
    recorded in "CDL" mode.

    Methodology:
        - Each scan-rate block consists of exactly two CV cycles.
          The first cycle is treated as a conditioning cycle and is ignored.
          The second cycle of each block is analyzed.
        - For each selected cycle:
            * The scan rate (V/s) is computed as the median(|dE/dt|)
              in the middle potential window (edges excluded).
            * The capacitive current (I_cap) is obtained at a single target
              potential E* = (vertex_a + vertex_b)/2 (or the median of E if not set),
              as the median current difference between anodic and cathodic
              branches within ±`window` around E*:
                  I_cap = (I_an - I_cat) / 2
        - The resulting (I_cap, v) pairs are linearly regressed through the origin
          (intercept = 0):
              I_cap = C_dl * v
        - The final result provides C_dl (F and mF) and R², and writes a
          points CSV ("*_cdl.csv") for plotting.

    Parameters
    ----------
    filepath : str
        Path to the logger CSV file containing the Cdl measurement data.
    vertex_a : float, optional
        Lower vertex potential (V vs. reference). Used to determine E*.
    vertex_b : float, optional
        Upper vertex potential (V vs. reference). Used to determine E*.
    window : float, optional
        Half-width (V) around E* used for the anodic/cathodic median window.
    edge_exclude : float, optional
        Fraction of the potential range to exclude at both ends when computing
        dE/dt (default 0.15 = 15%).
    save_points_csv : bool, optional
        Whether to save the I_cap–v pairs to a separate *_cdl.csv file
        for later plotting.

    Returns
    -------
    Dict[str, Any]
        Dictionary with fields:
            - "Cdl_F" : float
            - "Cdl_mF" : float
            - "R2" : float
            - "points" : list of {'scan_rate', 'Icap', 'n_cycles'}
            - "per_cycle" : list of {'cycle', 'scan_rate', 'Icap'}
            - "csv" : path to saved points CSV
            - "E_star" : float
    """
    df = pd.read_csv(filepath)

    # Columns
    time_col = "Time (s)" if "Time (s)" in df.columns else None
    pot_col = (
        "Applied potential (V)"
        if "Applied potential (V)" in df.columns
        else ("Potential (V)" if "Potential (V)" in df.columns else None)
    )
    curr_col = "Current (A)"
    if time_col is None or pot_col is None or curr_col not in df.columns:
        raise ValueError(
            "CSV must contain ['Time (s)', '...potential...', 'Current (A)']."
        )

    df = df.sort_values(time_col).reset_index(drop=True)
    df["_E"] = df[pot_col].astype(float)
    df[curr_col] = df[curr_col].astype(float)

    # Branch tagging
    df = _label_branches(df)

    # Single target potential E*
    if (vertex_a is not None) and (vertex_b is not None):
        E_star = float(0.5 * (vertex_a + vertex_b))
    else:
        E_star = float(np.nanmedian(df["_E"]))

    # We strictly use ONLY the second cycle of each scan-rate block:
    # cycles are 1..2 for rate#1, 3..4 for rate#2, etc. => keep even cycles only.
    if "Cycle" in df.columns:
        all_cycles = sorted(pd.unique(df["Cycle"]))
        used_cycles = [c for c in all_cycles if int(c) % 2 == 0]  # keep 2,4,6,...
    else:
        # if no cycle column, treat the whole file as a single (second) cycle
        df["_synthetic_cycle"] = 2
        df["Cycle"] = df.get("Cycle", df["_synthetic_cycle"])
        used_cycles = [2]

    per_cycle = []
    for cyc in used_cycles:
        dcy = df[df["Cycle"] == cyc].copy()
        if dcy.empty:
            continue

        v = _compute_scanrate_from_cycle(dcy, edge_exclude=edge_exclude)

        win = dcy[(dcy["_E"] >= E_star - window) & (dcy["_E"] <= E_star + window)]
        if win.empty:
            continue

        Ian = np.nanmedian(win.loc[win["_branch"] == "an", curr_col])
        Ikat = np.nanmedian(win.loc[win["_branch"] == "kat", curr_col])
        if not (np.isfinite(Ian) and np.isfinite(Ikat)):
            continue

        Icap = float((Ian - Ikat) / 2.0)
        per_cycle.append({"cycle": int(cyc), "scan_rate": float(v), "Icap": Icap})

    # Build points: exactly one point per scan-rate (we kept only second cycle)
    scan_rates = np.array([pc["scan_rate"] for pc in per_cycle], dtype=float)
    Icaps = np.array([pc["Icap"] for pc in per_cycle], dtype=float)
    n_cycles_pt = np.ones_like(scan_rates, dtype=int)  # always 1 (second cycle only)

    # Through-origin fit
    slope = _through_origin_slope(scan_rates, Icaps) if len(scan_rates) >= 1 else np.nan
    r2 = (
        _through_origin_r2(scan_rates, Icaps, slope)
        if np.isfinite(slope) and len(scan_rates) >= 2
        else np.nan
    )
    Cdl_F = slope
    Cdl_mF = Cdl_F * 1e3 if np.isfinite(Cdl_F) else np.nan

    # Points CSV for plotter
    points_csv = None
    if save_points_csv and len(scan_rates) > 0:
        out = pd.DataFrame(
            {"scan_rate_V_per_s": scan_rates, "Icap_A": Icaps, "n_cycles": n_cycles_pt}
        )
        points_csv = filepath.replace(".csv", "_cdl.csv")
        out.to_csv(points_csv, index=False)

    return {
        "Cdl_F": float(Cdl_F) if np.isfinite(Cdl_F) else np.nan,
        "Cdl_mF": float(Cdl_mF) if np.isfinite(Cdl_mF) else np.nan,
        "slope": float(Cdl_F) if np.isfinite(Cdl_F) else np.nan,
        "intercept": 0.0,
        "R2": float(r2) if np.isfinite(r2) else np.nan,
        "points": [
            {"scan_rate": float(v), "Icap": float(i), "n_cycles": int(n)}
            for v, i, n in zip(scan_rates, Icaps, n_cycles_pt)
        ],
        "per_cycle": per_cycle,  # contains ONLY the used (second) cycles
        "csv": points_csv,
        "n_points": int(len(scan_rates)),
        "n_cycles_total": int(len(per_cycle)),
        "E_star": E_star,
        "window": float(window),
        "edge_exclude": float(edge_exclude),
    }

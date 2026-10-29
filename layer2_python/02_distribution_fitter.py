"""
OR-ScheduleIQ | Layer 2 | 02_distribution_fitter.py
=====================================================
Fits Log-Normal and Weibull distributions to surgical case durations.

Outputs:
  - Per-procedure distribution parameters (mu, sigma for LogNorm; k, λ for Weibull)
  - P10 / P50 / P90 interval table
  - Goodness-of-fit statistics (AIC, BIC, KS test)
  - Matplotlib diagnostic plots saved to data/processed/
"""

import logging
import warnings
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Headless rendering
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
from scipy.stats import lognorm, weibull_min, kstest, norm

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import *

warnings.filterwarnings("ignore", category=RuntimeWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("distribution_fitter")

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTION FITTER
# ─────────────────────────────────────────────────────────────────────────────

class SurgeryDurationFitter:
    """
    Fits parametric distributions to surgical case durations.
    Returns parameter estimates, percentile intervals, and goodness-of-fit metrics.
    """

    CANDIDATE_DISTRIBUTIONS = ["lognormal", "weibull"]
    MIN_SAMPLE_SIZE = 10

    def __init__(self):
        self.results: Dict[str, dict] = {}
        log.info("SurgeryDurationFitter initialized")

    def fit_lognormal(self, durations: np.ndarray) -> dict:
        """MLE fit of Log-Normal distribution."""
        durations = durations[durations > 0]
        if len(durations) < self.MIN_SAMPLE_SIZE:
            return {}
        shape, loc, scale = lognorm.fit(durations, floc=0)
        sigma = shape
        mu    = np.log(scale)

        # KS test for goodness-of-fit
        ks_stat, ks_pval = kstest(durations, "lognorm",
                                   args=(shape, loc, scale))
        # AIC / BIC (2 parameters: mu, sigma)
        log_likelihood = np.sum(lognorm.logpdf(durations, shape, loc, scale))
        n = len(durations)
        aic = 2 * 2 - 2 * log_likelihood
        bic = np.log(n) * 2 - 2 * log_likelihood

        return {
            "distribution":  "lognormal",
            "mu":            round(float(mu), 4),
            "sigma":         round(float(sigma), 4),
            "loc":           round(float(loc), 4),
            "scale":         round(float(scale), 4),
            "ks_stat":       round(float(ks_stat), 4),
            "ks_pvalue":     round(float(ks_pval), 4),
            "aic":           round(float(aic), 2),
            "bic":           round(float(bic), 2),
            "log_likelihood":round(float(log_likelihood), 2),
            "n_samples":     n,
        }

    def fit_weibull(self, durations: np.ndarray) -> dict:
        """MLE fit of Weibull (2-parameter) distribution."""
        durations = durations[durations > 0]
        if len(durations) < self.MIN_SAMPLE_SIZE:
            return {}
        c, loc, scale = weibull_min.fit(durations, floc=0)

        ks_stat, ks_pval = kstest(durations, "weibull_min",
                                   args=(c, loc, scale))
        log_likelihood = np.sum(weibull_min.logpdf(durations, c, loc, scale))
        n = len(durations)
        aic = 2 * 2 - 2 * log_likelihood
        bic = np.log(n) * 2 - 2 * log_likelihood

        return {
            "distribution": "weibull",
            "k":            round(float(c), 4),      # Shape parameter
            "lambda":       round(float(scale), 4),   # Scale parameter
            "loc":          round(float(loc), 4),
            "ks_stat":      round(float(ks_stat), 4),
            "ks_pvalue":    round(float(ks_pval), 4),
            "aic":          round(float(aic), 2),
            "bic":          round(float(bic), 2),
            "log_likelihood":round(float(log_likelihood), 2),
            "n_samples":    n,
        }

    def compute_percentiles(self, durations: np.ndarray, lognorm_params: dict) -> dict:
        """Compute percentile intervals from fitted Log-Normal parameters."""
        if not lognorm_params:
            # Empirical fallback
            return {
                "p10_min": int(np.percentile(durations, 10)),
                "p25_min": int(np.percentile(durations, 25)),
                "p50_min": int(np.percentile(durations, 50)),
                "p75_min": int(np.percentile(durations, 75)),
                "p90_min": int(np.percentile(durations, 90)),
                "p95_min": int(np.percentile(durations, 95)),
                "method":  "empirical",
            }

        mu    = lognorm_params["mu"]
        sigma = lognorm_params["sigma"]

        def lnorm_ppf(p):
            return int(np.exp(mu + sigma * stats.norm.ppf(p)))

        return {
            "p10_min": lnorm_ppf(0.10),
            "p25_min": lnorm_ppf(0.25),
            "p50_min": lnorm_ppf(0.50),
            "p75_min": lnorm_ppf(0.75),
            "p90_min": lnorm_ppf(0.90),
            "p95_min": lnorm_ppf(0.95),
            "method":  "lognormal_mle",
        }

    def fit_all(self, cases_df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit distributions to all procedure types and return a summary DataFrame.
        Input: cases_df with columns [procedure_name, specialty, duration_min]
        """
        log.info("Fitting distributions across %d procedures...",
                 cases_df["procedure_name"].nunique())

        records = []
        for (procedure_name, specialty), group in cases_df.groupby(
            ["procedure_name", "specialty"]
        ):
            durations = group["duration_min"].dropna().values
            if len(durations) < self.MIN_SAMPLE_SIZE:
                log.debug("  Skipping %s (n=%d < min=%d)",
                          procedure_name, len(durations), self.MIN_SAMPLE_SIZE)
                continue

            lnorm_params  = self.fit_lognormal(durations)
            weibull_params = self.fit_weibull(durations)
            percentiles    = self.compute_percentiles(durations, lnorm_params)

            # Best-fit selection: lower AIC wins
            if lnorm_params and weibull_params:
                best_fit = "lognormal" if lnorm_params["aic"] <= weibull_params["aic"] else "weibull"
            else:
                best_fit = "lognormal" if lnorm_params else "weibull"

            record = {
                "procedure_name":    procedure_name,
                "specialty":         specialty,
                "n_cases":           len(durations),
                "mean_min":          round(float(np.mean(durations)), 1),
                "std_min":           round(float(np.std(durations)), 1),
                "cv_pct":            round(float(np.std(durations) / np.mean(durations) * 100), 1),
                "best_fit":          best_fit,
                # Log-Normal params
                "lnorm_mu":          lnorm_params.get("mu"),
                "lnorm_sigma":       lnorm_params.get("sigma"),
                "lnorm_ks_stat":     lnorm_params.get("ks_stat"),
                "lnorm_ks_pval":     lnorm_params.get("ks_pvalue"),
                "lnorm_aic":         lnorm_params.get("aic"),
                # Weibull params
                "weibull_k":         weibull_params.get("k"),
                "weibull_lambda":    weibull_params.get("lambda"),
                "weibull_ks_stat":   weibull_params.get("ks_stat"),
                "weibull_ks_pval":   weibull_params.get("ks_pvalue"),
                "weibull_aic":       weibull_params.get("aic"),
                # Percentile intervals
                **percentiles,
                # Scheduling recommendation: use P50 to schedule, flag P90 risk
                "scheduling_target_min": percentiles["p50_min"],
                "risk_buffer_min":       percentiles["p90_min"] - percentiles["p50_min"],
            }
            records.append(record)

        results_df = pd.DataFrame(records)
        log.info("Fitted %d procedure distributions", len(results_df))
        return results_df

    # ─────────────────────────────────────────────────────────────────────────
    # DIAGNOSTIC PLOTS
    # ─────────────────────────────────────────────────────────────────────────

    def plot_diagnostics(
        self,
        cases_df: pd.DataFrame,
        fit_results: pd.DataFrame,
        output_dir: Path,
        top_n: int = 9,
    ):
        """
        Generate a grid of QQ-plots and histogram overlays for the top N procedures.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        top_procs = (fit_results.nlargest(top_n, "n_cases")["procedure_name"].tolist())

        fig = plt.figure(figsize=(20, 18))
        fig.patch.set_facecolor("#0f1923")
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

        colors = {
            "hist":    "#3a86ff",
            "lognorm": "#ff6b6b",
            "weibull": "#ffd166",
            "empirical":"#06d6a0",
        }

        for idx, proc_name in enumerate(top_procs[:9]):
            ax = fig.add_subplot(gs[idx // 3, idx % 3])
            ax.set_facecolor("#1a2535")

            durations = cases_df[cases_df["procedure_name"] == proc_name]["duration_min"].dropna().values
            row = fit_results[fit_results["procedure_name"] == proc_name].iloc[0]

            # Histogram (normalized to density)
            ax.hist(durations, bins=25, density=True, color=colors["hist"],
                    alpha=0.55, label="Observed", edgecolor="none")

            x = np.linspace(durations.min(), durations.max(), 300)

            # Log-Normal overlay
            if row["lnorm_mu"] and row["lnorm_sigma"]:
                mu, sigma = row["lnorm_mu"], row["lnorm_sigma"]
                pdf_ln = lognorm.pdf(x, s=sigma, scale=np.exp(mu))
                ax.plot(x, pdf_ln, color=colors["lognorm"], lw=2,
                        label=f"LogNorm (μ={mu:.2f}, σ={sigma:.2f})")

            # Weibull overlay
            if row["weibull_k"] and row["weibull_lambda"]:
                k, lam = row["weibull_k"], row["weibull_lambda"]
                pdf_wb = weibull_min.pdf(x, c=k, scale=lam)
                ax.plot(x, pdf_wb, color=colors["weibull"], lw=2, ls="--",
                        label=f"Weibull (k={k:.2f}, λ={lam:.1f})")

            # Percentile markers
            for p, val, lbl in [
                (10, row["p10_min"], "P10"),
                (50, row["p50_min"], "P50"),
                (90, row["p90_min"], "P90"),
            ]:
                ax.axvline(val, ls=":", lw=1.5, color="#adb5bd",
                           label=f"{lbl}={val:.0f}m")

            ax.set_title(f"{proc_name}\n(n={len(durations)}, best={row['best_fit']})",
                         color="white", fontsize=9, pad=6)
            ax.set_xlabel("Duration (min)", color="#adb5bd", fontsize=8)
            ax.set_ylabel("Density", color="#adb5bd", fontsize=8)
            ax.tick_params(colors="#adb5bd", labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor("#2d3f55")
            ax.legend(fontsize=6, framealpha=0.2, labelcolor="white")

        fig.suptitle(
            "OR-ScheduleIQ | Surgical Duration Distribution Fits\n"
            "Log-Normal vs. Weibull | P10/P50/P90 Scheduling Intervals",
            color="white", fontsize=14, y=0.98, fontweight="bold"
        )

        out_path = output_dir / "distribution_diagnostics.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close()
        log.info("Diagnostic plot saved: %s", out_path)

    def plot_specialty_comparison(self, cases_df: pd.DataFrame, output_dir: Path):
        """Box + violin plot of duration distributions by specialty."""
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        fig.patch.set_facecolor("#0f1923")

        palette = {
            "General Surgery": "#3a86ff",
            "Orthopedics":     "#06d6a0",
            "Cardiac":         "#ff6b6b",
        }

        for ax in axes:
            ax.set_facecolor("#1a2535")
            for spine in ax.spines.values():
                spine.set_edgecolor("#2d3f55")

        # Left: violin
        specialties = cases_df["specialty"].unique()
        positions = list(range(len(specialties)))
        parts = axes[0].violinplot(
            [cases_df[cases_df["specialty"] == sp]["duration_min"].dropna().values
             for sp in specialties],
            positions=positions, showmedians=True, showextrema=True
        )
        for i, (pc, sp) in enumerate(zip(parts["bodies"], specialties)):
            pc.set_facecolor(palette.get(sp, "#adb5bd"))
            pc.set_alpha(0.75)
        axes[0].set_xticks(positions)
        axes[0].set_xticklabels(specialties, color="#adb5bd", fontsize=10)
        axes[0].set_ylabel("Duration (minutes)", color="#adb5bd")
        axes[0].set_title("Duration Distribution by Specialty\n(Violin)", color="white", fontsize=12)
        axes[0].tick_params(colors="#adb5bd")
        for line_key in ["cmedians", "cmaxes", "cmins", "cbars"]:
            if line_key in parts:
                parts[line_key].set_color("#ffffff")

        # Right: log-scale histogram overlay
        for sp in specialties:
            data = cases_df[cases_df["specialty"] == sp]["duration_min"].dropna().values
            axes[1].hist(data, bins=40, alpha=0.5, density=True,
                         color=palette.get(sp, "#adb5bd"), label=sp)
        axes[1].set_xlabel("Duration (minutes)", color="#adb5bd")
        axes[1].set_ylabel("Density", color="#adb5bd")
        axes[1].set_title("Duration Density Overlay\nAll Specialties", color="white", fontsize=12)
        axes[1].tick_params(colors="#adb5bd")
        axes[1].legend(fontsize=10, framealpha=0.2, labelcolor="white")

        fig.suptitle("OR-ScheduleIQ | Specialty Duration Analysis",
                     color="white", fontsize=14, fontweight="bold")
        out_path = output_dir / "specialty_comparison.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close()
        log.info("Specialty comparison plot saved: %s", out_path)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run(cases_df: pd.DataFrame = None) -> pd.DataFrame:
    if cases_df is None:
        # Load from processed CSV if called standalone
        csv_path = DATA_PROCESSED / "fact_surgery_cases.csv"
        if csv_path.exists():
            cases_df = pd.read_csv(csv_path)
        else:
            log.warning("fact_surgery_cases.csv not found — running data loader first")
            from data_loader_01 import run as load_data
            _, _, _, cases_raw = load_data()
            cases_df = cases_raw

    fitter = SurgeryDurationFitter()
    fit_results = fitter.fit_all(cases_df)

    # Save fit parameters table
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "duration_fit_parameters.csv"
    fit_results.to_csv(out_path, index=False)
    log.info("Fit parameters saved: %s", out_path)

    # Generate diagnostic plots
    fitter.plot_diagnostics(cases_df, fit_results, DATA_PROCESSED)
    fitter.plot_specialty_comparison(cases_df, DATA_PROCESSED)

    return fit_results


if __name__ == "__main__":
    run()

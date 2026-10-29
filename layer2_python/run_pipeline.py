"""
OR-ScheduleIQ | Layer 2 | run_pipeline.py
==========================================
Single-entry orchestrator that runs the complete pipeline end-to-end.

Usage:
  python run_pipeline.py                          # Full pipeline, synthetic data
  python run_pipeline.py --data-source mimic      # Use MIMIC-IV data
  python run_pipeline.py --buffer 45              # Change turnover buffer to 45 min
  python run_pipeline.py --replications 100       # Full Monte Carlo
  python run_pipeline.py --skip-sql               # Skip DuckDB feature engineering
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def run_sql_pipeline(con: duckdb.DuckDBPyConnection):
    """Execute the Layer 1 SQL feature engineering pipeline."""
    log.info("[LAYER 1] Running SQL Feature Engineering...")

    scripts = [
        PROJECT_ROOT / "layer1_sql" / "02_feature_engineering.sql",
        PROJECT_ROOT / "layer1_sql" / "03_export_csvs.sql",
    ]
    for script_path in scripts:
        log.info("  Executing: %s", script_path.name)
        try:
            sql = open(script_path).read()
            con.execute(sql)
            log.info("  ✓ %s complete", script_path.name)
        except Exception as e:
            log.error("  ✗ Error in %s: %s", script_path.name, e)
            raise


def main():
    parser = argparse.ArgumentParser(
        description="OR-ScheduleIQ Full Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-source",
        default=DEFAULT_DATA_SOURCE,
        choices=DATA_SOURCE_OPTIONS,
        help="Data source: synthetic (default) | mimic | kaggle",
    )
    parser.add_argument(
        "--buffer",
        type=float,
        default=TARGET_BUFFER_MIN,
        help=f"Turnover buffer time in minutes (default: {TARGET_BUFFER_MIN})",
    )
    parser.add_argument(
        "--replications",
        type=int,
        default=10,
        help="Number of Monte Carlo replications (default: 10, production: 100)",
    )
    parser.add_argument(
        "--skip-sql",
        action="store_true",
        help="Skip SQL feature engineering (use pre-existing CSVs)",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip generating matplotlib plots",
    )
    args = parser.parse_args()

    total_start = time.time()
    log.info("=" * 65)
    log.info("  OR-ScheduleIQ | Full Pipeline Execution")
    log.info("  Data Source:  %s", args.data_source)
    log.info("  Buffer:       %d min | Replications: %d", args.buffer, args.replications)
    log.info("=" * 65)

    # ── LAYER 2, Step 1: Data Loading ────────────────────────────────────────
    log.info("\n[LAYER 2 / Step 1] Data Loading...")
    t0 = time.time()

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "data_loader",
        Path(__file__).parent / "01_data_loader.py"
    )
    data_loader_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data_loader_mod)
    patients_df, rooms_df, surgeries_df, cases_raw_df = data_loader_mod.run(
        data_source=args.data_source
    )
    log.info("  ✓ Data loaded in %.1fs", time.time() - t0)

    # ── LAYER 1: SQL Pipeline ─────────────────────────────────────────────────
    if not args.skip_sql:
        log.info("\n[LAYER 1] SQL Feature Engineering...")
        t0 = time.time()
        con = duckdb.connect(str(DUCKDB_PATH))
        run_sql_pipeline(con)
        con.close()
        log.info("  ✓ SQL pipeline complete in %.1fs", time.time() - t0)

        # Load the exported CSVs
        fact_cases_path = DATA_PROCESSED / "fact_surgery_cases.csv"
        if fact_cases_path.exists():
            cases_df = pd.read_csv(fact_cases_path)
            log.info("  Loaded fact_surgery_cases.csv: %d rows", len(cases_df))
        else:
            log.warning("fact_surgery_cases.csv not found — using raw generated cases")
            cases_df = cases_raw_df
    else:
        log.info("[LAYER 1] Skipped (--skip-sql flag)")
        fact_cases_path = DATA_PROCESSED / "fact_surgery_cases.csv"
        cases_df = pd.read_csv(fact_cases_path) if fact_cases_path.exists() else cases_raw_df

    # ── LAYER 2, Step 2: Distribution Fitting ─────────────────────────────────
    log.info("\n[LAYER 2 / Step 2] Distribution Fitting...")
    t0 = time.time()

    spec2 = importlib.util.spec_from_file_location(
        "dist_fitter",
        Path(__file__).parent / "02_distribution_fitter.py"
    )
    dist_fitter_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(dist_fitter_mod)
    fit_results = dist_fitter_mod.run(cases_df)
    log.info("  ✓ Distribution fitting complete in %.1fs", time.time() - t0)

    # ── LAYER 2, Step 3: Simulation Engine ────────────────────────────────────
    log.info("\n[LAYER 2 / Step 3] Discrete-Event Simulation...")
    t0 = time.time()

    spec3 = importlib.util.spec_from_file_location(
        "sim_engine",
        Path(__file__).parent / "03_simulation_engine.py"
    )
    sim_mod = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(sim_mod)
    sim_results = sim_mod.run(
        fit_params=fit_results,
        buffer_min=args.buffer,
        n_replications=args.replications,
    )
    log.info("  ✓ Simulation complete in %.1fs", time.time() - t0)

    # ── LAYER 2, Step 4: Export Results & Dimension Build ─────────────────────
    log.info("\n[LAYER 2 / Step 4] Export Results & Dimension Build...")
    t0 = time.time()

    spec4 = importlib.util.spec_from_file_location(
        "export_results",
        Path(__file__).parent / "04_export_results.py"
    )
    export_mod = importlib.util.module_from_spec(spec4)
    spec4.loader.exec_module(export_mod)
    export_mod.run(start_date_str="2024-01-01", n_days=365)
    log.info("  ✓ Export complete in %.1fs", time.time() - t0)

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    log.info("\n" + "=" * 65)
    log.info("  PIPELINE COMPLETE  |  Total time: %.1fs", total_elapsed)
    log.info("=" * 65)
    log.info("  Output files (Power BI ready):")
    log.info("    Processed/")
    log.info("    ├── dim_date.csv")
    log.info("    ├── dim_operating_room.csv")
    log.info("    ├── dim_surgical_specialty.csv")
    log.info("    ├── dim_patient_risk_tier.csv")
    log.info("    ├── dim_time_slot.csv")
    log.info("    ├── dim_surgeries_master.csv")
    log.info("    ├── fact_surgery_cases.csv")
    log.info("    ├── fact_historical_cases.csv")
    log.info("    ├── duration_fit_parameters.csv")
    log.info("    ├── distribution_diagnostics.png")
    log.info("    └── specialty_comparison.png")
    log.info("    Simulated/")
    log.info("    ├── fact_simulated_schedule.csv  (enriched with cost cols)")
    log.info("    ├── sim_hourly_bed_trace.csv")
    log.info("    ├── sim_daily_metrics.csv")
    log.info("    └── simulation_dashboard.png")
    log.info("")
    log.info("  Next Step: Open Power BI Desktop and import the CSVs")
    log.info("  from data/processed/ and data/simulated/")
    log.info("=" * 65)


if __name__ == "__main__":
    main()

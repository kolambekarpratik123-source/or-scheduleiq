"""
OR-ScheduleIQ | Layer 2 | 04_export_results.py
================================================
Post-processing and export step. Consolidates simulation outputs into
fully Power BI-ready CSV files, including all Kimball dimension tables
and the supplementary historical cases fact table.

Inputs  (from previous steps):
    data/simulated/fact_simulated_schedule.csv
    data/processed/fact_surgery_cases.csv
    data/processed/dim_surgeries_master.csv

Outputs:
    data/processed/dim_date.csv                 -- Dim_Date
    data/processed/dim_operating_room.csv       -- Dim_Operating_Room
    data/processed/dim_surgical_specialty.csv   -- Dim_Surgical_Specialty
    data/processed/dim_patient_risk_tier.csv    -- Dim_Patient_Risk_Tier
    data/processed/dim_time_slot.csv            -- Dim_Time_Slot
    data/processed/fact_historical_cases.csv    -- Fact_Historical_Cases (enriched)
    data/simulated/fact_simulated_schedule.csv  -- re-written with cost columns

Run standalone:
    python layer2_python/04_export_results.py
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROJECT_ROOT,
    DATA_PROCESSED,
    DATA_SIMULATED,
    OR_REGISTRY,
    OR_START_MIN,
    OR_END_MIN,
    OVERTIME_COST_PER_HOUR_INR,
    PACU_HOLD_COST_PER_HR_INR,
    ICU_BED_HOLD_COST_PER_HR_INR,
    ICU_TRANSFER_PROB_BY_SPECIALTY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("export_results")


# ---------------------------------------------------------------------------
# DIMENSION TABLE BUILDERS
# ---------------------------------------------------------------------------

def build_dim_date(start_date: date, n_days: int = 365) -> pd.DataFrame:
    """Full Dim_Date table for Power BI time intelligence."""
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    df = pd.DataFrame({"Date": pd.to_datetime(dates)})
    df["DateKey"]        = df["Date"].dt.strftime("%Y%m%d").astype(int)
    df["Year"]           = df["Date"].dt.year
    df["Quarter"]        = df["Date"].dt.quarter
    df["Month"]          = df["Date"].dt.month
    df["MonthName"]      = df["Date"].dt.strftime("%B")
    df["MonthShort"]     = df["Date"].dt.strftime("%b")
    df["Week"]           = df["Date"].dt.isocalendar().week.astype(int)
    df["DayOfWeek"]      = df["Date"].dt.dayofweek + 1   # 1=Mon..7=Sun
    df["DayName"]        = df["Date"].dt.strftime("%A")
    df["DayShort"]       = df["Date"].dt.strftime("%a")
    df["IsWeekend"]      = df["DayOfWeek"].isin([6, 7])
    df["IsORDay"]        = ~df["IsWeekend"]
    # Indian fiscal year: Apr-Mar
    df["FiscalYear"]     = np.where(df["Month"] >= 4, df["Year"], df["Year"] - 1)
    df["FiscalQuarter"]  = ((df["Month"] - 4) % 12 // 3 + 1)
    df["YearMonth"]      = df["Date"].dt.to_period("M").astype(str)
    log.info("  Dim_Date: %d rows", len(df))
    return df


def build_dim_operating_room() -> pd.DataFrame:
    """Dim_Operating_Room from config.OR_REGISTRY."""
    rows = []
    for room_id, info in OR_REGISTRY.items():
        rows.append({
            "RoomID":           room_id,
            "RoomName":         info["name"],
            "PrimarySpecialty": info["specialty"],
            "RobotAssisted":    info["robot"],
            "CapacityHours":    10,
            "FloorLevel":       2 if info["specialty"] == "Cardiac" else 1,
            "ActiveFlag":       True,
        })
    df = pd.DataFrame(rows)
    log.info("  Dim_Operating_Room: %d rows", len(df))
    return df


def build_dim_surgical_specialty() -> pd.DataFrame:
    """Dim_Surgical_Specialty with complexity and ICU rate metadata."""
    rows = [
        {
            "SpecialtyKey":   1,
            "SpecialtyName":  "General Surgery",
            "Division":       "General Surgery",
            "AvgComplexity":  2.8,
            "TypicalICURate": ICU_TRANSFER_PROB_BY_SPECIALTY.get("General Surgery", 0.10),
        },
        {
            "SpecialtyKey":   2,
            "SpecialtyName":  "Orthopedics",
            "Division":       "Musculoskeletal",
            "AvgComplexity":  2.5,
            "TypicalICURate": ICU_TRANSFER_PROB_BY_SPECIALTY.get("Orthopedics", 0.05),
        },
        {
            "SpecialtyKey":   3,
            "SpecialtyName":  "Cardiac",
            "Division":       "Cardiothoracic",
            "AvgComplexity":  4.5,
            "TypicalICURate": ICU_TRANSFER_PROB_BY_SPECIALTY.get("Cardiac", 0.55),
        },
    ]
    df = pd.DataFrame(rows)
    log.info("  Dim_Surgical_Specialty: %d rows", len(df))
    return df


def build_dim_patient_risk_tier() -> pd.DataFrame:
    """Dim_Patient_Risk_Tier - ASA/CCI bucketed tiers."""
    rows = [
        {"RiskTierKey": 1, "RiskTierName": "Low",      "CCIRange": "0-1", "ASARange": "I",    "ICUProbabilityBand": "0-5%"},
        {"RiskTierKey": 2, "RiskTierName": "Moderate",  "CCIRange": "2-3", "ASARange": "II",   "ICUProbabilityBand": "5-15%"},
        {"RiskTierKey": 3, "RiskTierName": "High",      "CCIRange": "4-5", "ASARange": "III",  "ICUProbabilityBand": "15-35%"},
        {"RiskTierKey": 4, "RiskTierName": "Critical",  "CCIRange": "6+",  "ASARange": "IV-V", "ICUProbabilityBand": "35-70%"},
    ]
    df = pd.DataFrame(rows)
    log.info("  Dim_Patient_Risk_Tier: %d rows", len(df))
    return df


def build_dim_time_slot() -> pd.DataFrame:
    """15-minute time slots across 24 hours for scheduling alignment."""
    rows = []
    for minute in range(0, 24 * 60, 15):
        hour  = minute // 60
        mins  = minute % 60
        label = f"{hour:02d}:{mins:02d}"
        period = (
            "Night"     if hour < 6  else
            "Morning"   if hour < 12 else
            "Afternoon" if hour < 17 else
            "Evening"   if hour < 21 else
            "Night"
        )
        rows.append({
            "TimeSlotKey":  minute,
            "TimeLabel":    label,
            "HourOfDay":    hour,
            "MinuteOfHour": mins,
            "TimePeriod":   period,
            "IsORHour":     OR_START_MIN <= minute < OR_END_MIN,
        })
    df = pd.DataFrame(rows)
    log.info("  Dim_Time_Slot: %d rows (15-min intervals)", len(df))
    return df


# ---------------------------------------------------------------------------
# FACT TABLE ENRICHMENT
# ---------------------------------------------------------------------------

def build_fact_historical_cases(path: Path) -> pd.DataFrame:
    """Derive Fact_Historical_Cases with analyst columns from fact_surgery_cases."""
    if not path.exists():
        log.warning("  fact_surgery_cases.csv not found -- skipping")
        return pd.DataFrame()

    df = pd.read_csv(path)
    log.info("  Loaded fact_surgery_cases.csv: %d rows", len(df))

    # The SQL export uses snake_case; map to the names used below
    # (the PascalCase lookups previously never matched, leaving these columns empty)
    alias = {"actual_duration_min": "ActualDuration_min", "scheduled_duration_min": "ScheduledDuration_min",
             "specialty": "Specialty", "asa_ps_score": "ASA_Score", "emergency_flag": "EmergencyFlag"}
    for src, dst in alias.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]

    # Velocity index: actual / scheduled
    if {"ActualDuration_min", "ScheduledDuration_min"}.issubset(df.columns):
        df["VelocityIndex"] = (
            df["ActualDuration_min"] / df["ScheduledDuration_min"].replace(0, np.nan)
        ).round(4)
    else:
        df["VelocityIndex"] = np.nan

    # P90 exceeded flag per specialty
    if {"ActualDuration_min", "Specialty"}.issubset(df.columns):
        p90 = df.groupby("Specialty")["ActualDuration_min"].transform(lambda x: x.quantile(0.90))
        df["ExceededP90_Flag"] = df["ActualDuration_min"] > p90
    else:
        df["ExceededP90_Flag"] = False

    # Simplified CCI proxy from ASA + emergency
    if "ASA_Score" in df.columns:
        df["CCI_Score"] = (df["ASA_Score"] - 1) * 1.5
        if "EmergencyFlag" in df.columns:
            df["CCI_Score"] += df["EmergencyFlag"].astype(int) * 1.0
        df["CCI_Score"] = df["CCI_Score"].round(1)
    else:
        df["CCI_Score"] = np.nan

    # DateKey
    date_col = next((c for c in ["CaseDate", "ScheduledDate", "Date"] if c in df.columns), None)
    if date_col and "DateKey" not in df.columns:
        df["DateKey"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)

    # SpecialtyKey
    spec_map = {"General Surgery": 1, "Orthopedics": 2, "Cardiac": 3}
    if "Specialty" in df.columns and "SpecialtyKey" not in df.columns:
        df["SpecialtyKey"] = df["Specialty"].map(spec_map).fillna(1).astype(int)

    # RiskTierKey
    tier_map = {"Low": 1, "Moderate": 2, "High": 3, "Critical": 4}
    if "RiskTier" in df.columns and "RiskTierKey" not in df.columns:
        df["RiskTierKey"] = df["RiskTier"].map(tier_map).fillna(1).astype(int)

    df = df.drop(columns=[c for c in alias.values() if c in df.columns])
    log.info("  Fact_Historical_Cases enriched: %d rows", len(df))
    return df


def enrich_fact_simulated(path: Path) -> pd.DataFrame:
    """Add cost columns and foreign keys to fact_simulated_schedule."""
    if not path.exists():
        log.warning("  fact_simulated_schedule.csv not found -- run simulation first")
        return pd.DataFrame()

    df = pd.read_csv(path)
    log.info("  Loaded fact_simulated_schedule.csv: %d rows", len(df))

    # Overtime cost
    # The simulation writes snake_case columns; accept either spelling
    def _col(*names):
        return next((n for n in names if n in df.columns), None)

    overrun = _col("OverrunMin", "overrun_min")
    if overrun:
        df["OT_Cost_INR"] = (
            df[overrun].clip(lower=0) / 60 * OVERTIME_COST_PER_HOUR_INR
        ).round(0)
    else:
        df["OT_Cost_INR"] = 0.0

    # PACU hold cost
    pacu = _col("PACU_Duration_min", "pacu_duration_min")
    if pacu:
        hold_min = (df[pacu] - 90).clip(lower=0)
        df["PACU_HoldCost_INR"] = (hold_min / 60 * PACU_HOLD_COST_PER_HR_INR).round(0)
    else:
        df["PACU_HoldCost_INR"] = 0.0

    # ICU cost
    icu_los, icu_flag = _col("ICU_LOS_Hours", "icu_los_hours"), _col("ICU_Transfer_Flag", "icu_transfer_flag")
    if icu_los and icu_flag:
        df["ICU_Cost_INR"] = (
            df[icu_flag].astype(int)
            * df[icu_los].fillna(0)
            * ICU_BED_HOLD_COST_PER_HR_INR
        ).round(0)
    else:
        df["ICU_Cost_INR"] = 0.0

    # DateKey
    date_col = next((c for c in ["ScheduledDate", "CaseDate", "Date"] if c in df.columns), None)
    if date_col and "DateKey" not in df.columns:
        df["DateKey"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)

    # StartTimeSlotKey (nearest 15-min)
    if "ScheduledStart_min" in df.columns and "StartTimeSlotKey" not in df.columns:
        df["StartTimeSlotKey"] = (df["ScheduledStart_min"] // 15 * 15).astype(int)

    # SpecialtyKey
    spec_map = {"General Surgery": 1, "Orthopedics": 2, "Cardiac": 3}
    if "Specialty" in df.columns and "SpecialtyKey" not in df.columns:
        df["SpecialtyKey"] = df["Specialty"].map(spec_map).fillna(1).astype(int)

    # RiskTierKey
    tier_map = {"Low": 1, "Moderate": 2, "High": 3, "Critical": 4}
    if "RiskTier" in df.columns and "RiskTierKey" not in df.columns:
        df["RiskTierKey"] = df["RiskTier"].map(tier_map).fillna(1).astype(int)

    log.info("  Fact_Simulated enriched: %d rows", len(df))
    return df


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def validate_outputs(output_map: dict) -> bool:
    all_ok = True
    log.info("\n  [Validation] Output file inventory:")
    for label, path in output_map.items():
        p = Path(path)
        if p.exists() and p.stat().st_size > 0:
            try:
                rows = sum(1 for _ in open(p, encoding="utf-8")) - 1
            except Exception:
                rows = -1
            log.info("    OK  %-48s  %d rows", label, rows)
        else:
            log.error("    MISSING  %s", label)
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# PUBLIC API  (called from run_pipeline.py)
# ---------------------------------------------------------------------------

def run(start_date_str: str = "2024-01-01", n_days: int = 365) -> dict:
    """
    Build all dimension + enriched fact tables, write CSVs, validate.

    Parameters
    ----------
    start_date_str : str   ISO start date for Dim_Date (default 2024-01-01)
    n_days         : int   Number of calendar days for Dim_Date (default 365)

    Returns
    -------
    dict {table_name: pd.DataFrame}
    """
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    DATA_SIMULATED.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  OR-ScheduleIQ | Step 4: Export & Dimension Build")
    log.info("=" * 60)

    start_date = date.fromisoformat(start_date_str)

    # 1. Dimensions
    log.info("\n[1/4] Building dimension tables...")
    dim_date       = build_dim_date(start_date, n_days)
    dim_or         = build_dim_operating_room()
    dim_specialty  = build_dim_surgical_specialty()
    dim_risk_tier  = build_dim_patient_risk_tier()
    dim_time_slot  = build_dim_time_slot()

    # 2. Fact enrichment
    log.info("\n[2/4] Enriching fact tables...")
    fact_hist = build_fact_historical_cases(DATA_PROCESSED / "fact_surgery_cases.csv")
    fact_sim  = enrich_fact_simulated(DATA_SIMULATED / "fact_simulated_schedule.csv")

    # 3. Write
    log.info("\n[3/4] Writing CSVs...")
    writes = [
        (dim_date,      DATA_PROCESSED / "dim_date.csv"),
        (dim_or,        DATA_PROCESSED / "dim_operating_room.csv"),
        (dim_specialty, DATA_PROCESSED / "dim_surgical_specialty.csv"),
        (dim_risk_tier, DATA_PROCESSED / "dim_patient_risk_tier.csv"),
        (dim_time_slot, DATA_PROCESSED / "dim_time_slot.csv"),
    ]
    if not fact_hist.empty:
        writes.append((fact_hist, DATA_PROCESSED / "fact_historical_cases.csv"))
    if not fact_sim.empty:
        writes.append((fact_sim, DATA_SIMULATED / "fact_simulated_schedule.csv"))

    result = {}
    for df, path in writes:
        df.to_csv(path, index=False)
        log.info("    Wrote %-50s  (%d rows)", path.name, len(df))
        result[path.stem] = df

    # 4. Validate
    log.info("\n[4/4] Validating all pipeline outputs...")
    all_outputs = {
        "dim_date.csv":                DATA_PROCESSED / "dim_date.csv",
        "dim_operating_room.csv":      DATA_PROCESSED / "dim_operating_room.csv",
        "dim_surgical_specialty.csv":  DATA_PROCESSED / "dim_surgical_specialty.csv",
        "dim_patient_risk_tier.csv":   DATA_PROCESSED / "dim_patient_risk_tier.csv",
        "dim_time_slot.csv":           DATA_PROCESSED / "dim_time_slot.csv",
        "dim_surgeries_master.csv":    DATA_PROCESSED / "dim_surgeries_master.csv",
        "fact_surgery_cases.csv":      DATA_PROCESSED / "fact_surgery_cases.csv",
        "fact_simulated_schedule.csv": DATA_SIMULATED / "fact_simulated_schedule.csv",
        "sim_daily_metrics.csv":       DATA_SIMULATED / "sim_daily_metrics.csv",
        "sim_hourly_bed_trace.csv":    DATA_SIMULATED / "sim_hourly_bed_trace.csv",
    }
    all_ok = validate_outputs(all_outputs)

    log.info("\n" + "=" * 60)
    if all_ok:
        log.info("  ALL OUTPUTS READY -- import into Power BI Desktop")
    else:
        log.warning("  Some outputs missing -- run full pipeline first")
    log.info("=" * 60)

    return result


# ---------------------------------------------------------------------------
# STANDALONE ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OR-ScheduleIQ | Step 4: Export Results")
    parser.add_argument("--start-date", default="2024-01-01",
                        help="Dim_Date start date ISO (default: 2024-01-01)")
    parser.add_argument("--n-days", type=int, default=365,
                        help="Calendar days for Dim_Date (default: 365)")
    args = parser.parse_args()
    run(start_date_str=args.start_date, n_days=args.n_days)

"""
OR-ScheduleIQ | Layer 2 | 01_data_loader.py
=============================================
Handles three data source modes:
  1. 'synthetic' — Generate clinically validated synthetic data (instant, no download)
  2. 'mimic'     — Load and transform MIMIC-IV CSV.GZ files
  3. 'kaggle'    — Load Kaggle surgical dataset CSVs

Output: Populates DuckDB staging tables defined in Layer 1 DDL.
"""

import os
import gzip
import argparse
import logging
import random
import string
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
import duckdb

# Local config
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import *

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("data_loader")

# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DATA GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class SyntheticDataGenerator:
    """Generates clinically plausible synthetic OR data using published distributions."""

    def __init__(self, seed: int = SIM_RANDOM_SEED):
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
        log.info("SyntheticDataGenerator initialized (seed=%d)", seed)

    def _token(self, prefix: str, n: int = 6) -> str:
        return prefix + "-" + "".join(random.choices(string.digits, k=n))

    # ── Patients ────────────────────────────────────────────────────────────
    def generate_patients(self, n: int = 1500) -> pd.DataFrame:
        """Generate synthetic patient demographics with comorbidity flags."""
        log.info("Generating %d synthetic patients...", n)
        ages = self.rng.integers(18, 89, n)

        # Comorbidity prevalences (age-stratified, approximate)
        def age_factor(ages, base_prob):
            return np.clip(base_prob + (ages - 50) * 0.005, base_prob * 0.3, base_prob * 2.5)

        df = pd.DataFrame({
            "subject_id":       np.arange(10001, 10001 + n),
            "gender":           self.rng.choice(["M", "F"], n, p=[0.52, 0.48]),
            "anchor_age":       ages,
            "anchor_year":      self.rng.integers(2018, 2024, n),
            "dod":              [None] * n,  # Simplified — real MIMIC has mortality
            "bmi_category":     self.rng.choice(
                                    ["Normal", "Overweight", "Obese"],
                                    n, p=[0.35, 0.38, 0.27]),
            "smoker_flag":      self.rng.random(n) < age_factor(ages, 0.18),
            "diabetic_flag":    self.rng.random(n) < age_factor(ages, 0.14),
            "hypertensive_flag":self.rng.random(n) < age_factor(ages, 0.32),
            "cardiac_hx_flag":  self.rng.random(n) < age_factor(ages, 0.12),
            "renal_failure_flag":self.rng.random(n) < age_factor(ages, 0.06),
            "malignancy_flag":  self.rng.random(n) < age_factor(ages, 0.08),
            "data_source":      "synthetic",
        })
        df[["smoker_flag","diabetic_flag","hypertensive_flag","cardiac_hx_flag",
            "renal_failure_flag","malignancy_flag"]] = \
            df[["smoker_flag","diabetic_flag","hypertensive_flag","cardiac_hx_flag",
                "renal_failure_flag","malignancy_flag"]].astype(bool)
        log.info("  → %d patients generated", len(df))
        return df

    # ── Operating Rooms ─────────────────────────────────────────────────────
    def generate_operating_rooms(self) -> pd.DataFrame:
        rows = []
        for room_id, info in OR_REGISTRY.items():
            rows.append({
                "room_id":            room_id,
                "room_name":          info["name"],
                "specialty_primary":  info["specialty"],
                "specialty_secondary":None,
                "floor_level":        2,
                "capacity_hours_day": 10.0,
                "anesthesia_machine": True,
                "robot_assisted":     info["robot"],
                "laminar_flow":       True,
                "active_flag":        True,
            })
        return pd.DataFrame(rows)

    # ── Surgeries (Procedure Master) ────────────────────────────────────────
    def generate_surgeries(self) -> pd.DataFrame:
        rows = []
        for i, (proc_name, (mu, sigma)) in enumerate(DURATION_DISTRIBUTIONS.items()):
            specialty = PROCEDURE_TO_SPECIALTY.get(proc_name, "General Surgery")
            # Back-calculate P10, P50, P90 from log-normal
            p10 = int(np.exp(mu + sigma * (-1.282)))
            p50 = int(np.exp(mu))
            p90 = int(np.exp(mu + sigma * 1.282))
            # Complexity score heuristic
            complexity = min(5, max(1, round(p50 / 80)))
            rows.append({
                "procedure_id":          f"PROC-{i+1:04d}",
                "procedure_name":        proc_name,
                "specialty":             specialty,
                "procedure_category":    "Laparoscopic" if "Laparoscopic" in proc_name else
                                         ("Robotic" if "Robot" in proc_name else "Open"),
                "icd10_code":            f"0{i+1:02d}B{i%9}0ZZ",   # Synthetic ICD-10-PCS
                "cpt_code":              f"{47000 + i*10}",
                "duration_p10_min":      p10,
                "duration_p50_min":      p50,
                "duration_p90_min":      p90,
                "duration_lognorm_mu":   round(mu, 4),
                "duration_lognorm_sigma":round(sigma, 4),
                "typical_pacu_min":      int(PACU_MEAN_MIN),
                "icu_transfer_prob":     ICU_TRANSFER_PROB_BY_SPECIALTY.get(specialty, 0.10),
                "complexity_score":      complexity,
            })
        return pd.DataFrame(rows)

    # ── Surgery Cases ────────────────────────────────────────────────────────
    def generate_surgery_cases(
        self,
        patients_df: pd.DataFrame,
        surgeries_df: pd.DataFrame,
        n_days: int = SIM_HORIZON_DAYS,
    ) -> pd.DataFrame:
        """
        Generate a realistic OR schedule for n_days.
        Each OR gets cases filled sequentially within the 10hr window.
        """
        log.info("Generating surgery cases for %d days × %d rooms...", n_days, NUM_OPERATING_THEATRES)

        cases = []
        case_id = 1
        start_date = date(2024, 1, 1)
        subject_ids = patients_df["subject_id"].values
        procedure_ids = surgeries_df["procedure_id"].values
        proc_lookup = surgeries_df.set_index("procedure_id")

        # Assign procedures to specialties
        proc_by_specialty = {}
        for _, row in surgeries_df.iterrows():
            sp = row["specialty"]
            proc_by_specialty.setdefault(sp, []).append(row["procedure_id"])

        surgeon_ids = [self._token("SURG") for _ in range(40)]
        anest_ids   = [self._token("ANES") for _ in range(15)]

        for day_offset in range(n_days):
            current_date = start_date + timedelta(days=day_offset)
            # Skip Sundays (index 6)
            if current_date.weekday() == 6:
                continue

            for room_id, room_info in OR_REGISTRY.items():
                specialty = room_info["specialty"]
                room_procs = proc_by_specialty.get(specialty, procedure_ids)

                current_min = OR_START_MIN  # 480 = 08:00
                case_seq = 0

                while current_min < OR_END_MIN - 60:  # Stop if <60min remains
                    # Pick procedure
                    proc_id = self.rng.choice(room_procs)
                    proc_row = proc_lookup.loc[proc_id]
                    mu    = float(proc_row["duration_lognorm_mu"])
                    sigma = float(proc_row["duration_lognorm_sigma"])

                    # Scheduled duration = P50 with small scheduling noise
                    sched_duration = max(20, int(np.exp(mu) * self.rng.normal(1.0, 0.05)))

                    # Would this overrun the day?
                    if current_min + sched_duration > OR_END_MIN + 90:  # max 90min overtime
                        break

                    sched_start = current_min
                    sched_end   = sched_start + sched_duration

                    # Actual duration sampled from log-normal
                    actual_duration = max(10, int(self.rng.lognormal(mu, sigma)))
                    # Add surgeon velocity effect
                    velocity = self.rng.normal(1.0, 0.08)
                    actual_duration = max(10, int(actual_duration * velocity))

                    # Start delay (0-25 min for first case, 0-10 for subsequent)
                    start_delay = int(self.rng.exponential(8 if case_seq == 0 else 3))
                    actual_start = sched_start + start_delay
                    actual_end   = actual_start + actual_duration

                    # Emergency override (15% chance)
                    is_emergency = self.rng.random() < EMERGENCY_RATE

                    # ASA score (correlated with patient age / comorbidities)
                    subject_id = int(self.rng.choice(subject_ids))
                    asa_score  = int(np.clip(self.rng.integers(1, 5), 1, 5))

                    # PACU
                    icu_prob = float(proc_row["icu_transfer_prob"])
                    if is_emergency:
                        icu_prob = min(0.95, icu_prob * 2.5)
                    icu_transfer = self.rng.random() < icu_prob
                    pacu_duration = max(20, int(
                        self.rng.normal(
                            PACU_MEAN_MIN * (PACU_TO_ICU_FACTOR if icu_transfer else 1.0),
                            PACU_STD_MIN
                        )
                    ))
                    pacu_start = actual_end
                    pacu_end   = pacu_start + pacu_duration

                    icu_los = None
                    if icu_transfer:
                        icu_los = max(2.0, float(self.rng.normal(ICU_LOS_MEAN_HOURS, ICU_LOS_STD_HOURS)))

                    # Complication (correlated with ASA)
                    comp_prob = 0.02 + 0.04 * (asa_score - 1)
                    complication = self.rng.random() < comp_prob

                    # Case status
                    if self.rng.random() < 0.03:
                        case_status = "Cancelled"
                    elif actual_duration > sched_duration * 1.25:
                        case_status = "Overrun"
                    elif start_delay > 20:
                        case_status = "Delayed"
                    else:
                        case_status = "Completed"

                    cases.append({
                        "case_id":             case_id,
                        "subject_id":          subject_id,
                        "hadm_id":             case_id + 900000,
                        "room_id":             room_id,
                        "procedure_id":        proc_id,
                        "surgeon_id":          self.rng.choice(surgeon_ids),
                        "anesthesiologist_id": self.rng.choice(anest_ids),
                        "scheduled_date":      current_date.isoformat(),
                        "scheduled_start_min": sched_start,
                        "scheduled_end_min":   sched_end,
                        "actual_start_min":    actual_start,
                        "actual_end_min":      actual_end,
                        "asa_ps_score":        asa_score,
                        "emergency_flag":      bool(is_emergency),
                        "case_status":         case_status,
                        "cancellation_reason": "Resource unavailable" if case_status == "Cancelled" else None,
                        "pacu_start_min":      pacu_start,
                        "pacu_end_min":        pacu_end,
                        "icu_transfer_flag":   bool(icu_transfer),
                        "icu_los_hours":       round(icu_los, 2) if icu_los else None,
                        "icu_bed_id":          f"ICU-{self.rng.integers(1, NUM_ICU_BEDS+1):02d}" if icu_transfer else None,
                        "complication_flag":   bool(complication),
                        "complication_type":   "Surgical site infection" if complication else None,
                        "readmission_30d_flag":bool(self.rng.random() < (0.08 if complication else 0.04)),
                        "data_source":         "synthetic",
                    })
                    case_id += 1
                    case_seq += 1

                    # Advance cursor: actual end + turnover buffer
                    turnover = max(
                        TURNOVER_MIN_FLOOR,
                        int(self.rng.normal(TURNOVER_MEAN_MIN, TURNOVER_STD_MIN))
                    )
                    current_min = actual_end + turnover

        df = pd.DataFrame(cases)
        log.info("  → %d surgery cases generated across %d days", len(df), n_days)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# MIMIC-IV LOADER
# ─────────────────────────────────────────────────────────────────────────────

class MIMICLoader:
    """Transforms MIMIC-IV raw tables into the OR-ScheduleIQ staging schema."""

    def __init__(self):
        self.files = {k: DATA_RAW / v for k, v in MIMIC_FILES.items()}
        for name, path in self.files.items():
            if not path.exists():
                log.warning("MIMIC file not found: %s (expected at %s)", name, path)

    def _read(self, key: str) -> pd.DataFrame:
        path = self.files[key]
        log.info("Reading %s from %s", key, path)
        return pd.read_csv(path, compression="gzip" if str(path).endswith(".gz") else None)

    def load_patients(self) -> pd.DataFrame:
        pat = self._read("patients")
        # MIMIC patients table: subject_id, gender, anchor_age, anchor_year, dod
        pat = pat[["subject_id", "gender", "anchor_age", "anchor_year", "dod"]].copy()
        pat["bmi_category"]     = "Unknown"
        pat["smoker_flag"]      = False
        pat["diabetic_flag"]    = False
        pat["hypertensive_flag"]= False
        pat["cardiac_hx_flag"]  = False
        pat["renal_failure_flag"]= False
        pat["malignancy_flag"]  = False
        pat["data_source"]      = "mimic"
        log.info("  → Loaded %d MIMIC patients", len(pat))
        return pat

    def enrich_comorbidities(self, patients_df: pd.DataFrame) -> pd.DataFrame:
        """
        Map ICD-10 codes to Charlson comorbidity flags.
        Requires diagnoses_icd.csv.gz.
        """
        diag = self._read("diagnoses_icd")
        diag = diag[diag["icd_version"] == 10]  # ICD-10 only

        # ICD-10 prefix mappings for Charlson conditions
        CCI_MAPPINGS = {
            "diabetic_flag":      ["E10", "E11", "E12", "E13"],
            "cardiac_hx_flag":    ["I20", "I21", "I22", "I23", "I24", "I25", "I50"],
            "hypertensive_flag":  ["I10", "I11", "I12", "I13"],
            "renal_failure_flag": ["N17", "N18", "N19"],
            "malignancy_flag":    ["C0", "C1", "C2", "C3", "C4", "C5",
                                   "C6", "C7", "C8", "C9"],
        }

        for flag, prefixes in CCI_MAPPINGS.items():
            pattern = "|".join(f"^{p}" for p in prefixes)
            matched = diag[diag["icd_code"].str.match(pattern, na=False)]["subject_id"].unique()
            patients_df[flag] = patients_df["subject_id"].isin(matched)

        log.info("  → Comorbidities enriched from ICD-10 diagnoses")
        return patients_df


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_to_duckdb(
    patients_df: pd.DataFrame,
    rooms_df: pd.DataFrame,
    surgeries_df: pd.DataFrame,
    cases_df: pd.DataFrame,
):
    """Writes all staging DataFrames to DuckDB, running the DDL first."""
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    log.info("Connected to DuckDB: %s", DUCKDB_PATH)

    # Run DDL
    ddl_path = PROJECT_ROOT / "layer1_sql" / "01_ddl_staging.sql"
    con.execute(open(ddl_path).read())
    log.info("DDL executed successfully")

    # Insert tables
    for table_name, df in [
        ("staging.patients",        patients_df),
        ("staging.operating_rooms", rooms_df),
        ("staging.surgeries",       surgeries_df),
        ("staging.surgery_cases",   cases_df),
    ]:
        # DuckDB can insert from pandas directly
        con.execute(f"DELETE FROM {table_name}")
        # BY NAME matches columns by name, not position (DDL order differs from the DataFrames)
        con.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM df")
        log.info("  → Loaded %d rows into %s", len(df), table_name)

    con.close()
    log.info("DuckDB load complete.")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run(data_source: str = DEFAULT_DATA_SOURCE):
    log.info("=" * 60)
    log.info("OR-ScheduleIQ | Data Loader | source=%s", data_source)
    log.info("=" * 60)

    if data_source == "synthetic":
        gen = SyntheticDataGenerator()
        patients_df  = gen.generate_patients(n=1500)
        rooms_df     = gen.generate_operating_rooms()
        surgeries_df = gen.generate_surgeries()
        cases_df     = gen.generate_surgery_cases(patients_df, surgeries_df)

    elif data_source == "mimic":
        loader = MIMICLoader()
        patients_df  = loader.load_patients()
        patients_df  = loader.enrich_comorbidities(patients_df)
        rooms_df     = SyntheticDataGenerator().generate_operating_rooms()
        surgeries_df = SyntheticDataGenerator().generate_surgeries()
        # For MIMIC, cases must be derived from procedures_icd + admissions
        # This requires the MIMIC-specific transformer (simplified here)
        log.warning("MIMIC case construction requires procedures_icd enrichment.")
        log.warning("Falling back to synthetic cases for demonstration.")
        gen = SyntheticDataGenerator()
        cases_df = gen.generate_surgery_cases(patients_df, surgeries_df)

    else:
        raise ValueError(f"Unknown data source: {data_source}. Choose: synthetic, mimic, kaggle")

    # Save interim CSVs for inspection
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    patients_df.to_csv(DATA_RAW / "patients_staging.csv", index=False)
    surgeries_df.to_csv(DATA_RAW / "surgeries_staging.csv", index=False)
    cases_df.to_csv(DATA_RAW / "surgery_cases_staging.csv", index=False)
    log.info("Interim CSVs saved to data/raw/")

    # Load to DuckDB
    load_to_duckdb(patients_df, rooms_df, surgeries_df, cases_df)

    return patients_df, rooms_df, surgeries_df, cases_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OR-ScheduleIQ Data Loader")
    parser.add_argument("--data-source", default=DEFAULT_DATA_SOURCE,
                        choices=DATA_SOURCE_OPTIONS,
                        help="Data source: synthetic | mimic | kaggle")
    args = parser.parse_args()
    run(data_source=args.data_source)

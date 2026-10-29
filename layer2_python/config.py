"""
OR-ScheduleIQ | Layer 2 | config.py
====================================
Single source of truth for all tunable simulation parameters.
Edit this file to adjust hospital scale, specialties, costs, or data paths.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PROJECT PATHS
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW        = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED  = PROJECT_ROOT / "data" / "processed"
DATA_SIMULATED  = PROJECT_ROOT / "data" / "simulated"
DUCKDB_PATH     = PROJECT_ROOT / "data" / "or_scheduleiq.duckdb"

# ─────────────────────────────────────────────────────────────────────────────
# HOSPITAL CONFIGURATION  ← [EDIT THESE]
# ─────────────────────────────────────────────────────────────────────────────
NUM_OPERATING_THEATRES  = 8        # [Number of Operating Theatres]
NUM_PACU_BAYS           = 12       # Post-Anesthesia Care Unit bays
NUM_ICU_BEDS            = 16       # Total surgical ICU beds
OR_START_MIN            = 480      # 08:00 in minutes from midnight
OR_END_MIN              = 1080     # 18:00 in minutes from midnight (10hr day)
OR_CAPACITY_MIN         = OR_END_MIN - OR_START_MIN  # 600 minutes/day

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
SIM_HORIZON_DAYS        = 30       # [Target Day Horizon]
SIM_RANDOM_SEED         = 42       # For reproducibility
NUM_SIM_REPLICATIONS    = 100      # Monte Carlo replications for CI bounds
TARGET_BUFFER_MIN       = 30       # Default turnover buffer (mins); also Power BI slider default

# ─────────────────────────────────────────────────────────────────────────────
# SPECIALTY FOCUS  ← [EDIT THESE]
# ─────────────────────────────────────────────────────────────────────────────
TARGET_SPECIALTIES = [
    "General Surgery",
    "Orthopedics",
    "Cardiac",
]

# Daily case mix per specialty (approximate — used for synthetic generation)
SPECIALTY_DAILY_CASES = {
    "General Surgery": 14,
    "Orthopedics":     10,
    "Cardiac":          4,
}

EMERGENCY_RATE          = 0.15     # 15% emergency case prevalence (NHSE benchmark)

# ─────────────────────────────────────────────────────────────────────────────
# PROCEDURE DURATION DISTRIBUTIONS (Log-Normal parameters)
# Source: Strum 2000, Dexter 2004, Stepaniak 2009
# ─────────────────────────────────────────────────────────────────────────────
DURATION_DISTRIBUTIONS = {
    # (mu, sigma) for Log-Normal: E[X] = exp(mu + sigma²/2)
    # General Surgery
    "Laparoscopic Cholecystectomy":     (4.05, 0.38),   # ~80 min median
    "Open Appendectomy":                (3.85, 0.42),   # ~65 min
    "Laparoscopic Appendectomy":        (3.90, 0.40),   # ~70 min
    "Laparotomy / Exploratory":         (4.60, 0.50),   # ~115 min
    "Inguinal Hernia Repair":           (3.80, 0.35),   # ~60 min
    "Laparoscopic Colectomy":           (5.00, 0.48),   # ~165 min
    "Whipple Procedure":                (6.20, 0.55),   # ~500 min
    "Thyroidectomy":                    (4.30, 0.40),   # ~95 min
    # Orthopedics
    "Total Knee Arthroplasty":          (4.60, 0.35),   # ~115 min
    "Total Hip Arthroplasty":           (4.70, 0.38),   # ~130 min
    "Arthroscopic Knee Surgery":        (3.80, 0.40),   # ~60 min
    "ORIF Femur Fracture":              (4.90, 0.45),   # ~160 min
    "Spinal Fusion (Lumbar)":           (5.30, 0.48),   # ~230 min
    "Shoulder Arthroplasty":            (4.80, 0.42),   # ~145 min
    # Cardiac
    "CABG (On-pump)":                   (5.90, 0.52),   # ~380 min
    "AVR (Aortic Valve Replacement)":   (5.70, 0.50),   # ~310 min
    "MVR (Mitral Valve Repair)":        (5.80, 0.55),   # ~345 min
    "Off-pump CABG":                    (5.60, 0.48),   # ~280 min
    "VATS Lobectomy":                   (5.10, 0.45),   # ~190 min
}

# Specialty-level fallback distributions
SPECIALTY_FALLBACK = {
    "General Surgery": (4.20, 0.45),
    "Orthopedics":     (4.55, 0.40),
    "Cardiac":         (5.70, 0.52),
}

PROCEDURE_TO_SPECIALTY = {
    "Laparoscopic Cholecystectomy": "General Surgery",
    "Open Appendectomy":            "General Surgery",
    "Laparoscopic Appendectomy":    "General Surgery",
    "Laparotomy / Exploratory":     "General Surgery",
    "Inguinal Hernia Repair":       "General Surgery",
    "Laparoscopic Colectomy":       "General Surgery",
    "Whipple Procedure":            "General Surgery",
    "Thyroidectomy":                "General Surgery",
    "Total Knee Arthroplasty":      "Orthopedics",
    "Total Hip Arthroplasty":       "Orthopedics",
    "Arthroscopic Knee Surgery":    "Orthopedics",
    "ORIF Femur Fracture":          "Orthopedics",
    "Spinal Fusion (Lumbar)":       "Orthopedics",
    "Shoulder Arthroplasty":        "Orthopedics",
    "CABG (On-pump)":               "Cardiac",
    "AVR (Aortic Valve Replacement)":"Cardiac",
    "MVR (Mitral Valve Repair)":    "Cardiac",
    "Off-pump CABG":                "Cardiac",
    "VATS Lobectomy":               "Cardiac",
}

# ─────────────────────────────────────────────────────────────────────────────
# TURNOVER / CLEANING TIME (minutes)
# AORN Guidelines 2022 recommend 25-35 mins between cases
# ─────────────────────────────────────────────────────────────────────────────
TURNOVER_MEAN_MIN   = 28.0
TURNOVER_STD_MIN    = 6.0
TURNOVER_MIN_FLOOR  = 15      # Hard minimum cleaning time (regulatory)

# ─────────────────────────────────────────────────────────────────────────────
# PACU PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
PACU_MEAN_MIN               = 65.0     # Mean PACU stay in minutes
PACU_STD_MIN                = 25.0
PACU_EXTENDED_THRESHOLD_MIN = 90       # >90 min = "hold" (triggers delayed room release)
PACU_TO_ICU_FACTOR          = 1.35     # ICU-bound patients spend 35% longer in PACU

# ─────────────────────────────────────────────────────────────────────────────
# ICU PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
ICU_LOS_MEAN_HOURS    = 36.0
ICU_LOS_STD_HOURS     = 28.0
ICU_TRANSFER_PROB_BY_SPECIALTY = {
    "General Surgery": 0.10,
    "Orthopedics":     0.05,
    "Cardiac":         0.55,  # Cardiac cases have very high ICU requirement
}

# ─────────────────────────────────────────────────────────────────────────────
# COST PARAMETERS  ← Currency: INR (₹)
# ─────────────────────────────────────────────────────────────────────────────
OVERTIME_COST_PER_HOUR_INR  = 2500.0   # OR staff + anesthesia + overhead
CANCELLATION_COST_INR       = 15000.0  # Avg cost of a cancelled case
# Day-of-surgery cancellation rules (elective cases only; emergencies are never cancelled)
SAME_DAY_CANCEL_PROB        = 0.03     # Patient unfit / no-show / consent issue (~2-5% in literature)
MAX_ALLOWED_OVERTIME_MIN    = 60       # Cancel an elective case if it would finish more than this past OR close
ICU_BED_HOLD_COST_PER_HR_INR = 3500.0  # ICU bed opportunity cost per hour
PACU_HOLD_COST_PER_HR_INR   = 1800.0   # PACU delayed-discharge cost per hour

# ─────────────────────────────────────────────────────────────────────────────
# OPERATING ROOM REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
OR_REGISTRY = {
    "OR-01": {"name": "Theatre 1",  "specialty": "General Surgery",  "robot": False},
    "OR-02": {"name": "Theatre 2",  "specialty": "General Surgery",  "robot": False},
    "OR-03": {"name": "Theatre 3",  "specialty": "Orthopedics",       "robot": False},
    "OR-04": {"name": "Theatre 4",  "specialty": "Orthopedics",       "robot": False},
    "OR-05": {"name": "Theatre 5",  "specialty": "Cardiac",           "robot": False},
    "OR-06": {"name": "Theatre 6",  "specialty": "Cardiac",           "robot": False},
    "OR-07": {"name": "Theatre 7",  "specialty": "General Surgery",  "robot": True},   # Robotic
    "OR-08": {"name": "Theatre 8",  "specialty": "Orthopedics",       "robot": True},   # Robotic
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA SOURCE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
DATA_SOURCE_OPTIONS = ["synthetic", "mimic", "kaggle"]
DEFAULT_DATA_SOURCE = "synthetic"

# MIMIC-IV file paths (relative to DATA_RAW)
MIMIC_FILES = {
    "patients":        "mimic/hosp/patients.csv.gz",
    "admissions":      "mimic/hosp/admissions.csv.gz",
    "diagnoses_icd":   "mimic/hosp/diagnoses_icd.csv.gz",
    "procedures_icd":  "mimic/hosp/procedures_icd.csv.gz",
    "icustays":        "mimic/icu/icustays.csv.gz",
}

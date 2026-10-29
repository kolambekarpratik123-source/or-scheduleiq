"""
OR-ScheduleIQ | Layer 2 | 03_simulation_engine.py
===================================================
Discrete-Event Simulation (DES) of Operating Room scheduling using SimPy.

Simulates:
  ✦ 8 Operating Rooms across a 30-day horizon
  ✦ Case arrivals from a probabilistic schedule (P10/P50/P90 durations)
  ✦ Turnover/cleaning buffers between cases
  ✦ PACU bay capacity constraints
  ✦ ICU bed demand and downstream blockages
  ✦ Overtime risk and cost accumulation

Outputs:
  data/simulated/fact_simulated_schedule.csv  — main simulation fact table
  data/simulated/sim_metrics_daily.csv        — daily aggregate KPIs
  data/simulated/sim_metrics_hourly.csv       — hourly bed occupancy trace
"""

import logging
import warnings
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
import simpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import *

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("simulation_engine")

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SurgicalCase:
    case_id:            int
    room_id:            str
    procedure_name:     str
    specialty:          str
    patient_id:         int
    asa_score:          int
    emergency_flag:     bool
    scheduled_day:      int         # Day number in simulation (0-indexed)
    scheduled_start_t:  float       # Sim time in minutes from day 0, 00:00
    scheduled_duration: float       # Scheduled duration (P50) in minutes
    risk_tier:          str
    # Filled during simulation
    actual_start_t:     float = 0.0
    actual_end_t:       float = 0.0
    actual_duration:    float = 0.0
    pacu_start_t:       float = 0.0
    pacu_end_t:         float = 0.0
    icu_transfer:       bool = False
    icu_start_t:        float = 0.0
    icu_end_t:          float = 0.0
    case_status:        str = "Pending"
    overtime_min:       float = 0.0
    turnover_after_min: float = 0.0
    cancelled:          bool = False
    cancellation_reason:str = ""


@dataclass
class DailyMetrics:
    day:                 int
    date_str:            str
    total_cases:         int = 0
    completed_cases:     int = 0
    cancelled_cases:     int = 0
    total_overtime_min:  float = 0.0
    total_overtime_cost_inr: float = 0.0
    avg_utilization_pct: float = 0.0
    pacu_holds:          int = 0
    icu_transfers:       int = 0
    peak_icu_occupancy:  int = 0
    peak_pacu_occupancy: int = 0
    rooms_with_overtime: int = 0

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

class ScheduleBuilder:
    """Builds a deterministic baseline schedule for each OR day, which the
    simulation then perturbs with sampled durations."""

    def __init__(self, fit_params: Optional[pd.DataFrame], rng: np.random.Generator):
        self.fit_params = fit_params
        self.rng = rng
        self._build_proc_lookup()

    def _build_proc_lookup(self):
        self.proc_data = {}
        for proc_name, (mu, sigma) in DURATION_DISTRIBUTIONS.items():
            self.proc_data[proc_name] = {
                "mu":       mu,
                "sigma":    sigma,
                "specialty":PROCEDURE_TO_SPECIALTY.get(proc_name, "General Surgery"),
                "p50_min":  int(np.exp(mu)),
                "p10_min":  int(np.exp(mu + sigma * (-1.282))),
                "p90_min":  int(np.exp(mu + sigma * 1.282)),
            }
        # Override with fitted params if available
        if self.fit_params is not None:
            for _, row in self.fit_params.iterrows():
                proc = row["procedure_name"]
                if proc in self.proc_data and pd.notna(row.get("lnorm_mu")):
                    self.proc_data[proc]["mu"]    = float(row["lnorm_mu"])
                    self.proc_data[proc]["sigma"] = float(row["lnorm_sigma"])
                    self.proc_data[proc]["p50_min"] = int(row["p50_min"])
                    self.proc_data[proc]["p10_min"] = int(row["p10_min"])
                    self.proc_data[proc]["p90_min"] = int(row["p90_min"])

    def get_procs_for_specialty(self, specialty: str) -> list:
        return [p for p, d in self.proc_data.items() if d["specialty"] == specialty]

    def build_day_schedule(
        self, day: int, sim_start_min: float, buffer_min: float = TARGET_BUFFER_MIN
    ) -> List[SurgicalCase]:
        """Build the scheduled case list for one OR day across all rooms."""
        cases = []
        case_id_base = day * 10000
        patient_id_counter = day * 500

        for room_id, room_info in OR_REGISTRY.items():
            specialty  = room_info["specialty"]
            room_procs = self.get_procs_for_specialty(specialty)
            if not room_procs:
                continue

            # Day offset in simulation time (minutes from t=0)
            day_start = sim_start_min + day * 1440 + OR_START_MIN
            day_end   = sim_start_min + day * 1440 + OR_END_MIN

            cursor = day_start
            case_seq = 0

            while cursor < day_end - 45:
                proc_name = self.rng.choice(room_procs)
                proc_info = self.proc_data[proc_name]
                sched_dur = max(20, int(np.exp(proc_info["mu"]) *
                                        self.rng.normal(1.0, 0.04)))

                if cursor + sched_dur > day_end + 90:  # Max 90min overtime
                    break

                is_emergency  = self.rng.random() < EMERGENCY_RATE
                asa_score     = int(np.clip(
                    self.rng.normal(2.5 + 0.3 * (1 if is_emergency else 0), 0.8), 1, 5
                ))
                risk_tier = (
                    "Critical" if asa_score >= 4 else
                    "High"     if asa_score == 3 else
                    "Moderate" if asa_score == 2 else "Low"
                )

                case = SurgicalCase(
                    case_id            = case_id_base + case_seq,
                    room_id            = room_id,
                    procedure_name     = proc_name,
                    specialty          = specialty,
                    patient_id         = patient_id_counter,
                    asa_score          = asa_score,
                    emergency_flag     = is_emergency,
                    scheduled_day      = day,
                    scheduled_start_t  = cursor,
                    scheduled_duration = sched_dur,
                    risk_tier          = risk_tier,
                )
                cases.append(case)
                case_seq     += 1
                case_id_base += 1
                patient_id_counter += 1
                # Advance past scheduled slot + buffer (deterministic planning)
                cursor += sched_dur + buffer_min

        return cases


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION CORE
# ─────────────────────────────────────────────────────────────────────────────

class ORSimulation:
    """
    SimPy-based Discrete-Event Simulation of OR scheduling.
    Tracks resource utilization, overtime, PACU holds, and ICU demand.
    """

    def __init__(
        self,
        schedule: List[SurgicalCase],
        fit_params: Optional[pd.DataFrame],
        buffer_min: float = TARGET_BUFFER_MIN,
        seed: int = SIM_RANDOM_SEED,
        replication: int = 0,
    ):
        self.schedule      = schedule
        self.fit_params    = fit_params
        self.buffer_min    = buffer_min
        self.seed          = seed + replication
        self.rng           = np.random.default_rng(self.seed)
        self.replication   = replication

        # SimPy environment
        self.env = simpy.Environment()

        # Resources — PriorityResource allows emergency cases to jump the queue
        self.operating_rooms = {
            room_id: simpy.PriorityResource(self.env, capacity=1)
            for room_id in OR_REGISTRY
        }
        self.pacu_bays   = simpy.Resource(self.env, capacity=NUM_PACU_BAYS)
        self.icu_beds    = simpy.Resource(self.env, capacity=NUM_ICU_BEDS)

        # Tracking
        self.completed_cases:   List[SurgicalCase] = []
        self.hourly_icu_trace:  List[dict] = []
        self.hourly_pacu_trace: List[dict] = []
        self._snapshot_interval = 30  # minutes

    def _sample_actual_duration(self, case: SurgicalCase) -> float:
        """Sample actual duration from Log-Normal distribution for this procedure."""
        proc_info = DURATION_DISTRIBUTIONS.get(
            case.procedure_name,
            SPECIALTY_FALLBACK.get(case.specialty, (4.2, 0.45))
        )
        mu, sigma = proc_info
        # Emergency cases have 25% longer duration on average
        if case.emergency_flag:
            mu += np.log(1.25)
        # High-risk patients have 10% longer duration
        if case.risk_tier in ("Critical", "High"):
            mu += np.log(1.10)
        duration = max(10.0, float(self.rng.lognormal(mu, sigma)))
        return duration

    def _sample_turnover(self) -> float:
        """Sample room turnover/cleaning time."""
        return max(
            float(TURNOVER_MIN_FLOOR),
            float(self.rng.normal(self.buffer_min, TURNOVER_STD_MIN))
        )

    def _sample_pacu_duration(self, case: SurgicalCase) -> float:
        """Sample PACU stay duration."""
        mean = PACU_MEAN_MIN
        if case.icu_transfer:
            mean *= PACU_TO_ICU_FACTOR
        if case.asa_score >= 4:
            mean *= 1.20
        return max(15.0, float(self.rng.normal(mean, PACU_STD_MIN)))

    def _sample_icu_transfer(self, case: SurgicalCase) -> bool:
        """Determine if patient requires ICU transfer."""
        base_prob = ICU_TRANSFER_PROB_BY_SPECIALTY.get(case.specialty, 0.10)
        if case.emergency_flag:
            base_prob = min(0.98, base_prob * 2.5)
        if case.asa_score >= 4:
            base_prob = min(0.98, base_prob * 1.8)
        return bool(self.rng.random() < base_prob)

    def _sample_icu_los(self) -> float:
        """Sample ICU length-of-stay in minutes."""
        hours = max(2.0, float(self.rng.normal(ICU_LOS_MEAN_HOURS, ICU_LOS_STD_HOURS)))
        return hours * 60

    def surgical_case_process(self, case: SurgicalCase):
        """SimPy generator: lifecycle of one surgical case."""
        or_resource = self.operating_rooms[case.room_id]

        # Wait for scheduled start time
        yield self.env.timeout(max(0, case.scheduled_start_t - self.env.now))

        # Try to acquire OR (should be free at scheduled time unless overrun)
        with or_resource.request(priority=(0 if case.emergency_flag else 1)) as req:
            yield req  # Wait for room to become available

            # Day-of-surgery cancellation check (elective cases only)
            day_end_t = (case.scheduled_day * 1440) + OR_END_MIN
            if not case.emergency_flag:
                reason = ""
                if self.rng.random() < SAME_DAY_CANCEL_PROB:
                    reason = "Patient unfit / no-show"
                elif self.env.now + case.scheduled_duration > day_end_t + MAX_ALLOWED_OVERTIME_MIN:
                    reason = "Insufficient OR time (list overran)"
                if reason:
                    case.cancelled = True
                    case.cancellation_reason = reason
                    case.case_status = "Cancelled"
                    case.actual_start_t = case.actual_end_t = self.env.now
                    case.pacu_start_t = case.pacu_end_t = self.env.now
                    self.completed_cases.append(case)
                    return  # Room is released immediately

            # Record actual start
            case.actual_start_t = self.env.now
            actual_duration = self._sample_actual_duration(case)
            case.actual_duration = actual_duration

            # Simulate surgery
            yield self.env.timeout(actual_duration)

            case.actual_end_t = self.env.now
            # Calculate how far beyond the 10hr day this goes
            case.overtime_min = max(0.0, case.actual_end_t - day_end_t)

            if actual_duration > case.scheduled_duration * 1.25:
                case.case_status = "Overrun"
            elif case.actual_start_t > case.scheduled_start_t + 20:
                case.case_status = "Delayed"
            else:
                case.case_status = "Completed"

            # Turnover/cleaning (room is still held during turnover)
            turnover = self._sample_turnover()
            case.turnover_after_min = turnover
            yield self.env.timeout(turnover)

        # Room released — now move to PACU
        case.icu_transfer = self._sample_icu_transfer(case)

        with self.pacu_bays.request() as pacu_req:
            yield pacu_req  # Wait for PACU bay

            case.pacu_start_t  = self.env.now
            pacu_dur           = self._sample_pacu_duration(case)
            yield self.env.timeout(pacu_dur)
            case.pacu_end_t = self.env.now

        # ICU transfer (if needed)
        if case.icu_transfer:
            with self.icu_beds.request() as icu_req:
                yield icu_req
                case.icu_start_t = self.env.now
                icu_los = self._sample_icu_los()
                yield self.env.timeout(icu_los)
                case.icu_end_t = self.env.now

        self.completed_cases.append(case)

    def resource_monitor(self):
        """Periodically snapshot resource utilization."""
        while True:
            t = self.env.now
            self.hourly_icu_trace.append({
                "sim_time_min":    t,
                "day":             int(t // 1440),
                "hour":            int((t % 1440) // 60),
                "icu_occupancy":   self.icu_beds.count,
                "icu_capacity":    NUM_ICU_BEDS,
                "pacu_occupancy":  self.pacu_bays.count,
                "pacu_capacity":   NUM_PACU_BAYS,
                "icu_saturation":  self.icu_beds.count >= NUM_ICU_BEDS,
                "pacu_saturation": self.pacu_bays.count >= NUM_PACU_BAYS,
            })
            yield self.env.timeout(self._snapshot_interval)

    def run(self) -> List[SurgicalCase]:
        """Execute the simulation."""
        log.info("  Replication %02d: scheduling %d cases...",
                 self.replication, len(self.schedule))

        # Start monitor
        self.env.process(self.resource_monitor())

        # Launch all case processes
        for case in self.schedule:
            self.env.process(self.surgical_case_process(case))

        # Run simulation
        total_duration = SIM_HORIZON_DAYS * 1440 + 480  # Extra 8hrs for late ICU stays
        self.env.run(until=total_duration)

        log.info("  Replication %02d: %d/%d cases completed",
                 self.replication, len(self.completed_cases), len(self.schedule))
        return self.completed_cases


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────

class SimulationResultsProcessor:
    """Converts raw SimPy case outputs into structured DataFrames."""

    def __init__(self, start_date: date = date(2024, 1, 1)):
        self.start_date = start_date

    def cases_to_dataframe(self, cases: List[SurgicalCase]) -> pd.DataFrame:
        records = []
        for c in cases:
            sim_day_date = self.start_date + timedelta(days=c.scheduled_day)
            # Skip Sundays
            if sim_day_date.weekday() == 6:
                continue

            day_end_t = c.scheduled_day * 1440 + OR_END_MIN
            pacu_hold  = (c.pacu_end_t - c.pacu_start_t) > PACU_EXTENDED_THRESHOLD_MIN

            records.append({
                "case_id":                c.case_id,
                "replication":            0,
                "room_id":                c.room_id,
                "procedure_name":         c.procedure_name,
                "specialty":              c.specialty,
                "patient_id":             c.patient_id,
                "asa_score":              c.asa_score,
                "risk_tier":              c.risk_tier,
                "emergency_flag":         c.emergency_flag,
                "case_status":            c.case_status,
                "cancellation_reason":    c.cancellation_reason or None,
                "scheduled_date":         sim_day_date.isoformat(),
                "scheduled_start_min":    int(c.scheduled_start_t % 1440),
                "scheduled_end_min":      int((c.scheduled_start_t + c.scheduled_duration) % 1440),
                "actual_start_min":       int(c.actual_start_t % 1440),
                "actual_end_min":         int(c.actual_end_t % 1440),
                "scheduled_duration_min": round(c.scheduled_duration, 1),
                "actual_duration_min":    round(c.actual_duration, 1),
                "overrun_min":            round(c.overtime_min, 1),
                "turnover_min":           round(c.turnover_after_min, 1),
                "pacu_start_min":         int(c.pacu_start_t % 1440),
                "pacu_end_min":           int(c.pacu_end_t % 1440),
                "pacu_duration_min":      round(c.pacu_end_t - c.pacu_start_t, 1),
                "pacu_hold_flag":         pacu_hold,
                "icu_transfer_flag":      c.icu_transfer,
                "icu_los_hours":          round((c.icu_end_t - c.icu_start_t) / 60, 2)
                                          if c.icu_transfer else None,
                "overtime_cost_inr":      round(c.overtime_min / 60 * OVERTIME_COST_PER_HOUR_INR, 0),
                "pacu_hold_cost_inr":     round(
                    max(0, c.pacu_end_t - c.pacu_start_t - PACU_EXTENDED_THRESHOLD_MIN) / 60
                    * PACU_HOLD_COST_PER_HR_INR, 0
                ) if pacu_hold else 0,
                "sim_day":                c.scheduled_day,
                # Date dimension key
                "date_key":               int(sim_day_date.strftime("%Y%m%d")),
                "day_of_week":            sim_day_date.weekday(),
                "day_name":               sim_day_date.strftime("%A"),
                "case_month":             sim_day_date.month,
                "case_year":              sim_day_date.year,
            })
        return pd.DataFrame(records)

    def compute_daily_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate daily OR metrics."""
        daily = df.groupby(["scheduled_date", "date_key"]).agg(
            total_cases         =("case_id", "count"),
            completed_cases     =("case_status", lambda x: (x == "Completed").sum()),
            cancelled_cases     =("case_status", lambda x: (x == "Cancelled").sum()),
            overrun_cases       =("case_status", lambda x: (x == "Overrun").sum()),
            total_overtime_min  =("overrun_min", "sum"),
            avg_duration_min    =("actual_duration_min", "mean"),
            pacu_holds          =("pacu_hold_flag", "sum"),
            icu_transfers       =("icu_transfer_flag", "sum"),
            total_pacu_hold_cost=("pacu_hold_cost_inr", "sum"),
            total_overtime_cost =("overtime_cost_inr", "sum"),
        ).reset_index()

        daily["rooms_in_overtime"] = (
            df[df["overrun_min"] > 0]
            .groupby("scheduled_date")["room_id"]
            .nunique()
            .reindex(daily["scheduled_date"], fill_value=0)
            .values
        )
        daily["total_cost_inr"]    = daily["total_overtime_cost"] + daily["total_pacu_hold_cost"]
        # Booked surgical minutes across all theatres / total theatre capacity that day
        daily_minutes = (
            df.groupby("scheduled_date")["actual_duration_min"].sum()
            .reindex(daily["scheduled_date"], fill_value=0).values
        )
        daily["utilization_pct"]   = (
            daily_minutes / (NUM_OPERATING_THEATRES * OR_CAPACITY_MIN) * 100
        ).clip(0, 120)
        return daily

    def compute_hourly_bed_trace(self, hourly_raw: list) -> pd.DataFrame:
        """Clean up the raw monitoring snapshots."""
        df = pd.DataFrame(hourly_raw)
        # Add date info
        start = date(2024, 1, 1)
        df["date_str"] = df["day"].apply(
            lambda d: (start + timedelta(days=d)).isoformat()
        )
        df["time_label"] = df["hour"].apply(lambda h: f"{h:02d}:00")
        df["icu_saturation_pct"]  = (df["icu_occupancy"] / NUM_ICU_BEDS * 100).clip(0, 100)
        df["pacu_saturation_pct"] = (df["pacu_occupancy"] / NUM_PACU_BAYS * 100).clip(0, 100)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# MONTE CARLO WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

def run_monte_carlo(
    schedule: List[SurgicalCase],
    fit_params: Optional[pd.DataFrame],
    buffer_min: float = TARGET_BUFFER_MIN,
    n_replications: int = NUM_SIM_REPLICATIONS,
    seed: int = SIM_RANDOM_SEED,
) -> dict:
    """
    Run N independent replications and return aggregated statistics.
    """
    log.info("Running Monte Carlo: %d replications × %d cases",
             n_replications, len(schedule))

    all_dfs = []
    for rep in range(n_replications):
        sim = ORSimulation(schedule, fit_params, buffer_min=buffer_min,
                           seed=seed, replication=rep)
        completed = sim.run()
        proc = SimulationResultsProcessor()
        df = proc.cases_to_dataframe(completed)
        df["replication"] = rep
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    # Aggregate metrics across replications
    summary = combined.groupby(["scheduled_date", "room_id", "procedure_name"]).agg(
        n_cases             = ("case_id", "count"),
        mean_actual_min     = ("actual_duration_min", "mean"),
        p10_actual_min      = ("actual_duration_min", lambda x: x.quantile(0.10)),
        p50_actual_min      = ("actual_duration_min", lambda x: x.quantile(0.50)),
        p90_actual_min      = ("actual_duration_min", lambda x: x.quantile(0.90)),
        mean_overtime_min   = ("overrun_min", "mean"),
        p90_overtime_min    = ("overrun_min", lambda x: x.quantile(0.90)),
        icu_transfer_rate   = ("icu_transfer_flag", "mean"),
        pacu_hold_rate      = ("pacu_hold_flag", "mean"),
    ).reset_index()

    return {"combined": combined, "summary": summary}


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT PLOTS
# ─────────────────────────────────────────────────────────────────────────────

def plot_simulation_outputs(
    cases_df: pd.DataFrame,
    hourly_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    output_dir: Path,
):
    """Generate executive-grade simulation output charts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    DARK_BG  = "#0f1923"
    MID_BG   = "#1a2535"
    ACCENT_1 = "#3a86ff"  # Blue
    ACCENT_2 = "#06d6a0"  # Emerald
    ACCENT_3 = "#ff6b6b"  # Red
    ACCENT_4 = "#ffd166"  # Amber

    fig = plt.figure(figsize=(22, 14))
    fig.patch.set_facecolor(DARK_BG)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.40, wspace=0.35)

    def style_ax(ax, title):
        ax.set_facecolor(MID_BG)
        ax.set_title(title, color="white", fontsize=11, pad=8, fontweight="bold")
        ax.tick_params(colors="#adb5bd", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#2d3f55")

    # Panel 1: OR Utilization % by Room
    ax1 = fig.add_subplot(gs[0, 0])
    style_ax(ax1, "OR Utilization % by Room")
    room_util = cases_df.groupby("room_id")["actual_duration_min"].sum() / (OR_CAPACITY_MIN * SIM_HORIZON_DAYS) * 100
    bars = ax1.barh(room_util.index, room_util.values,
                    color=[ACCENT_2 if v <= 85 else ACCENT_4 if v <= 100 else ACCENT_3
                           for v in room_util.values],
                    height=0.6)
    ax1.axvline(85, ls="--", color=ACCENT_4, lw=1.5, label="85% Target")
    ax1.axvline(100, ls="--", color=ACCENT_3, lw=1.5, label="Overtime Line")
    ax1.set_xlabel("Utilization (%)", color="#adb5bd")
    ax1.legend(fontsize=7, framealpha=0.2, labelcolor="white")

    # Panel 2: Daily Overtime Minutes
    ax2 = fig.add_subplot(gs[0, 1])
    style_ax(ax2, "Daily Total Overtime (minutes)")
    ax2.bar(range(len(daily_df)), daily_df["total_overtime_min"],
            color=[ACCENT_3 if v > 60 else ACCENT_4 if v > 0 else ACCENT_2
                   for v in daily_df["total_overtime_min"]])
    ax2.axhline(60, ls="--", color=ACCENT_4, lw=1.5, label="60-min Alert")
    ax2.set_xlabel("Simulation Day", color="#adb5bd")
    ax2.set_ylabel("Overtime (min)", color="#adb5bd")
    ax2.legend(fontsize=8, framealpha=0.2, labelcolor="white")

    # Panel 3: Scheduled vs Actual Duration (specialty)
    ax3 = fig.add_subplot(gs[0, 2])
    style_ax(ax3, "Scheduled vs. Actual Duration")
    for sp, color in [("General Surgery", ACCENT_1), ("Orthopedics", ACCENT_2), ("Cardiac", ACCENT_3)]:
        sub = cases_df[cases_df["specialty"] == sp]
        ax3.scatter(sub["scheduled_duration_min"], sub["actual_duration_min"],
                    alpha=0.3, s=15, color=color, label=sp)
    xlim = ax3.get_xlim()
    ax3.plot([0, max(xlim)], [0, max(xlim)], 'w--', lw=1, label="Perfect Estimate")
    ax3.set_xlabel("Scheduled (min)", color="#adb5bd")
    ax3.set_ylabel("Actual (min)", color="#adb5bd")
    ax3.legend(fontsize=7, framealpha=0.2, labelcolor="white")

    # Panel 4: Hourly ICU Bed Occupancy
    ax4 = fig.add_subplot(gs[1, 0])
    style_ax(ax4, "ICU Bed Occupancy (Hourly Avg)")
    hourly_avg = hourly_df.groupby("hour")["icu_occupancy"].mean()
    ax4.fill_between(hourly_avg.index, hourly_avg.values, alpha=0.4, color=ACCENT_3)
    ax4.plot(hourly_avg.index, hourly_avg.values, color=ACCENT_3, lw=2)
    ax4.axhline(NUM_ICU_BEDS, ls="--", color="white", lw=1.5, label=f"Capacity ({NUM_ICU_BEDS})")
    ax4.axhline(NUM_ICU_BEDS * 0.80, ls=":", color=ACCENT_4, lw=1.5, label="80% Threshold")
    ax4.set_xlabel("Hour of Day", color="#adb5bd")
    ax4.set_ylabel("Beds Occupied", color="#adb5bd")
    ax4.legend(fontsize=7, framealpha=0.2, labelcolor="white")
    ax4.set_xticks(range(0, 24, 2))

    # Panel 5: Daily ICU Transfers
    ax5 = fig.add_subplot(gs[1, 1])
    style_ax(ax5, "Daily ICU Transfers by Specialty")
    pivot = cases_df[cases_df["icu_transfer_flag"]].groupby(
        ["scheduled_date", "specialty"]
    )["case_id"].count().unstack(fill_value=0)
    x = range(len(pivot))
    bottoms = np.zeros(len(pivot))
    colors_sp = {"General Surgery": ACCENT_1, "Orthopedics": ACCENT_2, "Cardiac": ACCENT_3}
    for sp in pivot.columns:
        vals = pivot[sp].values
        ax5.bar(x, vals, bottom=bottoms, label=sp,
                color=colors_sp.get(sp, "#adb5bd"), alpha=0.85)
        bottoms += vals
    ax5.set_xlabel("Simulation Day", color="#adb5bd")
    ax5.set_ylabel("ICU Transfers", color="#adb5bd")
    ax5.legend(fontsize=7, framealpha=0.2, labelcolor="white")

    # Panel 6: PACU Duration Distribution
    ax6 = fig.add_subplot(gs[1, 2])
    style_ax(ax6, "PACU Stay Distribution\n(Hold Threshold = 90 min)")
    pacu_durations = cases_df["pacu_duration_min"].dropna()
    ax6.hist(pacu_durations, bins=40, color=ACCENT_1, alpha=0.7, density=True)
    ax6.axvline(PACU_EXTENDED_THRESHOLD_MIN, ls="--", color=ACCENT_3, lw=2,
                label=f"Hold Threshold ({PACU_EXTENDED_THRESHOLD_MIN} min)")
    ax6.set_xlabel("PACU Duration (min)", color="#adb5bd")
    ax6.set_ylabel("Density", color="#adb5bd")
    ax6.legend(fontsize=8, framealpha=0.2, labelcolor="white")

    fig.suptitle(
        "OR-ScheduleIQ | Discrete-Event Simulation Results\n"
        f"{NUM_OPERATING_THEATRES} Theatres | {SIM_HORIZON_DAYS}-Day Horizon | "
        f"Buffer: {TARGET_BUFFER_MIN} min",
        color="white", fontsize=14, fontweight="bold", y=0.98
    )

    out_path = output_dir / "simulation_dashboard.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    log.info("Simulation dashboard plot saved: %s", out_path)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run(
    fit_params: Optional[pd.DataFrame] = None,
    buffer_min: float = TARGET_BUFFER_MIN,
    n_replications: int = 10,  # Use 10 for speed; set to 100 for production
) -> pd.DataFrame:
    log.info("=" * 60)
    log.info("OR-ScheduleIQ | Simulation Engine")
    log.info("  Theatres: %d | Horizon: %d days | Buffer: %d min",
             NUM_OPERATING_THEATRES, SIM_HORIZON_DAYS, buffer_min)
    log.info("=" * 60)

    rng = np.random.default_rng(SIM_RANDOM_SEED)
    builder = ScheduleBuilder(fit_params, rng)

    # Build full schedule across all days
    full_schedule: List[SurgicalCase] = []
    for day in range(SIM_HORIZON_DAYS):
        sim_day_date = date(2024, 1, 1) + timedelta(days=day)
        if sim_day_date.weekday() == 6:  # Skip Sundays
            continue
        day_cases = builder.build_day_schedule(day, sim_start_min=0.0, buffer_min=buffer_min)
        full_schedule.extend(day_cases)

    log.info("Total scheduled cases: %d", len(full_schedule))

    # Single replication for the main output (fast)
    sim = ORSimulation(full_schedule, fit_params, buffer_min=buffer_min)
    completed_cases = sim.run()

    # Process results
    proc = SimulationResultsProcessor()
    cases_df   = proc.cases_to_dataframe(completed_cases)
    hourly_df  = proc.compute_hourly_bed_trace(sim.hourly_icu_trace)
    daily_df   = proc.compute_daily_metrics(cases_df)

    # Save outputs
    DATA_SIMULATED.mkdir(parents=True, exist_ok=True)
    cases_df.to_csv(DATA_SIMULATED / "fact_simulated_schedule.csv", index=False)
    hourly_df.to_csv(DATA_SIMULATED / "sim_hourly_bed_trace.csv", index=False)
    daily_df.to_csv(DATA_SIMULATED / "sim_daily_metrics.csv", index=False)

    log.info("Saved: fact_simulated_schedule.csv (%d rows)", len(cases_df))
    log.info("Saved: sim_hourly_bed_trace.csv (%d rows)", len(hourly_df))
    log.info("Saved: sim_daily_metrics.csv (%d rows)", len(daily_df))

    # Generate plots
    plot_simulation_outputs(cases_df, hourly_df, daily_df, DATA_SIMULATED)

    # KPI summary
    log.info("\n" + "=" * 50)
    log.info("SIMULATION KPI SUMMARY")
    log.info("=" * 50)
    log.info("  Total cases simulated:      %d", len(cases_df))
    log.info("  Total overtime minutes:     %.0f", cases_df["overrun_min"].sum())
    log.info("  Total overtime cost (INR):  ₹%.0f", cases_df["overtime_cost_inr"].sum())
    log.info("  ICU transfers:              %d (%.1f%%)",
             cases_df["icu_transfer_flag"].sum(),
             cases_df["icu_transfer_flag"].mean() * 100)
    log.info("  PACU holds (>90 min):       %d (%.1f%%)",
             cases_df["pacu_hold_flag"].sum(),
             cases_df["pacu_hold_flag"].mean() * 100)
    log.info("  Avg OR utilization:         %.1f%%",
             cases_df["actual_duration_min"].sum() /
             (NUM_OPERATING_THEATRES * OR_CAPACITY_MIN * SIM_HORIZON_DAYS) * 100)

    return cases_df


if __name__ == "__main__":
    run()

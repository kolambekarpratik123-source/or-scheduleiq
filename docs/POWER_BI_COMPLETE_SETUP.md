# OR-ScheduleIQ | Power BI Desktop — Complete Setup Reference
## Everything you need to rebuild the dashboard from scratch

> **Created:** 2026-10-27
> **Project:** f:\project 3
> **Pipeline cmd:** `python layer2_python/run_pipeline.py --data-source synthetic --buffer 30 --replications 10`
> **Pre-req:** Run the pipeline first to generate all CSVs in `data/processed/` and `data/simulated/`

---

## TABLE OF CONTENTS

1. [Project Architecture](#1-project-architecture)
2. [Running the Pipeline](#2-running-the-pipeline)
3. [Loading Tables into Power BI](#3-loading-tables-into-power-bi)
4. [Column Name Reference (CSV → DAX)](#4-column-name-reference)
5. [Star Schema Relationships](#5-star-schema-relationships)
6. [What-If Parameters](#6-what-if-parameters)
7. [All DAX Measures](#7-all-dax-measures)
8. [Page 1 Layout: OR Utilization & Overtime Risk](#8-page-1-layout)
9. [Page 2 Layout: PACU & ICU Bottleneck](#9-page-2-layout)
10. [Theme & Styling](#10-theme--styling)
11. [Final Checklist](#11-final-checklist)

---

## 1. PROJECT ARCHITECTURE

```
f:\project 3\
├── layer1_sql/               SQL feature engineering (DuckDB)
│   ├── 01_ddl_staging.sql
│   ├── 02_feature_engineering.sql
│   └── 03_export_csvs.sql
├── layer2_python/            Python simulation engine
│   ├── config.py             All tunable parameters
│   ├── 01_data_loader.py     Synthetic/MIMIC/Kaggle data ingest
│   ├── 02_distribution_fitter.py   Log-Normal/Weibull fitting
│   ├── 03_simulation_engine.py     SimPy DES core
│   ├── 04_export_results.py  Dimension tables + fact enrichment
│   └── run_pipeline.py       Single-entry orchestrator
├── layer3_schema/
│   └── star_schema_definition.md   Kimball schema documentation
├── layer4_powerbi/
│   ├── OR_ScheduleIQ_Theme.json    Custom dark theme
│   ├── dax_measures.md             Full DAX library (PascalCase refs)
│   └── dashboard_layout.md         Visual layout blueprint
├── data/
│   ├── raw/                  Source data (generated or downloaded)
│   ├── processed/            Dimension + historical fact CSVs
│   └── simulated/            Simulation output CSVs
└── docs/
    ├── DATA_SOURCING.md      Free dataset instructions
    └── POWER_BI_COMPLETE_SETUP.md   ← THIS FILE
```

---

## 2. RUNNING THE PIPELINE

### Install dependencies
```bash
pip install duckdb pandas numpy scipy scikit-learn simpy matplotlib seaborn tqdm
```

### Run full pipeline
```bash
cd "f:\project 3"
python layer2_python/run_pipeline.py --data-source synthetic --buffer 30 --replications 10
```

### CLI options
```
--data-source synthetic|mimic|kaggle    Data source (default: synthetic)
--buffer 30                             Turnover buffer minutes (default: 30)
--replications 10                       Monte Carlo runs (default: 10, prod: 100)
--skip-sql                              Skip DuckDB feature engineering
--skip-plots                            Skip matplotlib plot generation
```

### Expected output (last run results)
- 1,500 synthetic patients generated
- 717 historical surgery cases
- 782 simulated cases across 30 days × 8 theatres
- OR utilization: 76.3%
- Total overtime: 26,050 min (₹10,85,395)
- ICU transfers: 124 (15.9%)
- PACU holds: 163 (20.8%)

---

## 3. LOADING TABLES INTO POWER BI

**Method:** Home → Get Data → Text/CSV → browse to file → Load

### Tables from `data\processed\`

| File | Rename to in PBI | Rows | Purpose |
|---|---|---|---|
| `dim_date.csv` | `dim_date` | 365 | Calendar dimension (time intelligence) |
| `dim_operating_room.csv` | `dim_operating_room` | 8 | OR theatre registry |
| `dim_surgical_specialty.csv` | `dim_surgical_specialty` | 3 | Specialty metadata |
| `dim_patient_risk_tier.csv` | `dim_patient_risk_tier` | 4 | ASA/CCI risk tiers |
| `dim_time_slot.csv` | `dim_time_slot` | 96 | 15-min scheduling slots |
| `dim_surgeries_master.csv` | `dim_surgeries_master` | 19 | Procedure reference table |
| `fact_surgery_cases.csv` | `fact_surgery_cases` | 717 | Historical surgical cases |
| `fact_historical_cases.csv` | `fact_historical_cases` | 717 | Enriched historical (velocity, CCI, P90) |
| `duration_fit_parameters.csv` | `duration_fit_parameters` | 19 | Distribution fit results |

### Tables from `data\simulated\`

| File | Rename to in PBI | Rows | Purpose |
|---|---|---|---|
| `fact_simulated_schedule.csv` | `Fact_Surgical_Schedule` | 782 | Main simulation fact table |
| `sim_hourly_bed_trace.csv` | `sim_hourly_bed_trace` | 1,456 | Hourly ICU/PACU occupancy |
| `sim_daily_metrics.csv` | `sim_daily_metrics` | 26 | Daily aggregate KPIs |

### Create `_Measures` table
Home → Enter Data → name it `_Measures` → Load (empty dummy table is fine)
Delete any auto-created `Column1` from it.

---

## 4. COLUMN NAME REFERENCE

**CRITICAL:** The CSV files use **snake_case** column names. The `dax_measures.md` file uses
**PascalCase** references. You must map between them.

### Fact_Surgical_Schedule (fact_simulated_schedule.csv)

| CSV column (snake_case) | DAX reference (PascalCase) |
|---|---|
| `case_id` | `[case_id]` |
| `room_id` | `[room_id]` or rename to `[RoomID]` |
| `specialty` | `[specialty]` or rename to `[Specialty]` |
| `scheduled_duration_min` | `[scheduled_duration_min]` or rename to `[ScheduledDuration_min]` |
| `actual_duration_min` | `[actual_duration_min]` or rename to `[ActualDuration_min]` |
| `overrun_min` | `[overrun_min]` or rename to `[OverrunMin]` |
| `turnover_min` | `[turnover_min]` or rename to `[TurnoverMin]` |
| `pacu_duration_min` | `[pacu_duration_min]` or rename to `[PACU_Duration_min]` |
| `pacu_hold_flag` | `[pacu_hold_flag]` or rename to `[PACU_Hold_Flag]` |
| `icu_transfer_flag` | `[icu_transfer_flag]` or rename to `[ICU_Transfer_Flag]` |
| `icu_los_hours` | `[icu_los_hours]` or rename to `[ICU_LOS_Hours]` |
| `emergency_flag` | `[emergency_flag]` or rename to `[EmergencyFlag]` |
| `asa_score` | `[asa_score]` or rename to `[ASA_Score]` |
| `case_status` | `[case_status]` or rename to `[CaseStatus]` |
| `risk_tier` | `[risk_tier]` or rename to `[RiskTier]` |
| `date_key` | `[date_key]` or rename to `[DateKey]` |
| `overtime_cost_inr` | `[overtime_cost_inr]` or rename to `[OvertimeCost_INR]` |
| `pacu_hold_cost_inr` | `[pacu_hold_cost_inr]` or rename to `[PACU_HoldCost_INR]` |
| `OT_Cost_INR` | `[OT_Cost_INR]` (already PascalCase from export step) |
| `PACU_HoldCost_INR` | `[PACU_HoldCost_INR]` (already PascalCase) |
| `ICU_Cost_INR` | `[ICU_Cost_INR]` (already PascalCase) |

**RECOMMENDED:** Rename all columns in Power Query to PascalCase to match the DAX in `dax_measures.md`.
In Power Query Editor (Home → Transform Data):
  - Select column → right-click → Rename
  - Or use: Table.RenameColumns(Source, {{"snake_case", "PascalCase"}})

**OR:** Use the DAX measures below (Section 7) which use the actual snake_case column names from the CSVs.

---

## 5. STAR SCHEMA RELATIONSHIPS

Open **Model view** (diagram icon in left sidebar). Drag from FK → PK.

| From Table | From Column | To Table | To Column | Cardinality |
|---|---|---|---|---|
| `Fact_Surgical_Schedule` | `date_key` | `dim_date` | `DateKey` | Many → 1 |
| `Fact_Surgical_Schedule` | `room_id` | `dim_operating_room` | `RoomID` | Many → 1 |
| `Fact_Surgical_Schedule` | `specialty` | `dim_surgical_specialty` | `SpecialtyName` | Many → 1 |
| `Fact_Surgical_Schedule` | `risk_tier` | `dim_patient_risk_tier` | `RiskTierName` | Many → 1 |
| `fact_historical_cases` | `date_key` | `dim_date` | `DateKey` | Many → 1 |
| `fact_historical_cases` | `specialty` | `dim_surgical_specialty` | `SpecialtyName` | Many → 1 |
| `fact_historical_cases` | `risk_tier` | `dim_patient_risk_tier` | `RiskTierName` | Many → 1 |

**Cross-filter direction:** Single for all.
**Note:** If Power BI auto-detects relationships, verify they match the above and remove duplicates.

---

## 6. WHAT-IF PARAMETERS

**Modeling tab → New Parameter → Numeric Range**

### Parameter 1: Buffer Time
```
Name:       Buffer_Time_Minutes
Data type:  Whole Number
Min:        15
Max:        60
Increment:  5
Default:    30
Add slicer: Yes
```
This auto-creates: `Buffer_Time_Minutes Value = SELECTEDVALUE('Buffer_Time_Minutes'[Buffer_Time_Minutes], 30)`

### Parameter 2: Overtime Cost Rate
```
Name:       OT_CostRate_INR
Data type:  Whole Number
Min:        1500
Max:        5000
Increment:  250
Default:    2500
Add slicer: Yes
```
This auto-creates: `OT_CostRate_INR Value = SELECTEDVALUE('OT_CostRate_INR'[OT_CostRate_INR], 2500)`

---

## 7. ALL DAX MEASURES

Right-click `_Measures` → New measure → paste each block.

**NOTE:** These DAX measures use the **actual snake_case column names** from the CSV files.
If you renamed columns to PascalCase in Power Query, use the `dax_measures.md` file instead.

### SECTION 1: Base Aggregations

```dax
Total_Cases = COUNTROWS( Fact_Surgical_Schedule )
```

```dax
Completed_Cases =
CALCULATE(
    COUNTROWS( Fact_Surgical_Schedule ),
    Fact_Surgical_Schedule[case_status] = "Completed"
)
```

```dax
Cancelled_Cases =
CALCULATE(
    COUNTROWS( Fact_Surgical_Schedule ),
    Fact_Surgical_Schedule[case_status] = "Cancelled"
)
```

```dax
Emergency_Cases =
CALCULATE(
    COUNTROWS( Fact_Surgical_Schedule ),
    Fact_Surgical_Schedule[emergency_flag] = TRUE()
)
```

```dax
Total_Scheduled_Hours =
DIVIDE(
    SUMX( Fact_Surgical_Schedule, Fact_Surgical_Schedule[scheduled_duration_min] ),
    60
)
```

```dax
Total_Actual_Hours =
DIVIDE(
    SUMX( Fact_Surgical_Schedule, Fact_Surgical_Schedule[actual_duration_min] ),
    60
)
```

### SECTION 2: OR Utilization

```dax
OR_Utilization_Pct =
VAR TotalActualMin =
    SUMX(
        Fact_Surgical_Schedule,
        IF(
            Fact_Surgical_Schedule[case_status] <> "Cancelled",
            Fact_Surgical_Schedule[actual_duration_min],
            0
        )
    )
VAR DistinctDays = DISTINCTCOUNT( Fact_Surgical_Schedule[date_key] )
VAR NumRooms     = DISTINCTCOUNT( Fact_Surgical_Schedule[room_id] )
VAR AvailableMin = NumRooms * DistinctDays * 600
RETURN ROUND( DIVIDE( TotalActualMin, AvailableMin, 0 ), 4 )
```
*Format: 0.0%*

```dax
OR_Utilization_Pct_ByRoom =
VAR TotalActualMin =
    SUMX(
        Fact_Surgical_Schedule,
        IF(
            Fact_Surgical_Schedule[case_status] <> "Cancelled",
            Fact_Surgical_Schedule[actual_duration_min],
            0
        )
    )
VAR DistinctDays = DISTINCTCOUNT( Fact_Surgical_Schedule[date_key] )
VAR AvailableMin = DistinctDays * 600
RETURN ROUND( DIVIDE( TotalActualMin, AvailableMin, 0 ), 4 )
```

```dax
Target_Utilization_Band =
VAR Util = [OR_Utilization_Pct]
RETURN
    SWITCH(
        TRUE(),
        Util >= 1.00, "OVERTIME",
        Util >= 0.85, "BUFFER BREACH",
        Util >= 0.70, "ON TRACK",
        "UNDERUTILIZED"
    )
```

### SECTION 3: Overtime

```dax
Total_Overtime_Minutes =
SUMX( Fact_Surgical_Schedule, MAX( 0, Fact_Surgical_Schedule[overrun_min] ) )
```

```dax
Total_Overtime_Hours = DIVIDE( [Total_Overtime_Minutes], 60 )
```
*Format: 0.0 "hrs"*

```dax
Rooms_With_Overtime =
CALCULATE(
    DISTINCTCOUNT( Fact_Surgical_Schedule[room_id] ),
    Fact_Surgical_Schedule[overrun_min] > 0
)
```

```dax
Projected_Overtime_Cost_INR =
VAR BufferMin   = [Buffer_Time_Minutes Value]
VAR CostPerHour = [OT_CostRate_INR Value]
VAR OvertimeMinutes =
    SUMX(
        Fact_Surgical_Schedule,
        MAX(
            0,
            Fact_Surgical_Schedule[actual_duration_min]
                - Fact_Surgical_Schedule[scheduled_duration_min]
                - BufferMin
        )
    )
VAR OvertimeHours = DIVIDE( OvertimeMinutes, 60 )
RETURN ROUND( OvertimeHours * CostPerHour, 0 )
```
*Format: "Rs " #,##0*

```dax
OT_Cost_vs_Baseline_INR =
VAR BaselineCost =
    CALCULATE(
        [Projected_Overtime_Cost_INR],
        'Buffer_Time_Minutes'[Buffer_Time_Minutes] = 30
    )
RETURN BaselineCost - [Projected_Overtime_Cost_INR]
```

```dax
Overtime_Alert_Color =
VAR OT = [Total_Overtime_Hours]
RETURN
    SWITCH(
        TRUE(),
        OT > 8,  "#DC2626",
        OT > 3,  "#D97706",
        OT > 0,  "#F59E0B",
        "#059669"
    )
```

### SECTION 4: Cancellation Risk

```dax
Case_Cancellation_Rate_Pct =
DIVIDE( [Cancelled_Cases], [Total_Cases], 0 )
```
*Format: 0.0%*

```dax
Predicted_Cancellation_Risk_Pct =
VAR AvgASA =
    AVERAGEX( Fact_Surgical_Schedule, Fact_Surgical_Schedule[asa_score] )
VAR EmergencyRate =
    DIVIDE( [Emergency_Cases], [Total_Cases], 0 )
VAR HighRiskRate =
    DIVIDE(
        CALCULATE(
            COUNTROWS( Fact_Surgical_Schedule ),
            Fact_Surgical_Schedule[risk_tier] IN { "High", "Critical" }
        ),
        [Total_Cases],
        0
    )
RETURN
    ROUND(
        0.03 + 0.015 * (AvgASA - 2) + 0.12 * EmergencyRate + 0.08 * HighRiskRate,
        4
    )
```

### SECTION 5: PACU

```dax
Total_PACU_Holds =
CALCULATE(
    COUNTROWS( Fact_Surgical_Schedule ),
    Fact_Surgical_Schedule[pacu_hold_flag] = TRUE()
)
```

```dax
PACU_Hold_Rate_Pct = DIVIDE( [Total_PACU_Holds], [Total_Cases], 0 )
```
*Format: 0.0%*

```dax
Avg_PACU_Duration_min =
AVERAGEX(
    FILTER(
        Fact_Surgical_Schedule,
        NOT ISBLANK( Fact_Surgical_Schedule[pacu_duration_min] )
    ),
    Fact_Surgical_Schedule[pacu_duration_min]
)
```

```dax
PACU_Hold_Time_Hours =
DIVIDE(
    SUMX(
        FILTER( Fact_Surgical_Schedule, Fact_Surgical_Schedule[pacu_hold_flag] = TRUE() ),
        MAX( 0, Fact_Surgical_Schedule[pacu_duration_min] - 90 )
    ),
    60
)
```

```dax
PACU_Total_Hold_Cost_INR =
SUMX( Fact_Surgical_Schedule, Fact_Surgical_Schedule[PACU_HoldCost_INR] )
```
*Format: "Rs " #,##0*

### SECTION 6: ICU

```dax
Total_ICU_Transfers =
CALCULATE(
    COUNTROWS( Fact_Surgical_Schedule ),
    Fact_Surgical_Schedule[icu_transfer_flag] = TRUE()
)
```

```dax
ICU_Transfer_Rate_Pct = DIVIDE( [Total_ICU_Transfers], [Completed_Cases], 0 )
```
*Format: 0.0%*

```dax
Avg_ICU_LOS_Hours =
AVERAGEX(
    FILTER(
        Fact_Surgical_Schedule,
        Fact_Surgical_Schedule[icu_transfer_flag] = TRUE()
            && NOT ISBLANK( Fact_Surgical_Schedule[icu_los_hours] )
    ),
    Fact_Surgical_Schedule[icu_los_hours]
)
```

```dax
Peak_ICU_Bed_Demand =
VAR ICUTransfers  = [Total_ICU_Transfers]
VAR AvgLOS        = [Avg_ICU_LOS_Hours]
VAR WorkingDays   = DISTINCTCOUNT( Fact_Surgical_Schedule[date_key] )
VAR DailyArrivals = DIVIDE( ICUTransfers, WorkingDays, 0 )
VAR AvgOccupancy  = DailyArrivals * DIVIDE( AvgLOS, 24, 0 )
RETURN ROUND( AvgOccupancy * 1.5, 0 )
```

```dax
ICU_Bed_Saturation_Risk =
VAR PeakDemand = [Peak_ICU_Bed_Demand]
VAR TotalBeds  = 16
RETURN ROUND( DIVIDE( PeakDemand, TotalBeds, 0 ), 4 )
```
*Format: 0.0%*

```dax
ICU_Saturation_Label =
VAR Sat = [ICU_Bed_Saturation_Risk]
RETURN
    SWITCH(
        TRUE(),
        Sat >= 0.95, "CRITICAL - Immediate Action Required",
        Sat >= 0.80, "HIGH - ICU Block Risk Active",
        Sat >= 0.60, "MODERATE - Monitor Closely",
        "NORMAL - Within Safe Operating Range"
    )
```

```dax
ICU_Saturation_Color =
VAR Sat = [ICU_Bed_Saturation_Risk]
RETURN
    SWITCH(
        TRUE(),
        Sat >= 0.95, "#DC2626",
        Sat >= 0.80, "#EA580C",
        Sat >= 0.60, "#D97706",
        "#059669"
    )
```

```dax
Total_ICU_Bed_Cost_INR =
SUMX(
    FILTER(
        Fact_Surgical_Schedule,
        Fact_Surgical_Schedule[icu_transfer_flag] = TRUE()
    ),
    Fact_Surgical_Schedule[icu_los_hours] * 3500
)
```
*Format: "Rs " #,##0*

### SECTION 7: Buffer What-If

```dax
Dynamic_Turnover_Buffer = [Buffer_Time_Minutes Value]
```

```dax
Adjusted_Cases_Per_Room_Per_Day =
VAR BufferMin  = [Buffer_Time_Minutes Value]
VAR AvgProcMin = AVERAGEX(
                    Fact_Surgical_Schedule,
                    Fact_Surgical_Schedule[scheduled_duration_min]
                 )
VAR SlotSize   = AvgProcMin + BufferMin
RETURN FLOOR( DIVIDE( 600, SlotSize, 0 ), 1 )
```

```dax
Buffer_Efficiency_Rate_Pct =
VAR BufferMin = [Buffer_Time_Minutes Value]
VAR AvgActualTurnover =
    AVERAGEX(
        FILTER(
            Fact_Surgical_Schedule,
            NOT ISBLANK( Fact_Surgical_Schedule[turnover_min] )
        ),
        Fact_Surgical_Schedule[turnover_min]
    )
RETURN ROUND( DIVIDE( AvgActualTurnover, BufferMin, 0 ), 4 )
```
*Format: 0.0%*

```dax
Wasted_Buffer_Hours =
VAR BufferMin = [Buffer_Time_Minutes Value]
VAR AvgActualTurnover =
    AVERAGEX(
        FILTER(
            Fact_Surgical_Schedule,
            NOT ISBLANK( Fact_Surgical_Schedule[turnover_min] )
        ),
        Fact_Surgical_Schedule[turnover_min]
    )
VAR WastedMin = MAX( 0, BufferMin - AvgActualTurnover ) * [Total_Cases]
RETURN ROUND( DIVIDE( WastedMin, 60 ), 1 )
```

### SECTION 8: Time Intelligence

```dax
Cases_MTD =
CALCULATE( [Total_Cases], DATESMTD( dim_date[Date] ) )
```

```dax
OT_Cost_WoW_Change_Pct =
VAR CurrentWeekCost  = [Projected_Overtime_Cost_INR]
VAR PreviousWeekCost =
    CALCULATE(
        [Projected_Overtime_Cost_INR],
        DATEADD( dim_date[Date], -7, DAY )
    )
RETURN
    DIVIDE(
        CurrentWeekCost - PreviousWeekCost,
        IF( PreviousWeekCost = 0, BLANK(), PreviousWeekCost ),
        BLANK()
    )
```

```dax
Rolling_7D_Avg_Utilization =
AVERAGEX(
    DATESINPERIOD( dim_date[Date], LASTDATE( dim_date[Date] ), -7, DAY ),
    [OR_Utilization_Pct]
)
```

### SECTION 9: Historical Comparison

```dax
Hist_vs_Sim_Duration_Variance_Pct =
VAR HistAvg = AVERAGEX( fact_historical_cases, fact_historical_cases[actual_duration_min] )
VAR SimAvg  = AVERAGEX( Fact_Surgical_Schedule, Fact_Surgical_Schedule[actual_duration_min] )
RETURN DIVIDE( SimAvg - HistAvg, IF( HistAvg = 0, BLANK(), HistAvg ), BLANK() )
```

```dax
Surgeon_Velocity_Index_Avg =
AVERAGEX(
    FILTER(
        fact_historical_cases,
        NOT ISBLANK( fact_historical_cases[VelocityIndex] )
    ),
    fact_historical_cases[VelocityIndex]
)
```
*Format: 0.00*

```dax
Exceeded_P90_Rate_Pct =
DIVIDE(
    CALCULATE(
        COUNTROWS( fact_historical_cases ),
        fact_historical_cases[ExceededP90_Flag] = TRUE()
    ),
    COUNTROWS( fact_historical_cases ),
    0
)
```
*Format: 0.0%*

### SECTION 10: KPI Formatting & Grand Totals

```dax
KPI_Util_Formatted =
FORMAT( [OR_Utilization_Pct], "0.0%" ) & "  " & [Target_Utilization_Band]
```

```dax
KPI_OT_Cost_Formatted =
"Rs " & FORMAT( [Projected_Overtime_Cost_INR], "#,##0" )
```

```dax
Total_Cost_All_Delays_INR =
[Projected_Overtime_Cost_INR]
    + [PACU_Total_Hold_Cost_INR]
    + SUMX(
        Fact_Surgical_Schedule,
        IF( Fact_Surgical_Schedule[case_status] = "Cancelled", 15000, 0 )
    )
```
*Format: "Rs " #,##0*

### SECTION 11: Scatter Plot Measures (Page 2)

```dax
Avg_CCI_Score =
AVERAGEX( fact_historical_cases, fact_historical_cases[CCI_Score] )
```

```dax
Avg_Recovery_Bed_Hours =
AVERAGEX(
    Fact_Surgical_Schedule,
    DIVIDE( Fact_Surgical_Schedule[pacu_duration_min], 60 )
        + IF(
            Fact_Surgical_Schedule[icu_transfer_flag],
            Fact_Surgical_Schedule[icu_los_hours],
            0
          )
)
```

### SECTION 12: Conditional Formatting Reference Table

```dax
_Alert_Thresholds =
DATATABLE(
    "Metric",     STRING,
    "GreenMax",   DOUBLE,
    "AmberMax",   DOUBLE,
    "RedMin",     DOUBLE,
    "GreenColor", STRING,
    "AmberColor", STRING,
    "RedColor",   STRING,
    {
        { "OR_Utilization",         0.85, 1.00, 1.00, "#059669", "#D97706", "#DC2626" },
        { "ICU_Bed_Saturation",     0.60, 0.80, 0.95, "#059669", "#D97706", "#DC2626" },
        { "PACU_Hold_Rate",         0.10, 0.20, 0.30, "#059669", "#D97706", "#DC2626" },
        { "Cancellation_Rate",      0.03, 0.07, 0.10, "#059669", "#D97706", "#DC2626" },
        { "OT_Hours",               3.0,  8.0,  12.0, "#059669", "#D97706", "#DC2626" }
    }
)
```

---

## 8. PAGE 1 LAYOUT: OR Utilization & Overtime Risk

**Page Name:** `OR Flow`
**Canvas:** 1280 x 720px

### Background
- Insert Rectangle shape → fill `#0B1628` → no border → send to back

### Header Band (y=0, h=52)
- Insert Rectangle → W=1280, H=52, fill `#0D1F3C`
- Text Box: "OR Utilization & Overtime Risk" — Segoe UI Semibold 16pt, color `#E8EDF5`
- Text Box: "Operating Theatre Performance Dashboard" — 10pt, `#8FA3BF`

### ROW 1 — 4 KPI Cards (y=60, h=80, width=280 each, gap=12)

| Card | X pos | Measure | Format | Conditional BG |
|---|---|---|---|---|
| Net OR Utilization | 16 | `OR_Utilization_Pct` | 0.0% | Green >=0.70 <0.85, Amber >=0.85 <1.0, Red >=1.0 |
| Overtime Hours | 308 | `Total_Overtime_Hours` | 0.0 "hrs" | Green <2, Amber 2-6, Red >6 |
| Projected OT Cost | 600 | `Projected_Overtime_Cost_INR` | Rs #,##0 | Fixed `#1C2E48` |
| Cancellation Risk | 892 | `Case_Cancellation_Rate_Pct` | 0.0% | Green <0.03, Amber 0.03-0.07, Red >0.07 |

### ROW 2 — Room Heatmap + Duration Chart (y=152, h=288)

**Left: Matrix Heatmap** (X=16, W=780)
- Rows: `dim_operating_room[RoomName]`
- Columns: `dim_date[DayName]`
- Values: `OR_Utilization_Pct_ByRoom`
- Background color rules: green/amber/red gradient
- Title: "OR Utilization by Room & Day"

**Right: Clustered Column Chart** (X=808, W=456)
- X: `Fact_Surgical_Schedule[actual_duration_min]` (binned by 30)
- Y: Count of case_id
- Title: "Scheduled vs. Actual Duration Distribution"

### ROW 3 — What-If + Specialty Breakdown (y=452, h=248)

**Left: What-If Panel** (X=16, W=390)
- Rectangle border: `#3A86FF` 2px, fill `#1C3050`
- Text: "What-If: Buffer Time Scenario"
- Buffer_Time_Minutes slicer (slider)
- 3 mini cards: `Adjusted_Cases_Per_Room_Per_Day`, `Projected_Overtime_Cost_INR`, `Buffer_Efficiency_Rate_Pct`

**Center: Waterfall Chart** (X=418, W=400)
- Category: `dim_surgical_specialty[SpecialtyName]`
- Y: `Projected_Overtime_Cost_INR`
- Title: "Overtime Cost by Specialty (Rs)"

**Right: Table** (X=830, W=434)
- Columns: SpecialtyName, Surgeon_Velocity_Index_Avg, Exceeded_P90_Rate_Pct, Total_Overtime_Hours
- Conditional format: Red if Velocity > 1.15, Amber 1.05-1.15
- Title: "Surgeon Velocity Index"

---

## 9. PAGE 2 LAYOUT: PACU & ICU Bottleneck

**Page Name:** `ICU / PACU`
Right-click page tab → Add page → Rename

### ROW 1 — 4 ICU KPI Cards (y=60, h=80)

| Card | Measure | Subtitle |
|---|---|---|
| Peak ICU Bed Demand | `Peak_ICU_Bed_Demand` | "Capacity: 16 beds" |
| ICU Saturation Risk | `ICU_Bed_Saturation_Risk` | `ICU_Saturation_Label` |
| PACU Hold Time | `PACU_Hold_Time_Hours` | `PACU_Hold_Rate_Pct` |
| Total Delay Costs | `Total_Cost_All_Delays_INR` | "OT + PACU + Cancellations" |

### ROW 2 — Area Chart + Scatter (y=152, h=278)

**Left: Area Chart** (X=16, W=620)
- X: `sim_hourly_bed_trace[HourOfDay]`
- Y: `sim_hourly_bed_trace[icu_occupancy]`
- Constant line at 16 (capacity), dashed `#E8EDF5`
- Constant line at 12.8 (80% threshold), dashed `#D97706`
- Title: "Hourly ICU Bed Occupancy vs. Capacity"

**Right: Scatter Chart** (X=648, W=616)
- X: `Avg_ICU_LOS_Hours`
- Y: `Avg_PACU_Duration_min`
- Legend: `dim_surgical_specialty[SpecialtyName]`
- Size: `Total_ICU_Transfers`
- Reference lines: Vertical at X=36, Horizontal at Y=90
- Title: "Patient Risk vs. Recovery Bed Demand"

### ROW 3 — Detail Panels (y=442, h=258)

**Left: Stacked Bar** (X=16, W=400)
- X: `Total_ICU_Transfers`
- Y: `dim_date[Date]`
- Legend: `dim_surgical_specialty[SpecialtyName]`
- Title: "Daily ICU Admissions by Specialty"

**Center: Donut Chart** (X=428, W=400)
- Legend: `dim_patient_risk_tier[RiskTierName]`
- Values: `Total_PACU_Holds`
- Colors: Critical=#DC2626, High=#EA580C, Moderate=#D97706, Low=#059669
- Title: "PACU Holds by Risk Tier"

**Right: Matrix** (X=840, W=424)
- Rows: `dim_surgical_specialty[SpecialtyName]`
- Values: `Projected_Overtime_Cost_INR`, `PACU_Total_Hold_Cost_INR`, `Total_ICU_Bed_Cost_INR`
- Enable row totals + data bars
- Title: "Cost Breakdown by Specialty (Rs)"

---

## 10. THEME & STYLING

### Apply theme
View → Themes → Browse for themes → select `f:\project 3\layer4_powerbi\OR_ScheduleIQ_Theme.json`

### Design Tokens Reference

| Token | Hex | Usage |
|---|---|---|
| BG Primary | `#0B1628` | Page canvas |
| BG Card | `#132035` | Visual card BG |
| BG Card Alt | `#1C2E48` | What-If zone cards |
| Border | `#2D4166` | Card borders |
| Text Primary | `#E8EDF5` | Titles, values |
| Text Secondary | `#8FA3BF` | Labels, subtitles |
| Accent Blue | `#3A86FF` | Primary charts |
| Green | `#059669` | On-track, good |
| Amber | `#D97706` | Buffer breach, warning |
| Red | `#DC2626` | Overtime, critical |
| Purple | `#7C3AED` | Cardiac specialty |

### Fonts
- All text: Segoe UI (built-in to PBI)
- KPI values: Segoe UI Semibold

### Page Navigation
On both pages, insert buttons:
Insert → Buttons → Blank → Action: Page navigation → target page
- Button 1: "P1 - OR Flow"
- Button 2: "P2 - ICU/PACU"
Position: (1140, 14), size 120x24

---

## 11. FINAL CHECKLIST

- [ ] Pipeline ran successfully (`python layer2_python/run_pipeline.py`)
- [ ] All 12 tables loaded (5 dims + 4 facts + 2 sim traces + 1 fit params)
- [ ] Column1 deleted from _Measures
- [ ] Theme JSON applied (dark slate-navy)
- [ ] 7+ star schema relationships created in Model view
- [ ] Both What-If parameters created (Buffer + Cost Rate)
- [ ] All 35+ DAX measures added to _Measures table
- [ ] Page 1 built: 4 KPI cards, heatmap, histogram, What-If zone, waterfall, velocity table
- [ ] Page 2 built: 4 KPI cards, area chart, scatter, stacked bar, donut, cost matrix
- [ ] Conditional formatting applied to all KPI cards
- [ ] Page navigation buttons on both pages
- [ ] Saved as .pbix file
- [ ] Exported to PDF: File → Export → Export to PDF (for portfolio)

---

## KEY CONFIGURATION VALUES

| Setting | Value | Where to change |
|---|---|---|
| Number of OR Theatres | 8 | `layer2_python/config.py` → NUM_OPERATING_THEATRES |
| Simulation Horizon | 30 days | `config.py` → SIM_HORIZON_DAYS |
| PACU Bays | 12 | `config.py` → NUM_PACU_BAYS |
| ICU Beds | 16 | `config.py` → NUM_ICU_BEDS |
| OR Day Hours | 08:00-18:00 (10hr) | `config.py` → OR_START_MIN / OR_END_MIN |
| Turnover Buffer Default | 30 min | `config.py` → TARGET_BUFFER_MIN |
| OT Cost Rate | Rs 2,500/hr | `config.py` → OVERTIME_COST_PER_HOUR_INR |
| ICU Bed Cost | Rs 3,500/hr | `config.py` → ICU_BED_HOLD_COST_PER_HR_INR |
| PACU Hold Cost | Rs 1,800/hr | `config.py` → PACU_HOLD_COST_PER_HR_INR |
| Cancellation Cost | Rs 15,000/case | `config.py` → CANCELLATION_COST_INR |
| Currency | INR (Rs) | All DAX format strings |
| Random Seed | 42 | `config.py` → SIM_RANDOM_SEED |

---

## TROUBLESHOOTING

### "Column not found" in DAX
The CSV columns are snake_case (e.g. `actual_duration_min`). The `dax_measures.md` file uses
PascalCase (e.g. `ActualDuration_min`). Either rename columns in Power Query or use the DAX
in Section 7 of this file (already snake_case).

### Relationships won't create
Check that columns have matching data types. `date_key` in fact tables should be Integer,
matching `DateKey` in dim_date. If one is Text, change type in Power Query.

### What-If slider not affecting measures
Ensure the auto-generated measure `Buffer_Time_Minutes Value` exists and matches the name
used in DAX (e.g. `[Buffer_Time_Minutes Value]`). Same for `OT_CostRate_INR Value`.

### No data showing in visuals
Check Model view — verify relationships exist between fact and dimension tables.
Check that filter direction is "Single" (Dim → Fact).

### Pipeline won't run
```bash
python validate_environment.py    # Check all packages installed
pip install -r requirements.txt   # Install missing packages
```

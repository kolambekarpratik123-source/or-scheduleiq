# OR-ScheduleIQ: Surgical OR Scheduling Decision-Support System

> **Portfolio Project** | End-to-End Healthcare Analytics | Power BI + Python + DuckDB  
> *Principal Healthcare Analytics Engineer — Senior BI Solutions Architect*

---

## Project Overview

A production-grade, four-layer decision-support system that models surgical case duration uncertainty, simulates Operating Room (OR) queue dynamics using Discrete-Event Simulation (DES), and surfaces resource bottlenecks on an executive-grade Power BI dashboard.

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OR-ScheduleIQ Architecture                   │
├─────────────────────┬───────────────────────────────────────────┤
│  LAYER 1            │  SQL Analytics Engine (DuckDB)            │
│  Data Ingestion     │  DDL, staging tables, feature engineering │
├─────────────────────┼───────────────────────────────────────────┤
│  LAYER 2            │  Python Statistical + SimPy DES Engine    │
│  Simulation         │  Log-Normal/Weibull fit, OR queue sim     │
├─────────────────────┼───────────────────────────────────────────┤
│  LAYER 3            │  Kimball Star Schema                      │
│  Data Modeling      │  Fact + Dimension tables for Power BI     │
├─────────────────────┼───────────────────────────────────────────┤
│  LAYER 4            │  Power BI Desktop Dashboard + DAX         │
│  Visualization      │  Executive 2-page flight-deck layout      │
└─────────────────────┴───────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
```bash
pip install duckdb pandas numpy scipy scikit-learn simpy matplotlib seaborn tqdm
```

### Step-by-Step Execution

1. **Data Sourcing** → See `docs/DATA_SOURCING.md`
2. **SQL Pipeline** → Run `layer1_sql/01_ddl_staging.sql` → `02_feature_engineering.sql` → `03_export_csvs.sql`
3. **Python Engine** → Run `layer2_python/run_pipeline.py`
4. **Power BI** → Open `layer4_powerbi/OR_ScheduleIQ.pbip` in Power BI Desktop (Power BI Project format, so the model and report are plain text and diff-able in git).
   - The model reads CSVs through one parameter, `DataFolder` (default `F:\project 3\data\`). After cloning, set it to your own `data\` folder: **Transform data → Edit parameters**, then **Refresh**.
   - The DuckDB file is not committed; `run_pipeline.py` rebuilds it.

---

## Variable Configuration

| Variable | Default | Location |
|---|---|---|
| Number of OR Theatres | 8 | `layer2_python/config.py` |
| Simulation Horizon (days) | 30 | `layer2_python/config.py` |
| Target Specialties | General Surgery, Orthopedics, Cardiac | `layer1_sql/02_feature_engineering.sql` |
| Currency | INR (₹) | `layer4_powerbi/dax_measures.md` |
| DB Engine | DuckDB | `layer1_sql/` |

---

## Folder Structure

```
project-3/
├── README.md
├── docs/
│   ├── DATA_SOURCING.md          # Free dataset instructions
│   └── POWER_BI_COMPLETE_SETUP.md# Full PBI setup reference (start here!)
├── layer1_sql/
│   ├── 01_ddl_staging.sql        # Table creation DDL
│   ├── 02_feature_engineering.sql# Feature tables + baselines
│   └── 03_export_csvs.sql        # Final CSV exports
├── layer2_python/
│   ├── config.py                 # All tunable parameters
│   ├── 01_data_loader.py         # Ingest CSVs into DuckDB
│   ├── 02_distribution_fitter.py # Log-Normal / Weibull fitting
│   ├── 03_simulation_engine.py   # SimPy DES core
│   ├── 04_export_results.py      # Dimension tables + fact enrichment
│   └── run_pipeline.py           # Single-entry orchestrator
├── layer3_schema/
│   └── star_schema_definition.md # Kimball schema + relationships
├── layer4_powerbi/
│   ├── OR_ScheduleIQ.pbip        # Power BI Project (open this)
│   ├── OR_ScheduleIQ.SemanticModel/ # TMDL model: 14 tables, 52 measures
│   ├── OR_ScheduleIQ.Report/     # 2 pages: OR Flow, ICU / PACU
│   ├── OR_ScheduleIQ_Theme.json  # Custom dark healthcare theme
│   ├── dax_measures.md           # All DAX with documentation
│   └── dashboard_layout.md       # Visual layout blueprint
└── data/
    ├── raw/                      # Place downloaded source data here
    ├── processed/                # dim_*.csv, fact_*.csv, fit params
    └── simulated/                # fact_simulated_schedule.csv, traces
```

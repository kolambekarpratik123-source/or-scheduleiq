-- ============================================================
-- OR-ScheduleIQ | Layer 1 | Script 01: DDL Staging Tables
-- Engine: DuckDB (compatible with PostgreSQL with minor syntax edits)
-- Author: OR-ScheduleIQ Pipeline
-- ============================================================
-- Run: python -c "import duckdb; duckdb.connect('data/or_scheduleiq.duckdb').execute(open('layer1_sql/01_ddl_staging.sql').read())"
-- ============================================================

-- ------------------------------------------------------------
-- SECTION 0: Schema Setup
-- ------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS exports;

-- ------------------------------------------------------------
-- SECTION 1: Core Staging Tables
-- ------------------------------------------------------------

-- Drop in child-first order to avoid FK constraint errors
DROP TABLE IF EXISTS staging.icu_stays       CASCADE;
DROP TABLE IF EXISTS staging.surgery_cases   CASCADE;
DROP TABLE IF EXISTS staging.pipeline_log    CASCADE;
DROP TABLE IF EXISTS staging.surgeons        CASCADE;
DROP TABLE IF EXISTS staging.patients        CASCADE;
DROP TABLE IF EXISTS staging.operating_rooms CASCADE;
DROP TABLE IF EXISTS staging.surgeries       CASCADE;

-- 1.1 PATIENTS — demographic and administrative profile
CREATE TABLE staging.patients (
    subject_id          BIGINT PRIMARY KEY,
    gender              VARCHAR(1),             -- 'M' / 'F'
    anchor_age          INTEGER,                -- Age at anchor year (MIMIC-IV style)
    anchor_year         INTEGER,
    dod                 DATE,                   -- Date of death (NULL if alive)
    -- Synthetic / derived fields
    bmi_category        VARCHAR(20),            -- 'Normal','Overweight','Obese'
    smoker_flag         BOOLEAN DEFAULT FALSE,
    diabetic_flag       BOOLEAN DEFAULT FALSE,
    hypertensive_flag   BOOLEAN DEFAULT FALSE,
    cardiac_hx_flag     BOOLEAN DEFAULT FALSE,
    renal_failure_flag  BOOLEAN DEFAULT FALSE,
    malignancy_flag     BOOLEAN DEFAULT FALSE,
    data_source         VARCHAR(50) DEFAULT 'synthetic'
);

-- 1.2 OPERATING ROOMS — physical resource registry
CREATE TABLE staging.operating_rooms (
    room_id             VARCHAR(10) PRIMARY KEY,   -- e.g. 'OR-01' .. 'OR-08'
    room_name           VARCHAR(100),
    specialty_primary   VARCHAR(100),              -- Primary specialty assigned
    specialty_secondary VARCHAR(100),
    floor_level         INTEGER,
    capacity_hours_day  DECIMAL(5,2) DEFAULT 10.0, -- Available hours per day
    anesthesia_machine  BOOLEAN DEFAULT TRUE,
    robot_assisted      BOOLEAN DEFAULT FALSE,
    laminar_flow        BOOLEAN DEFAULT TRUE,
    active_flag         BOOLEAN DEFAULT TRUE
);

-- 1.3 SURGERIES — master procedure reference table
CREATE TABLE staging.surgeries (
    procedure_id        VARCHAR(20) PRIMARY KEY,   -- ICD-10-PCS or local code
    procedure_name      VARCHAR(255),
    procedure_category  VARCHAR(100),              -- 'Laparoscopic','Open','Robotic'
    specialty           VARCHAR(100),              -- 'General Surgery','Orthopedics','Cardiac'
    icd10_code          VARCHAR(10),
    cpt_code            VARCHAR(10),
    -- Duration benchmarks (minutes) from literature
    duration_p10_min    INTEGER,                   -- 10th percentile (optimistic)
    duration_p50_min    INTEGER,                   -- Median
    duration_p90_min    INTEGER,                   -- 90th percentile (pessimistic)
    duration_lognorm_mu DECIMAL(8,4),              -- Fitted log-normal mu
    duration_lognorm_sigma DECIMAL(8,4),           -- Fitted log-normal sigma
    typical_pacu_min    INTEGER DEFAULT 60,        -- Post-anesthesia care unit time
    icu_transfer_prob   DECIMAL(5,4) DEFAULT 0.10, -- Probability of ICU transfer
    complexity_score    INTEGER CHECK (complexity_score BETWEEN 1 AND 5)
);

-- 1.4 SURGERY CASES — individual scheduled/historical case log
CREATE TABLE staging.surgery_cases (
    case_id             BIGINT PRIMARY KEY,
    subject_id          BIGINT REFERENCES staging.patients(subject_id),
    hadm_id             BIGINT,                    -- Hospital admission ID (MIMIC style)
    room_id             VARCHAR(10) REFERENCES staging.operating_rooms(room_id),
    procedure_id        VARCHAR(20) REFERENCES staging.surgeries(procedure_id),
    surgeon_id          VARCHAR(20),               -- De-identified surgeon token
    anesthesiologist_id VARCHAR(20),
    -- Timing (all in minutes from midnight on scheduled_date)
    scheduled_date      DATE,
    scheduled_start_min INTEGER,                   -- Planned start (mins from midnight)
    scheduled_end_min   INTEGER,                   -- Planned end (mins from midnight)
    actual_start_min    INTEGER,                   -- Actual start
    actual_end_min      INTEGER,                   -- Actual end
    -- Derived durations
    scheduled_duration_min INTEGER GENERATED ALWAYS AS (scheduled_end_min - scheduled_start_min) VIRTUAL,
    actual_duration_min    INTEGER GENERATED ALWAYS AS (actual_end_min - actual_start_min) VIRTUAL,
    -- Case metadata
    asa_ps_score        INTEGER CHECK (asa_ps_score BETWEEN 1 AND 5),
    emergency_flag      BOOLEAN DEFAULT FALSE,
    case_status         VARCHAR(20) DEFAULT 'Completed', -- 'Completed','Cancelled','Delayed','Overrun'
    cancellation_reason VARCHAR(255),
    -- Post-operative outcomes
    pacu_start_min      INTEGER,
    pacu_end_min        INTEGER,
    icu_transfer_flag   BOOLEAN DEFAULT FALSE,
    icu_los_hours       DECIMAL(8,2),
    icu_bed_id          VARCHAR(20),
    -- Complications
    complication_flag   BOOLEAN DEFAULT FALSE,
    complication_type   VARCHAR(100),
    readmission_30d_flag BOOLEAN DEFAULT FALSE,
    data_source         VARCHAR(50) DEFAULT 'synthetic'
);

-- 1.5 ICU STAYS — downstream bed demand tracking
CREATE TABLE staging.icu_stays (
    stay_id             BIGINT PRIMARY KEY,
    case_id             BIGINT REFERENCES staging.surgery_cases(case_id),
    subject_id          BIGINT REFERENCES staging.patients(subject_id),
    icu_unit            VARCHAR(50),               -- 'SICU','MICU','CCU','CTICU'
    intime              TIMESTAMP,
    outtime             TIMESTAMP,
    los_hours           DECIMAL(8,2) GENERATED ALWAYS AS (DATEDIFF('hour', intime, outtime)) VIRTUAL,
    first_careunit      VARCHAR(50),
    last_careunit       VARCHAR(50),
    data_source         VARCHAR(50) DEFAULT 'synthetic'
);

-- 1.6 SURGEON REGISTRY — velocity and performance tracking
CREATE TABLE staging.surgeons (
    surgeon_id          VARCHAR(20) PRIMARY KEY,
    specialty           VARCHAR(100),
    seniority_level     VARCHAR(20),  -- 'Consultant','Senior Registrar','Registrar'
    -- Velocity index (will be populated by feature engineering)
    velocity_index      DECIMAL(8,4), -- Ratio: (median_actual / median_scheduled)
    case_volume_ytd     INTEGER,
    avg_overrun_pct     DECIMAL(5,2),
    active_flag         BOOLEAN DEFAULT TRUE
);

-- ------------------------------------------------------------
-- SECTION 2: Audit / Metadata
-- ------------------------------------------------------------
DROP TABLE IF EXISTS staging.pipeline_log;
CREATE TABLE staging.pipeline_log (
    log_id              INTEGER PRIMARY KEY,
    run_timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    script_name         VARCHAR(100),
    rows_inserted       INTEGER,
    rows_updated        INTEGER,
    notes               VARCHAR(500)
);

-- Verification
SELECT 'DDL complete. Tables created:' AS status,
       COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'staging';

-- ============================================================
-- OR-ScheduleIQ | Layer 1 | Script 03: Export Clean CSVs
-- Engine: DuckDB
-- Outputs:
--   data/processed/dim_surgeries_master.csv
--   data/processed/fact_surgery_cases.csv
-- ============================================================

-- ============================================================
-- EXPORT 1: dim_surgeries_master.csv
-- Dimension table: one row per procedure type with statistical profile
-- ============================================================

COPY (
    SELECT
        s.procedure_id,
        s.procedure_name,
        s.specialty,
        s.procedure_category,
        s.icd10_code,
        s.cpt_code,
        s.complexity_score,
        s.typical_pacu_min,
        s.icu_transfer_prob,
        -- Duration benchmarks (raw from reference table)
        s.duration_p10_min     AS ref_p10_min,
        s.duration_p50_min     AS ref_p50_min,
        s.duration_p90_min     AS ref_p90_min,
        -- Statistical estimates from actual data (if available)
        bd.p10_min             AS hist_p10_min,
        bd.median_duration_min AS hist_p50_min,
        bd.p90_min             AS hist_p90_min,
        bd.lognorm_mu          AS hist_lognorm_mu,
        bd.lognorm_sigma       AS hist_lognorm_sigma,
        bd.mean_duration_min   AS hist_mean_min,
        bd.stddev_duration_min AS hist_stddev_min,
        bd.cv_pct              AS duration_cv_pct,
        bd.n_cases             AS historical_case_count,
        bd.overrun_rate_pct,
        bd.duration_risk_tier,
        -- Use historical data when available, fallback to reference
        COALESCE(bd.p10_min, s.duration_p10_min)           AS effective_p10_min,
        COALESCE(bd.median_duration_min, s.duration_p50_min) AS effective_p50_min,
        COALESCE(bd.p90_min, s.duration_p90_min)           AS effective_p90_min,
        COALESCE(bd.lognorm_mu, s.duration_lognorm_mu)     AS effective_lognorm_mu,
        COALESCE(bd.lognorm_sigma, s.duration_lognorm_sigma) AS effective_lognorm_sigma,
        CURRENT_DATE                                        AS exported_date
    FROM staging.surgeries s
    LEFT JOIN analytics.baseline_durations bd ON s.procedure_id = bd.procedure_id
    ORDER BY s.specialty, s.complexity_score DESC, s.procedure_name
)
TO 'data/processed/dim_surgeries_master.csv'
(HEADER TRUE, DELIMITER ',', QUOTE '"', NULLSTR '');

-- ============================================================
-- EXPORT 2: fact_surgery_cases.csv
-- Fact table: one row per surgical case (grain = case_id)
-- ============================================================

COPY (
    SELECT
        -- Keys
        cf.case_id,
        cf.subject_id,
        cf.hadm_id,
        cf.room_id,
        cf.procedure_id,
        cf.surgeon_id,
        -- Date dimension key (YYYYMMDD integer for joining to Dim_Date)
        CAST(STRFTIME(cf.scheduled_date, '%Y%m%d') AS INTEGER) AS date_key,
        cf.scheduled_date,
        -- Time slot keys (30-min buckets: 0-47 for 0:00-23:30)
        (cf.scheduled_start_min / 30)  AS start_timeslot_key,
        (cf.scheduled_end_min / 30)    AS end_timeslot_key,
        -- Timing
        cf.scheduled_start_min,
        cf.scheduled_end_min,
        cf.actual_start_min,
        cf.actual_end_min,
        cf.scheduled_duration_min,
        cf.actual_duration_min,
        cf.duration_min,
        cf.pacu_duration_min,
        cf.icu_los_hours,
        cf.overrun_min,
        -- Case attributes
        cf.asa_ps_score,
        cf.emergency_flag,
        cf.case_status,
        -- Procedure attributes (denormalized for ease)
        cf.procedure_name,
        cf.specialty,
        cf.procedure_category,
        cf.complexity_score,
        -- Benchmark comparison
        cf.proc_p10_min,
        cf.proc_p50_min,
        cf.proc_p90_min,
        cf.proc_lognorm_mu,
        cf.proc_lognorm_sigma,
        cf.duration_risk_tier,
        -- Patient risk
        cf.cci_score,
        cf.avg_asa_score,
        cf.risk_tier,
        cf.predicted_icu_prob,
        -- Surgeon performance
        cf.velocity_index,
        cf.surgeon_overrun_pct,
        cf.surgeon_tier,
        -- Outcome flags
        cf.icu_transfer_flag,
        cf.complication_flag,
        cf.readmission_30d_flag,
        cf.exceeded_p90_flag,
        cf.major_overrun_flag,
        -- Measures
        cf.utilization_fraction,
        -- Date parts
        cf.case_year,
        cf.case_month,
        cf.day_of_week,
        cf.day_name,
        -- PACU hold flag (>90 mins considered a delay)
        CASE WHEN cf.pacu_duration_min > 90 THEN TRUE ELSE FALSE END AS pacu_hold_flag,
        -- Overtime contribution (minutes beyond 10hr/600min day)
        GREATEST(0, cf.actual_end_min - 600) AS overtime_minutes,
        -- Rough INR cost of overtime (₹2,500/hour for OR staff + overhead)
        ROUND(GREATEST(0, cf.actual_end_min - 600) / 60.0 * 2500, 0) AS overtime_cost_inr,
        cf.data_source,
        CURRENT_TIMESTAMP AS exported_at
    FROM analytics.case_features cf
    ORDER BY cf.scheduled_date, cf.room_id, cf.scheduled_start_min
)
TO 'data/processed/fact_surgery_cases.csv'
(HEADER TRUE, DELIMITER ',', QUOTE '"', NULLSTR '');

-- ============================================================
-- Validation Report
-- ============================================================

SELECT '=== EXPORT VALIDATION ===' AS report;

SELECT
    'dim_surgeries_master.csv' AS export_file,
    COUNT(DISTINCT procedure_id) AS distinct_procedures,
    COUNT(DISTINCT specialty) AS distinct_specialties
FROM staging.surgeries;

SELECT
    'fact_surgery_cases.csv'     AS export_file,
    COUNT(*)                      AS total_cases,
    COUNT(DISTINCT room_id)       AS rooms_used,
    COUNT(DISTINCT surgeon_id)    AS surgeons,
    COUNT(DISTINCT scheduled_date) AS distinct_days,
    SUM(CAST(emergency_flag AS INTEGER)) AS emergency_cases,
    SUM(CAST(icu_transfer_flag AS INTEGER)) AS icu_transfers,
    ROUND(AVG(duration_min), 1)   AS avg_duration_min,
    SUM(GREATEST(0, actual_end_min - 600)) AS total_overtime_min
FROM analytics.case_features;

INSERT INTO staging.pipeline_log (log_id, script_name, rows_inserted, notes)
SELECT
    3,
    '03_export_csvs.sql',
    (SELECT COUNT(*) FROM analytics.case_features),
    'Exported: dim_surgeries_master.csv and fact_surgery_cases.csv';

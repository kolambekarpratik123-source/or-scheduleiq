-- ============================================================
-- OR-ScheduleIQ | Layer 1 | Script 02: Feature Engineering
-- Engine: DuckDB
-- Produces: analytics.baseline_durations, analytics.patient_risk,
--           analytics.surgeon_velocity, analytics.case_features
-- ============================================================

-- ============================================================
-- SECTION A: Procedure Duration Baselines (per specialty + procedure)
-- ============================================================

DROP TABLE IF EXISTS analytics.baseline_durations;
CREATE TABLE analytics.baseline_durations AS

WITH raw_durations AS (
    SELECT
        sc.procedure_id,
        s.procedure_name,
        s.specialty,
        s.procedure_category,
        -- Use actual duration where available, fall back to scheduled
        COALESCE(sc.actual_duration_min, sc.scheduled_duration_min) AS duration_min,
        sc.emergency_flag,
        sc.asa_ps_score,
        sc.scheduled_date,
        YEAR(sc.scheduled_date)  AS case_year,
        EXTRACT(DOW FROM sc.scheduled_date) AS day_of_week  -- 0=Sun, 1=Mon...
    FROM staging.surgery_cases sc
    JOIN staging.surgeries s ON sc.procedure_id = s.procedure_id
    WHERE sc.case_status = 'Completed'
      AND COALESCE(sc.actual_duration_min, sc.scheduled_duration_min) BETWEEN 15 AND 600
),

elective_only AS (
    SELECT * FROM raw_durations WHERE emergency_flag = FALSE
),

-- Step 1: compute all percentile/aggregate stats (no nesting)
stats_by_procedure_base AS (
    SELECT
        procedure_id,
        procedure_name,
        specialty,
        procedure_category,
        COUNT(*)                        AS n_cases,
        ROUND(AVG(duration_min), 1)     AS mean_duration_min,
        ROUND(STDDEV(duration_min), 1)  AS stddev_duration_min,
        ROUND(MEDIAN(duration_min), 1)  AS median_duration_min,
        ROUND(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY duration_min), 1) AS p10_min,
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_min), 1) AS p25_min,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_min), 1) AS p75_min,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_min), 1) AS p90_min,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_min), 1) AS p95_min,
        ROUND(AVG(LN(duration_min)), 4)      AS lognorm_mu,
        ROUND(STDDEV(LN(duration_min)), 4)   AS lognorm_sigma,
        ROUND(STDDEV(duration_min) / NULLIF(AVG(duration_min), 0) * 100, 2) AS cv_pct
    FROM elective_only
    GROUP BY procedure_id, procedure_name, specialty, procedure_category
    HAVING COUNT(*) >= 5
),

-- Step 2: compute overrun rate by joining pre-computed p75 threshold back to raw rows
stats_by_procedure AS (
    SELECT
        b.*,
        ROUND(
            SUM(CASE WHEN e.duration_min > b.p75_min THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 2
        ) AS overrun_rate_pct
    FROM stats_by_procedure_base b
    JOIN elective_only e
      ON  e.procedure_id       = b.procedure_id
      AND e.procedure_name     = b.procedure_name
      AND e.specialty          = b.specialty
      AND e.procedure_category = b.procedure_category
    GROUP BY
        b.procedure_id, b.procedure_name, b.specialty, b.procedure_category,
        b.n_cases, b.mean_duration_min, b.stddev_duration_min, b.median_duration_min,
        b.p10_min, b.p25_min, b.p75_min, b.p90_min, b.p95_min,
        b.lognorm_mu, b.lognorm_sigma, b.cv_pct
),

-- Add specialty-level aggregates for procedures with thin samples
specialty_fallback AS (
    SELECT
        'SPECIALTY_AGGREGATE'           AS procedure_id,
        specialty || ' (Aggregate)'    AS procedure_name,
        specialty,
        'Aggregate'                    AS procedure_category,
        COUNT(*)                       AS n_cases,
        ROUND(AVG(duration_min), 1)    AS mean_duration_min,
        ROUND(STDDEV(duration_min), 1) AS stddev_duration_min,
        ROUND(MEDIAN(duration_min), 1) AS median_duration_min,
        ROUND(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY duration_min), 1) AS p10_min,
        ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY duration_min), 1) AS p25_min,
        ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY duration_min), 1) AS p75_min,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_min), 1) AS p90_min,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_min), 1) AS p95_min,
        ROUND(AVG(LN(duration_min)), 4)    AS lognorm_mu,
        ROUND(STDDEV(LN(duration_min)), 4) AS lognorm_sigma,
        ROUND(STDDEV(duration_min) / NULLIF(AVG(duration_min), 0) * 100, 2) AS cv_pct,
        25.00                              AS overrun_rate_pct
    FROM elective_only
    GROUP BY specialty
)

SELECT
    *,
    -- Risk tier based on CV
    CASE
        WHEN cv_pct < 20 THEN 'Low'
        WHEN cv_pct BETWEEN 20 AND 35 THEN 'Medium'
        ELSE 'High'
    END AS duration_risk_tier,
    CURRENT_TIMESTAMP AS calculated_at
FROM stats_by_procedure

UNION ALL

SELECT *, 'Medium' AS duration_risk_tier, CURRENT_TIMESTAMP AS calculated_at
FROM specialty_fallback;

-- ============================================================
-- SECTION B: Patient Risk Score (Charlson Comorbidity Index Proxy)
-- ============================================================

DROP TABLE IF EXISTS analytics.patient_risk;
CREATE TABLE analytics.patient_risk AS

WITH charlson_components AS (
    SELECT
        p.subject_id,
        p.anchor_age,
        p.gender,
        -- Charlson weights (simplified — full ICD mapping done in Python if MIMIC)
        CAST(p.diabetic_flag AS INTEGER) * 1          AS w_diabetes,
        CAST(p.cardiac_hx_flag AS INTEGER) * 1        AS w_cardiac,
        CAST(p.hypertensive_flag AS INTEGER) * 1      AS w_hypertension,
        CAST(p.renal_failure_flag AS INTEGER) * 2     AS w_renal,
        CAST(p.malignancy_flag AS INTEGER) * 2        AS w_malignancy,
        CAST(p.smoker_flag AS INTEGER) * 1            AS w_smoker,
        -- Age contribution (Charlson age score)
        CASE
            WHEN p.anchor_age < 50 THEN 0
            WHEN p.anchor_age BETWEEN 50 AND 59 THEN 1
            WHEN p.anchor_age BETWEEN 60 AND 69 THEN 2
            WHEN p.anchor_age BETWEEN 70 AND 79 THEN 3
            ELSE 4
        END AS w_age
    FROM staging.patients p
),

cci_totals AS (
    SELECT
        subject_id,
        anchor_age,
        gender,
        (w_diabetes + w_cardiac + w_hypertension + w_renal + w_malignancy + w_smoker + w_age) AS cci_score,
        w_diabetes, w_cardiac, w_hypertension, w_renal, w_malignancy, w_smoker, w_age
    FROM charlson_components
),

-- Average ASA score for each patient (from their case history)
asa_agg AS (
    SELECT
        subject_id,
        ROUND(AVG(asa_ps_score), 1) AS avg_asa_score,
        MAX(asa_ps_score)           AS max_asa_score
    FROM staging.surgery_cases
    WHERE asa_ps_score IS NOT NULL
    GROUP BY subject_id
)

SELECT
    c.subject_id,
    c.anchor_age,
    c.gender,
    c.cci_score,
    COALESCE(a.avg_asa_score, 2.0) AS avg_asa_score,
    COALESCE(a.max_asa_score, 2)   AS max_asa_score,
    -- Composite risk tier (portfolio-grade blended score)
    CASE
        WHEN c.cci_score >= 5 OR COALESCE(a.max_asa_score, 2) >= 4 THEN 'Critical'
        WHEN c.cci_score BETWEEN 3 AND 4 OR COALESCE(a.max_asa_score, 2) = 3 THEN 'High'
        WHEN c.cci_score BETWEEN 1 AND 2 THEN 'Moderate'
        ELSE 'Low'
    END AS risk_tier,
    -- Predicted ICU probability (logistic regression proxy formula from literature)
    ROUND(
        1.0 / (1.0 + EXP(-(
            -3.2
            + 0.4 * c.cci_score
            + 0.6 * COALESCE(a.max_asa_score, 2)
            + 0.02 * c.anchor_age
        ))), 4
    ) AS predicted_icu_prob,
    c.w_diabetes, c.w_cardiac, c.w_hypertension, c.w_renal, c.w_malignancy, c.w_smoker
FROM cci_totals c
LEFT JOIN asa_agg a ON c.subject_id = a.subject_id;

-- ============================================================
-- SECTION C: Surgeon Velocity Index
-- ============================================================

DROP TABLE IF EXISTS analytics.surgeon_velocity;
CREATE TABLE analytics.surgeon_velocity AS

WITH surgeon_case_stats AS (
    SELECT
        sc.surgeon_id,
        s.specialty,
        COUNT(*)                                            AS total_cases,
        ROUND(AVG(sc.actual_duration_min), 1)              AS avg_actual_min,
        ROUND(AVG(sc.scheduled_duration_min), 1)           AS avg_scheduled_min,
        ROUND(STDDEV(sc.actual_duration_min), 1)           AS stddev_actual_min,
        ROUND(MEDIAN(sc.actual_duration_min), 1)           AS median_actual_min,
        ROUND(MEDIAN(sc.scheduled_duration_min), 1)        AS median_scheduled_min,
        -- Overrun cases
        SUM(CASE WHEN sc.actual_duration_min > sc.scheduled_duration_min THEN 1 ELSE 0 END) AS overrun_count,
        -- On-time start
        SUM(CASE WHEN sc.actual_start_min <= sc.scheduled_start_min + 10 THEN 1 ELSE 0 END) AS on_time_start_count,
        -- Emergency case mix
        ROUND(AVG(CAST(sc.emergency_flag AS INTEGER)) * 100, 1) AS emergency_pct,
        -- ICU transfer rate
        ROUND(AVG(CAST(sc.icu_transfer_flag AS INTEGER)) * 100, 1) AS icu_transfer_pct
    FROM staging.surgery_cases sc
    JOIN staging.surgeries s ON sc.procedure_id = s.procedure_id
    WHERE sc.case_status = 'Completed'
      AND sc.actual_duration_min IS NOT NULL
      AND sc.scheduled_duration_min IS NOT NULL
    GROUP BY sc.surgeon_id, s.specialty
    HAVING COUNT(*) >= 3
)

SELECT
    surgeon_id,
    specialty,
    total_cases,
    avg_actual_min,
    avg_scheduled_min,
    stddev_actual_min,
    median_actual_min,
    median_scheduled_min,
    overrun_count,
    on_time_start_count,
    emergency_pct,
    icu_transfer_pct,
    -- VELOCITY INDEX: ratio of median actual to median scheduled duration
    -- <1.0 = faster than scheduled (efficient), >1.0 = slower (risk factor)
    ROUND(NULLIF(median_actual_min, 0) / NULLIF(median_scheduled_min, 1), 4) AS velocity_index,
    -- OVERRUN RATE
    ROUND(overrun_count * 100.0 / total_cases, 2) AS overrun_rate_pct,
    -- ON-TIME START RATE
    ROUND(on_time_start_count * 100.0 / total_cases, 2) AS on_time_start_pct,
    -- Performance tier
    CASE
        WHEN ROUND(median_actual_min / NULLIF(median_scheduled_min, 1), 4) <= 0.95
             AND ROUND(overrun_count * 100.0 / total_cases, 2) < 20 THEN 'Elite'
        WHEN ROUND(median_actual_min / NULLIF(median_scheduled_min, 1), 4) <= 1.05
             AND ROUND(overrun_count * 100.0 / total_cases, 2) < 35 THEN 'Proficient'
        WHEN ROUND(median_actual_min / NULLIF(median_scheduled_min, 1), 4) <= 1.15 THEN 'Average'
        ELSE 'Needs Review'
    END AS performance_tier,
    CURRENT_TIMESTAMP AS calculated_at
FROM surgeon_case_stats;

-- ============================================================
-- SECTION D: Enriched Case Feature Table (joins all above)
-- ============================================================

DROP TABLE IF EXISTS analytics.case_features;
CREATE TABLE analytics.case_features AS

SELECT
    sc.case_id,
    sc.subject_id,
    sc.hadm_id,
    sc.room_id,
    sc.procedure_id,
    sc.surgeon_id,
    sc.scheduled_date,
    -- Timing
    sc.scheduled_start_min,
    sc.scheduled_end_min,
    sc.actual_start_min,
    sc.actual_end_min,
    COALESCE(sc.actual_duration_min, sc.scheduled_duration_min) AS duration_min,
    sc.scheduled_duration_min,
    sc.actual_duration_min,
    -- Case metadata
    sc.asa_ps_score,
    sc.emergency_flag,
    sc.case_status,
    -- PACU
    sc.pacu_start_min,
    sc.pacu_end_min,
    (sc.pacu_end_min - sc.pacu_start_min) AS pacu_duration_min,
    sc.icu_transfer_flag,
    sc.icu_los_hours,
    sc.complication_flag,
    sc.complication_type,
    sc.readmission_30d_flag,
    -- Procedure enrichment
    s.procedure_name,
    s.specialty,
    s.procedure_category,
    s.complexity_score,
    -- Duration benchmarks
    bd.p10_min        AS proc_p10_min,
    bd.median_duration_min AS proc_p50_min,      -- alias median
    bd.p90_min        AS proc_p90_min,
    bd.lognorm_mu     AS proc_lognorm_mu,
    bd.lognorm_sigma  AS proc_lognorm_sigma,
    bd.duration_risk_tier,
    -- Patient risk
    pr.cci_score,
    pr.avg_asa_score,
    pr.risk_tier,
    pr.predicted_icu_prob,
    -- Surgeon velocity
    sv.velocity_index,
    sv.overrun_rate_pct AS surgeon_overrun_pct,
    sv.performance_tier AS surgeon_tier,
    -- Computed flags
    CASE WHEN sc.actual_duration_min > bd.p90_min THEN TRUE ELSE FALSE END AS exceeded_p90_flag,
    CASE WHEN sc.actual_duration_min > sc.scheduled_duration_min * 1.20 THEN TRUE ELSE FALSE END AS major_overrun_flag,
    -- Overrun minutes (negative = under-run)
    COALESCE(sc.actual_duration_min, sc.scheduled_duration_min) - sc.scheduled_duration_min AS overrun_min,
    -- Room utilization contribution (fraction of 10hr day = 600 min)
    ROUND(COALESCE(sc.actual_duration_min, sc.scheduled_duration_min) / 600.0, 4) AS utilization_fraction,
    -- Date parts for slicing
    YEAR(sc.scheduled_date)                 AS case_year,
    MONTH(sc.scheduled_date)                AS case_month,
    DAYOFWEEK(sc.scheduled_date)            AS day_of_week,
    STRFTIME(sc.scheduled_date, '%A')       AS day_name,
    sc.data_source
FROM staging.surgery_cases sc
JOIN staging.surgeries s       ON sc.procedure_id = s.procedure_id
LEFT JOIN analytics.baseline_durations bd ON sc.procedure_id = bd.procedure_id
LEFT JOIN analytics.patient_risk pr        ON sc.subject_id = pr.subject_id
LEFT JOIN analytics.surgeon_velocity sv    ON sc.surgeon_id = sv.surgeon_id AND s.specialty = sv.specialty;

-- Log completion
INSERT INTO staging.pipeline_log (log_id, script_name, rows_inserted, notes)
SELECT
    2,
    '02_feature_engineering.sql',
    (SELECT COUNT(*) FROM analytics.case_features),
    'Feature tables built: baseline_durations, patient_risk, surgeon_velocity, case_features';

SELECT 'Feature engineering complete.' AS status,
       (SELECT COUNT(*) FROM analytics.baseline_durations) AS baseline_rows,
       (SELECT COUNT(*) FROM analytics.patient_risk)        AS patient_risk_rows,
       (SELECT COUNT(*) FROM analytics.surgeon_velocity)    AS surgeon_velocity_rows,
       (SELECT COUNT(*) FROM analytics.case_features)       AS case_features_rows;

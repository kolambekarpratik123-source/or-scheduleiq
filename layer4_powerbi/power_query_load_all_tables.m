// ===================================================================
// OR-ScheduleIQ | Paste this ONCE into Power Query Advanced Editor
// ===================================================================
// HOW TO USE:
//   1. In Power BI Desktop: Home → Transform Data (opens Power Query)
//   2. Home → New Source → Blank Query
//   3. Right-click the new query → Advanced Editor
//   4. DELETE everything in the editor
//   5. PASTE this entire script
//   6. Click Done
//   7. Repeat steps 2-6 for EACH section below (one query per table)
//   8. Click "Close & Apply" when done
// ===================================================================

// ─── QUERY 1: Fact_Surgical_Schedule ─────────────────────────────
// Name this query: Fact_Surgical_Schedule
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\simulated\fact_simulated_schedule.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"case_id", Int64.Type},
        {"room_id", type text},
        {"procedure_name", type text},
        {"specialty", type text},
        {"asa_score", Int64.Type},
        {"risk_tier", type text},
        {"emergency_flag", type logical},
        {"case_status", type text},
        {"scheduled_date", type date},
        {"scheduled_duration_min", type number},
        {"actual_duration_min", type number},
        {"overrun_min", type number},
        {"turnover_min", type number},
        {"pacu_duration_min", type number},
        {"pacu_hold_flag", type logical},
        {"icu_transfer_flag", type logical},
        {"icu_los_hours", type number},
        {"overtime_cost_inr", type number},
        {"pacu_hold_cost_inr", type number},
        {"date_key", Int64.Type},
        {"day_name", type text},
        {"OT_Cost_INR", type number},
        {"PACU_HoldCost_INR", type number},
        {"ICU_Cost_INR", type number}
    })
in
    Typed


// ─── QUERY 2: dim_date ──────────────────────────────────────────
// Name this query: dim_date
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\dim_date.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"DateKey", Int64.Type},
        {"Date", type date},
        {"Year", Int64.Type},
        {"Quarter", Int64.Type},
        {"Month", Int64.Type},
        {"MonthName", type text},
        {"Week", Int64.Type},
        {"DayOfWeek", Int64.Type},
        {"DayName", type text},
        {"IsWeekend", type logical},
        {"IsORDay", type logical},
        {"FiscalYear", Int64.Type},
        {"FiscalQuarter", Int64.Type}
    })
in
    Typed


// ─── QUERY 3: dim_operating_room ────────────────────────────────
// Name this query: dim_operating_room
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\dim_operating_room.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"RoomID", type text},
        {"RoomName", type text},
        {"PrimarySpecialty", type text},
        {"RobotAssisted", type logical},
        {"CapacityHours", Int64.Type},
        {"FloorLevel", Int64.Type},
        {"ActiveFlag", type logical}
    })
in
    Typed


// ─── QUERY 4: dim_surgical_specialty ────────────────────────────
// Name this query: dim_surgical_specialty
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\dim_surgical_specialty.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"SpecialtyKey", Int64.Type},
        {"SpecialtyName", type text},
        {"Division", type text},
        {"AvgComplexity", type number},
        {"TypicalICURate", type number}
    })
in
    Typed


// ─── QUERY 5: dim_patient_risk_tier ─────────────────────────────
// Name this query: dim_patient_risk_tier
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\dim_patient_risk_tier.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"RiskTierKey", Int64.Type},
        {"RiskTierName", type text},
        {"CCIRange", type text},
        {"ASARange", type text},
        {"ICUProbabilityBand", type text}
    })
in
    Typed


// ─── QUERY 6: dim_time_slot ─────────────────────────────────────
// Name this query: dim_time_slot
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\dim_time_slot.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"TimeSlotKey", Int64.Type},
        {"TimeLabel", type text},
        {"HourOfDay", Int64.Type},
        {"MinuteOfHour", Int64.Type},
        {"TimePeriod", type text},
        {"IsORHour", type logical}
    })
in
    Typed


// ─── QUERY 7: fact_historical_cases ─────────────────────────────
// Name this query: fact_historical_cases
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\processed\fact_historical_cases.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"case_id", Int64.Type},
        {"date_key", Int64.Type},
        {"room_id", type text},
        {"specialty", type text},
        {"risk_tier", type text},
        {"scheduled_duration_min", type number},
        {"actual_duration_min", type number},
        {"overrun_min", type number},
        {"icu_transfer_flag", type logical},
        {"velocity_index", type number},
        {"cci_score", type number},
        {"exceeded_p90_flag", type logical},
        {"VelocityIndex", type number},
        {"ExceededP90_Flag", type logical},
        {"CCI_Score", type number}
    })
in
    Typed


// ─── QUERY 8: sim_hourly_bed_trace ──────────────────────────────
// Name this query: sim_hourly_bed_trace
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\simulated\sim_hourly_bed_trace.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Promoted


// ─── QUERY 9: sim_daily_metrics ─────────────────────────────────
// Name this query: sim_daily_metrics
let
    Source = Csv.Document(
        File.Contents("F:\project 3\data\simulated\sim_daily_metrics.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Promoted

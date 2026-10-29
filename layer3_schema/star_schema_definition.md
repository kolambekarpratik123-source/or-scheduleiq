# OR-ScheduleIQ | Layer 3 | Kimball Star Schema Definition
## Power BI Data Model — Relationship Map & Grain Documentation

> **Pattern:** Kimball Dimensional Model (Star Schema)  
> **Tool:** Power BI Desktop (Import mode, DirectQuery disabled for performance)  
> **Refresh:** Manual / Scheduled (can be moved to Power BI Service with gateway)

---

## Schema Diagram

```
                          ┌──────────────────────┐
                          │     Dim_Date          │
                          │  ─────────────────    │
                          │  DateKey (PK)         │
                          │  Date                 │
                          │  Year, Month, Quarter │
                          │  DayOfWeek, IsWeekend │
                          │  MonthName, DayName   │
                          └──────────┬───────────┘
                                     │ 1:*
        ┌────────────────────────────┼─────────────────────────────┐
        │                            │                             │
        ▼                            ▼                             ▼
┌──────────────────┐   ┌──────────────────────────┐   ┌──────────────────────┐
│  Dim_Time_Slot   │   │  Fact_Surgical_Schedule   │   │  Fact_Historical     │
│ ──────────────   │   │  ──────────────────────   │   │  Cases               │
│ TimeSlotKey (PK) │   │  CaseID (PK)              │   │  ──────────────────  │
│ TimeLabel        │◄──│  DateKey (FK)             │──►│  CaseID (PK)         │
│ HourOfDay        │1:*│  StartTimeSlotKey (FK)    │   │  DateKey (FK)        │
│ TimePeriod       │   │  RoomID (FK)              │   │  RoomID (FK)         │
└──────────────────┘   │  SpecialtyKey (FK)        │   │  SpecialtyKey (FK)   │
                        │  RiskTierKey (FK)         │   │  RiskTierKey (FK)    │
┌──────────────────┐   │  ─────────────────────    │   │  ──────────────────  │
│  Dim_Operating   │   │  [MEASURES — see below]   │   │  [MEASURES]          │
│  Room            │   └──────────────────────────┘   └──────────────────────┘
│ ──────────────── │              │ *                             │ *
│ RoomID (PK)      │◄─────────────┘                              │
│ RoomName         │                                             │
│ Specialty        │   ┌──────────────────────┐                 │
│ RobotAssisted    │   │  Dim_Surgical         │◄────────────────┘
│ FloorLevel       │   │  Specialty            │ 1:*
│ CapacityHours    │   │ ──────────────────── │
└──────────────────┘   │  SpecialtyKey (PK)    │
                        │  SpecialtyName        │
┌──────────────────┐    │  Division             │
│  Dim_Patient     │    │  AvgComplexity        │
│  Risk_Tier       │    │  TypicalICURate       │
│ ──────────────── │    └──────────────────────┘
│ RiskTierKey (PK) │◄────────────────────────────
│ RiskTierName     │ 1:*
│ CCIRange         │
│ ASARange         │
│ ICUProbabilityBand│
└──────────────────┘
```

---

## Table Definitions

### FACT TABLES

#### `Fact_Surgical_Schedule` (Grain: 1 row = 1 simulated surgical case)
| Column | Type | Description |
|---|---|---|
| `CaseID` | Integer (PK) | Unique simulation case identifier |
| `DateKey` | Integer (FK → Dim_Date) | YYYYMMDD format |
| `StartTimeSlotKey` | Integer (FK → Dim_Time_Slot) | 30-min bucket index |
| `EndTimeSlotKey` | Integer (FK → Dim_Time_Slot) | 30-min bucket index |
| `RoomID` | Text (FK → Dim_Operating_Room) | e.g. "OR-01" |
| `SpecialtyKey` | Integer (FK → Dim_Surgical_Specialty) | |
| `RiskTierKey` | Integer (FK → Dim_Patient_Risk_Tier) | |
| `ProcedureName` | Text | Full procedure name |
| `ScheduledDuration_min` | Decimal | Planned case time |
| `ActualDuration_min` | Decimal | Simulated actual time |
| `OverrunMin` | Decimal | Minutes beyond scheduled (0 if under) |
| `TurnoverMin` | Decimal | Room cleaning/turnover time |
| `PACU_Duration_min` | Decimal | Post-anesthesia care time |
| `ICU_Transfer_Flag` | Boolean | TRUE = ICU required |
| `ICU_LOS_Hours` | Decimal | ICU length of stay |
| `PACU_Hold_Flag` | Boolean | TRUE = PACU >90 min |
| `EmergencyFlag` | Boolean | TRUE = emergency case |
| `ASA_Score` | Integer | ASA physical status (1–5) |
| `CaseStatus` | Text | Completed / Delayed / Overrun / Cancelled |
| `OvertimeCost_INR` | Decimal | Computed cost in ₹ |
| `PACU_HoldCost_INR` | Decimal | Delayed PACU bay cost in ₹ |
| `Utilization_Fraction` | Decimal | Case share of 10hr day |
| `DayName` | Text | Monday–Saturday |

#### `Fact_Historical_Cases` (Grain: 1 row = 1 historical surgical case)
| Column | Type | Description |
|---|---|---|
| `CaseID` | Integer (PK) | |
| `DateKey` | Integer (FK → Dim_Date) | |
| `RoomID` | Text (FK) | |
| `SpecialtyKey` | Integer (FK) | |
| `RiskTierKey` | Integer (FK) | |
| `ScheduledDuration_min` | Decimal | |
| `ActualDuration_min` | Decimal | |
| `OverrunMin` | Decimal | |
| `ICU_Transfer_Flag` | Boolean | |
| `Complication_Flag` | Boolean | |
| `VelocityIndex` | Decimal | Surgeon velocity (1.0 = on-time) |
| `CCI_Score` | Integer | Charlson Comorbidity Index |
| `PredictedICU_Prob` | Decimal | Model-predicted ICU probability |
| `DurationRiskTier` | Text | Low / Medium / High |
| `ExceededP90_Flag` | Boolean | |
| `OvertimeCost_INR` | Decimal | |

---

### DIMENSION TABLES

#### `Dim_Date` (Standard Date Spine — generated in Power Query)
| Column | Type | Notes |
|---|---|---|
| `DateKey` | Integer (PK) | YYYYMMDD |
| `Date` | Date | |
| `Year` | Integer | |
| `Quarter` | Integer | 1–4 |
| `Month` | Integer | 1–12 |
| `MonthName` | Text | "January"…"December" |
| `Week` | Integer | ISO week number |
| `DayOfWeek` | Integer | 1=Mon, 7=Sun |
| `DayName` | Text | "Monday"…"Sunday" |
| `IsWeekend` | Boolean | |
| `IsHoliday` | Boolean | (manual flag) |
| `FiscalYear` | Integer | April–March (Indian FY) |
| `FiscalQuarter` | Integer | |

#### `Dim_Time_Slot` (30-minute time buckets)
| Column | Type | Notes |
|---|---|---|
| `TimeSlotKey` | Integer (PK) | 0–47 (48 × 30-min slots/day) |
| `TimeLabel` | Text | "08:00", "08:30"… |
| `HourOfDay` | Integer | 0–23 |
| `MinuteOfHour` | Integer | 0 or 30 |
| `OR_Session` | Text | "Morning" (06–12), "Afternoon" (12–18), "Evening" (18–24) |
| `IsORHours` | Boolean | TRUE if 08:00–18:00 |

#### `Dim_Operating_Room`
| Column | Type | Notes |
|---|---|---|
| `RoomID` | Text (PK) | "OR-01"…"OR-08" |
| `RoomName` | Text | "Theatre 1"… |
| `SpecialtyPrimary` | Text | "General Surgery" / "Orthopedics" / "Cardiac" |
| `RobotAssisted` | Boolean | |
| `FloorLevel` | Integer | |
| `CapacityHoursDay` | Decimal | 10.0 |
| `AnnualCapacity_hours` | Integer | (calculated) |

#### `Dim_Surgical_Specialty`
| Column | Type | Notes |
|---|---|---|
| `SpecialtyKey` | Integer (PK) | 1=General, 2=Ortho, 3=Cardiac |
| `SpecialtyName` | Text | |
| `Division` | Text | "Surgical" / "Cardiac-Thoracic" |
| `AvgComplexityScore` | Decimal | |
| `TypicalICUTransferRate_pct` | Decimal | |
| `TypicalDuration_min` | Integer | Specialty P50 benchmark |

#### `Dim_Patient_Risk_Tier`
| Column | Type | Notes |
|---|---|---|
| `RiskTierKey` | Integer (PK) | 1=Low, 2=Moderate, 3=High, 4=Critical |
| `RiskTierName` | Text | |
| `CCI_RangeLow` | Integer | Charlson score lower bound |
| `CCI_RangeHigh` | Integer | Charlson score upper bound |
| `ASA_Typical` | Text | "ASA I–II" / "ASA III" / "ASA IV–V" |
| `ICU_ProbabilityBand` | Text | "<10%" / "10–30%" / "30–60%" / ">60%" |
| `ColorCode` | Text | Hex color for conditional formatting |

---

## Relationships (Power BI Desktop → Model View)

| From Table | From Column | To Table | To Column | Cardinality | Direction | Active |
|---|---|---|---|---|---|---|
| `Fact_Surgical_Schedule` | `DateKey` | `Dim_Date` | `DateKey` | Many-to-1 (`*:1`) | Single (→ Dim) | ✅ Active |
| `Fact_Surgical_Schedule` | `StartTimeSlotKey` | `Dim_Time_Slot` | `TimeSlotKey` | `*:1` | Single | ✅ Active |
| `Fact_Surgical_Schedule` | `RoomID` | `Dim_Operating_Room` | `RoomID` | `*:1` | Single | ✅ Active |
| `Fact_Surgical_Schedule` | `SpecialtyKey` | `Dim_Surgical_Specialty` | `SpecialtyKey` | `*:1` | Single | ✅ Active |
| `Fact_Surgical_Schedule` | `RiskTierKey` | `Dim_Patient_Risk_Tier` | `RiskTierKey` | `*:1` | Single | ✅ Active |
| `Fact_Historical_Cases` | `DateKey` | `Dim_Date` | `DateKey` | `*:1` | Single | ✅ Active |
| `Fact_Historical_Cases` | `RoomID` | `Dim_Operating_Room` | `RoomID` | `*:1` | Single | ✅ Active |
| `Fact_Historical_Cases` | `SpecialtyKey` | `Dim_Surgical_Specialty` | `SpecialtyKey` | `*:1` | Single | ✅ Active |
| `Fact_Historical_Cases` | `RiskTierKey` | `Dim_Patient_Risk_Tier` | `RiskTierKey` | `*:1` | Single | ✅ Active |
| `Fact_Surgical_Schedule` | `EndTimeSlotKey` | `Dim_Time_Slot` | `TimeSlotKey` | `*:1` | Single | ❌ Inactive (use USERELATIONSHIP in DAX) |

> **Note on cross-filter direction:** All relationships use **single direction** (Dim → Fact filtering). Bi-directional filtering is avoided to prevent ambiguous filter paths and performance degradation.

---

## Power Query M — Dim_Date Generation

```m
let
    StartDate   = #date(2024, 1, 1),
    EndDate     = #date(2024, 12, 31),
    DateList    = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1,0,0,0)),
    AsTable     = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}),
    TypeDate    = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    AddDateKey  = Table.AddColumn(TypeDate, "DateKey", each
                    Date.Year([Date])*10000 + Date.Month([Date])*100 + Date.Day([Date]),
                    type number),
    AddYear     = Table.AddColumn(AddDateKey, "Year", each Date.Year([Date]), type number),
    AddQuarter  = Table.AddColumn(AddYear, "Quarter", each Date.QuarterOfYear([Date]), type number),
    AddMonth    = Table.AddColumn(AddQuarter, "Month", each Date.Month([Date]), type number),
    AddMonthName= Table.AddColumn(AddMonth, "MonthName", each Date.MonthName([Date]), type text),
    AddWeek     = Table.AddColumn(AddMonthName, "Week", each Date.WeekOfYear([Date]), type number),
    AddDOW      = Table.AddColumn(AddWeek, "DayOfWeek", each Date.DayOfWeek([Date], Day.Monday) + 1, type number),
    AddDayName  = Table.AddColumn(AddDOW, "DayName", each Date.DayOfWeekName([Date]), type text),
    AddIsWeekend= Table.AddColumn(AddDayName, "IsWeekend",
                    each Date.DayOfWeek([Date], Day.Monday) >= 5, type logical),
    AddFY       = Table.AddColumn(AddIsWeekend, "FiscalYear",
                    each if Date.Month([Date]) >= 4 then Date.Year([Date])
                         else Date.Year([Date]) - 1, type number),
    AddFQ       = Table.AddColumn(AddFY, "FiscalQuarter",
                    each let m = Date.Month([Date]),
                         q = if m >= 4 and m <= 6 then 1
                             else if m >= 7 and m <= 9 then 2
                             else if m >= 10 and m <= 12 then 3
                             else 4
                         in q, type number)
in
    AddFQ
```

## Power Query M — Dim_Time_Slot Generation

```m
let
    Slots   = List.Numbers(0, 48),
    AsTable = Table.FromList(Slots, Splitter.SplitByNothing(), {"TimeSlotKey"}),
    AddHour = Table.AddColumn(AsTable, "HourOfDay",
                each Number.IntegerDivide([TimeSlotKey], 2), type number),
    AddMin  = Table.AddColumn(AddHour, "MinuteOfHour",
                each Number.Mod([TimeSlotKey], 2) * 30, type number),
    AddLabel= Table.AddColumn(AddMin, "TimeLabel",
                each Text.PadStart(Text.From([HourOfDay]), 2, "0") & ":" &
                     Text.PadStart(Text.From([MinuteOfHour]), 2, "0"), type text),
    AddSess = Table.AddColumn(AddLabel, "OR_Session",
                each if [HourOfDay] >= 6 and [HourOfDay] < 12 then "Morning"
                     else if [HourOfDay] >= 12 and [HourOfDay] < 18 then "Afternoon"
                     else "Evening", type text),
    AddORHrs= Table.AddColumn(AddSess, "IsORHours",
                each [HourOfDay] >= 8 and [HourOfDay] < 18, type logical)
in
    AddORHrs
```

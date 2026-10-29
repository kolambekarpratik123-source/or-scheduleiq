# OR-ScheduleIQ | Layer 4 | Power BI Dashboard Blueprint
## Executive 2-Page Layout — Detailed Construction Guide

> **Design System:** Corporate Healthcare — Slate Navy + Neutral Greys + Traffic-Light Alerts  
> **Canvas Size:** 1280 × 720px (16:9, standard widescreen)  
> **Theme:** Custom JSON theme provided below

---

## DESIGN TOKENS

| Token | Value | Usage |
|---|---|---|
| `--bg-primary` | `#0B1628` | Page canvas background |
| `--bg-card` | `#132035` | Visual card background |
| `--bg-card-alt` | `#1C2E48` | Alternating card |
| `--border` | `#2D4166` | Card borders, dividers |
| `--text-primary` | `#E8EDF5` | Primary text |
| `--text-secondary` | `#8FA3BF` | Labels, subtitles |
| `--accent-blue` | `#3A86FF` | Primary accent, charts |
| `--color-green` | `#059669` | On-track, good state |
| `--color-amber` | `#D97706` | Buffer breach, warning |
| `--color-red` | `#DC2626` | Overtime, critical |
| `--color-purple` | `#7C3AED` | Cardiac specialty |
| Font | `Segoe UI` (built-in PBI) | All text |
| Font — Numbers | `Segoe UI Semibold` | KPI card values |

---

## POWER BI CUSTOM THEME JSON

Save as `OR_ScheduleIQ_Theme.json` and import via **View → Themes → Browse for Themes**:

```json
{
  "name": "OR-ScheduleIQ Corporate Healthcare",
  "dataColors": [
    "#3A86FF", "#059669", "#D97706", "#DC2626",
    "#7C3AED", "#06B6D4", "#F59E0B", "#8B5CF6"
  ],
  "background": "#0B1628",
  "foreground": "#E8EDF5",
  "tableAccent": "#3A86FF",
  "visualStyles": {
    "*": {
      "*": {
        "background": [{ "color": "#132035" }],
        "border": [{ "color": "#2D4166" }],
        "title": {
          "fontColor": [{ "color": "#E8EDF5" }],
          "fontSize": [{ "fontSize": 12 }]
        },
        "legend": {
          "labelColor": [{ "color": "#8FA3BF" }]
        },
        "axis": {
          "gridlineColor": [{ "color": "#1C3050" }],
          "titleColor": [{ "color": "#8FA3BF" }],
          "labelColor": [{ "color": "#8FA3BF" }]
        }
      }
    },
    "card": {
      "*": {
        "background": [{ "color": "#132035" }],
        "calloutValue": {
          "fontSize": [{ "fontSize": 36 }],
          "fontColor": [{ "color": "#E8EDF5" }]
        }
      }
    }
  }
}
```

---

## PAGE 1: OR Utilization & Overtime Risk

### Page Setup
- **Canvas:** 1280 × 720px
- **Background:** Rectangle shape filled `#0B1628`
- **Header band:** Rectangle `1280×52px`, fill `#0D1F3C`, at top

### Header Elements
| Element | Position | Size | Content |
|---|---|---|---|
| Logo placeholder | (16, 12) | 28×28 | Hospital icon (SVG or PNG) |
| Page title | (52, 8) | auto | `OR Utilization & Overtime Risk` — Segoe UI Semibold 16pt, #E8EDF5 |
| Subtitle | (52, 30) | auto | `Operating Theatre Performance Dashboard` — 10pt, #8FA3BF |
| Last refresh | (1050, 18) | auto | `Last Refreshed: [auto]` — 9pt, #5A7299 |
| Page nav pill | (1140, 14) | 120×24 | Buttons: `P1 · OR Flow` (active) `P2 · ICU/PACU` |

---

### ROW 1: KPI Cards (y=60 to y=140)

**Card 1: Net OR Utilization Rate**
- Position: (16, 60) | Size: 280×80
- Measure: `[OR_Utilization_%]`
- Format: `0.0%`
- Title: "Net OR Utilization Rate"
- Conditional Format Background:
  - Green (`#059669`) if ≥70% and <85%
  - Amber (`#D97706`) if ≥85% and <100%  
  - Red (`#DC2626`) if ≥100%
- Subtitle (data label): `[Target_Utilization_Band]`

**Card 2: Total Overtime Hours**
- Position: (308, 60) | Size: 280×80
- Measure: `[Total_Overtime_Hours]`
- Format: `0.0 "hrs"`
- Title: "Total Overtime Hours"
- Conditional Format: Green <2 | Amber 2–6 | Red >6
- Subtitle: `[Rooms_With_Overtime]` & " rooms overran"

**Card 3: Projected Overtime Cost (₹)**
- Position: (600, 60) | Size: 280×80
- Measure: `[Projected_Overtime_Cost_INR]`
- Format: `"₹ "#,##0`
- Title: "Projected OT Cost (Dynamic)"
- Subtitle: "Responds to Buffer slider ↓"
- Background: Always `#1C2E48` (indicates it's What-If driven)

**Card 4: Case Cancellation Risk**
- Position: (892, 60) | Size: 280×80
- Measure: `[Case_Cancellation_Rate_%]`
- Format: `0.0%`
- Title: "Cancellation Risk"
- Conditional Format: Green <3% | Amber 3–7% | Red >7%

> *Tip:* Use **New Card** visual (not classic Card) to enable subtitle/reference label.

---

### ROW 2: Left Panel — Gantt-Style Room Timeline (y=152 to y=440)

**Visual: Clustered Bar Chart (used as Gantt proxy)**

Power BI does not have a native Gantt chart. Use one of:
1. **AppSource Visual:** "Gantt Chart by MAQ Software" (free)
2. **Alternative:** "Timeline by Zebra BI" or built-in **Matrix** with conditional formatting

**Setup for MAQ Gantt (recommended):**
- Add from AppSource → Search "Gantt Chart by MAQ Software"
- Position: (16, 152) | Size: 780×288

| Gantt Field | Bind To |
|---|---|
| Task (Y-axis) | `Dim_Operating_Room[RoomName]` |
| Start Date | `Fact_Surgical_Schedule[ScheduledDate]` |
| Duration | `Fact_Surgical_Schedule[ActualDuration_min]` |
| Legend/Category | `Fact_Surgical_Schedule[Specialty]` |
| Tooltip | `[Total_Overtime_Hours]`, `[OR_Utilization_%]` |

**Color rules:**
- General Surgery: `#3A86FF`
- Orthopedics: `#059669`
- Cardiac: `#DC2626`
- Overrun cases: `#D97706` (apply via conditional format on CaseStatus = "Overrun")

**Alternative — Matrix Heatmap (no AppSource required):**
- Rows: `Dim_Operating_Room[RoomName]`
- Columns: `Dim_Date[DayName]`
- Values: `[OR_Utilization_%]`
- Background conditional format: Green→Amber→Red gradient
- Data bars: enabled

---

### ROW 2: Right Panel — Duration Distribution (y=152 to y=440)

**Visual: Histogram / Column Chart**
- Position: (808, 152) | Size: 456×288
- Title: "Scheduled vs. Actual Duration Distribution"
- X-axis: Duration buckets (create binned column in Power Query: `= Number.RoundDown([ActualDuration_min] / 30) * 30`)
- Y-axis: Case count
- Series 1: Scheduled duration bins — `#3A86FF`, 70% opacity
- Series 2: Actual duration bins — `#D97706`, 70% opacity
- Reference line: P90 benchmark — add Analytics pane → Constant line → value from `[Exceeded_P90_Rate_%]`

---

### ROW 3: What-If Zone + Specialty Breakdown (y=452 to y=700)

**Left: What-If Slicer + Dynamic Cost Card**
- Position: (16, 452) | Size: 390×248
- Card background: `#1C3050`, border: `#3A86FF 2px`
- Header text: "⚙️ What-If: Buffer Time Scenario" — 11pt, `#3A86FF`
- Slicer (`Buffer_Time_Minutes`): Slider style, range 15–60 min
- Below slicer, 3 inline KPI tiles:
  | Measure | Label |
  |---|---|
  | `[Dynamic_Turnover_Buffer]` | "Buffer (min)" |
  | `[Adjusted_Cases_Per_Room_Per_Day]` | "Cases/Room/Day" |
  | `[Projected_Overtime_Cost_INR]` | "Est. OT Cost (₹)" |

**Center: Overtime Cost Waterfall by Specialty**
- Position: (418, 452) | Size: 400×248
- Visual: **Waterfall Chart**
- Category: `Dim_Surgical_Specialty[SpecialtyName]`
- Y-axis: `[Projected_Overtime_Cost_INR]`
- Colors: Increase = `#DC2626`, Decrease = `#059669`, Total = `#3A86FF`
- Title: "Overtime Cost by Specialty (₹)"

**Right: Surgeon Velocity Table**
- Position: (830, 452) | Size: 434×248
- Visual: **Table** with conditional formatting
- Columns: Specialty | Velocity Index | Overrun % | OT Hours
- Row background: Red if VelocityIndex > 1.15, Amber if 1.05–1.15, Green if ≤ 1.0
- Title: "Surgeon Velocity Index"
- Sort by Velocity Index descending

---

## PAGE 2: PACU & ICU Bottleneck Flight Deck

### Header
- Page title: `PACU & ICU Downstream Bottleneck Analysis`
- Navigation: Page 2 active | Page 1 inactive

---

### ROW 1: ICU KPI Cards (y=60 to y=140)

**Card 1: Peak ICU Bed Demand**
- Measure: `[Peak_ICU_Bed_Demand]`
- Format: `0 "Beds"`
- Reference label: `"Capacity: 16 beds"`
- Conditional: Red if ≥13 (>80% of 16)

**Card 2: ICU Bed Saturation Risk**
- Measure: `[ICU_Bed_Saturation_Risk]`
- Format: `0.0%`
- Title: "ICU Saturation Risk"
- Subtitle: `[ICU_Saturation_Label]`
- Conditional format: color via `[ICU_Saturation_Color]`

**Card 3: PACU Hold Time**
- Measure: `[PACU_Hold_Time_Hours]`
- Format: `0.0 "hrs"`
- Title: "PACU Extended Hold Time"
- Subtitle: `[PACU_Hold_Rate_%]` as "%"

**Card 4: Total Downstream Cost**
- Measure: `[Total_Cost_All_Delays_INR]`
- Format: `"₹ "#,##0`
- Title: "Total Delay Costs (₹)"
- Subtitle: "OT + PACU Hold + Cancellations"

---

### ROW 2: Left — Hourly ICU Bed Occupancy Curve (y=152 to y=430)

**Visual: Area Chart / Line Chart**
- Position: (16, 152) | Size: 620×278
- Data: `sim_hourly_bed_trace` table (connect as separate query)
- X-axis: `HourOfDay` (0–23)
- Y-axis: `icu_occupancy` (actual), `icu_capacity` (constant = 16)
- Series 1 "Avg Occupancy": Area fill `#DC2626`, 40% opacity, line `#DC2626`
- Series 2 "Capacity": Dashed line `#E8EDF5`, constant at 16
- Series 3 "80% Threshold": Dashed line `#D97706`, constant at 12.8
- Shading: Fill region between Occupancy and Capacity in red when exceeded
- Title: "Hourly ICU Bed Occupancy vs. Capacity (Avg over Simulation)"

**Analytics pane additions:**
- Min line, Max line (enabled)
- Average line with label

---

### ROW 2: Right — Scatter: Comorbidity vs Recovery Hours (y=152 to y=430)

**Visual: Scatter Chart**
- Position: (648, 152) | Size: 616×278
- X-axis: `[Avg_CCI_Score]` → "Patient Comorbidity Burden (CCI)"
- Y-axis: `[Avg_Recovery_Bed_Hours]` → "Avg Recovery Bed Hours (PACU + ICU)"
- Legend: `Dim_Surgical_Specialty[SpecialtyName]`
- Size (bubble): `[Total_ICU_Transfers]`
- Play axis: `Dim_Date[Month]` (animated trend over months)
- Colors: General Surgery=`#3A86FF` | Ortho=`#059669` | Cardiac=`#DC2626`
- Title: "Patient Risk vs. Recovery Bed Demand"
- Quadrant reference lines:
  - Vertical at CCI = 3 (moderate risk boundary)
  - Horizontal at 6 hours (ICU escalation threshold)

---

### ROW 3: Bottom — PACU + ICU Detail Panels (y=442 to y=700)

**Left: Daily ICU Transfers — Stacked Bar**
- Position: (16, 442) | Size: 400×258
- X-axis: `Dim_Date[Date]`
- Y-axis: `[Total_ICU_Transfers]`
- Legend: `Dim_Surgical_Specialty[SpecialtyName]`
- Reference line: `NUM_ICU_BEDS × 0.3` = 4.8 (daily ICU intake warning)
- Title: "Daily ICU Admissions by Specialty"

**Center: PACU Hold Distribution by Risk Tier**
- Position: (428, 442) | Size: 400×258
- Visual: Donut chart
- Legend: `Dim_Patient_Risk_Tier[RiskTierName]`
- Values: `[Total_PACU_Holds]`
- Colors: Critical=`#DC2626` | High=`#EA580C` | Moderate=`#D97706` | Low=`#059669`
- Center label: Total PACU holds count
- Title: "PACU Holds by Patient Risk Tier"

**Right: Cost Breakdown Matrix**
- Position: (840, 442) | Size: 424×258
- Visual: **Matrix**
- Rows: `Dim_Surgical_Specialty[SpecialtyName]`
- Columns: Cost Category (manually or via unpivot)
- Values:
  - Overtime: `[Projected_Overtime_Cost_INR]`
  - PACU Hold: `[PACU_Total_Hold_Cost_INR]`
  - ICU Beds: `[Total_ICU_Bed_Cost_INR]`
- Row totals: enabled
- Conditional format: Data bars on each column
- Title: "Cost Breakdown by Specialty (₹)"
- Grand total row: `[Total_Cost_All_Delays_INR]`

---

## TOOLTIP PAGES (Optional — Advanced)

Create 2 custom tooltip pages (canvas = 320×180px):

### Tooltip 1: Case Detail Tooltip
Binds to: Gantt / Scatter visual
Shows: Procedure Name | Specialty | Duration P10/P50/P90 | Status | Surgeon Velocity

### Tooltip 2: Room Daily Summary Tooltip
Binds to: Room bar chart
Shows: Date | Room | Total Cases | Utilization % | Overtime min

---

## BOOKMARKS

Create the following bookmarks for executive presentations:

| Bookmark Name | State |
|---|---|
| "All Specialties — Default" | No specialty filter, current month |
| "Cardiac Focus" | Specialty slicer = Cardiac only |
| "High Overtime Alert" | Filter: OverrunMin > 60 |
| "ICU Saturation Alert" | Filter: ICU_Transfer_Flag = TRUE |
| "Buffer = 15 min scenario" | Buffer slider = 15 |
| "Buffer = 60 min scenario" | Buffer slider = 60 |

Apply bookmarks via **Insert → Buttons → Bookmark** for presentation mode.

---

## REPORT PUBLISHING CHECKLIST

- [ ] Import `OR_ScheduleIQ_Theme.json`
- [ ] Load `fact_simulated_schedule.csv` + `sim_hourly_bed_trace.csv` + `dim_surgeries_master.csv`
- [ ] Build Star Schema relationships in Model view
- [ ] Create `_Measures` table (Home → Enter Data → blank table, then add measures)
- [ ] Create both What-If parameters (Buffer, Cost Rate)
- [ ] Add all DAX measures from `dax_measures.md`
- [ ] Apply conditional formatting to all KPI cards
- [ ] Set Page 1 navigation buttons linking to Page 2 (and vice versa)
- [ ] Enable row-level security if sharing with hospital stakeholders
- [ ] Set report theme and disable scroll bars on slicers
- [ ] Export to PDF for portfolio: File → Export → PDF

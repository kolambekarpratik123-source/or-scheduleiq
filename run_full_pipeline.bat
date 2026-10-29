@echo off
REM ============================================================
REM OR-ScheduleIQ | Quick Start Launcher
REM Run this from the project root directory
REM ============================================================

echo.
echo  ============================================================
echo   OR-ScheduleIQ ^| Full Pipeline Setup and Execution
echo  ============================================================
echo.

REM Step 1: Install dependencies
echo [1/4] Installing Python dependencies...
python -m pip install duckdb pandas numpy scipy scikit-learn simpy matplotlib seaborn tqdm
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Ensure Python 3.8+ is installed.
    pause
    exit /b 1
)
echo     Dependencies installed.
echo.

REM Step 2: Create output directories
echo [2/4] Creating output directories...
if not exist "data\raw" mkdir "data\raw"
if not exist "data\processed" mkdir "data\processed"
if not exist "data\simulated" mkdir "data\simulated"
echo     Directories ready.
echo.

REM Step 3: Run the full Python pipeline
echo [3/4] Running pipeline (synthetic data mode)...
python layer2_python\run_pipeline.py --data-source synthetic --buffer 30 --replications 10
if %errorlevel% neq 0 (
    echo ERROR: Pipeline failed. Check Python output above.
    pause
    exit /b 1
)
echo.

REM Step 4: Open outputs
echo [4/4] Pipeline complete! Output files:
echo   data\processed\dim_surgeries_master.csv
echo   data\processed\fact_surgery_cases.csv
echo   data\processed\duration_fit_parameters.csv
echo   data\processed\distribution_diagnostics.png
echo   data\simulated\fact_simulated_schedule.csv
echo   data\simulated\sim_hourly_bed_trace.csv
echo   data\simulated\sim_daily_metrics.csv
echo.
echo  Now open Power BI Desktop and follow:
echo    layer4_powerbi\dashboard_layout.md
echo  to build the executive dashboard.
echo.
pause

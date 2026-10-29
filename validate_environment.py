"""
OR-ScheduleIQ | requirements.txt compatible validation script
Run: python validate_environment.py
"""
import sys
import importlib

REQUIRED = {
    "duckdb":        "0.9.0",
    "pandas":        "1.5.0",
    "numpy":         "1.23.0",
    "scipy":         "1.10.0",
    "sklearn":       "1.2.0",
    "simpy":         "4.0.0",
    "matplotlib":    "3.6.0",
    "seaborn":       "0.12.0",
}

print("=" * 55)
print("  OR-ScheduleIQ | Environment Validation")
print("=" * 55)
print(f"  Python: {sys.version}")
print()

all_ok = True
for pkg, min_ver in REQUIRED.items():
    try:
        mod = importlib.import_module(pkg)
        ver = getattr(mod, "__version__", "?")
        print(f"  ✅  {pkg:<18} {ver}")
    except ImportError:
        print(f"  ❌  {pkg:<18} NOT INSTALLED (min: {min_ver})")
        all_ok = False

print()
if all_ok:
    print("  All dependencies satisfied. Run: python layer2_python/run_pipeline.py")
else:
    print("  Install missing packages:")
    print("  python -m pip install duckdb pandas numpy scipy scikit-learn simpy matplotlib seaborn tqdm")
print("=" * 55)

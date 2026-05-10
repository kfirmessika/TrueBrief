"""Quick AYR engine test."""
from truebrief.ledger.ayr_engine import ayr_to_interval, calculate_topic_ayr, update_topic_interval, MAX_INTERVAL
from truebrief.tasks.pipeline_task import run_pipeline_task
from truebrief.api.routes import router

# Band tests
cases = [
    (1.00, 1800), (0.75, 1800), (0.70, 1800),
    (0.55, 3600), (0.50, 3600),
    (0.35, 7200),
    (0.15, 14400),
    (0.05, 21600), (0.00, 21600),
]
all_pass = True
print("=== ayr_to_interval tests ===")
for ayr, expected in cases:
    result = ayr_to_interval(ayr)
    ok = result == expected
    all_pass = all_pass and ok
    status = "OK" if ok else "FAIL"
    print(f"  {status}: ayr={ayr:.2f} -> {result}s  (expected {expected}s)")

print()
print("All band tests pass:", all_pass)

# AYR route registered
routes = [r.path for r in router.routes]
ayr_ok = "/topics/{topic_id}/ayr" in routes
print("AYR API route registered:", ayr_ok)
print("All imports OK")

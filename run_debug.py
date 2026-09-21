import sys
import traceback
import os

# Redirect stderr to a file so we can capture errors
log_path = os.path.join(os.path.dirname(__file__), "error_log.txt")
sys.stderr = open(log_path, "w", encoding="utf-8")
sys.stdout = open(log_path, "a", encoding="utf-8")

try:
    print("=== Starting main.py ===", flush=True)
    exec(open("main.py", encoding="utf-8").read())
except Exception as e:
    print(f"\n=== ERROR ===", flush=True)
    traceback.print_exc()
    print(f"Error: {e}", flush=True)
finally:
    sys.stderr.flush()
    sys.stdout.flush()

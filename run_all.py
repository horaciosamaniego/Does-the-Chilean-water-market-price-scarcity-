"""Run the full analysis and write the console output to output/.

Equivalent to `make all`, for systems without make.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
(ROOT / "output").mkdir(exist_ok=True)

STEPS = [("wr_spatial_corrected.py", "model.txt"),
         ("wr_projection.py", "projection.txt"),
         ("make_figure.py", None)]

for script, log in STEPS:
    print(f"\n{'=' * 70}\nRunning {script}\n{'=' * 70}")
    r = subprocess.run([sys.executable, str(ROOT / "src" / script)],
                       capture_output=True, text=True)
    text = "\n".join(l for l in r.stdout.splitlines() if l.strip() != "ML_Lag")
    print(text)
    if r.returncode:
        print(r.stderr, file=sys.stderr)
        sys.exit(r.returncode)
    if log:
        (ROOT / "output" / log).write_text(text)
        print(f"[written to output/{log}]")

"""Admin-controlled solver settings. End users see these in the UI but cannot change them.
Edit this file on the VPS and restart Streamlit to apply."""
import os

TIME_LIMIT_SECONDS = 600                       # total time budget per run
WORKERS = max(8, os.cpu_count() or 1)          # CP-SAT workers
USE_CP_SAT = True                              # False = heuristic only (fastest, no proof)

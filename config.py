"""Admin-controlled solver settings. End users see these in the UI but cannot change them.
Edit this file on the VPS and restart Streamlit to apply."""
import os

TIME_LIMIT_SECONDS = 0                         # 0 = NO TIMEOUT. Runs until a proven/best minimum ticket set
                                                # is found, or the admin stops the job. See README.
WORKERS = max(8, os.cpu_count() or 1)          # CP-SAT workers
THREADS = os.cpu_count() or 1                  # NumPy threads for greedy/prune/verify
USE_CP_SAT = True                              # False = heuristic only (fastest, no proof)

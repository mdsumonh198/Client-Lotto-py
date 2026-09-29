"""Run optimizer jobs as detached background OS processes, independent of any Streamlit
browser session. Closing the browser (or the whole computer) does NOT stop a running job —
only stopping the VPS itself does. The UI just launches a job and polls its files on disk.
"""
import json
import os
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "jobs")
LAST_JOB_FILE = os.path.join(JOBS_DIR, "last_job_id.txt")


def _job_dir(job_id):
    return os.path.join(JOBS_DIR, job_id)


def start_job(cfg, time_limit, workers, threads, use_cp_sat):
    os.makedirs(JOBS_DIR, exist_ok=True)
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    jdir = _job_dir(job_id)
    os.makedirs(jdir, exist_ok=True)

    with open(os.path.join(jdir, "cfg.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    with open(os.path.join(jdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"started_at": time.time()}, f)

    targets_str = ",".join(f"{k}:{v}" for k, v in cfg["targets"].items())
    cmd = [
        sys.executable, os.path.join(ROOT, "app.py"),
        "--from", str(cfg["from"]), "--to", str(cfg["to"]),
        "--ticket", str(cfg["ticket"]), "--result", str(cfg["result"]),
        "--targets", targets_str,
        "--time", str(time_limit), "--workers", str(workers), "--threads", str(threads),
        "--out", os.path.join(jdir, "output"),
    ]
    if not use_cp_sat:
        cmd.append("--no-exact")

    log_path = os.path.join(jdir, "run.log")
    with open(log_path, "w", encoding="utf-8") as logf:
        # start_new_session detaches the child from this process's session, so it keeps
        # running even if the Streamlit server process (or the browser tab) goes away.
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=ROOT,
                                 start_new_session=True)
    with open(os.path.join(jdir, "pid.txt"), "w") as f:
        f.write(str(proc.pid))

    with open(LAST_JOB_FILE, "w") as f:
        f.write(job_id)
    return job_id


def get_last_job_id():
    if os.path.exists(LAST_JOB_FILE):
        with open(LAST_JOB_FILE) as f:
            jid = f.read().strip()
        if jid and os.path.isdir(_job_dir(jid)):
            return jid
    return None


def is_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
    except Exception:
        return True   # unknown -> assume alive rather than lose the job


def get_status(job_id):
    jdir = _job_dir(job_id)
    cfg = json.load(open(os.path.join(jdir, "cfg.json"), encoding="utf-8"))
    meta_path = os.path.join(jdir, "meta.json")
    started_at = json.load(open(meta_path, encoding="utf-8"))["started_at"] if os.path.exists(meta_path) else None
    pid_path = os.path.join(jdir, "pid.txt")
    pid = int(open(pid_path).read().strip()) if os.path.exists(pid_path) else None
    log_path = os.path.join(jdir, "run.log")
    log_lines = []
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log_lines = f.read().splitlines()

    result_path = os.path.join(jdir, "output", "result.json")
    result = None
    if os.path.exists(result_path):
        try:
            result = json.load(open(result_path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            result = None

    running = result is None and pid is not None and is_alive(pid)
    crashed = result is None and not running
    elapsed = (result["elapsed_seconds"] if result else
               (time.time() - started_at if started_at else None))
    return {
        "job_id": job_id, "cfg": cfg, "log_lines": log_lines, "elapsed_seconds": elapsed,
        "result": result, "running": running, "crashed": crashed,
    }


def stop_job(job_id):
    jdir = _job_dir(job_id)
    pid_path = os.path.join(jdir, "pid.txt")
    if os.path.exists(pid_path):
        pid = int(open(pid_path).read().strip())
        try:
            os.killpg(os.getpgid(pid), 15)
        except (OSError, ProcessLookupError):
            pass

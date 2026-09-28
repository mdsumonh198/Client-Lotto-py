#!/usr/bin/env bash
# Usage:  ./run_vps.sh --from 1 --to 25 --ticket 6 --result 6 --targets 4:10,3:25 --time 900
# Runs in background (survives SSH logout). Watch progress:  tail -f run.log
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
nohup python app.py "$@" > run.log 2>&1 &
echo "Started (PID $!). Progress: tail -f run.log   |   Results in ./output/"

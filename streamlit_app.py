import os
import time

import streamlit as st

import config
from src.core import combination_count, validate_game
from src.export import tickets_frame, verification_frame
from src.optimizer import optimize_with_constraint_generation

st.set_page_config(page_title="Universal Combination Optimizer", layout="wide")
st.title("Universal Lottery / Combination Optimizer")
st.caption("Long jobs: prefer the CLI (python app.py / ./run_vps.sh). This page blocks until the run finishes.")

c1, c2, c3, c4 = st.columns(4)
with c1:
    number_from = st.number_input("Number From", min_value=0, max_value=40, value=1, step=1)
with c2:
    number_to = st.number_input("Number To", min_value=0, max_value=40, value=25, step=1)
with c3:
    ticket_size = st.number_input("Ticket Size", min_value=1, max_value=41, value=6, step=1)
with c4:
    result_size = st.number_input("Result Size", min_value=1, max_value=41, value=6, step=1)

st.subheader("Exact-match minimum targets")
max_k = int(min(ticket_size, result_size))
selected_targets = {}
cols = st.columns(min(max_k + 1, 6))
for k in range(max_k + 1):
    with cols[k % len(cols)]:
        v = st.number_input(f"Exact {k} minimum", min_value=0, value=0, step=1, key=f"k{k}")
        if v > 0:
            selected_targets[k] = int(v)

st.subheader("Solver settings (fixed by admin)")
o1, o2, o3 = st.columns(3)
with o1:
    st.number_input("Total time limit (seconds)", value=int(config.TIME_LIMIT_SECONDS), disabled=True)
with o2:
    st.number_input("CP-SAT workers", value=int(config.WORKERS), disabled=True)
with o3:
    st.checkbox("Use CP-SAT exact solver", value=bool(config.USE_CP_SAT), disabled=True)

if st.button("Start Optimization", type="primary"):
    try:
        validate_game(int(number_from), int(number_to), int(ticket_size), int(result_size))
        st.write("Possible tickets:", f"{combination_count(int(number_from), int(number_to), int(ticket_size)):,}")
        st.write("Possible results:", f"{combination_count(int(number_from), int(number_to), int(result_size)):,}")
        box = st.empty()
        lines, t0 = [], time.time()

        def log(m):
            lines.append(f"[{time.time() - t0:6.1f}s] {m}")
            box.code("\n".join(lines[-15:]))

        out = optimize_with_constraint_generation(
            int(number_from), int(number_to), int(ticket_size), int(result_size), selected_targets,
            time_limit_seconds=int(config.TIME_LIMIT_SECONDS), workers=int(config.WORKERS),
            use_cp_sat=bool(config.USE_CP_SAT), log=log,
        )
        if out["status"] == "INFEASIBLE":
            st.error(f"INFEASIBLE: {out.get('reason')}")
        else:
            st.success(f"Status: {out['status']}")
            st.write("Selected tickets:", out["objective"], "| Proven lower bound:", out["lower_bound"],
                     "| Rounds:", out["rounds"], f"| {out['elapsed_seconds']:.1f}s")
            tdf = tickets_frame(out["tickets"])
            if len(tdf):
                st.dataframe(tdf, use_container_width=True)
                st.download_button("Download tickets CSV", tdf.to_csv(index=False).encode(), "tickets.csv", "text/csv")
            ver = out["verification"]
            vdf = verification_frame(ver)
            st.subheader("Verification report")
            st.dataframe(vdf, use_container_width=True)
            st.write("Total results checked (all, exact):", f"{ver['total_results_checked']:,}")
            for k, t in sorted(ver["targets"].items()):
                st.write(f"Exact-{k} >= {t['required']}: worst-case {t['worst_case']} -> {'PASS' if t['pass'] else 'FAIL'}")
            st.download_button("Download verification CSV", vdf.to_csv(index=False).encode(), "verification.csv", "text/csv")
    except Exception as e:
        st.error(str(e))

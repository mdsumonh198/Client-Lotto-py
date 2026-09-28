import pandas as pd
import streamlit as st
from src.core import validate_game, combination_count
from src.optimizer import optimize_with_constraint_generation

st.set_page_config(page_title="Universal Combination Optimizer", layout="wide")
st.title("Universal Lottery / Combination Optimizer")

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

time_limit = st.number_input("Solver time limit per round (seconds)", min_value=1, value=60, step=1)

if st.button("Start Optimization", type="primary"):
    try:
        validate_game(int(number_from), int(number_to), int(ticket_size), int(result_size))
        st.write("Possible tickets:", combination_count(int(number_from), int(number_to), int(ticket_size)))
        st.write("Possible results:", combination_count(int(number_from), int(number_to), int(result_size)))

        with st.spinner("Optimizing and verifying all possible results..."):
            out = optimize_with_constraint_generation(
                int(number_from), int(number_to), int(ticket_size), int(result_size),
                selected_targets, time_limit_seconds=int(time_limit)
            )

        st.success(f"Status: {out.get('status')}")
        st.write("Rounds:", out.get("rounds"))
        st.write("Selected tickets:", out.get("objective"))

        tickets = out.get("tickets", [])
        if tickets:
            df = pd.DataFrame(tickets, columns=[f"N{i+1}" for i in range(len(tickets[0]))])
            st.dataframe(df, use_container_width=True)
            st.download_button("Download tickets CSV", df.to_csv(index=False).encode(), "tickets.csv", "text/csv")

        ver = out.get("verification")
        if ver:
            rows = []
            for k, s in sorted(ver["stats"].items()):
                rows.append({
                    "Exact Match": k,
                    "Minimum": s["min"],
                    "Maximum": s["max"],
                    "Average": s["avg"],
                    "Worst Result": ",".join(map(str, s["worst_result"])),
                    "Best Result": ",".join(map(str, s["best_result"])),
                })
            vdf = pd.DataFrame(rows)
            st.subheader("Verification report")
            st.dataframe(vdf, use_container_width=True)
            st.write("Total results checked:", ver["total_results_checked"])
            st.write("All targets pass:", ver["all_targets_pass"])
            st.download_button("Download verification CSV", vdf.to_csv(index=False).encode(), "verification.csv", "text/csv")
    except Exception as e:
        st.error(str(e))

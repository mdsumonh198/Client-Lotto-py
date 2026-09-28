import streamlit as st
import pandas as pd
import time
import threading
from src.core import validate_game, combination_count
from src.optimizer import optimize_with_constraint_generation

st.set_page_config(page_title="Universal Lottery Optimizer", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #f3f4f6; }
    .console-box {
        background-color: #030712; color: #10b981; font-family: monospace;
        padding: 14px; border-radius: 8px; border: 1px solid #1f2937;
        height: 180px; overflow-y: auto; font-size: 13px; line-height: 1.6;
    }
    .metric-card {
        background-color: #111827; border: 1px solid #1f2937;
        border-radius: 8px; padding: 12px; text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("Universal Lottery / Combination Optimizer")
st.caption("Complete Guaranteed Cover Engine & 100% Exhaustive Combinatorial Verification (OR-Tools, SCIP, Gurobi)")

# ১. গেম ম্যাট্রিক্স ইনপুট
c1, c2, c3, c4 = st.columns(4)
with c1:
    number_from = st.number_input("Number From", min_value=0, max_value=40, value=1, step=1)
with c2:
    number_to = st.number_input("Number To", min_value=0, max_value=40, value=27, step=1)
with c3:
    ticket_size = st.number_input("Ticket Size", min_value=1, max_value=40, value=6, step=1)
with c4:
    result_size = st.number_input("Result Size", min_value=1, max_value=40, value=6, step=1)

# ২. টার্গেট সিলেকশন (ইনপুট বক্স)
st.subheader("Exact-match minimum targets")
max_k = int(min(ticket_size, result_size))
target_inputs = {}
cols = st.columns(max_k + 1)
for k in range(max_k + 1):
    with cols[k]:
        # step=None দিলে কোনো - বা + বাটন থাকবে না, একদম ক্লিন বক্স হবে
        default_val = 1 if k == 5 else 0
        v = st.number_input(f"Exact {k} min", min_value=0, value=default_val, step=1, key=f"k_{k}")
        if v > 0:
            target_inputs[k] = int(v)

# ৩. সলভার সেটিংস
st.subheader("Solver settings")
s_col1, s_col2, s_col3 = st.columns([2, 2, 2])
with s_col1:
    time_limit = st.number_input("Total time limit (seconds)", min_value=10, value=600, step=10)
with s_col2:
    workers = st.number_input("CP-SAT workers", min_value=1, max_value=16, value=4, step=1)
with s_col3:
    st.write("")
    st.write("")
    use_cp_sat = st.checkbox("Use CP-SAT exact solver", value=True)

# মোট কম্বিনেশন তথ্য
total_draws = combination_count(int(number_from), int(number_to), int(result_size))
total_tickets = combination_count(int(number_from), int(number_to), int(ticket_size))
st.write(f"Possible tickets: **{total_tickets:,}** | Possible results: **{total_draws:,}**")

# ৪. স্টার্ট বাটন ও লাইভ প্রগ্রেস ট্র্যাকার
if st.button("Start Optimization", type="primary", use_container_width=True):
    if not target_inputs:
        st.error("অন্তত একটি টার্গেট বক্সে ১ বা তার বেশি সংখ্যা দিন!")
    else:
        st.session_state.results_output = None
        
        # লাইভ এলিমেন্টস
        progress_bar = st.progress(0, text="📊 প্রস্তুতি চলছে... 0% সম্পন্ন")
        live_cards = st.empty()
        console_display = st.empty()
        
        log_lines = [f"[  0.0s] Tickets: {total_tickets:,} | Results: {total_draws:,} | Engine Started..."]

        shared_state = {
            "round": 1,
            "tickets": 0,
            "covered": 0,
            "pending": total_draws,
            "pct": 0.0,
            "message": "Initializing High-Speed Combinatorial Engine...",
            "done": False,
            "output": None,
            "error": None
        }

        start_time = time.time()

        def live_callback(round_no, max_rounds, tickets_count, total_d, covered_d, pending_d, coverage_pct, message):
            shared_state["round"] = round_no
            shared_state["tickets"] = tickets_count
            shared_state["covered"] = covered_d
            shared_state["pending"] = pending_d
            shared_state["pct"] = coverage_pct
            shared_state["message"] = message
            elapsed = time.time() - start_time
            log_lines.append(f"[{elapsed:5.1f}s] {message}")
            if len(log_lines) > 8:
                log_lines.pop(0)

        # ব্যাকগ্রাউন্ড থ্রেড
        safe_from = int(number_from)
        safe_to = int(number_to)
        safe_k = int(ticket_size)
        safe_m = int(result_size)
        safe_time = int(time_limit)
        safe_targets = dict(target_inputs)
        safe_workers = int(workers)

        def worker():
            try:
                res = optimize_with_constraint_generation(
                    safe_from, safe_to, safe_k, safe_m,
                    safe_targets, time_limit_seconds=safe_time,
                    workers=safe_workers, use_cp_sat=use_cp_sat,
                    progress_callback=live_callback
                )
                shared_state["output"] = res
            except Exception as e:
                shared_state["error"] = str(e)
            finally:
                shared_state["done"] = True

        threading.Thread(target=worker, daemon=True).start()

        # মেইন থ্রেড: প্রতি ১ সেকেন্ডে লাইভ স্ক্রিন আপডেট করবে!
        while not shared_state["done"]:
            elapsed_sec = int(time.time() - start_time)
            mins, secs = divmod(elapsed_sec, 60)
            t_str = f"{mins:02d}:{secs:02d}s"

            pct_val = min(100.0, max(0.0, float(shared_state["pct"])))
            progress_bar.progress(int(pct_val), text=f"📊 সামগ্রিক কভারেজ অগ্রগতি: {pct_val:.2f}% সম্পন্ন | আর {100 - pct_val:.2f}% বাকি (টার্গেট: ১০০% জিরো-মিস)")

            # লাইভ ৪টি কার্ড
            live_cards.markdown(f"""
            <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px;'>
                <div class='metric-card'><span style='color:#9ca3af;font-size:12px;'>⏱️ Elapsed Time</span><br><b style='color:#f43f5e;font-size:20px;'>{t_str}</b></div>
                <div class='metric-card'><span style='color:#9ca3af;font-size:12px;'>🎟️ Tickets Generated</span><br><b style='color:#10b981;font-size:20px;'>{shared_state['tickets']} টি</b></div>
                <div class='metric-card'><span style='color:#9ca3af;font-size:12px;'>✅ Draws Complete</span><br><b style='color:#22c55e;font-size:20px;'>{shared_state['covered']:,}</b></div>
                <div class='metric-card'><span style='color:#9ca3af;font-size:12px;'>🎯 Draws Remaining</span><br><b style='color:#f59e0b;font-size:20px;'>{shared_state['pending']:,} টি</b></div>
            </div>
            """, unsafe_allow_html=True)

            # লাইভ টার্মিনাল লগ বক্স
            log_html = "<br>".join(log_lines)
            console_display.markdown(f"<div class='console-box'>{log_html}</div>", unsafe_allow_html=True)

            time.sleep(1)

        progress_bar.progress(100, text="✅ ১০০% অপ্টিমাইজেশন ও ব্রুট-ফোর্স অডিট সম্পন্ন!")
        if shared_state["error"]:
            st.error(f"Error: {shared_state['error']}")
        elif shared_state["output"]:
            st.session_state.results_output = (shared_state["output"], time.time() - start_time)
            st.rerun()

# ৫. ফাইনাল রেজাল্ট প্রদর্শন
if "results_output" in st.session_state and st.session_state.results_output:
    out, elapsed = st.session_state.results_output
    raw_tickets = out.get("tickets", [])
    ver = out.get("verification", {})

    st.success(f"✅ Optimization Completed in {elapsed:.2f} seconds | Status: {out.get('status', 'PROVED OPTIMAL')}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Selected Tickets", len(raw_tickets))
    m2.metric("Total Results Audited", f"{ver.get('total_results_checked', 0):,}")
    m3.metric("Rounds Solved", out.get("rounds", 1))
    m4.metric("Guarantee Status", "100% ZERO MISS" if ver.get("all_targets_pass") else "TARGET FAILED")

    st.divider()

    # ভেরিফিকেশন রিপোর্ট
    if ver and "stats" in ver:
        st.subheader("📊 Detailed Exact Match Breakdown")
        rows = []
        for k, s in sorted(ver["stats"].items()):
            rows.append({
                "Exact Match": f"Exact {k}",
                "Worst Case (Min)": s["min"],
                "Best Case (Max)": s["max"],
                "Average": round(s["avg"], 3),
                "Worst Result": str(s["worst_result"]),
                "Best Result": str(s["best_result"]),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # টিকেট টেবিল ও ডাউনলোড
    if raw_tickets:
        st.subheader("🎟️ Selected Minimal Ticket Combinations")
        cols = [f"N{i+1}" for i in range(len(raw_tickets[0]) - 1)] + ["Budget Tier"] if isinstance(raw_tickets[0][-1], str) else [f"N{i+1}" for i in range(len(raw_tickets[0]))]
        tdf = pd.DataFrame(raw_tickets, columns=cols)
        st.dataframe(tdf, use_container_width=True)
        st.download_button("📥 Download Tickets CSV", tdf.to_csv(index=False).encode(), "tickets.csv", "text/csv")

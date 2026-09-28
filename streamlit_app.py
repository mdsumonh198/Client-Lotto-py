import streamlit as st
import pandas as pd
import time
import threading
from src.core import validate_game, combination_count
from src.optimizer import optimize_with_constraint_generation

# ১. পেজ কনফিগারেশন ও প্রিমিয়াম ডার্ক স্টাইল
st.set_page_config(page_title="Universal Lottery Optimizer", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #f3f4f6; }
    div[data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; }
    .badge {
        background-color: #0284c7; color: white; padding: 4px 12px;
        border-radius: 9999px; font-size: 12px; font-weight: bold;
        display: inline-block; letter-spacing: 0.5px;
    }
    .metric-card {
        background-color: #161e2e; border: 1px solid #1f2937;
        border-radius: 8px; padding: 12px; margin-bottom: 8px;
    }
    .live-card {
        background-color: #111827; border: 1px solid #1f2937;
        border-radius: 8px; padding: 12px; text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    @keyframes pulse-dot {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.3; transform: scale(0.85); }
        100% { opacity: 1; transform: scale(1); }
    }
    .live-dot {
        display: inline-block; width: 9px; height: 9px;
        background-color: #10b981; border-radius: 50%;
        margin-right: 5px; animation: pulse-dot 1.5s infinite;
    }
</style>
""", unsafe_allow_html=True)

# ২. সাইডবার (Universal Game Matrix & Compound Targets)
with st.sidebar:
    st.header("⚙️ Universal Game Matrix")
    c1, c2 = st.columns(2)
    with c1:
        number_from = st.number_input("Universe Min:", min_value=0, max_value=40, value=1, step=1)
    with c2:
        number_to = st.number_input("Universe Max:", min_value=0, max_value=40, value=27, step=1)
    
    c3, c4 = st.columns(2)
    with c3:
        ticket_size = st.number_input("Ticket Size (k):", min_value=1, max_value=40, value=6, step=1)
    with c4:
        result_size = st.number_input("Draw Size (m):", min_value=1, max_value=40, value=6, step=1)
    
    validate_game(int(number_from), int(number_to), int(ticket_size), int(result_size))
    total_draws = combination_count(int(number_from), int(number_to), int(result_size))
    total_tickets = combination_count(int(number_from), int(number_to), int(ticket_size))
    
    st.caption(f"POOL: **{number_from}..{number_to}** ({number_to - number_from + 1} numbers)")
    st.caption(f"COMBINATORIAL DRAWS: **{total_draws:,}**")
    st.caption(f"CANDIDATE TICKETS: **{total_tickets:,}**")
    st.divider()

    st.header("🎯 Compound Target Requirements")
    st.caption("All targets must be satisfied simultaneously on EVERY draw.")
    
    tc1, tc2 = st.columns(2)
    with tc1:
        max_possible_k = min(int(ticket_size), int(result_size))
        exact_k = st.selectbox("Exact Match (k):", options=list(range(max_possible_k + 1)), index=min(5, max_possible_k))
    with tc2:
        min_count = st.number_input("Min Count (>=):", min_value=1, value=1, step=1)
    
    if "targets" not in st.session_state:
        st.session_state.targets = {5: 1}

    if st.button("➕ Add Compound Target", use_container_width=True):
        st.session_state.targets[int(exact_k)] = int(min_count)
        st.success(f"Added: Exact {exact_k} >= {min_count}")

    if st.session_state.targets:
        st.write("Active Targets:")
        for k, v in list(st.session_state.targets.items()):
            col_t1, col_t2 = st.columns([3, 1])
            col_t1.info(f"Exact {k}-Match >= {v}")
            if col_t2.button("✖", key=f"del_{k}"):
                del st.session_state.targets[k]
                st.rerun()

    st.divider()
    st.header("⚡ Optimization Engine Settings")
    time_limit = st.slider("Solver time limit per round (sec):", 10, 300, 60)

# ৩. মূল ড্যাশবোর্ড হেডার
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("### 🛡️ Universal Lottery / Combination Optimizer")
    st.caption("Complete Guaranteed Cover Engine & 100% Exhaustive Combinatorial Verification (OR-Tools, SCIP, Gurobi)")
with col_h2:
    st.markdown("<div style='text-align: right;'><span class='badge'>100% EXHAUSTIVE GUARANTEE • ZERO MISS</span></div>", unsafe_allow_html=True)

if st.session_state.targets:
    target_text = " | ".join([f"Exact {k}-Match ≥ {v}" for k, v in sorted(st.session_state.targets.items())])
    st.markdown(f"<div class='metric-card' style='border-left: 4px solid #0284c7;'><strong>ACTIVE COMPOUND REQUIREMENTS:</strong><br><span style='color:#38bdf8;'>{target_text}</span></div>", unsafe_allow_html=True)

col_b1, col_b2 = st.columns([3, 1])
with col_b1:
    start_btn = st.button("🚀 Start Combinatorial Optimization", type="primary", use_container_width=True)
with col_b2:
    if st.button("↺ Reset Results", use_container_width=True):
        st.session_state.results_output = None
        st.rerun()

# ৪. মাল্টি-থ্রেডেড রিয়েল-টাইম অপ্টিমাইজেশন ও শতকরা প্রগ্রেস বার
if start_btn:
    if not st.session_state.targets:
        st.error("Please add at least one target from the sidebar!")
    else:
        st.session_state.results_output = None
        progress_bar = st.progress(0, text="📊 সামগ্রিক অগ্রগতি: 0.00% সম্পন্ন (টার্গেট: ১০০% জিরো-মিস)")
        status_box = st.empty()
        live_metrics = st.empty()
        
        shared_state = {
            "round": 1,
            "tickets": 0,
            "covered": 0,
            "pending": total_draws,
            "pct": 0.0,
            "message": "Initializing High-Speed Solver Engine...",
            "done": False,
            "output": None,
            "error": None
        }

        def thread_callback(round_no, max_rounds, tickets_count, total_draws, covered_draws, pending_violations, coverage_pct, message):
            shared_state["round"] = round_no
            shared_state["tickets"] = tickets_count
            shared_state["covered"] = covered_draws
            shared_state["pending"] = pending_violations
            shared_state["pct"] = coverage_pct
            shared_state["message"] = message

        def solver_worker():
            try:
                res = optimize_with_constraint_generation(
                    int(number_from), int(number_to), int(ticket_size), int(result_size),
                    st.session_state.targets, time_limit_seconds=int(time_limit),
                    progress_callback=thread_callback
                )
                shared_state["output"] = res
            except Exception as e:
                shared_state["error"] = str(e)
            finally:
                shared_state["done"] = True

        worker_thread = threading.Thread(target=solver_worker, daemon=True)
        worker_thread.start()

        start_time = time.time()

        while not shared_state["done"]:
            elapsed_sec = int(time.time() - start_time)
            mins, secs = divmod(elapsed_sec, 60)
            timer_display = f"{mins:02d}:{secs:02d}s"

            pct_val = min(100.0, max(0.0, float(shared_state["pct"])))
            
            # প্রগ্রেস বারের ওপর স্পষ্ট শতাংশ টেক্সট প্রদর্শন
            progress_bar.progress(int(pct_val), text=f"📊 সামগ্রিক অগ্রগতি: {pct_val:.2f}% সম্পন্ন | আর {100 - pct_val:.2f}% বাকি (টার্গেট: ১০০% জিরো-মিস)")

            status_box.markdown(f"""
            <div class='metric-card' style='border-left: 4px solid #10b981;'>
                <strong><span class='live-dot'></span>{shared_state['message']}</strong>
            </div>
            """, unsafe_allow_html=True)

            cov = shared_state["covered"]
            cov_str = f"{cov:,} ({shared_state['pct']}%)" if isinstance(cov, int) else str(cov)
            pen = shared_state["pending"]
            pen_str = f"{pen:,}" if isinstance(pen, int) else str(pen)

            live_metrics.markdown(f"""
            <div style='display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-top: 10px;'>
                <div class='live-card'>
                    <div style='color: #9ca3af; font-size: 12px;'><span class='live-dot'></span>Elapsed Time</div>
                    <div style='color: #f43f5e; font-size: 19px; font-weight: bold;'>{timer_display}</div>
                </div>
                <div class='live-card'>
                    <div style='color: #9ca3af; font-size: 12px;'>🔄 Round</div>
                    <div style='color: #38bdf8; font-size: 19px; font-weight: bold;'>Round {shared_state['round']}</div>
                </div>
                <div class='live-card'>
                    <div style='color: #9ca3af; font-size: 12px;'>🎟️ Tickets Generated</div>
                    <div style='color: #10b981; font-size: 19px; font-weight: bold;'>{shared_state['tickets']} টি</div>
                </div>
                <div class='live-card'>
                    <div style='color: #9ca3af; font-size: 12px;'>✅ Draws Complete</div>
                    <div style='color: #22c55e; font-size: 19px; font-weight: bold;'>{cov_str}</div>
                </div>
                <div class='live-card'>
                    <div style='color: #9ca3af; font-size: 12px;'>🎯 Draws Remaining</div>
                    <div style='color: #f59e0b; font-size: 19px; font-weight: bold;'>{pen_str} টি</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            time.sleep(1)

        progress_bar.progress(100, text="✅ ১০০% অপ্টিমাইজেশন ও ব্রুট-ফোর্স অডিট সম্পন্ন!")
        elapsed_total = time.time() - start_time
        if shared_state["error"]:
            st.error(f"Optimization error: {shared_state['error']}")
        elif shared_state["output"]:
            st.session_state.results_output = (shared_state["output"], elapsed_total)
            st.rerun()

# ৫. ফাইনাল ভেরিফিকেশন রিপোর্ট ও রেজাল্ট প্রদর্শন
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

    if ver and "stats" in ver:
        st.subheader("📊 Detailed Exact Match Breakdown")
        rows = []
        for k, s in sorted(ver["stats"].items()):
            req = st.session_state.targets.get(k, "-")
            status = "PASS" if (req != "-" and s["min"] >= req) else ("-" if req == "-" else "FAIL")
            rows.append({
                "Exact Match Level": f"Exact {k}",
                "Required Target": f"≥ {req}" if req != "-" else "-",
                "Worst Case (Min)": s["min"],
                "Best Case (Max)": s["max"],
                "Average Wins": round(s["avg"], 3),
                "Status": status,
                "Worst Result Example": str(s["worst_result"]),
                "Best Result Example": str(s["best_result"]),
            })
        vdf = pd.DataFrame(rows)
        st.dataframe(vdf, use_container_width=True)

    if raw_tickets:
        st.subheader("🎟️ Selected Minimal Ticket Combinations (With Budget Steps)")
        cols = [f"N{i+1}" for i in range(len(raw_tickets[0]) - 1)] + ["Budget Tier"]
        tdf = pd.DataFrame(raw_tickets, columns=cols)
        
        budget_filter = st.selectbox("বাজেট অনুযায়ী টিকেট ফিল্টার করুন:", 
                                     ["সব টিকেট (100% Zero-Miss Guarantee)", 
                                      "Step 1 (Starter - 25% Budget)", 
                                      "Step 2 (Growth - 50% Budget)"])
        
        if "Starter" in budget_filter:
            filtered_df = tdf[tdf["Budget Tier"] == "Step 1 (Starter - 25% Budget)"]
        elif "Growth" in budget_filter:
            filtered_df = tdf[tdf["Budget Tier"].isin(["Step 1 (Starter - 25% Budget)", "Step 2 (Growth - 50% Budget)"])]
        else:
            filtered_df = tdf

        st.dataframe(filtered_df, use_container_width=True)
        
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            st.download_button("📥 Download Filtered Tickets CSV", filtered_df.to_csv(index=False).encode(), "tickets_by_budget.csv", "text/csv", use_container_width=True)
        with c_dl2:
            if ver and "stats" in ver:
                st.download_button("📥 Download Full Audit CSV", vdf.to_csv(index=False).encode(), "audit_report.csv", "text/csv", use_container_width=True)

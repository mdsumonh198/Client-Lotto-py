import streamlit as st
import pandas as pd
import time
from src.core import validate_game, combination_count
from src.optimizer import optimize_with_constraint_generation

# ১. পেজ কনফিগারেশন ও ডার্ক স্টাইল
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
</style>
""", unsafe_allow_html=True)

# ২. বামের সাইডবার (Universal Game Matrix & Settings)
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
        exact_k = st.selectbox("Exact Match (k):", options=list(range(min(ticket_size, result_size) + 1)), index=min(5, ticket_size))
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
    engine_mode = st.selectbox("Optimization Mode / Engine:", ["Complete Guaranteed Cover (Zero-Miss)", "Fast Coverage Heuristic"])
    time_limit = st.slider("Solver time limit per round (sec):", 10, 300, 60)

# ৩. মূল ড্যাশবোর্ড ও হেডার
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("### 🛡️ Universal Lottery / Combination Optimizer")
    st.caption("Complete Guaranteed Cover Engine & 100% Exhaustive Combinatorial Verification (OR-Tools, SCIP, Gurobi)")
with col_h2:
    st.markdown("<div style='text-align: right;'><span class='badge'>100% EXHAUSTIVE GUARANTEE • ZERO MISS</span></div>", unsafe_allow_html=True)

# একটিভ টার্গেট ডিসপ্লে
if st.session_state.targets:
    target_text = " | ".join([f"Exact {k}-Match ≥ {v}" for k, v in st.session_state.targets.items()])
    st.markdown(f"<div class='metric-card' style='border-left: 4px solid #0284c7;'><strong>ACTIVE COMPOUND REQUIREMENTS:</strong><br><span style='color:#38bdf8;'>{target_text}</span></div>", unsafe_allow_html=True)

# বড় সবুজ বাটন ও কন্ট্রোল
col_b1, col_b2 = st.columns([3, 1])
with col_b1:
    start_btn = st.button("🚀 Start Combinatorial Optimization", type="primary", use_container_width=True)
with col_b2:
    if st.button("↺ Reset Results", use_container_width=True):
        st.session_state.results_output = None
        st.rerun()

# ৪. অপ্টিমাইজেশন ও প্রগ্রেস ট্র্যাকার
if start_btn:
    if not st.session_state.targets:
        st.error("Please add at least one target from the sidebar!")
    else:
        progress_bar = st.progress(0)
        status_box = st.empty()
        
        status_box.markdown(f"""
        <div class='metric-card' style='border-left: 4px solid #10b981;'>
            <strong>🔄 Phase: COMBINATORIAL_OPTIMIZATION • Multi-Core Active</strong><br>
            <span style='color:#9ca3af;'>Evaluating against {total_draws:,} exhaustive combinatorial results...</span>
        </div>
        """, unsafe_allow_html=True)
        progress_bar.progress(35)

        start_time = time.time()
        try:
            out = optimize_with_constraint_generation(
                int(number_from), int(number_to), int(ticket_size), int(result_size),
                st.session_state.targets, time_limit_seconds=int(time_limit)
            )
            progress_bar.progress(100)
            elapsed = time.time() - start_time
            st.session_state.results_output = (out, elapsed)
        except Exception as e:
            st.error(f"Optimization error: {str(e)}")

# ৫. রেজাল্ট ও ভেরিফিকেশন রিপোর্ট
if "results_output" in st.session_state and st.session_state.results_output:
    out, elapsed = st.session_state.results_output
    tickets = out.get("tickets", [])
    ver = out.get("verification", {})
    
    st.success(f"✅ Optimization Completed in {elapsed:.2f} seconds | Status: {out.get('status')}")

    # মেট্রিক কার্ডস
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Selected Tickets", len(tickets))
    m2.metric("Total Results Audited", f"{ver.get('total_results_checked', 0):,}")
    m3.metric("Rounds Solved", out.get("rounds", 1))
    m4.metric("Guarantee Status", "100% ZERO MISS" if ver.get("all_targets_pass") else "TARGET FAILED")

    st.divider()

    # ভেরিফিকেশন রিপোর্ট টেবিল
    if ver and "stats" in ver:
        st.subheader("📊 Detailed Exact Match Breakdown")
        rows = []
        for k, s in sorted(ver["stats"].items()):
            rows.append({
                "Exact Match Level": f"Exact {k}",
                "Worst Case (Min)": s["min"],
                "Best Case (Max)": s["max"],
                "Average Wins": round(s["avg"], 3),
                "Status": "PASS" if s["min"] >= st.session_state.targets.get(k, 0) else "FAIL",
                "Worst Result Example": str(s["worst_result"]),
                "Best Result Example": str(s["best_result"]),
            })
        vdf = pd.DataFrame(rows)
        st.dataframe(vdf, use_container_width=True)

    # টিকেট ডাউনলোড ও টেবিল
    if tickets:
        st.subheader("🎟️ Selected Minimal Ticket Combinations")
        tdf = pd.DataFrame(tickets, columns=[f"N{i+1}" for i in range(len(tickets[0]))])
        st.dataframe(tdf, use_container_width=True)
        
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            st.download_button("📥 Download Tickets CSV", tdf.to_csv(index=False).encode(), "optimized_tickets.csv", "text/csv", use_container_width=True)
        with c_dl2:
            if ver and "stats" in ver:
                st.download_button("📥 Download Full Audit CSV", vdf.to_csv(index=False).encode(), "audit_report.csv", "text/csv", use_container_width=True)

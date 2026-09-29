import os
import re
import time

import streamlit as st

import config
from src import jobs
from src.core import combination_count, validate_game
from src.export import tickets_frame, verification_frame

st.set_page_config(page_title="Universal Combination Optimizer", layout="wide")
st.title("লটারি / কম্বিনেশন অপ্টিমাইজার")
st.caption("একবার 'শুরু করুন' চাপলে হিসাব সার্ভারেই আলাদাভাবে চলতে থাকে। ব্রাউজার বন্ধ করলে বা এই পেজ রিলোড "
           "করলেও কাজ থামবে না — পরে আবার এই পেজ খুললেই চলমান/শেষ হওয়া কাজ দেখা যাবে।")

_SHORT_RE = re.compile(r"([\d,]+)\s+results still short")


def _plain_message(raw):
    if "greedy" in raw and "results still short" in raw:
        return "প্রাথমিক টিকেট সেট তৈরি হচ্ছে..."
    if "greedy+prune" in raw:
        return "অপ্রয়োজনীয় টিকেট বাদ দেওয়া হচ্ছে..."
    if "CP-SAT" in raw or "round" in raw:
        return "টিকেট সংখ্যা আরও কমানো যায় কিনা যাচাই হচ্ছে (প্রমাণিত সমাধান খোঁজা হচ্ছে)..."
    if "LNS" in raw:
        return "শেষ ধাপে আরও কম টিকেটে সমাধান খোঁজা হচ্ছে..."
    if "Tickets:" in raw:
        return "গেম হিসাব করা হচ্ছে..."
    return "কাজ চলছে..."


def _fmt_elapsed(sec):
    if sec is None:
        return "00:00:00"
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s2 = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s2:02d}"


def _progress_fraction(log_lines, n_results):
    for line in reversed(log_lines):
        m = _SHORT_RE.search(line)
        if m and n_results:
            short = int(m.group(1).replace(",", ""))
            return max(0.0, min(1.0, 1 - short / n_results))
    return None


_RE_LB = re.compile(r"Counting lower bound: (\d+)")
_RE_PRUNE_DONE = re.compile(r"greedy\+prune -> (\d+) tickets")
_RE_FULL_MODEL = re.compile(r"status=\S+ candidate=\S+ lower_bound=(\d+) best=(\d+)")
_RE_ROUND = re.compile(r"round (\d+): status=\S+ candidate=\S+ lower_bound=(\d+) best=(\d+)")
_RE_LNS = re.compile(r"LNS round (\d+): improved -> (\d+) tickets")


def _parse_state(log_lines):
    """Scan the whole log so far and build a picture of: which phase we're in, the best
    ticket count found so far, and the proven mathematical lower bound (if known)."""
    state = {"phase": 1, "phase_name": "ধাপ ১/৩: প্রাথমিক টিকেট সেট তৈরি হচ্ছে",
             "best": None, "lower_bound": None, "round": None}
    for line in log_lines:
        if m := _RE_LB.search(line):
            state["lower_bound"] = int(m.group(1))
        if m := _SHORT_RE.search(line):
            pass  # handled by _progress_fraction separately
        if m := _RE_PRUNE_DONE.search(line):
            state["best"] = int(m.group(1))
            state["phase"] = 2
            state["phase_name"] = "ধাপ ২/৩: টিকেট সংখ্যা প্রমাণসহ কমানো হচ্ছে (CP-SAT)"
        if "CP-SAT skipped" in line:
            state["phase"] = 3
            state["phase_name"] = "ধাপ ৩/৩: বাকি সময়ে আরও কম টিকেট খোঁজা হচ্ছে (LNS)"
        if m := _RE_FULL_MODEL.search(line):
            state["lower_bound"] = int(m.group(1))
            state["best"] = min(state["best"], int(m.group(2))) if state["best"] else int(m.group(2))
            state["phase"] = 2
        if m := _RE_ROUND.search(line):
            state["round"] = int(m.group(1))
            state["lower_bound"] = int(m.group(2))
            state["best"] = min(state["best"], int(m.group(3))) if state["best"] else int(m.group(3))
            state["phase"] = 2
        if "Step 3: LNS" in line:
            state["phase"] = 3
            state["phase_name"] = "ধাপ ৩/৩: বাকি সময়ে আরও কম টিকেট খোঁজা হচ্ছে (LNS)"
        if m := _RE_LNS.search(line):
            state["best"] = min(state["best"], int(m.group(2))) if state["best"] else int(m.group(2))
            state["phase"] = 3
    return state


def _render_result(result):
    if result["status"] == "INFEASIBLE":
        st.error("❌ এই গেমে আপনার টার্গেট কোনোভাবেই সম্ভব না। কারণ:")
        st.error(result.get("reason"))
        return

    ver = result["verification"]
    ver["stats"] = {int(k): v for k, v in ver["stats"].items()}
    ver["targets"] = {int(k): v for k, v in ver["targets"].items()}
    all_pass = ver["all_targets_pass"]

    if all_pass:
        st.success(
            f"✅ **টার্গেট গ্যারান্টেড।** সম্ভাব্য {ver['total_results_checked']:,} টা ড্রয়ের প্রতিটার "
            f"বিপরীতে যাচাই করা হয়েছে — সবচেয়ে খারাপ অবস্থাতেও (worst case) আপনার টার্গেট মিলবে।"
        )
    else:
        st.error("⚠️ যাচাইয়ে সমস্যা পাওয়া গেছে — টার্গেট সব ড্রয়ে মিলছে না। এই ফলাফল ব্যবহার করবেন না।")

    proof_note = (
        "এই সংখ্যাটাই সর্বনিম্ন — গাণিতিকভাবে প্রমাণিত।" if result["status"] == "PROVED OPTIMAL"
        else "এটা এখন পর্যন্ত পাওয়া সেরা (সর্বনিম্ন) সংখ্যা। আরও কম সম্ভব কিনা নিশ্চিত না।"
    )
    def _fmt(sec):
        sec = int(sec)
        h, r = divmod(sec, 3600)
        m, s2 = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s2:02d}"

    m1, m2, m3 = st.columns(3)
    m1.metric("মোট টিকেট", result["objective"])
    m2.metric("⏱️ মোট সময় লেগেছে", _fmt(result["elapsed_seconds"]))
    m3.metric("প্রমাণিত সর্বনিম্ন?", "হ্যাঁ" if result["status"] == "PROVED OPTIMAL" else "না")
    st.caption(proof_note)

    st.subheader("প্রতিটা টার্গেট লেভেলের ফলাফল (worst case)")
    for k, t in sorted(ver["targets"].items()):
        icon = "✅" if t["pass"] else "❌"
        st.write(f"{icon} ঠিক {k}টা মিললে: দরকার কমপক্ষে {t['required']}টা, সবচেয়ে খারাপ ড্রয়ে পাওয়া গেছে {t['worst_case']}টা")

    tdf = tickets_frame(result["tickets"])
    if len(tdf):
        st.subheader(f"টিকেট তালিকা ({len(tdf)}টা)")
        st.dataframe(tdf, use_container_width=True)
        st.download_button("টিকেট CSV ডাউনলোড করুন", tdf.to_csv(index=False).encode(), "tickets.csv", "text/csv")

    with st.expander("বিস্তারিত ভেরিফিকেশন রিপোর্ট"):
        vdf = verification_frame(ver)
        st.dataframe(vdf, use_container_width=True)
        st.download_button("ভেরিফিকেশন CSV ডাউনলোড করুন", vdf.to_csv(index=False).encode(), "verification.csv", "text/csv")


# ---------------------------------------------------------------------------
last_job_id = jobs.get_last_job_id()
running_status = jobs.get_status(last_job_id) if last_job_id else None

if running_status and (running_status["running"] or running_status["result"]):
    st.subheader("চলমান / সবশেষ কাজ")
    cfg = running_status["cfg"]
    st.write(f"গেম: {cfg['from']}–{cfg['to']}, টিকেটে {cfg['ticket']}টা, ড্রয়ে {cfg['result']}টা, "
             f"টার্গেট: {cfg['targets']}")
    n_results = combination_count(cfg["from"], cfg["to"], cfg["result"])

    if running_status["running"]:
        st.info("🟢 কাজ চলছে (ব্যাকগ্রাউন্ডে, সার্ভারে)। **কোনো সময়সীমা নাই** — যতক্ষণ না সর্বনিম্ন টিকেট সংখ্যা "
                "পাওয়া যায় (অথবা আপনি নিজে বন্ধ করেন), ততক্ষণ চলবে।")
        pstate = _parse_state(running_status["log_lines"])
        tcol1, tcol2 = st.columns(2)
        tcol1.metric("⏱️ এখন পর্যন্ত সময় লেগেছে", _fmt_elapsed(running_status["elapsed_seconds"]))
        tcol2.metric("বর্তমান ধাপ", f"{pstate['phase']}/৩")
        st.write(f"**{pstate['phase_name']}**")

        frac = _progress_fraction(running_status["log_lines"], n_results)
        if pstate["phase"] == 1:
            st.progress(frac or 0, text=f"কভারেজ: {(frac or 0) * 100:.1f}% সম্পন্ন")
        else:
            st.progress(1.0, text="ধাপ ১ সম্পন্ন (সব সম্ভাব্য ড্র কভার হয়ে গেছে)")

        if pstate["best"] is not None:
            b1, b2 = st.columns(2)
            b1.metric("🎟️ এখন পর্যন্ত সেরা", f"{pstate['best']:,} টিকেট")
            if pstate["lower_bound"] is not None:
                b2.metric("📐 গাণিতিক সর্বনিম্ন সীমা", f"{pstate['lower_bound']:,} টিকেট")
                closeness = min(1.0, pstate["lower_bound"] / pstate["best"]) if pstate["best"] else 0
                st.progress(closeness, text=f"সর্বনিম্নের কতটা কাছে: {closeness * 100:.1f}% "
                                             f"(১০০% মানে গাণিতিকভাবে প্রমাণিত সর্বনিম্ন পাওয়া গেছে)")
                st.caption("এই দুইটা সংখ্যা যত কাছাকাছি আসবে, তত নিশ্চিত হওয়া যাবে যে আর কম টিকেট সম্ভব না।")
            if pstate["round"] is not None:
                st.caption(f"রাউন্ড সংখ্যা: {pstate['round']}")

        last_msg = running_status["log_lines"][-1] if running_status["log_lines"] else ""
        st.write(_plain_message(last_msg))
        with st.expander("টেকনিক্যাল লগ"):
            st.code("\n".join(running_status["log_lines"][-25:]))
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 রিফ্রেশ করুন"):
                st.rerun()
        with c2:
            if st.button("⛔ কাজ বন্ধ করুন"):
                jobs.stop_job(last_job_id)
                st.rerun()
        auto = st.checkbox("প্রতি ৪ সেকেন্ডে নিজে থেকে রিফ্রেশ হোক", value=True)
        if auto:
            time.sleep(4)
            st.rerun()
    elif running_status["crashed"]:
        st.error("এই কাজটা শেষ হওয়ার আগেই থেমে গেছে (ক্র্যাশ)। নিচে টেকনিক্যাল লগ দেখুন।")
        st.code("\n".join(running_status["log_lines"][-40:]))
    else:
        st.success("এই কাজ শেষ হয়ে গেছে। ফলাফল নিচে:")
        _render_result(running_status["result"])

    st.divider()
    st.subheader("নতুন গেম চালাতে চান?")
else:
    st.subheader("গেম সেট করুন")

# ---------------------------------------------------------------------------
disabled_new = bool(running_status and running_status["running"])
if disabled_new:
    st.warning("একটা কাজ এখনো চলছে। নতুন কাজ শুরু করার আগে সেটা শেষ হতে দিন, অথবা উপরে থেকে বন্ধ করুন।")

c1, c2, c3, c4 = st.columns(4)
with c1:
    number_from = st.number_input("নম্বর শুরু (From)", min_value=0, max_value=40, value=1, step=1, disabled=disabled_new)
with c2:
    number_to = st.number_input("নম্বর শেষ (To)", min_value=0, max_value=40, value=25, step=1, disabled=disabled_new)
with c3:
    ticket_size = st.number_input("এক টিকেটে কয়টা নম্বর", min_value=1, max_value=41, value=6, step=1, disabled=disabled_new)
with c4:
    result_size = st.number_input("ড্রয়ে কয়টা নম্বর ওঠে", min_value=1, max_value=41, value=6, step=1, disabled=disabled_new)

st.caption('উদাহরণ: "ঠিক 5 মিললে, কমপক্ষে 1 টা টিকেট" মানে — যেকোনো সম্ভাব্য ড্রয়ে, আপনার টিকেটের মধ্যে অন্তত '
           '১টা টিকেট থাকতেই হবে যেটায় ঠিক ৫টা নম্বর মিলবে।')
max_k = int(min(ticket_size, result_size))
selected_targets = {}
cols = st.columns(min(max_k + 1, 6))
for k in range(max_k + 1):
    with cols[k % len(cols)]:
        v = st.number_input(f"ঠিক {k}টা মিললে, কমপক্ষে কয়টা টিকেট", min_value=0, value=0, step=1,
                             key=f"k{k}", disabled=disabled_new)
        if v > 0:
            selected_targets[k] = int(v)

with st.expander("অ্যাডভান্সড সেটিংস (শুধু দেখার জন্য, অ্যাডমিন ঠিক করে দিয়েছে)"):
    o1, o2, o3 = st.columns(3)
    with o1:
        st.text_input("মোট সময়সীমা", value=("কোনো সময়সীমা নাই" if not config.TIME_LIMIT_SECONDS
                                            else f"{int(config.TIME_LIMIT_SECONDS)} সেকেন্ড"), disabled=True)
    with o2:
        st.number_input("CP-SAT workers", value=int(config.WORKERS), disabled=True)
        st.number_input("NumPy threads", value=int(config.THREADS), disabled=True)
    with o3:
        st.checkbox("CP-SAT exact solver ব্যবহার হবে", value=bool(config.USE_CP_SAT), disabled=True)

if st.button("▶️ অপ্টিমাইজেশন শুরু করুন", type="primary", disabled=disabled_new):
    try:
        validate_game(int(number_from), int(number_to), int(ticket_size), int(result_size))
        if not selected_targets:
            st.error("অন্তত একটা টার্গেট দিন।")
            st.stop()
        cfg = {"from": int(number_from), "to": int(number_to), "ticket": int(ticket_size),
               "result": int(result_size), "targets": selected_targets}
        jobs.start_job(cfg, config.TIME_LIMIT_SECONDS, config.WORKERS, config.THREADS, config.USE_CP_SAT)
        st.rerun()
    except Exception as e:
        st.error(f"সমস্যা হয়েছে: {e}")

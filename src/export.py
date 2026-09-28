"""Save results: tickets.csv, verification.csv, tickets_and_report.xlsx, report.txt, result.json"""
import json
import os

import pandas as pd


def verification_frame(ver):
    rows = []
    for k, s in sorted(ver["stats"].items()):
        rows.append({
            "Exact Match": k, "Minimum": s["min"], "Maximum": s["max"], "Average": round(s["avg"], 4),
            "Worst Result": ",".join(map(str, s["worst_result"])),
            "Best Result": ",".join(map(str, s["best_result"])),
        })
    return pd.DataFrame(rows)


def tickets_frame(tickets):
    if not tickets:
        return pd.DataFrame()
    return pd.DataFrame(tickets, columns=[f"N{i + 1}" for i in range(len(tickets[0]))])


def report_text(out, cfg):
    ver = out.get("verification") or {}
    lines = [
        "UNIVERSAL LOTTERY / COMBINATION OPTIMIZER - REPORT",
        f"Game            : numbers {cfg['from']}..{cfg['to']}, ticket size {cfg['ticket']}, result size {cfg['result']}",
        f"Targets         : {cfg['targets']}",
        f"Solver status   : {out.get('status')}",
        f"Total tickets   : {out.get('objective')}",
        f"Lower bound     : {out.get('lower_bound')}  (proof only if equal to Total tickets)",
        f"Results checked : {ver.get('total_results_checked')}  (ALL possible results, exact)",
        f"Elapsed seconds : {out.get('elapsed_seconds', 0):.1f}",
        "",
    ]
    for k, s in sorted(ver.get("stats", {}).items()):
        lines.append(f"Exact {k}: min={s['min']} max={s['max']} avg={s['avg']:.3f} "
                     f"worst={s['worst_result']} best={s['best_result']}")
    lines.append("")
    for k, t in sorted(ver.get("targets", {}).items()):
        lines.append(f"Target exact-{k} >= {t['required']}: worst-case={t['worst_case']} -> {'PASS' if t['pass'] else 'FAIL'}")
    lines.append(f"ALL TARGETS PASS: {ver.get('all_targets_pass')}")
    return "\n".join(lines)


def save_outputs(out, outdir, cfg):
    os.makedirs(outdir, exist_ok=True)
    tdf = tickets_frame(out.get("tickets", []))
    files = []
    if len(tdf):
        tdf.to_csv(os.path.join(outdir, "tickets.csv"), index=False)
        files.append("tickets.csv")
    if out.get("verification"):
        vdf = verification_frame(out["verification"])
        vdf.to_csv(os.path.join(outdir, "verification.csv"), index=False)
        files.append("verification.csv")
        with pd.ExcelWriter(os.path.join(outdir, "tickets_and_report.xlsx")) as xw:
            tdf.to_excel(xw, sheet_name="Tickets", index=False)
            vdf.to_excel(xw, sheet_name="Verification", index=False)
        files.append("tickets_and_report.xlsx")
    with open(os.path.join(outdir, "report.txt"), "w", encoding="utf-8") as f:
        f.write(report_text(out, cfg))
    files.append("report.txt")
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, **out}, f, default=str)
    files.append("result.json")
    return files

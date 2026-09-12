import os
import sys
import json
import asyncio
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph import build_civiclens_graph

async def analyze_file(pdf_path: str):
    if not os.path.exists(pdf_path):
        print(f"Error: File '{pdf_path}' not found.")
        sys.exit(1)

    print(f"[*] Reading PDF: {pdf_path}...")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    filename = os.path.basename(pdf_path)
    doc_id = f"cli_{filename.replace('.', '_')}"

    app = build_civiclens_graph(interrupt_audit=False)
    initial_state = {
        "document_id": doc_id,
        "filename": filename,
        "raw_bytes": pdf_bytes
    }
    config = {"configurable": {"thread_id": doc_id}}

    print("[*] Executing CivicLens Multi-Agent Pipeline...")
    final_state = await app.ainvoke(initial_state, config=config)

    pages = final_state.get("pages_text", [])
    raw_clauses = final_state.get("raw_clauses", [])
    verified_claims = final_state.get("verified_claims", [])
    report = final_state.get("report", {})

    print("\n" + "=" * 60)
    print(f"  CIVICLENS ANALYSIS REPORT: {filename}")
    print("=" * 60)
    print(f"Pages Ingested: {len(pages)}")
    print(f"Operative Clauses Found: {len(raw_clauses)}")
    print(f"Verified Claims: {len(verified_claims)}")
    print("-" * 60)

    print("\n--- EXTRACTED VERBATIM CLAUSES & VERIFICATION ---")
    for idx, claim in enumerate(verified_claims, 1):
        clause = claim.get("clause", {})
        status = claim.get("status")
        nli = claim.get("nli_score")
        llm_score = claim.get("llm_judge_score")
        verdict = claim.get("llm_judge_verdict")
        typology = clause.get("typology", "unclassified")
        ward = clause.get("ward") or "N/A"
        offsets = f"[{clause.get('char_start')}:{clause.get('char_end')}] (Page {clause.get('page')})"

        print(f"\n[{idx}] Status: {status}")
        print(f"    Text: \"{clause.get('text')}\"")
        print(f"    Typology: {typology} | Ward: {ward} | Offset: {offsets}")
        print(f"    Ensemble Gate: NLI Entailment={nli} | LLM-Judge={verdict} ({llm_score})")

    if report:
        print("\n" + "=" * 60)
        print("  FINAL CIVIC IMPACT REPORT")
        print("=" * 60)
        print(f"Policy Summary:\n  {report.get('policy_summary')}\n")
        print(f"Overall Verdict: {str(report.get('overall_verdict')).upper()}")
        print(f"Impacted Stakeholders: {', '.join(report.get('stakeholders_impacted', []))}")
        
        positives = report.get("positive_impacts", [])
        if positives:
            print("\nPositive Civic Impacts:")
            for p in positives:
                print(f"  + {p}")

        negatives = report.get("negative_impacts", [])
        if negatives:
            print("\nNegative / Restrictive Impacts:")
            for n in negatives:
                print(f"  - {n}")

        risks = report.get("risk_flags", [])
        if risks:
            print("\nIdentified Risk Flags:")
            for r in risks:
                print(f"  ! {r}")

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/analyze_pdf.py <path_to_pdf>")
        sys.exit(1)

    asyncio.run(analyze_file(sys.argv[1]))

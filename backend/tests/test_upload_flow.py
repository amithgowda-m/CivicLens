import asyncio
import httpx
from backend.main import app
from backend.tests.test_checkpoint2 import create_valid_test_pdf

async def test_upload_and_analyze():
    transport = httpx.ASGITransport(app=app)
    pdf_bytes = create_valid_test_pdf()
    files = {"file": ("municipal_order.pdf", pdf_bytes, "application/pdf")}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/api/documents/upload?analyze=true", files=files)
        print("Upload + analyze status:", res.status_code)
        assert res.status_code == 200
        data = res.json()
        print("Doc ID:", data["document_id"])
        print("Pages count:", data["pages_count"])
        print("Raw clauses extracted:", len(data["raw_clauses"]))
        print("First clause:", data["raw_clauses"][0]["text"] if data["raw_clauses"] else None)
        print("Verified claims count:", len(data["verified_claims"]))
        for c in data["verified_claims"]:
            st = c["status"]
            nli = c["nli_score"]
            llm = c["llm_judge_score"]
            txt = c["clause"]["text"][:60]
            print(f"  - [{st}] (NLI: {nli}, LLM: {llm}) -> {txt}...")
        print("Audit pending:", data["audit_pending"])
        print("Report generated:", data["report"] is not None)
        assert data["pages_count"] >= 1
        assert len(data["raw_clauses"]) >= 1

if __name__ == "__main__":
    asyncio.run(test_upload_and_analyze())

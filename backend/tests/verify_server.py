import asyncio
import httpx
from backend.main import app

async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        res_root = await client.get("/")
        print("Root response:", res_root.status_code, res_root.json())
        assert res_root.status_code == 200

        # 2. Sample docs listing
        res_samples = await client.get("/api/samples")
        print("Samples response:", res_samples.status_code, res_samples.json())
        assert res_samples.status_code == 200

        # 3. Document upload endpoint
        res_upload = await client.post("/api/upload")
        print("Upload response:", res_upload.status_code, res_upload.json())
        assert res_upload.status_code == 200
        doc_id = res_upload.json()["document_id"]

        # 4. Evaluation harness endpoint
        res_eval = await client.get("/api/eval")
        print("Eval response:", res_eval.status_code, res_eval.json())
        assert res_eval.status_code == 200
        assert res_eval.json()["status"] == "awaiting_gold_data"
        assert res_eval.json()["system_reliability_score"] is None

        print("--- ALL FASTAPI ENDPOINTS VERIFIED SUCCESSFULLY ---")

if __name__ == "__main__":
    asyncio.run(main())

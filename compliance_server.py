import os
import hmac
import hashlib
import base64
import json
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Set this in Railway environment variables
VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN", "listeraiebaycompliancetoken2024secure1234")

@app.get("/")
def root():
    return {"status": "ok", "service": "Lister AI eBay Compliance"}

@app.get("/ebay/deletion")
async def ebay_challenge(request: Request):
    """
    eBay sends a GET request with challenge_code to verify the endpoint.
    We must respond with the correct hash.
    """
    challenge_code = request.query_params.get("challenge_code", "")
    if not challenge_code:
        return Response(status_code=400)

    # Hash: SHA-256(challenge_code + verification_token + endpoint_url)
    # Hardcode the endpoint URL to ensure exact match with what eBay has registered
    endpoint_url = "https://ebay-compliance-production.up.railway.app/ebay/deletion"

    hash_input = challenge_code + VERIFICATION_TOKEN + endpoint_url
    digest = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    return JSONResponse({"challengeResponse": digest})

@app.post("/ebay/deletion")
async def ebay_deletion(request: Request):
    """
    eBay sends POST requests when a marketplace account is deleted.
    We acknowledge receipt — no user data stored so nothing to delete.
    """
    try:
        body = await request.json()
        print(f"eBay deletion notification received: {json.dumps(body)}")
    except Exception:
        pass
    # Acknowledge with 200 — we don't store eBay user data
    return Response(status_code=200)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

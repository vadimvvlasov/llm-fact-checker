from fastapi import FastAPI
from pydantic import BaseModel

from src.claim_extractor import extract_claims
from src.verifier import verify_claim

app = FastAPI(title="Fact-Checker RAG")


@app.get("/health")
def health():
    return {"status": "ok"}


class VerifyRequest(BaseModel):
    text: str


class ClaimVerdict(BaseModel):
    claim: str
    verdict: str
    source: str | None
    quote: str | None


class VerifyResponse(BaseModel):
    claims: list[ClaimVerdict]


@app.post("/verify")
def verify(request: VerifyRequest) -> VerifyResponse:
    results = []
    for claim in extract_claims(request.text):
        v = verify_claim(claim)
        results.append(ClaimVerdict(claim=claim.text, verdict=v.verdict, source=v.source, quote=v.quote))
    return VerifyResponse(claims=results)

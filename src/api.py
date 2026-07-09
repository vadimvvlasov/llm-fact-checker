from fastapi import FastAPI

app = FastAPI(title="Fact-Checker RAG")


@app.get("/health")
def health():
    return {"status": "ok"}

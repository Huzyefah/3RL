from fastapi import FastAPI

app = FastAPI(title="finpay-sim", docs_url=None, redoc_url=None)


@app.get("/health")
@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok", "service": "finpay-sim"}

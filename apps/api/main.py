from fastapi import FastAPI

app = FastAPI(
    title="EasyDev AI Platform",
    version="1.0.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "EasyDev AI Platform is running"}
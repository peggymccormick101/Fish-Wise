from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import searches

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FishWise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(searches.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

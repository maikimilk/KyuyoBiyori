from fastapi import FastAPI
from app.routers import payslip, settings
from app.database import engine
from app import models
import logging
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
print("DEBUG GEMINI_API_KEY:", os.getenv("GEMINI_API_KEY"))

# Ensure application logs show informative messages
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s"
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="KyuyoBiyori API")

app.include_router(payslip.router, prefix="/api/payslip", tags=["payslip"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

@app.get("/")
def read_root():
    return {"message": "KyuyoBiyori API"}

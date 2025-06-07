from fastapi import FastAPI
from app.routers import payslip, settings
from app.database import engine
from app import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="KyuyoBiyori API")

app.include_router(payslip.router, prefix="/api/payslip", tags=["payslip"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

@app.get("/")
def read_root():
    return {"message": "KyuyoBiyori API"}

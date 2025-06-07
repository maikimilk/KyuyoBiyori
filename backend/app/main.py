from fastapi import FastAPI
from .routers import payslip, settings
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="KyuyoBiyori API")

app.include_router(payslip.router, prefix="/api/payslip", tags=["payslip"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

@app.get("/")
def read_root():
    return {"message": "KyuyoBiyori API"}

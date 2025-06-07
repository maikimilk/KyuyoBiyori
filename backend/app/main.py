from fastapi import FastAPI
from .routers import payslip
from .database import engine
from . import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="KyuyoBiyori API")

app.include_router(payslip.router, prefix="/api/payslip", tags=["payslip"])

@app.get("/")
def read_root():
    return {"message": "KyuyoBiyori API"}

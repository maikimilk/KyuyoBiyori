from fastapi import FastAPI, UploadFile, File, Depends
from .routers import payslip

app = FastAPI(title="KyuyoBiyori API")

app.include_router(payslip.router, prefix="/api/payslip", tags=["payslip"])

@app.get("/")
def read_root():
    return {"message": "KyuyoBiyori API"}

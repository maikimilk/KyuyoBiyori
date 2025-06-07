from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas import PayslipCreate, Payslip
from .. import models, database

router = APIRouter()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post('/upload', response_model=Payslip)
async def upload_payslip(file: UploadFile = File(...), db: Session = Depends(get_db)):
    payslip = models.Payslip(filename=file.filename)
    db.add(payslip)
    db.commit()
    db.refresh(payslip)
    return payslip

@router.get('/', response_model=list[Payslip])
def list_payslips(db: Session = Depends(get_db)):
    return db.query(models.Payslip).all()

@router.get('/{payslip_id}', response_model=Payslip)
def get_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail='Not found')
    return payslip

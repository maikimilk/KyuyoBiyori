from fastapi import APIRouter, UploadFile, File
from ..schemas import PayslipCreate, Payslip

router = APIRouter()

@router.post('/upload', response_model=Payslip)
async def upload_payslip(file: UploadFile = File(...)):
    """Stub endpoint for payslip upload."""
    # This is a placeholder implementation
    return Payslip(id=1, filename=file.filename)

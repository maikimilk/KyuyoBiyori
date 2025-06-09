from pydantic import BaseModel
from typing import Optional

class Item(BaseModel):
    name: str
    amount: int
    category: Optional[str] = None

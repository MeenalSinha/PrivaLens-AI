from typing import Optional, List
from pydantic import BaseModel


class MitigateRequest(BaseModel):
    dataset_id: str
    mitigations: Optional[List[dict]] = None  # if omitted, use recommended mitigations


class RetestRequest(BaseModel):
    dataset_id: str
    mitigated_dataset_id: str


class DemoRunRequest(BaseModel):
    preset: str = "healthcare"
    n: int = 500

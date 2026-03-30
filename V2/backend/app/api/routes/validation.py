"""Validierungs-Routen."""
from fastapi import APIRouter, HTTPException
from app.schemas.validation import ValidationRequest, ValidationResponse

router = APIRouter()


@router.post("/", response_model=ValidationResponse)
async def validate_scenario(request: ValidationRequest):
    """Validiert ein Szenario gegen MITRE ATT&CK."""
    from app.services.validation_service import validation_service

    return await validation_service.validate(request)

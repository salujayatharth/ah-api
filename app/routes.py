from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from httpx import HTTPStatusError

from app.client import AHClient, TOKEN_FILE
from app.config import get_settings, Settings

router = APIRouter(prefix="/receipts", tags=["receipts"])


class AuthCodeRequest(BaseModel):
    code: str


def get_client(settings: Settings = Depends(get_settings)) -> AHClient:
    return AHClient(settings)


@router.post("/auth")
async def authenticate(request: AuthCodeRequest, client: AHClient = Depends(get_client)):
    """Exchange authorization code for tokens."""
    try:
        result = await client.exchange_code(request.code)
        return {"status": "authenticated", "expires_in": result.get("expires_in")}
    except HTTPStatusError as e:
        detail = f"AH API error: {e.response.status_code}"
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text or detail
        raise HTTPException(status_code=e.response.status_code, detail=detail)


@router.delete("/auth")
async def logout():
    """Clear stored tokens."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    AHClient._instance = None
    return {"status": "logged out"}


@router.get("/auth/status")
async def auth_status(client: AHClient = Depends(get_client)):
    """Check authentication status."""
    return {"authenticated": client.is_authenticated()}


@router.get("")
async def list_receipts(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    client: AHClient = Depends(get_client),
):
    """List all receipts for the authenticated user."""
    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated. POST code to /receipts/auth first.")
    try:
        return await client.get_receipts(offset=offset, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{receipt_id}")
async def get_receipt(receipt_id: str, client: AHClient = Depends(get_client)):
    """Get detailed receipt by ID."""
    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated. POST code to /receipts/auth first.")
    try:
        return await client.get_receipt(receipt_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{receipt_id}/pdf")
async def get_receipt_pdf(receipt_id: str, client: AHClient = Depends(get_client)):
    """Get receipt PDF URL."""
    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated. POST code to /receipts/auth first.")
    try:
        return await client.get_receipt_pdf(receipt_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

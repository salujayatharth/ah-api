from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from httpx import HTTPStatusError
from sqlalchemy.orm import Session

from app.client import AHClient, TOKEN_FILE
from app.config import get_settings, Settings
from app.database import get_db
from app.models import SyncResultResponse, SyncedReceiptSummary, SyncError
from app.sync_service import SyncService

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


@router.post("/sync", response_model=SyncResultResponse)
async def sync_receipts(
    full_sync: bool = Query(False, description="If true, sync all receipts. Otherwise stop after finding 3 consecutive existing."),
    client: AHClient = Depends(get_client),
    db: Session = Depends(get_db),
):
    """
    Sync receipts from AH API to local database.

    Fetches receipts from the AH API and stores them in the local SQLite database.
    By default, performs incremental sync (stops after finding 3 consecutive existing receipts).
    Use full_sync=true to sync all receipts.
    """
    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated. POST code to /receipts/auth first.")

    try:
        sync_service = SyncService(client=client, db=db)
        result = await sync_service.sync_receipts(full_sync=full_sync)

        # Determine status
        if result.error_count == 0:
            status = "success"
        elif result.synced_count > 0:
            status = "partial"
        else:
            status = "error"

        return SyncResultResponse(
            status=status,
            synced_count=result.synced_count,
            skipped_count=result.skipped_count,
            error_count=result.error_count,
            total_in_db=sync_service.get_total_receipts_count(),
            synced_receipts=[
                SyncedReceiptSummary(**r) for r in result.synced_receipts
            ],
            errors=[SyncError(**e) for e in result.errors],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import httpx
import json
import os
import time
from pathlib import Path
from typing import Optional
from app.config import Settings

DATA_DIR = os.environ.get("DATA_DIR", str(Path(__file__).parent.parent))
TOKEN_FILE = Path(DATA_DIR) / ".tokens.json"


class AHClient:
    _instance: Optional["AHClient"] = None

    def __new__(cls, settings: Settings):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, settings: Settings):
        if self._initialized:
            return
        self._initialized = True
        self.settings = settings
        self.base_url = settings.ah_base_url
        self.headers = {
            "User-Agent": settings.ah_user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[float] = None
        self._load_tokens()

    def _load_tokens(self):
        if TOKEN_FILE.exists():
            try:
                data = json.loads(TOKEN_FILE.read_text())
                self._access_token = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                self._token_expiry = data.get("expiry")
            except (json.JSONDecodeError, IOError):
                pass

    def _save_tokens(self):
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expiry": self._token_expiry,
        }
        TOKEN_FILE.write_text(json.dumps(data))

    def _get_auth_headers(self) -> dict:
        headers = self.headers.copy()
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def _is_token_expired(self) -> bool:
        if not self._token_expiry:
            return False
        return time.time() > self._token_expiry - 60

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/mobile-auth/v1/auth/token",
                headers=self.headers,
                json={"clientId": "appie", "code": code},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 7200)
            self._token_expiry = time.time() + expires_in
            self._save_tokens()
            return data

    async def refresh_token(self) -> dict:
        if not self._refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/mobile-auth/v1/auth/token/refresh",
                headers=self.headers,
                json={"clientId": "appie", "refreshToken": self._refresh_token},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 7200)
            self._token_expiry = time.time() + expires_in
            self._save_tokens()
            return data

    async def _ensure_valid_token(self):
        if self._is_token_expired() and self._refresh_token:
            await self.refresh_token()

    async def _graphql(self, query: str, variables: dict = None) -> dict:
        """Execute GraphQL query with auto-refresh on 401."""
        await self._ensure_valid_token()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/graphql",
                headers=self._get_auth_headers(),
                json=payload,
            )

            if response.status_code == 401 and self._refresh_token:
                await self.refresh_token()
                response = await client.post(
                    f"{self.base_url}/graphql",
                    headers=self._get_auth_headers(),
                    json=payload,
                )

            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                raise Exception(result["errors"])

            return result.get("data", {})

    async def get_receipts(self, offset: int = 0, limit: int = 20) -> dict:
        """Get list of receipts via GraphQL."""
        query = """
        query GetReceipts($pagination: OffsetLimitPagination!) {
            posReceiptsPage(pagination: $pagination) {
                pagination {
                    offset
                    limit
                    totalElements
                }
                posReceipts {
                    id
                    dateTime
                    totalAmount {
                        amount
                        formatted
                    }
                    storeAddress {
                        city
                        street
                    }
                }
            }
        }
        """
        variables = {"pagination": {"offset": offset, "limit": limit}}
        data = await self._graphql(query, variables)
        return data.get("posReceiptsPage", {})

    async def get_receipt(self, receipt_id: str) -> dict:
        """Get detailed receipt by ID via GraphQL."""
        query = """
        query GetReceipt($id: String!) {
            posReceiptDetails(id: $id) {
                id
                memberId
                storeInfo
                products {
                    id
                    name
                    quantity
                    price {
                        amount
                        formatted
                    }
                    amount {
                        amount
                        formatted
                    }
                }
                subtotalProducts {
                    amount {
                        amount
                        formatted
                    }
                }
                discounts {
                    type
                    name
                    amount {
                        amount
                        formatted
                    }
                }
                discountTotal {
                    amount
                    formatted
                }
                total {
                    amount
                    formatted
                }
                payments {
                    method
                    amount {
                        amount
                        formatted
                    }
                }
                transaction {
                    dateTime
                    store
                    lane
                    id
                }
                address {
                    street
                    city
                    postalCode
                }
                vat {
                    levels {
                        percentage
                        amount {
                            amount
                            formatted
                        }
                    }
                    total {
                        amount {
                            amount
                            formatted
                        }
                    }
                }
            }
        }
        """
        variables = {"id": receipt_id}
        data = await self._graphql(query, variables)
        return data.get("posReceiptDetails", {})

    async def get_receipt_pdf(self, receipt_id: str) -> dict:
        """Get receipt PDF URL."""
        query = """
        query GetReceiptPdf($id: String!) {
            posReceiptPdf(id: $id) {
                url
            }
        }
        """
        variables = {"id": receipt_id}
        data = await self._graphql(query, variables)
        return data.get("posReceiptPdf", {})

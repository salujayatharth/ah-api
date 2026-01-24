import asyncio
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.client import AHClient
from app.db_models import Receipt, ReceiptDiscount, ReceiptItem, ReceiptVAT


class SyncResult:
    """Tracks sync operation results."""

    def __init__(self):
        self.synced_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.synced_receipts: list[dict] = []
        self.errors: list[dict] = []

    def add_synced(self, receipt_id: str, transaction_moment: datetime, total_amount: float, store_name: Optional[str]):
        self.synced_count += 1
        self.synced_receipts.append({
            "id": receipt_id,
            "transaction_moment": transaction_moment,
            "total_amount": total_amount,
            "store_name": store_name,
        })

    def add_skipped(self):
        self.skipped_count += 1

    def add_error(self, receipt_id: str, error: str):
        self.error_count += 1
        self.errors.append({"receipt_id": receipt_id, "error": error})


def map_receipt_to_db(receipt_data: dict) -> Receipt:
    """Map API receipt response to database Receipt model."""
    transaction = receipt_data.get("transaction", {}) or {}
    address = receipt_data.get("address", {}) or {}

    # Parse transaction datetime
    dt_str = transaction.get("dateTime")
    transaction_moment = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.utcnow()

    # Get total amount
    total = receipt_data.get("total", {})
    total_amount = total.get("amount", 0) if isinstance(total, dict) else 0

    # Get subtotal
    subtotal_products = receipt_data.get("subtotalProducts", {}) or {}
    subtotal_amount = subtotal_products.get("amount", {}) or {}
    subtotal = subtotal_amount.get("amount") if isinstance(subtotal_amount, dict) else None

    # Get discount total
    discount_total_data = receipt_data.get("discountTotal", {}) or {}
    discount_total = discount_total_data.get("amount") if isinstance(discount_total_data, dict) else None

    # Get payment method from first payment
    payments = receipt_data.get("payments", []) or []
    payment_method = payments[0].get("method") if payments else None

    # Get store name - construct from address (storeInfo only contains store ID)
    # Format: "Albert Heijn {street}" e.g. "Albert Heijn Frederiksplein"
    street = address.get("street") if address else None
    if street:
        store_name = f"Albert Heijn {street}"
    else:
        # Fallback to storeInfo if no address
        store_info = receipt_data.get("storeInfo")
        if isinstance(store_info, list):
            store_name = store_info[0] if store_info else None
        else:
            store_name = store_info

    # Create Receipt object
    receipt = Receipt(
        id=receipt_data.get("id"),
        transaction_moment=transaction_moment,
        total_amount=total_amount,
        subtotal=subtotal,
        discount_total=discount_total,
        member_id=receipt_data.get("memberId"),
        store_id=transaction.get("store"),
        store_name=store_name,
        store_street=address.get("street") if address else None,
        store_city=address.get("city") if address else None,
        store_postal_code=address.get("postalCode") if address else None,
        checkout_lane=transaction.get("lane"),
        payment_method=payment_method,
    )

    return receipt


def map_items_to_db(receipt_id: str, products: list) -> list[ReceiptItem]:
    """Map API products to database ReceiptItem models."""
    items = []
    if not products:
        return items
    for product in products:
        price_data = product.get("price", {})
        amount_data = product.get("amount", {})

        item = ReceiptItem(
            receipt_id=receipt_id,
            product_id=product.get("id"),
            product_name=product.get("name", "Unknown"),
            quantity=product.get("quantity", 1),
            unit_price=price_data.get("amount") if isinstance(price_data, dict) else None,
            line_total=amount_data.get("amount") if isinstance(amount_data, dict) else None,
        )
        items.append(item)
    return items


def map_discounts_to_db(receipt_id: str, discounts: list) -> list[ReceiptDiscount]:
    """Map API discounts to database ReceiptDiscount models."""
    discount_items = []
    if not discounts:
        return discount_items
    for discount in discounts:
        amount_data = discount.get("amount", {})
        discount_amount = amount_data.get("amount") if isinstance(amount_data, dict) else 0

        discount_item = ReceiptDiscount(
            receipt_id=receipt_id,
            discount_type=discount.get("type"),
            discount_name=discount.get("name"),
            discount_amount=discount_amount,
        )
        discount_items.append(discount_item)
    return discount_items


def map_vat_to_db(receipt_id: str, vat_data: dict) -> list[ReceiptVAT]:
    """Map API VAT data to database ReceiptVAT models."""
    vat_entries = []
    if not vat_data:
        return vat_entries
    levels = vat_data.get("levels", []) or []

    for level in levels:
        amount_data = level.get("amount", {})
        vat_amount = amount_data.get("amount") if isinstance(amount_data, dict) else 0

        vat_entry = ReceiptVAT(
            receipt_id=receipt_id,
            vat_percentage=level.get("percentage", 0),
            vat_amount=vat_amount,
        )
        vat_entries.append(vat_entry)
    return vat_entries


class SyncService:
    """Service for syncing receipts from AH API to local database."""

    def __init__(
        self,
        client: AHClient,
        db: Session,
        consecutive_existing_threshold: int = 3,
        batch_size: int = 50,
        rate_limit_delay: float = 0.5,
    ):
        self.client = client
        self.db = db
        self.consecutive_existing_threshold = consecutive_existing_threshold
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay

    def get_existing_receipt_ids(self) -> set[str]:
        """Get all existing receipt IDs from the database."""
        result = self.db.query(Receipt.id).all()
        return {r[0] for r in result}

    def get_total_receipts_count(self) -> int:
        """Get total number of receipts in database."""
        return self.db.query(Receipt).count()

    async def sync_receipts(self, full_sync: bool = False) -> SyncResult:
        """
        Sync receipts from AH API to local database.

        Args:
            full_sync: If True, process all receipts. If False, stop after
                      finding consecutive_existing_threshold existing receipts.

        Returns:
            SyncResult with counts and details of synced receipts.
        """
        result = SyncResult()
        existing_ids = self.get_existing_receipt_ids()
        consecutive_existing = 0
        offset = 0

        while True:
            # Fetch batch of receipt summaries from API
            try:
                receipts_page = await self.client.get_receipts(offset=offset, limit=self.batch_size)
                receipts = receipts_page.get("posReceipts", [])
            except Exception as e:
                result.add_error("batch_fetch", f"Failed to fetch receipts at offset {offset}: {str(e)}")
                break

            if not receipts:
                break

            for receipt_summary in receipts:
                receipt_id = receipt_summary.get("id")
                if not receipt_id:
                    continue

                # Check if receipt already exists
                if receipt_id in existing_ids:
                    result.add_skipped()
                    consecutive_existing += 1

                    # For incremental sync, stop after finding enough consecutive existing
                    if not full_sync and consecutive_existing >= self.consecutive_existing_threshold:
                        return result
                    continue

                # Reset consecutive counter when we find a new receipt
                consecutive_existing = 0

                # Fetch full receipt details
                try:
                    # Rate limiting delay
                    await asyncio.sleep(self.rate_limit_delay)

                    receipt_details = await self.client.get_receipt(receipt_id)
                    if not receipt_details:
                        result.add_error(receipt_id, "Empty receipt details returned")
                        continue

                    # Map and insert receipt
                    self._insert_receipt(receipt_details, result)

                except Exception as e:
                    result.add_error(receipt_id, str(e))
                    continue

            # Move to next batch
            offset += self.batch_size

            # Rate limiting delay between batches
            await asyncio.sleep(self.rate_limit_delay)

            # Check if we've processed all receipts
            pagination = receipts_page.get("pagination", {})
            total_elements = pagination.get("totalElements", 0)
            if offset >= total_elements:
                break

        return result

    def _insert_receipt(self, receipt_data: dict, result: SyncResult):
        """Insert a receipt and its related data into the database."""
        receipt_id = receipt_data.get("id")

        try:
            # Map main receipt
            receipt = map_receipt_to_db(receipt_data)

            # Map related items
            items = map_items_to_db(receipt_id, receipt_data.get("products", []))
            discounts = map_discounts_to_db(receipt_id, receipt_data.get("discounts", []))
            vat_entries = map_vat_to_db(receipt_id, receipt_data.get("vat", {}))

            # Add all to session
            self.db.add(receipt)
            for item in items:
                self.db.add(item)
            for discount in discounts:
                self.db.add(discount)
            for vat_entry in vat_entries:
                self.db.add(vat_entry)

            # Commit
            self.db.commit()

            # Track success
            result.add_synced(
                receipt_id=receipt_id,
                transaction_moment=receipt.transaction_moment,
                total_amount=receipt.total_amount,
                store_name=receipt.store_name,
            )

        except Exception as e:
            self.db.rollback()
            result.add_error(receipt_id, f"Database error: {str(e)}")

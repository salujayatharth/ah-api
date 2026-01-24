"""API routes for AH Product information."""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.db_models import ProductCache
from app.product_client import AHProductClient, get_product_client
from app.product_models import (
    ProductDetail,
    ProductSearchResponse,
    ProductCacheEntry,
)

router = APIRouter(prefix="/products", tags=["products"])

# Cache duration in days
CACHE_DURATION_DAYS = 30


def _is_cache_valid(cached: ProductCache) -> bool:
    """Check if a cache entry is still valid."""
    if not cached or not cached.expires_at:
        return False
    expires_at = cached.expires_at
    # Handle both naive and aware datetimes from DB
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def get_client(settings: Settings = Depends(get_settings)) -> AHProductClient:
    """Get product client dependency."""
    return get_product_client(settings)


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: str,
    refresh: bool = Query(False, description="Force refresh from AH API"),
    client: AHProductClient = Depends(get_client),
    db: Session = Depends(get_db),
):
    """
    Get product details by product ID.

    Returns cached data if available and not expired, otherwise fetches from AH API.
    Use refresh=true to force a fresh fetch from AH API.
    """
    # Check cache first (unless refresh requested)
    if not refresh:
        cached = db.query(ProductCache).filter(ProductCache.product_id == product_id).first()
        if _is_cache_valid(cached):
            return _cache_to_product_detail(cached)

    # Fetch from AH API
    try:
        product = await client.get_product(product_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from AH API: {str(e)}")

    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    # Update cache
    _update_cache(db, product)

    return product


@router.get("/webshop/{webshop_id}", response_model=ProductDetail)
async def get_product_by_webshop_id(
    webshop_id: str,
    refresh: bool = Query(False, description="Force refresh from AH API"),
    client: AHProductClient = Depends(get_client),
    db: Session = Depends(get_db),
):
    """
    Get product details by webshop ID.

    The webshop ID is the 'wi' prefixed ID used in AH URLs (e.g., wi193679).
    """
    # Check cache first
    if not refresh:
        cached = db.query(ProductCache).filter(ProductCache.webshop_id == webshop_id).first()
        if _is_cache_valid(cached):
            return _cache_to_product_detail(cached)

    # Fetch from AH API
    try:
        product = await client.get_product(webshop_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from AH API: {str(e)}")

    if not product:
        raise HTTPException(status_code=404, detail=f"Product {webshop_id} not found")

    # Update cache
    _update_cache(db, product)

    return product


@router.get("/barcode/{barcode}", response_model=ProductDetail)
async def get_product_by_barcode(
    barcode: str,
    client: AHProductClient = Depends(get_client),
    db: Session = Depends(get_db),
):
    """
    Get product details by barcode (EAN/GTIN).

    Looks up the product using the barcode and returns full details.
    """
    try:
        product = await client.get_product_by_barcode(barcode)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from AH API: {str(e)}")

    if not product:
        raise HTTPException(status_code=404, detail=f"Product with barcode {barcode} not found")

    # Update cache
    _update_cache(db, product)

    return product


@router.get("/search/", response_model=ProductSearchResponse)
async def search_products(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    sort: str = Query("RELEVANCE", description="Sort order: RELEVANCE, PRICE_ASC, PRICE_DESC"),
    client: AHProductClient = Depends(get_client),
):
    """
    Search for products by name or keyword.

    Returns paginated results sorted by relevance (default) or price.
    """
    if sort not in ["RELEVANCE", "PRICE_ASC", "PRICE_DESC"]:
        raise HTTPException(status_code=400, detail="Invalid sort option")

    try:
        results = await client.search_products(query=q, page=page, size=size, sort=sort)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to search AH API: {str(e)}")

    return results


@router.get("/batch/", response_model=list[ProductCacheEntry])
async def get_products_batch(
    ids: str = Query(..., description="Comma-separated product IDs"),
    client: AHProductClient = Depends(get_client),
    db: Session = Depends(get_db),
):
    """
    Get multiple products by their IDs.

    Returns cached data where available, fetches missing products from AH API.
    Products not found are silently skipped.
    """
    product_ids = [pid.strip() for pid in ids.split(",") if pid.strip()]

    if not product_ids:
        raise HTTPException(status_code=400, detail="No product IDs provided")

    if len(product_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 products per request")

    results = []
    now = datetime.now(timezone.utc)

    # Check cache for all products
    cached_products = (
        db.query(ProductCache)
        .filter(ProductCache.product_id.in_(product_ids))
        .all()
    )
    cached_map = {c.product_id: c for c in cached_products}

    for pid in product_ids:
        cached = cached_map.get(pid)

        # Use cache if valid
        if _is_cache_valid(cached):
            results.append(_cache_to_entry(cached))
            continue

        # Fetch from API
        try:
            product = await client.get_product(pid)
            if product:
                _update_cache(db, product)
                results.append(ProductCacheEntry(
                    product_id=product.product_id,
                    webshop_id=product.webshop_id,
                    title=product.title,
                    brand=product.brand,
                    category=product.category,
                    price=product.price.amount if product.price else None,
                    unit_size=product.unit_size,
                    image_url=product.images[0].url if product.images else None,
                    fetched_at=now,
                    raw_json=product.raw_data,
                ))
        except Exception:
            # Skip products that fail to fetch
            pass

    return results


@router.get("/cache/stats")
async def get_cache_stats(db: Session = Depends(get_db)):
    """Get product cache statistics."""
    all_cached = db.query(ProductCache).all()
    total = len(all_cached)
    valid = sum(1 for c in all_cached if _is_cache_valid(c))
    expired = total - valid

    return {
        "total_cached": total,
        "valid": valid,
        "expired": expired,
        "cache_duration_days": CACHE_DURATION_DAYS,
    }


@router.delete("/cache/expired")
async def clear_expired_cache(db: Session = Depends(get_db)):
    """Clear expired cache entries."""
    all_cached = db.query(ProductCache).all()
    deleted = 0
    for cached in all_cached:
        if not _is_cache_valid(cached):
            db.delete(cached)
            deleted += 1
    db.commit()

    return {"deleted": deleted}


def _update_cache(db: Session, product: ProductDetail):
    """Update or create cache entry for a product."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=CACHE_DURATION_DAYS)

    # Check if exists
    existing = db.query(ProductCache).filter(ProductCache.product_id == product.product_id).first()

    if existing:
        existing.webshop_id = product.webshop_id
        existing.title = product.title
        existing.brand = product.brand
        existing.category = product.category
        existing.subcategory = product.subcategory
        existing.price = product.price.amount if product.price else None
        existing.unit_size = product.unit_size
        existing.image_url = product.images[0].url if product.images else None
        existing.description = product.description
        existing.raw_json = json.dumps(product.raw_data) if product.raw_data else None
        existing.fetched_at = now
        existing.expires_at = expires
    else:
        cache_entry = ProductCache(
            product_id=product.product_id,
            webshop_id=product.webshop_id,
            title=product.title,
            brand=product.brand,
            category=product.category,
            subcategory=product.subcategory,
            price=product.price.amount if product.price else None,
            unit_size=product.unit_size,
            image_url=product.images[0].url if product.images else None,
            description=product.description,
            raw_json=json.dumps(product.raw_data) if product.raw_data else None,
            fetched_at=now,
            expires_at=expires,
        )
        db.add(cache_entry)

    db.commit()


def _cache_to_product_detail(cached: ProductCache) -> ProductDetail:
    """Convert cache entry to ProductDetail."""
    from app.product_models import ProductPrice, ProductImage

    raw_data = None
    if cached.raw_json:
        try:
            raw_data = json.loads(cached.raw_json)
        except json.JSONDecodeError:
            pass

    price = None
    if cached.price is not None:
        price = ProductPrice(amount=cached.price, unit_size=cached.unit_size)

    images = []
    if cached.image_url:
        images = [ProductImage(url=cached.image_url)]

    return ProductDetail(
        product_id=cached.product_id,
        webshop_id=cached.webshop_id or "",
        title=cached.title,
        brand=cached.brand,
        category=cached.category,
        subcategory=cached.subcategory,
        description=cached.description,
        price=price,
        unit_size=cached.unit_size,
        images=images,
        raw_data=raw_data,
    )


def _cache_to_entry(cached: ProductCache) -> ProductCacheEntry:
    """Convert cache entry to ProductCacheEntry model."""
    raw_data = None
    if cached.raw_json:
        try:
            raw_data = json.loads(cached.raw_json)
        except json.JSONDecodeError:
            pass

    return ProductCacheEntry(
        product_id=cached.product_id,
        webshop_id=cached.webshop_id or "",
        title=cached.title,
        brand=cached.brand,
        category=cached.category,
        price=cached.price,
        unit_size=cached.unit_size,
        image_url=cached.image_url,
        fetched_at=cached.fetched_at,
        raw_json=raw_data,
    )

"""Models for AH Product API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProductPrice(BaseModel):
    """Product price information."""
    amount: float
    unit_size: Optional[str] = None
    unit_price_description: Optional[str] = None


class ProductImage(BaseModel):
    """Product image URLs."""
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


class NutritionInfo(BaseModel):
    """Nutritional information per serving."""
    energy_kj: Optional[float] = None
    energy_kcal: Optional[float] = None
    fat: Optional[float] = None
    saturated_fat: Optional[float] = None
    carbohydrates: Optional[float] = None
    sugars: Optional[float] = None
    fiber: Optional[float] = None
    protein: Optional[float] = None
    salt: Optional[float] = None


class ProductDetail(BaseModel):
    """Full product information from AH API."""
    product_id: str
    webshop_id: str
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    price: Optional[ProductPrice] = None
    unit_size: Optional[str] = None
    images: list[ProductImage] = []
    nutrition: Optional[NutritionInfo] = None
    is_available: bool = True
    is_bonus: bool = False
    bonus_price: Optional[float] = None
    raw_data: Optional[dict] = None


class ProductSearchResult(BaseModel):
    """Single product in search results."""
    product_id: str
    webshop_id: str
    title: str
    brand: Optional[str] = None
    price: Optional[float] = None
    unit_size: Optional[str] = None
    image_url: Optional[str] = None
    is_bonus: bool = False


class ProductSearchResponse(BaseModel):
    """Response from product search."""
    query: str
    total_results: int
    page: int
    page_size: int
    products: list[ProductSearchResult]


class ProductCacheEntry(BaseModel):
    """Cached product entry."""
    product_id: str
    webshop_id: str
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    unit_size: Optional[str] = None
    image_url: Optional[str] = None
    fetched_at: datetime
    raw_json: Optional[dict] = None

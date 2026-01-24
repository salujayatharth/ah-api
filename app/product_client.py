"""AH Product API Client - No user authentication required."""
import httpx
import time
from typing import Optional
from app.config import Settings
from app.product_models import (
    ProductDetail,
    ProductPrice,
    ProductImage,
    NutritionInfo,
    ProductSearchResult,
    ProductSearchResponse,
)


class AHProductClient:
    """Client for AH Product API using anonymous authentication."""

    _instance: Optional["AHProductClient"] = None

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
            "X-Application": "AHWEBSHOP",
        }
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None

    def _is_token_expired(self) -> bool:
        if not self._token_expiry:
            return True
        return time.time() > self._token_expiry - 60

    async def _get_anonymous_token(self) -> str:
        """Get anonymous access token for product API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/mobile-auth/v1/auth/token/anonymous",
                headers=self.headers,
                json={"clientId": "appie"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in
            return self._access_token

    async def _ensure_valid_token(self):
        """Ensure we have a valid anonymous token."""
        if self._is_token_expired():
            await self._get_anonymous_token()

    def _get_auth_headers(self) -> dict:
        headers = self.headers.copy()
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def get_product(self, product_id: str) -> Optional[ProductDetail]:
        """
        Get product details by product ID.

        Args:
            product_id: The webshop product ID (numeric ID from receipts)

        Returns:
            ProductDetail or None if not found
        """
        await self._ensure_valid_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/mobile-services/product/detail/v4/fir/{product_id}",
                headers=self._get_auth_headers(),
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            return self._parse_product_detail(data)

    async def search_products(
        self,
        query: str,
        page: int = 0,
        size: int = 20,
        sort: str = "RELEVANCE",
    ) -> ProductSearchResponse:
        """
        Search for products by query.

        Args:
            query: Search query string
            page: Page number (0-indexed)
            size: Results per page
            sort: Sort order (RELEVANCE, PRICE_ASC, PRICE_DESC)

        Returns:
            ProductSearchResponse with results
        """
        await self._ensure_valid_token()

        params = {
            "query": query,
            "page": page,
            "size": size,
            "sortOn": sort,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/mobile-services/product/search/v2",
                headers=self._get_auth_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_search_response(data, query, page, size)

    async def get_product_by_barcode(self, barcode: str) -> Optional[ProductDetail]:
        """
        Get product by barcode/GTIN.

        Args:
            barcode: Product barcode (EAN/GTIN)

        Returns:
            ProductDetail or None if not found
        """
        await self._ensure_valid_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/mobile-services/product/search/v1/gtin/{barcode}",
                headers=self._get_auth_headers(),
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # GTIN endpoint might return search results or direct product
            if "products" in data and data["products"]:
                product_data = data["products"][0]
                product_id = str(product_data.get("webshopId", ""))
                if product_id:
                    return await self.get_product(product_id)

            return self._parse_product_detail(data)

    def _parse_product_detail(self, data: dict) -> ProductDetail:
        """Parse raw API response into ProductDetail model."""
        # Handle nested structure - product might be under 'productCard' or directly
        product = data.get("productCard", data)

        # Extract price info - can be a float or a dict
        price_info = product.get("priceBeforeBonus") or product.get("price")
        price = None
        if price_info is not None:
            if isinstance(price_info, (int, float)):
                # Direct price value
                price = ProductPrice(
                    amount=float(price_info),
                    unit_size=product.get("salesUnitSize") or product.get("unitSize"),
                    unit_price_description=product.get("unitPriceDescription"),
                )
            elif isinstance(price_info, dict):
                # Nested price object
                price = ProductPrice(
                    amount=price_info.get("now", price_info.get("amount", 0)),
                    unit_size=product.get("salesUnitSize") or product.get("unitSize"),
                    unit_price_description=price_info.get("unitPriceDescription"),
                )

        # Extract images
        images = []
        image_data = product.get("images", [])
        if isinstance(image_data, list):
            for img in image_data:
                if isinstance(img, dict):
                    images.append(ProductImage(
                        url=img.get("url", ""),
                        width=img.get("width"),
                        height=img.get("height"),
                    ))
                elif isinstance(img, str):
                    images.append(ProductImage(url=img))

        # Extract nutrition if available
        nutrition = None
        nutrition_data = product.get("nutritionInfo") or product.get("nutrition", {})
        if nutrition_data:
            nutrition = NutritionInfo(
                energy_kj=self._get_nutrition_value(nutrition_data, "energyKj"),
                energy_kcal=self._get_nutrition_value(nutrition_data, "energyKcal"),
                fat=self._get_nutrition_value(nutrition_data, "fat"),
                saturated_fat=self._get_nutrition_value(nutrition_data, "saturatedFat"),
                carbohydrates=self._get_nutrition_value(nutrition_data, "carbohydrates"),
                sugars=self._get_nutrition_value(nutrition_data, "sugars"),
                fiber=self._get_nutrition_value(nutrition_data, "fiber"),
                protein=self._get_nutrition_value(nutrition_data, "protein"),
                salt=self._get_nutrition_value(nutrition_data, "salt"),
            )

        # Get bonus info
        is_bonus = product.get("isBonus", False) or product.get("bonus", False)
        bonus_price = None
        if is_bonus:
            bonus_data = product.get("bonusPrice") or product.get("price", {})
            bonus_price = bonus_data.get("now") or bonus_data.get("amount")

        return ProductDetail(
            product_id=str(product.get("hqId", product.get("id", ""))),
            webshop_id=str(product.get("webshopId", "")),
            title=product.get("title", product.get("name", "")),
            brand=product.get("brand"),
            category=product.get("mainCategory") or product.get("category"),
            subcategory=product.get("subCategory"),
            description=product.get("description") or product.get("productDescription"),
            price=price,
            unit_size=product.get("unitSize") or product.get("salesUnitSize"),
            images=images,
            nutrition=nutrition,
            is_available=product.get("isAvailable", True),
            is_bonus=is_bonus,
            bonus_price=bonus_price,
            raw_data=data,
        )

    def _parse_search_response(
        self, data: dict, query: str, page: int, size: int
    ) -> ProductSearchResponse:
        """Parse search API response."""
        products = []
        raw_products = data.get("products", [])

        for p in raw_products:
            image_url = None
            images = p.get("images", [])
            if images and isinstance(images, list):
                if isinstance(images[0], dict):
                    image_url = images[0].get("url")
                elif isinstance(images[0], str):
                    image_url = images[0]

            price_info = p.get("priceBeforeBonus") or p.get("price")
            if isinstance(price_info, (int, float)):
                price = float(price_info)
            elif isinstance(price_info, dict):
                price = price_info.get("now") or price_info.get("amount")
            else:
                price = None

            products.append(ProductSearchResult(
                product_id=str(p.get("hqId", p.get("id", ""))),
                webshop_id=str(p.get("webshopId", "")),
                title=p.get("title", p.get("name", "")),
                brand=p.get("brand"),
                price=price,
                unit_size=p.get("unitSize"),
                image_url=image_url,
                is_bonus=p.get("isBonus", False) or p.get("bonus", False),
            ))

        return ProductSearchResponse(
            query=query,
            total_results=data.get("page", {}).get("totalElements", len(products)),
            page=page,
            page_size=size,
            products=products,
        )

    def _get_nutrition_value(self, data: dict, key: str) -> Optional[float]:
        """Extract nutrition value from nested structure."""
        value = data.get(key)
        if isinstance(value, dict):
            return value.get("amount") or value.get("value")
        return value


# Singleton getter
_product_client: Optional[AHProductClient] = None


def get_product_client(settings: Settings) -> AHProductClient:
    """Get or create product client singleton."""
    global _product_client
    if _product_client is None:
        _product_client = AHProductClient(settings)
    return _product_client

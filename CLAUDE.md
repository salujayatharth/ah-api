# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
# Install dependencies with uv (creates venv automatically)
uv sync
source .venv/bin/activate

# Run the server
uvicorn app.main:app --reload --port 8000
```

Alternative (if no pyproject.toml):
```bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
```

**Common uv commands:**
- `uv sync` - Install/update all dependencies
- `uv add <package>` - Add a new dependency
- `uv remove <package>` - Remove a dependency
- `uv pip install <package>` - Install package in current venv
- `uv run <command>` - Run command in uv-managed environment

API docs at http://localhost:8000/docs, dashboard at http://localhost:8000/dashboard

## Authentication Flow

1. Get auth code: `https://login.ah.nl/secure/oauth/authorize?client_id=appie&redirect_uri=appie://login-exit&response_type=code`
2. Exchange code: `POST /receipts/auth` with `{"code": "YOUR_CODE"}`
3. Tokens stored in `.tokens.json` (gitignored), auto-refresh on expiry

## Architecture

**Data Flow:**
```
AH GraphQL API → AHClient → FastAPI Routes → SQLite DB → Analytics Service
```

**Key Components:**
- `app/client.py` - Singleton `AHClient` handling AH GraphQL API communication, token management, and auto-refresh
- `app/routes.py` - Receipt endpoints (`/receipts/*`) including sync functionality
- `app/analytics_routes.py` - Analytics endpoints (`/analytics/*`)
- `app/product_routes.py` - Product endpoints (`/products/*`) for fetching product details
- `app/product_client.py` - `ProductClient` for fetching product info from AH webshop API
- `app/product_models.py` - Pydantic models for product data
- `app/sync_service.py` - Syncs receipts from AH API to local SQLite database
- `app/analytics_service.py` - Query functions for spending analytics (by time, store, product, savings)
- `app/database.py` - SQLAlchemy setup with SQLite (`receipts.db`)
- `app/db_models.py` - Database models: Receipt, ReceiptItem, ReceiptDiscount, ReceiptVAT, ProductCache

**API Structure:**
- `/receipts/auth` - Token management
- `/receipts` - List/get receipts from AH API
- `/receipts/sync` - Sync receipts to local DB
- `/analytics/*` - Spending analytics (summary, over-time, stores, products, savings)
- `/recommendations` - AI-powered shopping list predictions
- `/products/*` - Fetch product details from AH webshop (cached in ProductCache table)
- `/dashboard` - Static HTML analytics dashboard
- `/recommendations-ui` - Interactive shopping list dashboard with compact grid layout

## Technical Notes

- AH GraphQL API at `https://api.ah.nl/graphql` (REST endpoints are broken)
- Required User-Agent: `Appie/9.27.0`
- GraphQL queries defined inline in `client.py`
- Sync has incremental mode (stops after 3 consecutive existing receipts) and full mode
- Product details fetched from AH webshop API (`https://www.ah.nl/gql`) with different auth/headers
- Product cache uses 7-day TTL to avoid excessive API calls
- Recommendations UI uses compact grid layout with expandable cards for detailed product analysis
- Shopping list includes interactive info popovers explaining decay rate, confidence thresholds, etc.
- Uses `uv` for fast dependency management (replaces pip) with `pyproject.toml` for modern Python packaging

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

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
- `app/sync_service.py` - Syncs receipts from AH API to local SQLite database
- `app/analytics_service.py` - Query functions for spending analytics (by time, store, product, savings)
- `app/database.py` - SQLAlchemy setup with SQLite (`receipts.db`)
- `app/db_models.py` - Database models: Receipt, ReceiptItem, ReceiptDiscount

**API Structure:**
- `/receipts/auth` - Token management
- `/receipts` - List/get receipts from AH API
- `/receipts/sync` - Sync receipts to local DB
- `/analytics/*` - Spending analytics (summary, over-time, stores, products, savings)
- `/dashboard` - Static HTML analytics dashboard

## Technical Notes

- AH GraphQL API at `https://api.ah.nl/graphql` (REST endpoints are broken)
- Required User-Agent: `Appie/9.27.0`
- GraphQL queries defined inline in `client.py`
- Sync has incremental mode (stops after 3 consecutive existing receipts) and full mode

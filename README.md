# AH Receipts API

A FastAPI wrapper for accessing Albert Heijn digital receipts via their GraphQL API.

## Features

- **OAuth Authentication** - Secure token-based auth with auto-refresh
- **Receipt Sync & Storage** - Sync receipts to local SQLite database
- **Receipt Details** - Full product breakdown, discounts, VAT, payments
- **PDF Export** - Get receipt PDF URLs
- **Spending Analytics** - Analyze spending by time, store, product, and track savings
- **Smart Recommendations** - AI-powered shopping list predictions based on purchase history
- **Product Information** - Fetch and cache detailed product info from AH webshop (brand, category, images)

## Installation

### Option 1: Docker (Recommended for production)

```bash
# Using pre-built image from GitHub Container Registry
docker pull ghcr.io/yatharth/ah-api:latest

# Run with volume for data persistence
docker run -d \
  --name ah-api \
  -p 8000:8000 \
  -v ah-data:/data \
  ghcr.io/yatharth/ah-api:latest
```

Or use Docker Compose:

```bash
docker compose up -d
```

### Option 2: Local Development

```bash
# Clone the repo
git clone https://github.com/yourusername/ah-api.git
cd ah-api

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync
source .venv/bin/activate  # uv creates .venv automatically
```

## Usage

### 1. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Authenticate

Get an auth code by logging in at:
```
https://login.ah.nl/secure/oauth/authorize?client_id=appie&redirect_uri=appie://login-exit&response_type=code
```

After login, extract the `code` from the redirect URL and exchange it:

```bash
curl -X POST http://localhost:8000/receipts/auth \
  -H "Content-Type: application/json" \
  -d '{"code": "your-auth-code"}'
```

Tokens are stored locally and auto-refresh when expired.

### 3. Fetch receipts

```bash
# List receipts
curl http://localhost:8000/receipts

# Get receipt details
curl http://localhost:8000/receipts/{receipt_id}

# Get receipt PDF
curl http://localhost:8000/receipts/{receipt_id}/pdf
```

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/receipts/auth` | Exchange auth code for tokens |
| `GET` | `/receipts/auth/status` | Check authentication status |
| `DELETE` | `/receipts/auth` | Clear stored tokens |

### Receipts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/receipts` | List receipts (`?offset=0&limit=20`) |
| `GET` | `/receipts/{id}` | Get receipt details |
| `GET` | `/receipts/{id}/pdf` | Get receipt PDF URL |
| `POST` | `/receipts/sync` | Sync receipts to local database |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/analytics/summary` | Overall spending summary |
| `GET` | `/analytics/over-time` | Spending trends over time |
| `GET` | `/analytics/stores` | Spending by store |
| `GET` | `/analytics/products` | Top products by spending/quantity |
| `GET` | `/analytics/savings` | Discount and savings analysis |
| `GET` | `/recommendations` | AI shopping list predictions |
| `GET` | `/recommendations/product/{name}` | Detailed analysis for a product |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/products/{product_id}` | Get cached product details |
| `POST` | `/products/batch` | Fetch multiple products in batch |

### Dashboards
| Endpoint | Description |
|----------|-------------|
| `/dashboard` | Main analytics dashboard |
| `/recommendations-ui` | Smart shopping list interface |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

Interactive API docs available at `/docs` when running.

## Example Response

```json
{
  "pagination": {
    "offset": 0,
    "limit": 20,
    "totalElements": 42
  },
  "posReceipts": [
    {
      "id": "AH360976848209b9c8335b7b6c1b241a9ab3929",
      "dateTime": "2026-01-19T20:05:00.000Z",
      "totalAmount": {
        "amount": 4.16,
        "formatted": "€ 4,16"
      },
      "storeAddress": {
        "city": "Amsterdam",
        "street": "Utrechtsestraat"
      }
    }
  ]
}
```

## Tech Stack

- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM
- **SQLite** - Local database for receipts and product cache
- **httpx** - Async HTTP client
- **Pydantic** - Data validation
- **uv** - Fast Python package installer and resolver
- **Docker** - Containerization with multi-arch support (amd64/arm64)
- **AH GraphQL API** - Albert Heijn's internal API

## Development

### Building Docker Images Locally

```bash
# Build image
docker build -t ah-api:local .

# Test locally
docker run -p 8000:8000 -v ah-data:/data ah-api:local
```

Images are automatically built and pushed to GitHub Container Registry on tagged releases.

## Notes

- This uses the unofficial AH GraphQL API (`https://api.ah.nl/graphql`)
- The legacy REST endpoints (`/mobile-services/v1/receipts`) are no longer functional
- Tokens are valid for ~7 days and auto-refresh

## License

MIT

# Albert Heijn Receipts API

FastAPI wrapper for the Albert Heijn (AH) receipts API using GraphQL.

## Quick Start

```bash
# Activate venv
source venv/bin/activate

# Run server
uvicorn app.main:app --reload --port 8000
```

## Authentication

1. Get auth code from: `https://login.ah.nl/secure/oauth/authorize?client_id=appie&redirect_uri=appie://login-exit&response_type=code`
2. POST the code to `/receipts/auth`:
   ```bash
   curl -X POST http://localhost:8000/receipts/auth \
     -H "Content-Type: application/json" \
     -d '{"code": "YOUR_CODE"}'
   ```

Tokens are stored in `.tokens.json` (gitignored) and auto-refresh when expired.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/receipts/auth` | Exchange auth code for tokens |
| GET | `/receipts/auth/status` | Check authentication status |
| DELETE | `/receipts/auth` | Clear stored tokens |
| GET | `/receipts?offset=0&limit=20` | List receipts (paginated) |
| GET | `/receipts/{id}` | Get receipt details |
| GET | `/receipts/{id}/pdf` | Get receipt PDF URL |

## Technical Notes

- Uses AH GraphQL API (`https://api.ah.nl/graphql`) - REST endpoints are broken
- User-Agent: `Appie/9.27.0`
- Tokens valid for ~7 days, auto-refresh on expiry

## Files

- `app/client.py` - AH API client with GraphQL queries
- `app/routes.py` - FastAPI endpoints
- `app/config.py` - Settings
- `.tokens.json` - Stored tokens (gitignored)

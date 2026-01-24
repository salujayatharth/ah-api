# Development Scripts

This directory contains scripts for development and Vibe Kanban integration.

## Available Scripts

### dev-server.sh
Starts the FastAPI development server on any available port.

```bash
./scripts/dev-server.sh
```

The script will automatically find and use the first available port, displaying it in the startup output.

Or manually:
```bash
uv sync
source .venv/bin/activate
uvicorn app.main:app --reload --port 0
```

## Vibe Kanban Configuration

To enable Vibe Kanban with this project:

1. **Open project settings** in Vibe Kanban (top right gear icon)
2. **Set up scripts:**
   - **Setup Script**: `uv sync` - Installs dependencies in the isolated worktree
   - **Dev Server Script**: `./scripts/dev-server.sh` - Starts the development server
   - **Cleanup Script** (optional): Remove temporary files after agent execution

3. **Important Configuration - Copy Files:**
   - **`.tokens.json`** - Add this if you need authentication tokens in the worktree for API testing
   - **`receipts.db`** - Add this if you need test data (existing receipts) for development
   - **`.env`** - Add this if you have environment variables needed for the app
   - All these files are already in `.gitignore` to prevent accidental commits

## Server Access

Once the dev server is running, check the console output for the assigned port, then access it at:
- API: `http://localhost:{PORT}`
- Interactive Docs: `http://localhost:{PORT}/docs`
- Dashboard: `http://localhost:{PORT}/dashboard`
- Recommendations UI: `http://localhost:{PORT}/recommendations-ui`

Example: if the server starts on port 8734, access the API at `http://localhost:8734`

## Notes

- The dev server includes hot-reload (`--reload`), so changes are reflected immediately
- Tokens are auto-saved to `.tokens.json` and auto-refresh on expiry
- The database (`receipts.db`) persists between server restarts

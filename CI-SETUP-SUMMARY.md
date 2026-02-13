# CI/CD Setup Summary

This document summarizes the Docker and CI/CD configuration for the AH API project.

## What Was Done

### 1. Docker Configuration

**Dockerfile** - Multi-stage build with:
- Python 3.12-slim base image
- UV package manager for fast dependency installation
- Multi-stage build for smaller image size
- Health check endpoint (`/docs`)
- Support for both amd64 and arm64 architectures
- Volume mount point at `/data` for persistence

**.dockerignore** - Excludes:
- Development files (.venv, tests, scripts)
- Git files
- Database and token files (should be in volumes)
- Documentation

**docker-compose.yml** - For local development:
- Service definition with volume mount
- Port mapping (8000:8000)
- Health checks
- Auto-restart policy

### 2. GitHub Actions CI/CD

**`.github/workflows/docker-publish.yml`** - Automated image publishing:
- Triggers on tags matching `v*.*.*` (e.g., v1.2.3)
- Multi-architecture builds (amd64, arm64)
- Pushes to GitHub Container Registry (ghcr.io)
- Creates multiple tags for flexibility:
  - `1.2.3` (exact version)
  - `1.2` (latest patch in minor)
  - `1` (latest minor in major)
  - `latest` (latest release)
  - `main-abc123` (git commit SHA)
- Build cache optimization
- Build provenance attestation

### 3. Documentation

**DOCKER.md** - Comprehensive Docker guide:
- Quick start instructions
- Volume management
- Using pre-built images from ghcr.io
- Initial authentication setup
- Multi-architecture support
- Troubleshooting

**RELEASE.md** - Release process guide:
- How to create releases
- Versioning strategy (semantic versioning)
- Image tagging explanation
- CI/CD architecture diagram
- Rollback procedures
- Troubleshooting

**README.md** - Updated with:
- Docker installation option
- Links to Docker documentation
- Docker in tech stack

**.env.example** - Environment variable template

## File Structure

```
ah-api/
├── .github/
│   └── workflows/
│       ├── docker-publish.yml  # NEW: CI/CD for Docker images
│       └── deploy.yml          # Existing Fly.io deployment (optional)
├── app/
│   ├── client.py               # Already uses DATA_DIR ✓
│   └── database.py             # Already uses DATA_DIR ✓
├── Dockerfile                  # UPDATED: Multi-stage build
├── .dockerignore               # UPDATED: Comprehensive exclusions
├── docker-compose.yml          # NEW: Local development
├── .env.example                # NEW: Environment variables
├── DOCKER.md                   # NEW: Docker documentation
├── RELEASE.md                  # NEW: Release process
└── CI-SETUP-SUMMARY.md         # NEW: This file
```

## How It Works

### Development Flow

1. **Develop locally**
   ```bash
   uv sync
   uvicorn app.main:app --reload --port 8000
   ```

2. **Test with Docker**
   ```bash
   docker build -t ah-api:test .
   docker run -p 8001:8000 -v test-data:/data ah-api:test
   ```

3. **Commit changes**
   ```bash
   git add .
   git commit -m "Add new feature"
   ```

### Release Flow

1. **Create tag**
   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

2. **CI builds automatically**
   - GitHub Actions detects tag
   - Builds Docker images for amd64 and arm64
   - Pushes to ghcr.io with multiple tags

3. **Deploy (in separate repo)**
   ```yaml
   # In your deployment repo
   services:
     ah-api:
       image: ghcr.io/yatharth/ah-api:1.2.3
       volumes:
         - ah-data:/data
   ```

## Data Persistence

The application stores data in `/data` (configurable via `DATA_DIR`):

- **receipts.db** - SQLite database
- **.tokens.json** - AH API tokens (auto-refreshing)

### Volume Strategy

**Docker Volume (Recommended)**
```bash
docker run -v ah-data:/data ghcr.io/yatharth/ah-api:latest
```
- Persists across container restarts
- Managed by Docker
- Best for production

**Bind Mount (Development)**
```bash
docker run -v $(pwd)/data:/data ghcr.io/yatharth/ah-api:latest
```
- Direct access to files from host
- Good for debugging
- Requires proper permissions

## Quick Reference

### Local Development
```bash
# Start with Docker Compose
docker compose up -d

# Or build and run manually
docker build -t ah-api:local .
docker run -p 8000:8000 -v ah-data:/data ah-api:local
```

### Using Pre-built Images
```bash
# Pull latest
docker pull ghcr.io/yatharth/ah-api:latest

# Run
docker run -d -p 8000:8000 -v ah-data:/data ghcr.io/yatharth/ah-api:latest
```

### Creating a Release
```bash
# Tag and push
git tag v1.0.0
git push origin v1.0.0

# Wait for GitHub Actions to complete
# Images available at ghcr.io/yatharth/ah-api:1.0.0
```

### Testing Locally
```bash
./scripts/docker-test.sh
```

## Next Steps

### To Start Using This Setup:

1. **Test locally**
   ```bash
   docker build -t ah-api:test .
   docker run -p 8001:8000 -v test-data:/data ah-api:test
   ```

2. **Create your first release**
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. **Verify image published**
   - Go to GitHub → Packages
   - Find `ah-api` package
   - Verify tags exist

4. **Pull and test**
   ```bash
   docker pull ghcr.io/yatharth/ah-api:0.1.0
   docker run -p 8000:8000 -v test-data:/data ghcr.io/yatharth/ah-api:0.1.0
   ```

5. **Set up deployment in separate repo**
   - Reference the image: `ghcr.io/yatharth/ah-api:X.Y.Z`
   - Mount volumes for data persistence
   - Configure secrets/environment as needed

### Optional Improvements:

- Add tests and run in CI before building image
- Add image vulnerability scanning (Trivy, Snyk)
- Add automatic changelog generation
- Add release notes to GitHub Releases
- Add Docker Hub mirror (in addition to ghcr.io)
- Add staging environment for pre-release testing

## Troubleshooting

### CI Build Fails
Check GitHub Actions logs at: `https://github.com/yatharth/ah-api/actions`

### Cannot Pull Image
Ensure package is public in GitHub Container Registry settings or authenticate:
```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

### Volume Data Lost
Verify you're using volumes (not relying on container filesystem):
```bash
docker volume ls
docker volume inspect ah-data
```

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [GitHub Container Registry](https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Semantic Versioning](https://semver.org/)
- [UV Package Manager](https://github.com/astral-sh/uv)

---

**Created:** 2026-02-13
**Status:** ✅ Complete and ready to use

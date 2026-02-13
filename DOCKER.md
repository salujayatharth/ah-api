# Docker Setup

This document explains how to build, run, and deploy the AH API using Docker.

## Quick Start

### Using Docker Compose (Recommended for local development)

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Stop and remove volumes (WARNING: deletes database and tokens)
docker compose down -v
```

Access the API at http://localhost:8000/docs

### Using Docker directly

```bash
# Build image
docker build -t ah-api:latest .

# Create volume for data persistence
docker volume create ah-data

# Run container
docker run -d \
  --name ah-api \
  -p 8000:8000 \
  -v ah-data:/data \
  ah-api:latest

# View logs
docker logs -f ah-api

# Stop and remove
docker stop ah-api && docker rm ah-api
```

## Data Persistence

The application stores two types of persistent data in `/data`:
- `receipts.db` - SQLite database with receipts and analytics
- `.tokens.json` - AH API authentication tokens (auto-refreshing)

### Volume Options

**1. Named Volume (Recommended for production)**
```bash
docker run -v ah-data:/data ah-api:latest
```

**2. Bind Mount (for development/debugging)**
```bash
mkdir -p ./data
docker run -v $(pwd)/data:/data ah-api:latest
```

**3. Inspect Volume Data**
```bash
# List volumes
docker volume ls

# Inspect volume location
docker volume inspect ah-data

# Access volume data
docker run --rm -v ah-data:/data alpine ls -la /data
```

## Initial Authentication Setup

On first run, you need to authenticate with Albert Heijn:

1. Get auth code from AH:
   ```
   https://login.ah.nl/secure/oauth/authorize?client_id=appie&redirect_uri=appie://login-exit&response_type=code
   ```

2. Exchange code for tokens:
   ```bash
   curl -X POST http://localhost:8000/receipts/auth \
     -H "Content-Type: application/json" \
     -d '{"code": "YOUR_AUTH_CODE"}'
   ```

3. Tokens are now saved in `/data/.tokens.json` and will auto-refresh

## Using Pre-built Images from GitHub Container Registry

Instead of building locally, you can use images from ghcr.io:

```bash
# Pull latest version
docker pull ghcr.io/yatharth/ah-api:latest

# Pull specific version
docker pull ghcr.io/yatharth/ah-api:1.2.3

# Run pre-built image
docker run -d \
  --name ah-api \
  -p 8000:8000 \
  -v ah-data:/data \
  ghcr.io/yatharth/ah-api:latest
```

### Available Tags

Images are tagged with multiple versions for flexibility:
- `latest` - Latest tagged release
- `1` - Latest version in major version 1
- `1.2` - Latest version in minor version 1.2
- `1.2.3` - Specific version
- `main-abc123` - Git commit SHA (for advanced users)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Directory for database and tokens |

## Health Checks

The container includes a health check that pings `/docs`:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' ah-api

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' ah-api
```

## Multi-Architecture Support

Images are built for both `linux/amd64` and `linux/arm64` (Apple Silicon, AWS Graviton, etc.):

```bash
# Docker automatically pulls the right architecture
docker pull ghcr.io/yatharth/ah-api:latest
```

## Building for Different Platforms

```bash
# Build for specific platform
docker buildx build --platform linux/amd64 -t ah-api:amd64 .
docker buildx build --platform linux/arm64 -t ah-api:arm64 .

# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t ah-api:multi .
```

## Testing Locally

```bash
# Build image
docker build -t ah-api:test .

# Run test container
docker run -d --name ah-api-test -p 8001:8000 -v ah-api-test-data:/data ah-api:test

# Check health
docker inspect --format='{{.State.Health.Status}}' ah-api-test

# Test endpoints
curl http://localhost:8001/health
curl http://localhost:8001/docs

# Clean up
docker stop ah-api-test && docker rm ah-api-test && docker volume rm ah-api-test-data
```

## Troubleshooting

### Container exits immediately
Check logs: `docker logs ah-api`

### Cannot connect to API
Ensure port 8000 is not already in use: `lsof -i :8000`

### Lost tokens after container restart
Make sure you're using a volume: `-v ah-data:/data`

### Database locked errors
Ensure only one container is using the volume at a time

### Permission issues with bind mounts
```bash
# Ensure correct permissions on host directory
chmod 755 ./data
chown -R $(id -u):$(id -g) ./data
```

## Advanced Usage

### Custom Port

```bash
docker run -p 9000:8000 -v ah-data:/data ah-api:latest
# Access at http://localhost:9000
```

### Read-only Root Filesystem (security hardening)

```bash
docker run \
  --read-only \
  --tmpfs /tmp \
  -v ah-data:/data \
  ah-api:latest
```

### Resource Limits

```bash
docker run \
  --memory=512m \
  --cpus=1.0 \
  -v ah-data:/data \
  ah-api:latest
```

## CI/CD Integration

Images are automatically built and pushed to GitHub Container Registry on every tag:

1. Create a tag: `git tag v1.0.0`
2. Push tag: `git push origin v1.0.0`
3. GitHub Actions builds and pushes to `ghcr.io/yatharth/ah-api:1.0.0`

See `.github/workflows/docker-publish.yml` for workflow details.

## Deployment

For production deployment, see your separate deployment repository. The Docker images from ghcr.io can be pulled and deployed to any container orchestration platform:

- Kubernetes
- Docker Swarm
- Nomad
- Cloud Run
- ECS/Fargate
- Fly.io
- Railway
- etc.

Example for deployment repo:
```yaml
# In your deployment repo
services:
  ah-api:
    image: ghcr.io/yatharth/ah-api:1.2.3
    volumes:
      - /mnt/ah-data:/data
```

# Release Process

This document explains how to create releases and trigger Docker image builds.

## Creating a Release

Docker images are automatically built and pushed to GitHub Container Registry when you create a git tag.

### 1. Update Version (if applicable)

Edit `pyproject.toml` and update the version:

```toml
[project]
version = "1.2.3"  # Update this
```

### 2. Commit Changes

```bash
git add .
git commit -m "Release v1.2.3"
```

### 3. Create and Push Tag

```bash
# Create annotated tag (recommended)
git tag -a v1.2.3 -m "Release version 1.2.3"

# Or lightweight tag
git tag v1.2.3

# Push tag to trigger CI
git push origin v1.2.3
```

### 4. Monitor Build

1. Go to GitHub Actions tab in your repository
2. Watch the "Build and Push Docker Image" workflow
3. Verify images are pushed to ghcr.io

### 5. Verify Published Images

```bash
# Pull the new version
docker pull ghcr.io/yatharth/ah-api:1.2.3

# Verify tags
docker pull ghcr.io/yatharth/ah-api:1.2     # Minor version
docker pull ghcr.io/yatharth/ah-api:1       # Major version
docker pull ghcr.io/yatharth/ah-api:latest  # Latest
```

## Versioning Strategy

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version (1.0.0 → 2.0.0): Breaking changes
- **MINOR** version (1.1.0 → 1.2.0): New features, backwards compatible
- **PATCH** version (1.2.1 → 1.2.2): Bug fixes, backwards compatible

## Image Tags Created

For tag `v1.2.3`, the following Docker tags are created:

| Tag | Description | Example |
|-----|-------------|---------|
| `1.2.3` | Exact version | `ghcr.io/yatharth/ah-api:1.2.3` |
| `1.2` | Latest patch in minor | `ghcr.io/yatharth/ah-api:1.2` |
| `1` | Latest minor in major | `ghcr.io/yatharth/ah-api:1` |
| `latest` | Latest release | `ghcr.io/yatharth/ah-api:latest` |
| `main-abc123` | Git SHA | `ghcr.io/yatharth/ah-api:main-abc123` |

## CI/CD Architecture

```
┌─────────────┐
│  Git Tag    │
│   v1.2.3    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ GitHub Actions  │
│ (docker-publish)│
└──────┬──────────┘
       │
       ├─► Build for linux/amd64
       ├─► Build for linux/arm64
       │
       ▼
┌─────────────────┐
│   ghcr.io       │
│  (Container     │
│   Registry)     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Deployment     │
│  Repo/Platform  │
│  (pull image)   │
└─────────────────┘
```

## Rollback

To rollback to a previous version:

```bash
# In your deployment repo/config, change image tag
image: ghcr.io/yatharth/ah-api:1.2.2  # Previous version

# Or pull and run specific version
docker pull ghcr.io/yatharth/ah-api:1.2.2
docker run -d -p 8000:8000 -v ah-data:/data ghcr.io/yatharth/ah-api:1.2.2
```

## Deleting Tags

If you need to delete a tag:

```bash
# Delete local tag
git tag -d v1.2.3

# Delete remote tag
git push origin :refs/tags/v1.2.3
```

Note: GitHub Container Registry images are not automatically deleted when tags are removed.

## Pre-release Versions

For beta/RC versions:

```bash
git tag v2.0.0-beta.1
git push origin v2.0.0-beta.1
```

Image will be tagged as: `ghcr.io/yatharth/ah-api:2.0.0-beta.1`

## Troubleshooting

### Build Failed

1. Check GitHub Actions logs for errors
2. Common issues:
   - Invalid `pyproject.toml` or `uv.lock`
   - Missing dependencies
   - Test failures (if tests are added)

### Image Not Published

1. Verify GitHub Actions has `packages: write` permission
2. Check if workflow completed successfully
3. Verify tag format matches `v*.*.*`

### Cannot Pull Image

1. Ensure the image is public in GitHub Container Registry settings
2. Or authenticate with GitHub:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

## Best Practices

1. **Always test locally first**
   ```bash
   docker build -t ah-api:test .
   docker run -p 8001:8000 -v test-data:/data ah-api:test
   ```

2. **Use annotated tags** for better git history
   ```bash
   git tag -a v1.2.3 -m "Release version 1.2.3"
   ```

3. **Update changelog** before tagging (if you maintain one)

4. **Test the published image** before deploying
   ```bash
   docker run --rm ghcr.io/yatharth/ah-api:1.2.3 --help
   ```

5. **Keep deployment config separate** - use your deployment repo to reference specific image versions

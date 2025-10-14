# Deployment Pipeline

## Overview

AgriConnect uses a fully automated CI/CD pipeline that deploys to a Kubernetes test cluster on every push to the `main` branch. The pipeline handles testing, building Docker images, and rolling out updates to the cluster.

## Architecture

### Infrastructure
- **Platform**: Google Kubernetes Engine (GKE)
- **Cluster**: `test` cluster
- **Namespace**: `agriconnect2-namespace`
- **Registry**: Google Container Registry (GCR)

### Components Deployed
1. **Nginx**: Reverse proxy/load balancer
2. **Backend**: FastAPI Python application
3. **Frontend**: Next.js React application
4. **Mobile App**: APK built via Expo EAS

## Deployment Workflow

### Trigger
```yaml
on:
  push:
    branches:
      - main
```
Deployment automatically starts when code is pushed to the `main` branch.

### Pipeline Stages

#### 1. Run Tests
```yaml
jobs:
  run-tests:
    uses: ./.github/workflows/test-reusable.yml
```
- Executes backend and frontend tests
- Must pass before proceeding to build stage
- Uses reusable workflow from `test-reusable.yml`

#### 2. Build Mobile App (APK)
```yaml
build-mobile:
  needs: run-tests
  steps:
    - Setup Node.js 24
    - Setup Expo and EAS
    - Build Android APK via EAS Build (non-interactive, no-wait)
```
- Runs in parallel after tests pass
- Uses **Expo Application Services (EAS)** for building
- Builds with `production` profile
- **Non-blocking**: Uses `--no-wait` flag (build continues in background)

#### 3. Build and Push Docker Images
```yaml
build-push:
  needs: [run-tests, build-mobile]
```

**Preparation Steps:**
1. **Frontend Build Prep**:
   ```bash
   mv frontend/next.config.prod.mjs frontend/next.config.mjs
   echo 'WEBDOMAIN=${{ secrets.WEBDOMAIN }}' >> frontend/.env
   ```
2. **Node Operations**: Install dependencies and build frontend

**Docker Build (3 services):**
- **Nginx** (`nginx/Dockerfile`)
  - Includes `nginx/conf.d/default.conf`
  - Built from nginx:1.26.1-alpine base image
- **Frontend** (`frontend/Dockerfile`)
  - Next.js production build
- **Backend** (`backend/Dockerfile`)
  - FastAPI application

**Docker Push:**
All images pushed to GCR with tags for the test cluster.

#### 4. Kubernetes Rollout
```yaml
rollout:
  needs: build-push
```

Sequentially rolls out updates to K8s deployments:
1. **Nginx** (`nginx-deployment`)
2. **Backend** (`backend-deployment`)
3. **Frontend** (`frontend-deployment`)

Each rollout updates the container image and triggers a rolling update.

## Configuration Files Used in Deployment

### Nginx Configuration
- **File**: `nginx/conf.d/default.conf`
- **Purpose**: Reverse proxy configuration
- **Key Routes**:
  - `/ws` → WebSocket connections to backend
  - `/api` → Backend API endpoints
  - `/storage` → Backend storage system
  - `/` → Frontend application

**Important**: Changes to `nginx/conf.d/default.conf` are included in the nginx Docker image and deployed to production.

### Frontend Configuration
- **Build Config**: `frontend/next.config.prod.mjs` (renamed to `next.config.mjs` during build)
- **Environment**: `WEBDOMAIN` secret injected into `.env`

### Backend Configuration
- **Dockerfile**: `backend/Dockerfile`
- **Environment**: Secrets managed via K8s ConfigMaps/Secrets (not in repo)

## Kubernetes Manifests

**Note**: Kubernetes manifests (Deployments, Services, Ingress) are managed in a **separate repository**, not in this codebase.

### Deployed Resources
- **Deployments**:
  - `nginx-deployment`
  - `backend-deployment`
  - `frontend-deployment`
- **Services**: (managed separately)
- **Ingress**: Routes external traffic to nginx service (managed separately)

## Secrets Management

Secrets are managed via GitHub Secrets and injected into the pipeline:

### Required GitHub Secrets
- `EXPO_TOKEN`: Expo authentication for EAS builds
- `WEBDOMAIN`: Production web domain URL
- `GH_PAT`: GitHub Personal Access Token for composite actions
- `GCLOUD_SERVICE_ACCOUNT_REGISTRY`: GCP service account for pushing to GCR
- `GCLOUD_SERVICE_ACCOUNT_K8S`: GCP service account for K8s rollouts

### Application Secrets
Runtime secrets (database credentials, API keys, etc.) are managed via Kubernetes Secrets in the K8s manifests repository.

## Deployment Process

### Automatic Deployment
1. Push code to `main` branch
2. GitHub Actions automatically triggers deployment workflow
3. Tests run first (must pass)
4. Docker images built and pushed to GCR
5. K8s deployments rolled out with new images
6. Rolling update ensures zero-downtime deployment

### Manual Intervention
If you need to manually trigger or monitor:

```bash
# Check workflow status
gh run list --workflow=deploy.yml

# Watch specific run
gh run watch <run-id>

# Rerun failed deployment
gh run rerun <run-id>
```

## Rollback Procedure

If a deployment causes issues:

```bash
# Via kubectl (requires K8s access)
kubectl rollout undo deployment/nginx-deployment -n agriconnect2-namespace
kubectl rollout undo deployment/backend-deployment -n agriconnect2-namespace
kubectl rollout undo deployment/frontend-deployment -n agriconnect2-namespace

# Or revert git commit and push
git revert <bad-commit-hash>
git push origin main
# This triggers automatic redeployment with previous working code
```

## Monitoring Deployment

### Check Rollout Status
```bash
kubectl rollout status deployment/nginx-deployment -n agriconnect2-namespace
kubectl rollout status deployment/backend-deployment -n agriconnect2-namespace
kubectl rollout status deployment/frontend-deployment -n agriconnect2-namespace
```

### View Pod Status
```bash
kubectl get pods -n agriconnect2-namespace
kubectl logs -f <pod-name> -n agriconnect2-namespace
```

### Check Service Health
- **Frontend**: https://agriconnect2.akvotest.org
- **Backend API**: https://agriconnect2.akvotest.org/api/health-check
- **Storage**: https://agriconnect2.akvotest.org/storage

## Common Deployment Scenarios

### Adding New Environment Variables

**Backend/Frontend**:
1. Update K8s ConfigMap/Secret in manifests repo
2. Update deployment to reference new config
3. No code changes needed if using `os.getenv()`

**Note**: Code changes that reference new env vars should be deployed after K8s config is updated.

### Updating Nginx Configuration

1. Edit `nginx/conf.d/default.conf`
2. Commit and push to `main`
3. Pipeline automatically rebuilds nginx image with new config
4. Nginx deployment rolled out with updated configuration

**Example**: Adding new route (like `/storage` fix in commit 28138bc)

### Database Migrations

Backend uses Alembic for database migrations:
1. Migrations run automatically on backend container startup
2. New migration files in `backend/alembic/versions/` deployed with code
3. Backend pod restart triggers migration execution

### Deployment with Breaking Changes

For breaking changes requiring coordination:
1. Deploy backend first (backwards compatible)
2. Update K8s manifests if needed
3. Deploy frontend/mobile with changes
4. Or use feature flags to toggle functionality

## Troubleshooting

### Deployment Fails at Test Stage
- Check test logs in GitHub Actions
- Fix failing tests and push again
- Tests must pass before deployment proceeds

### Docker Build Fails
- Check build logs in GitHub Actions
- Common issues: Missing dependencies, build errors
- Test locally: `docker build -f <dockerfile> .`

### Rollout Fails or Pods CrashLooping
- Check pod logs: `kubectl logs <pod-name> -n agriconnect2-namespace`
- Check events: `kubectl describe pod <pod-name> -n agriconnect2-namespace`
- Common issues: Missing secrets, database connection, port conflicts

### Frontend 404 Errors After Deployment
- Check nginx configuration is correct
- Verify frontend build completed successfully
- Check nginx proxy paths match frontend routes

### Backend 500 Errors After Deployment
- Check backend logs for errors
- Verify environment variables are set
- Check database connectivity
- Verify migrations completed successfully

## Best Practices

1. **Always test locally** before pushing to main
2. **Use feature branches** for development, merge to main when ready
3. **Monitor deployment** via GitHub Actions after pushing
4. **Check health endpoints** after deployment completes
5. **Keep nginx config in sync** - changes deploy automatically
6. **Database migrations** should be backwards compatible
7. **Breaking changes** require careful coordination
8. **Use semantic commit messages** for clear deployment history

## Related Documentation

- [Mobile App Deployment](MOBILE_APP_DEPLOYMENT.md): Detailed EAS Build setup
- [Mobile Build Quick Reference](MOBILE_BUILD_QUICK_REFERENCE.md): Quick build commands
- [Storage System](STORAGE_SYSTEM.md): Storage endpoint configuration
- [CLAUDE.md](../CLAUDE.md): Project architecture overview

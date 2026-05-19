# Facemaxx EC2 Deploy

This directory is meant for a backend-only GitHub repository whose root is `back/`.

The deployment runs the FastAPI container on localhost port `8000`.
Nginx terminates HTTPS for `facemaxx.nostalgia-drive.com` and proxies to the container.

## Required GitHub Secrets

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_KEY`

`EC2_USER` is usually `ubuntu`.

## Required EC2 Files

Create `/opt/facemaxx/.env` manually on the server. Do not commit production secrets.

```env
APP_ENV=production
API_PREFIX=/v1
AUTH_DISABLED=true
AI_PROVIDER=gemini
GEMINI_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
IMAGE_STORAGE_PROVIDER=cloudinary
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_FOLDER=facemaxx
REVENUECAT_SECRET_API_KEY=
REVENUECAT_WEBHOOK_BEARER_TOKEN=
```

## Manual Deploy Check

```bash
cd /opt/facemaxx
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose pull
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose up -d
curl http://127.0.0.1:8000/health
curl https://facemaxx.nostalgia-drive.com/health
```

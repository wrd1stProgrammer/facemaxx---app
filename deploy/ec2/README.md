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
AUTH_DISABLED=false
AI_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
FLIRTIST_AI_PROVIDER=openai
FLIRTIST_OPENAI_API_KEY=
FLIRTIST_OPENAI_MODEL=gpt-4.1-mini
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

`AUTH_DISABLED=false` is required in production. RevenueCat purchases are tied to the logged-in app user id; if auth is disabled, the server falls back to the install id and `/v1/pro-scans/sync` can return 200 while syncing the wrong RevenueCat subscriber.

If `REVENUECAT_WEBHOOK_BEARER_TOKEN` is set, configure the same value in the RevenueCat webhook Authorization header. The server accepts either `Bearer <token>` or the raw token value.

`AI_PROVIDER` is the Facemaxx face-analysis requested provider. Production should set `AI_PROVIDER=openai`; older Gemini provider values are accepted for old deployments but Facemaxx analysis still routes to OpenAI. Flirtist reads `FLIRTIST_AI_PROVIDER` separately. If `FLIRTIST_AI_PROVIDER=openai` is set without `FLIRTIST_OPENAI_API_KEY` or a shared `OPENAI_API_KEY`, `/health` will report `flirtist_ai_requested_provider=openai` and `flirtist_ai_provider=mock`.

## Manual Deploy Check

```bash
cd /opt/facemaxx
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose pull
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose up -d
curl http://127.0.0.1:8000/health
curl https://facemaxx.nostalgia-drive.com/health
```

The health response should include requested and effective providers, for example `ai_provider: "openai"`, `facemaxx_ai_provider: "openai"`, and `flirtist_ai_provider: "openai"`.

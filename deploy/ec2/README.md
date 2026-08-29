# Facemaxx EC2 Deploy

This directory is meant for a backend-only GitHub repository whose root is `back/`.

The deployment runs FaceMaxx on localhost port `8000` and ChartAgent on localhost port `8010`.
Nginx terminates HTTPS for `facemaxx.nostalgia-drive.com` and proxies to the containers.

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
FLIRTIST_AI_PROVIDER=codex_cli
FLIRTIST_AI_FALLBACK_PROVIDER=openai
FLIRTIST_OPENAI_API_KEY=
FLIRTIST_OPENAI_MODEL=gpt-4.1-mini
FLIRTIST_CODEX_MODEL=gpt-5.6-luna
FLIRTIST_CODEX_REASONING_EFFORT=low
FLIRTIST_CODEX_BIN=/usr/local/bin/codex
FLIRTIST_CODEX_TIMEOUT_SECONDS=45
FLIRTIST_CODEX_MAX_CONCURRENCY=2
CODEX_HOME=/home/app/.codex
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

ChartAgent secrets stay in a separate `/opt/chartagent/.env`. The compose file reads that file directly, while both services share only the persistent `codex-home` authentication volume.

```env
CHARTAGENT_APP_ENV=production
CHARTAGENT_OPENAI_API_KEY=
CHARTAGENT_OPENAI_MODEL=gpt-5-mini
INSIGHTSENTRY_RAPIDAPI_KEY=
INSIGHTSENTRY_RAPIDAPI_HOST=insightsentry.p.rapidapi.com
CHARTAGENT_CODEX_BINARY=/usr/local/bin/codex
CHARTAGENT_CODEX_TIMEOUT_SECONDS=60
CHARTAGENT_CODEX_MAX_CONCURRENCY=5
CODEX_HOME=/home/app/.codex
```

`AUTH_DISABLED=false` is required in production. RevenueCat purchases are tied to the logged-in app user id; if auth is disabled, the server falls back to the install id and `/v1/pro-scans/sync` can return 200 while syncing the wrong RevenueCat subscriber.

If `REVENUECAT_WEBHOOK_BEARER_TOKEN` is set, configure the same value in the RevenueCat webhook Authorization header. The server accepts either `Bearer <token>` or the raw token value.

`AI_PROVIDER` is the Facemaxx face-analysis requested provider. Production should set `AI_PROVIDER=openai`; older Gemini provider values are accepted for old deployments but Facemaxx analysis still routes to OpenAI. Flirtist reads `FLIRTIST_AI_PROVIDER` separately. With `FLIRTIST_AI_PROVIDER=codex_cli`, the container runs Codex first and uses `FLIRTIST_AI_FALLBACK_PROVIDER` (OpenAI by default) on timeout, process failure, or invalid JSON. The Codex login is stored in the named `codex-home` Docker volume, not in `.env` or the image.

After the first deployment, authenticate the persistent volume once:

```bash
cd /opt/facemaxx
docker compose exec -it api codex login --device-auth
docker compose exec api codex login status
docker compose exec chartagent-api codex login status
```

`/health` reports the selected provider, fallback provider, Codex model/reasoning setting, and whether the binary is installed. It intentionally does not report authentication tokens.

## Manual Deploy Check

```bash
cd /opt/facemaxx
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose pull
FACEMAXX_IMAGE=<dockerhub-user>/facemaxx:latest docker compose up -d
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8010/health
curl https://facemaxx.nostalgia-drive.com/health
curl https://facemaxx.nostalgia-drive.com/chartagent/health
```

The deployment workflow installs the idempotent `/chartagent/` Nginx location from `deploy/ec2/nginx-chartagent.conf.example`, validates the full Nginx configuration, and reloads Nginx. If the existing FaceMaxx server block cannot be identified safely, deployment fails without changing it.

The health response should include requested/effective/fallback settings, for example `flirtist_ai_requested_provider: "codex_cli"`, `flirtist_ai_provider: "codex_cli"`, `flirtist_ai_fallback_provider: "openai"`, `flirtist_codex_model: "gpt-5.6-luna"`, and `flirtist_codex_reasoning_effort: "low"`.

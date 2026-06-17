# Facemaxx Backend

FastAPI backend for Facemaxx analysis runs, Supabase persistence, and switchable AI providers.

## Setup

```bash
cd back
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Supabase

1. Create a Supabase project.
2. Run `supabase/schema.sql` in the Supabase SQL editor for a new project.
   If the base schema is already installed, run the dated migration files in order, including `supabase/20260516_user_onboarding_preferences.sql` for onboarding preference storage and analysis snapshots.
   For RevenueCat-backed Pro scan limits, also run `supabase/20260518_revenuecat_pro_scans.sql`.
3. Copy project URL and service role key into `back/.env`.
4. Keep `SUPABASE_SERVICE_ROLE_KEY` server-only. Never ship it in the iOS app.

`AUTH_DISABLED=true` is only for local dummy testing. When Supabase persistence is enabled, use a real Supabase Auth user id through `Authorization: Bearer <jwt>` or `X-Facemaxx-User-Id`; `schema.sql` automatically creates `profiles` and `user_usage` when a new auth user is inserted.

## Image Storage

Photos are uploaded to FastAPI first. FastAPI always keeps a local development backup in `back/.data/photos`, then stores the remote image with the configured provider.

Recommended Cloudinary settings:

```env
IMAGE_STORAGE_PROVIDER=cloudinary
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_FOLDER=facemaxx
```

`CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET` are not enough by themselves. Cloudinary upload URLs also require the cloud name. You can alternatively set `CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>`.

Supabase is still used for database metadata. Supabase Storage is only used when `IMAGE_STORAGE_PROVIDER=supabase`, or in `auto` mode when Cloudinary is not configured.

## Database Map

- `profiles`, `user_usage`: app user profile, scan allowance, streak/progress counters.
- `user_onboarding_preferences`: authenticated user's onboarding goals, gender, age range, and completion timestamp.
- `photos`: uploaded face-photo storage metadata. Actual files live in Cloudinary in production, with local development backups under `back/.data/photos`.
- `face_scan_captures`: one row per camera/upload scan event. This is the root row for geometry and deterministic measurements.
- `face_geometry_snapshots`: ARKit TrueDepth or Vision landmark payload captured at shutter time: vertices, triangle indices, blend shapes, transforms, optional 2D landmarks, and quality metadata.
- `face_metric_measurements`: server-calculated numeric measurements from the captured geometry. Proportions should be calculated here without an LLM.
- `analysis_modes`: the analyze-tab modes: proportions, aesthetics, glow-up coach, look archetype, and the photo/profile optimization modes.
- `analysis_runs`: one root row per scan/mode result, including the onboarding context snapshot used for that run.
- `analysis_score_rings`: circular score cards used by the aesthetics-style result view.
- `analysis_metrics`: expandable rows for proportions, detailed metrics, and fun AI metrics.
- `growth_opportunities`: potential score and action-plan style recommendations.
- `glow_up_coach_items`: facial analysis, needs-work, and strengths accordion items.
- `look_archetypes`, `look_archetype_traits`, `look_archetype_sections`, `look_archetype_bullets`: shareable archetype result structure.
- `localized_strings`: optional server-managed i18n strings for English/Korean and future locales.
- `user_progress_snapshots`, `user_analysis_summary`: progress-tab summary data.
- `habitdot_install_metrics`: Habitdot install-level counters, including total paywall entries.

## AI Provider

Set `AI_PROVIDER` in `.env`:

- `dummy`: deterministic placeholder response for UI integration.
- `gemini`: uses Gemini provider module.
- `openai`: uses OpenAI provider module.

The route contract stays the same while provider internals can change.

Provider keys are read from `GEMINI_API_KEY` or `OPENAI_API_KEY`. Use `AI_PROVIDER=gemini` for the current real-photo analysis flow, and switch back to `AI_PROVIDER=dummy` only when you intentionally want local placeholder responses.

## Habitdot Motivation

`POST /v1/habitdot/motivation` returns a short stateless motivation line for Habitdot. Because the app mounts the API router both with and without `API_PREFIX`, the same endpoint is also available at `POST /habitdot/motivation`.

The endpoint uses server-side `GEMINI_API_KEY` when configured. If the key is missing or generation fails, it returns deterministic fallback copy with `provider="fallback"` and `model_name=null`.

The iOS client should send `X-Facemaxx-Install-Id`; the route applies a small in-memory per-install/IP rate limit to protect Gemini usage. App-side caching should still keep normal usage to about one request per relevant daily habit state.

Example payload:

```json
{
  "locale": "ko",
  "date": "2026-05-28",
  "habits": [
    {
      "title": "아침 물 마시기",
      "purpose": "하루를 가볍게 시작하기",
      "color_hex": "#4CB3FF",
      "completed_today": false,
      "current_streak": 3,
      "weekly_completion_count": 4
    }
  ]
}
```

## Flirtist Dating Coach

Flirtist endpoints are mounted with and without `API_PREFIX`, so local clients can call either `/api/flirtist/...` or `/v1/api/flirtist/...`.

- `POST /api/flirtist/analyze-chat`: situation read, interest score, risk flags, next move, suggested replies.
- `POST /api/flirtist/generate-replies`: locale-aware replies and explanations.
- `POST /api/flirtist/check-draft`: draft rewrite plus safety blocking for minor, explicit, coercive, or stalking content.
- `POST /api/flirtist/profile-coach`: dating profile strengths, fixes, bio options, and DM hooks.
- `POST /api/flirtist/goal-coach`: next-step coaching for a dating goal.
- `POST /api/flirtist/ocr-chat`: screenshot/OCR handoff shape for chat extraction.

Provider selection is independent from the Facemaxx face-analysis provider:

```env
AI_PROVIDER=gemini
FLIRTIST_AI_PROVIDER=openai
FLIRTIST_OPENAI_API_KEY=
FLIRTIST_OPENAI_MODEL=gpt-5-mini
FLIRTIST_ANTHROPIC_API_KEY=
FLIRTIST_GEMINI_API_KEY=
```

If `FLIRTIST_AI_PROVIDER` is omitted but `FLIRTIST_OPENAI_API_KEY` exists, Flirtist defaults to OpenAI. If the selected provider key is absent, Flirtist falls back to deterministic mock responses while preserving the response contract. `/health` reports both the global `ai_provider` and Flirtist's `flirtist_ai_provider`.

## RevenueCat

The iOS app uses the public RevenueCat SDK key, while FastAPI uses the server-side secret key for subscriber sync and webhook processing.

Recommended RevenueCat setup:

1. Create the iOS app in RevenueCat with the Facemaxx bundle id.
2. Import App Store products:
   - Subscriptions: `facemaxx1wk`, `facemaxx1mo`
   - Consumables: `facemaxx10scan`, `facemaxx20scan`, `facemaxx50scan`
3. Create entitlement `pro` and attach the subscription products to it. The entitlement only proves that a subscription is active; scan limits are enforced by the backend quota tables.
4. Create offering `default` and add the subscription packages plus custom packages for the scan packs.
5. Set `REVENUECAT_IOS_API_KEY` in `Facemaxx/Config/Secrets.xcconfig`.
6. Set `REVENUECAT_SECRET_API_KEY` in `back/.env`.
7. Configure a RevenueCat webhook to `POST /v1/revenuecat/webhook`; if `REVENUECAT_WEBHOOK_BEARER_TOKEN` is set on the server, configure the same value in the RevenueCat webhook Authorization header. The server accepts either `Bearer <token>` or the raw token value.

Server-side enforcement happens in `POST /v1/analysis-runs`: Pro modes require at least one remaining quota credit. `facemaxx1wk` refreshes 12 subscription credits per weekly cycle, `facemaxx1mo` refreshes 50 subscription credits per monthly cycle, and 10/20/50 consumables add separate non-renewing credits. Credit consumption is atomic in Supabase and is refunded if the AI provider or persistence step fails.

## Capture Data Flow

Do not connect the iOS app directly with the Supabase service role key. The app should call FastAPI, and FastAPI writes to Supabase with the server-only service key.

1. iOS captures a photo and keeps a generated `X-Facemaxx-Install-Id` in `UserDefaults` until real auth is added.
2. iOS extracts the current ARKit face snapshot:
   - `vertices`: `ARFaceGeometry.vertices`
   - `triangle_indices`: `ARFaceGeometry.triangleIndices`
   - `blend_shapes`: `ARFaceAnchor.blendShapes`
   - `face_transform`: `ARFaceAnchor.transform`
   - optional `landmarks_2d`: Vision face landmark points for semantic ratios such as canthal tilt and eye spacing.
3. iOS uploads the JPEG to `POST /v1/photos/upload`.
4. iOS sends the snapshot to `POST /v1/face-scans` with the returned `photo_id`.
5. FastAPI stores raw geometry in `face_geometry_snapshots`.
6. FastAPI calculates deterministic ratios and saves them in `face_metric_measurements`.
7. Later, `POST /v1/analysis-runs` can reference `face_scan_capture_id` so Gemini/OpenAI only generates narrative explanations from already-calculated metrics.

For a real iPhone hitting a local FastAPI server, replace the Xcode build setting `FACEMAXX_API_BASE_URL` with your Mac LAN URL, for example `http://192.168.0.12:8000`. `127.0.0.1` only works for the simulator.

Example payload:

```json
{
  "source": "camera",
  "capture_backend": "arkit_true_depth",
  "device_model": "iPhone",
  "os_version": "iOS 26.0",
  "image_width": 1170,
  "image_height": 2532,
  "geometry": {
    "provider": "arkit_true_depth",
    "coordinate_space": "arkit_local",
    "vertices": [[0.01, 0.02, -0.03]],
    "triangle_indices": [0, 1, 2],
    "blend_shapes": { "jawOpen": 0.02 },
    "face_transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    "landmarks_2d": {
      "leftEye": [[0.42, 0.38], [0.46, 0.37]],
      "rightEye": [[0.55, 0.37], [0.59, 0.38]]
    }
  }
}
```

## Main Endpoints

- `GET /health`
- `GET /v1/analysis-modes`
- `POST /v1/photos`
- `POST /v1/photos/upload`
- `POST /v1/face-scans`
- `POST /v1/analysis-runs`
- `GET /v1/analysis-runs/{run_id}`
- `POST /v1/habitdot/motivation`
- `POST /v1/habitdot/paywall-view`

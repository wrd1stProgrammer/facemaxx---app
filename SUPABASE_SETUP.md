# Supabase Setup

## 1. iOS App Keys

iOS target build settings are loaded from:

- `Facemaxx/Config/Debug.xcconfig`
- `Facemaxx/Config/Release.xcconfig`

Both files optionally include:

- `Facemaxx/Config/Secrets.xcconfig`

`Secrets.xcconfig` is git-ignored and should contain only public client values:

```xcconfig
SUPABASE_URL = https:/$()/YOUR-PROJECT-REF.supabase.co
SUPABASE_ANON_KEY = YOUR_SUPABASE_ANON_OR_PUBLISHABLE_KEY
```

These values are injected into:

- `Facemaxx/Resources/Info.plist`
  - `FacemaxxSupabaseURL`
  - `FacemaxxSupabaseAnonKey`

Never put `SUPABASE_SERVICE_ROLE_KEY` in the iOS project.

## 2. Backend Keys

FastAPI reads Supabase settings from:

- `back/.env`

Required backend values:

```env
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_OR_PUBLISHABLE_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_SERVICE_ROLE_OR_SECRET_KEY
SUPABASE_STORAGE_BUCKET=face-photos
```

For real Supabase Auth enforcement, set:

```env
AUTH_DISABLED=false
```

Keep `AUTH_DISABLED=true` only for local pre-auth testing with `X-Facemaxx-Install-Id`.

## 3. SQL Order

Fresh Supabase project:

1. Run `back/supabase/schema.sql`.
2. Run `back/supabase/20260511_seed_look_archetypes.sql`.

Existing older project:

1. `back/supabase/20260510_face_scan_captures.sql`
2. `back/supabase/20260510_client_install_capture_identity.sql`
3. `back/supabase/20260510_rls_and_index_advisor_fixes.sql`
4. `back/supabase/20260511_seed_look_archetypes.sql`
5. `back/supabase/20260513_add_photo_optimization_modes.sql`

`schema.sql` already includes the current 8 analysis modes, user profile/usage tables, capture tables, result tables, RLS policies, storage bucket, and core indexes.

## 4. Quick Checks

Backend Supabase DB check:

```bash
cd back
.venv/bin/python - <<'PY'
from app.core.config import get_settings
from app.db.supabase import get_supabase_service_client

settings = get_settings()
print("configured:", settings.supabase_configured)
client = get_supabase_service_client()
print(client.table("analysis_modes").select("id", count="exact").limit(1).execute().count)
PY
```

iOS build setting check:

```bash
xcodebuild -project Facemaxx.xcodeproj -scheme Facemaxx -configuration Debug -showBuildSettings \
  | rg "SUPABASE_URL|SUPABASE_ANON_KEY|FACEMAXX_API_BASE_URL"
```

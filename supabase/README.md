# Facemaxx Supabase Setup

Run SQL from the Supabase SQL Editor for the target project.

## Fresh Project

1. Run `schema.sql`.
2. Run `20260511_seed_look_archetypes.sql` to add the expanded archetype seed set.

`schema.sql` already includes the current 8 analysis modes, capture-data tables, client install identity columns, storage bucket, indexes, RLS policies, and user profile/usage trigger.

## Existing Older Project

If the database was created before the latest schema file, run the migration-style patches in this order:

1. `20260510_face_scan_captures.sql`
2. `20260510_client_install_capture_identity.sql`
3. `20260510_rls_and_index_advisor_fixes.sql`
4. `20260511_seed_look_archetypes.sql`
5. `20260513_add_photo_optimization_modes.sql`
6. `20260530_habitdot_onboarding_feedback_bug.sql`
7. `20260605_habitdot_paywall_metrics.sql`

All app user-owned tables in `public` have RLS enabled. FastAPI writes through the server-only service role key; the iOS app must only receive the Supabase URL and anon/publishable key.

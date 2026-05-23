-- Mirror onboarding preferences onto profiles for profile-level reads.
-- The canonical onboarding record remains public.user_onboarding_preferences.

alter table if exists public.profiles
  add column if not exists onboarding_selected_goal_ids text[] not null default '{}'::text[],
  add column if not exists onboarding_gender_id text,
  add column if not exists onboarding_age integer,
  add column if not exists onboarding_age_range_id text,
  add column if not exists onboarding_discovery_source_id text,
  add column if not exists onboarding_completed_at timestamptz,
  add column if not exists onboarding_metadata jsonb not null default '{}'::jsonb,
  add column if not exists onboarding_updated_at timestamptz;

alter table if exists public.profiles
  drop constraint if exists profiles_onboarding_goal_ids_check;

alter table if exists public.profiles
  add constraint profiles_onboarding_goal_ids_check
  check (
    onboarding_selected_goal_ids <@ array[
      'symmetry',
      'jawline',
      'skin',
      'glow',
      'proportions',
      'progress',
      'photos',
      'profile'
    ]::text[]
  );

alter table if exists public.profiles
  drop constraint if exists profiles_onboarding_gender_id_check;

alter table if exists public.profiles
  add constraint profiles_onboarding_gender_id_check
  check (onboarding_gender_id is null or onboarding_gender_id in ('male', 'female', 'other'));

alter table if exists public.profiles
  drop constraint if exists profiles_onboarding_age_check;

alter table if exists public.profiles
  add constraint profiles_onboarding_age_check
  check (onboarding_age is null or onboarding_age between 13 and 70);

alter table if exists public.profiles
  drop constraint if exists profiles_onboarding_age_range_id_check;

alter table if exists public.profiles
  add constraint profiles_onboarding_age_range_id_check
  check (
    onboarding_age_range_id is null
    or onboarding_age_range_id in ('18-24', '25-34', '35-44', '45+')
  );

alter table if exists public.profiles
  drop constraint if exists profiles_onboarding_discovery_source_id_check;

alter table if exists public.profiles
  add constraint profiles_onboarding_discovery_source_id_check
  check (
    onboarding_discovery_source_id is null
    or onboarding_discovery_source_id in (
      'app-store',
      'tiktok',
      'instagram',
      'youtube',
      'google',
      'friend',
      'other'
    )
  );

update public.profiles as profile
set
  onboarding_selected_goal_ids = preferences.selected_goal_ids,
  onboarding_gender_id = preferences.gender_id,
  onboarding_age = preferences.age,
  onboarding_age_range_id = preferences.age_range_id,
  onboarding_discovery_source_id = preferences.metadata ->> 'discovery_source',
  onboarding_completed_at = preferences.completed_at,
  onboarding_metadata = preferences.metadata,
  onboarding_updated_at = preferences.updated_at,
  updated_at = now()
from public.user_onboarding_preferences as preferences
where profile.id = preferences.user_id;

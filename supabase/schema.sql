-- Facemaxx Supabase schema
-- Run this in the Supabase SQL editor after creating a new project.

create extension if not exists pgcrypto;

do $$
begin
  create type public.scan_source as enum ('upload', 'camera');
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.analysis_run_status as enum ('queued', 'processing', 'completed', 'failed');
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.ai_provider_name as enum ('dummy', 'gemini', 'openai');
exception
  when duplicate_object then null;
end $$;

do $$
begin
  create type public.face_capture_backend as enum ('arkit_true_depth', 'vision_landmarks', 'manual_upload');
exception
  when duplicate_object then null;
end $$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  locale text not null default 'en' check (locale in ('en', 'ko', 'ja', 'de', 'es-419', 'zh-Hant', 'pt-BR', 'fr', 'it', 'id', 'tr', 'ar')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_onboarding_preferences (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  selected_goal_ids text[] not null default '{}'::text[],
  gender_id text check (gender_id in ('male', 'female', 'other')),
  age integer check (age between 13 and 70),
  age_range_id text check (age_range_id in ('18-24', '25-34', '35-44', '45+')),
  completed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_onboarding_preferences_goal_ids_check
    check (
      selected_goal_ids <@ array[
        'symmetry',
        'jawline',
        'skin',
        'glow',
        'proportions',
        'progress',
        'photos',
        'profile'
      ]::text[]
    )
);

create index if not exists user_onboarding_preferences_completed_idx
  on public.user_onboarding_preferences (completed_at desc);

create table if not exists public.user_usage (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  scans_remaining integer not null default 5 check (scans_remaining >= 0),
  pro_scans_remaining integer not null default 0 check (pro_scans_remaining >= 0),
  current_streak integer not null default 0 check (current_streak >= 0),
  last_scan_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name, locale)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'display_name', new.email),
    case
      when coalesce(nullif(new.raw_user_meta_data ->> 'locale', ''), 'en') in (
        'en', 'ko', 'ja', 'de', 'es-419', 'zh-Hant', 'pt-BR', 'fr', 'it', 'id', 'tr', 'ar'
      )
        then coalesce(nullif(new.raw_user_meta_data ->> 'locale', ''), 'en')
      else 'en'
    end
  )
  on conflict (id) do nothing;

  insert into public.user_usage (user_id)
  values (new.id)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

revoke all on function public.handle_new_user() from public, anon, authenticated;

create table if not exists public.analysis_modes (
  id text primary key,
  title_key text not null,
  icon_name text not null,
  badge_key text not null,
  badge_type text not null check (badge_type in ('unlimited', 'pro_scan')),
  badge_color text not null,
  is_highlighted boolean not null default false,
  sort_order integer not null,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.analysis_modes (
  id, title_key, icon_name, badge_key, badge_type, badge_color, is_highlighted, sort_order, is_enabled
) values
  ('proportions', 'analysis.mode.proportions', 'chart.bar.fill', 'analysis.badge.unlimited', 'unlimited', '#34D15C', false, 10, true),
  ('aesthetics', 'analysis.mode.aesthetics', 'brain.head.profile', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 20, true),
  ('glow-up-coach', 'analysis.mode.glowUpCoach', 'sparkles', 'analysis.badge.proScan', 'pro_scan', '#6175FF', true, 30, true),
  ('look-archetype', 'analysis.mode.lookArchetype', 'theatermasks.fill', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 40, true),
  ('best-photo-selector', 'analysis.mode.bestPhotoSelector', 'checkmark.seal.fill', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 50, true),
  ('best-angle-finder', 'analysis.mode.bestAngleFinder', 'viewfinder', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 60, true),
  ('dating-profile-score', 'analysis.mode.datingProfileScore', 'heart.fill', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 70, true),
  ('instagram-profile-score', 'analysis.mode.instagramProfileScore', 'square.grid.3x3.fill', 'analysis.badge.proScan', 'pro_scan', '#6175FF', false, 80, true)
on conflict (id) do update set
  title_key = excluded.title_key,
  icon_name = excluded.icon_name,
  badge_key = excluded.badge_key,
  badge_type = excluded.badge_type,
  badge_color = excluded.badge_color,
  is_highlighted = excluded.is_highlighted,
  sort_order = excluded.sort_order,
  is_enabled = excluded.is_enabled,
  updated_at = now();

create table if not exists public.photos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete cascade,
  client_install_id uuid not null default gen_random_uuid(),
  storage_bucket text not null default 'face-photos',
  storage_path text not null,
  original_filename text,
  mime_type text,
  width integer,
  height integer,
  sha256 text,
  created_at timestamptz not null default now(),
  unique (storage_bucket, storage_path)
);

create index if not exists photos_user_id_idx
  on public.photos (user_id);

create index if not exists photos_client_install_created_idx
  on public.photos (client_install_id, created_at desc);

create table if not exists public.face_scan_captures (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete cascade,
  client_install_id uuid not null default gen_random_uuid(),
  photo_id uuid references public.photos(id) on delete set null,
  source public.scan_source not null default 'camera',
  capture_backend public.face_capture_backend not null default 'arkit_true_depth',
  device_model text,
  os_version text,
  app_version text,
  image_width integer,
  image_height integer,
  is_front_camera boolean not null default true,
  is_mirrored boolean not null default true,
  tracking_state text,
  quality_score numeric(5,4),
  metadata jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists face_scan_captures_user_created_idx
  on public.face_scan_captures (user_id, created_at desc);

create index if not exists face_scan_captures_client_created_idx
  on public.face_scan_captures (client_install_id, created_at desc);

create index if not exists face_scan_captures_photo_id_idx
  on public.face_scan_captures (photo_id);

create table if not exists public.face_geometry_snapshots (
  id uuid primary key default gen_random_uuid(),
  capture_id uuid not null unique references public.face_scan_captures(id) on delete cascade,
  provider public.face_capture_backend not null default 'arkit_true_depth',
  coordinate_space text not null default 'arkit_local',
  vertex_count integer not null default 0,
  triangle_count integer not null default 0,
  vertices jsonb not null default '[]'::jsonb,
  triangle_indices jsonb not null default '[]'::jsonb,
  blend_shapes jsonb not null default '{}'::jsonb,
  face_transform jsonb,
  camera_transform jsonb,
  camera_intrinsics jsonb,
  landmarks_2d jsonb,
  quality jsonb not null default '{}'::jsonb,
  raw_payload jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.face_metric_measurements (
  id uuid primary key default gen_random_uuid(),
  capture_id uuid not null references public.face_scan_captures(id) on delete cascade,
  metric_group text not null check (metric_group in ('proportions', 'aesthetics', 'quality', 'pose', 'derived')),
  metric_id text not null,
  numeric_value numeric,
  unit text,
  display_value text,
  interpretation_key text,
  interpretation_label_en text,
  interpretation_label_ko text,
  confidence numeric(5,4),
  source text not null default 'geometry',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (capture_id, metric_group, metric_id)
);

create index if not exists face_metric_measurements_capture_idx
  on public.face_metric_measurements (capture_id, metric_group, metric_id);

create table if not exists public.look_archetypes (
  id text primary key,
  type_name text not null,
  title_key text not null,
  subtitle_key text,
  body_key text,
  share_badge_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.look_archetypes (
  id, type_name, title_key, subtitle_key, body_key, share_badge_key
) values (
  'clean-cut-heartthrob',
  'Clean-cut Heartthrob',
  'analysis.lookArchetype.title',
  'analysis.lookArchetype.typeSubtitle',
  'analysis.lookArchetype.typeBody',
  'analysis.lookArchetype.shareReady'
) on conflict (id) do update set
  type_name = excluded.type_name,
  title_key = excluded.title_key,
  subtitle_key = excluded.subtitle_key,
  body_key = excluded.body_key,
  share_badge_key = excluded.share_badge_key,
  updated_at = now();

create table if not exists public.look_archetype_traits (
  id uuid primary key default gen_random_uuid(),
  archetype_id text not null references public.look_archetypes(id) on delete cascade,
  trait_id text not null,
  title_key text not null,
  tint text,
  sort_order integer not null,
  unique (archetype_id, trait_id)
);

create table if not exists public.look_archetype_sections (
  id uuid primary key default gen_random_uuid(),
  archetype_id text not null references public.look_archetypes(id) on delete cascade,
  section_id text not null,
  title_key text not null,
  icon_name text not null,
  tint text,
  is_default_expanded boolean not null default false,
  sort_order integer not null,
  unique (archetype_id, section_id)
);

create table if not exists public.look_archetype_bullets (
  id uuid primary key default gen_random_uuid(),
  section_row_id uuid not null references public.look_archetype_sections(id) on delete cascade,
  bullet_id text not null,
  title_key text not null,
  icon_name text not null,
  sort_order integer not null,
  unique (section_row_id, bullet_id)
);

insert into public.look_archetype_traits (
  archetype_id, trait_id, title_key, tint, sort_order
) values
  ('clean-cut-heartthrob', 'clean', 'analysis.lookArchetype.trait.clean', '#34D15C', 10),
  ('clean-cut-heartthrob', 'youthful', 'analysis.lookArchetype.trait.youthful', '#1F91FF', 20),
  ('clean-cut-heartthrob', 'approachable', 'analysis.lookArchetype.trait.approachable', '#63CCFA', 30)
on conflict (archetype_id, trait_id) do update set
  title_key = excluded.title_key,
  tint = excluded.tint,
  sort_order = excluded.sort_order;

insert into public.look_archetype_sections (
  archetype_id, section_id, title_key, icon_name, tint, is_default_expanded, sort_order
) values
  ('clean-cut-heartthrob', 'why-this-fits', 'analysis.lookArchetype.whyThisFits', 'checkmark.seal.fill', '#34D15C', true, 10),
  ('clean-cut-heartthrob', 'best-features', 'analysis.lookArchetype.bestFeatures', 'star.fill', '#1F91FF', false, 20),
  ('clean-cut-heartthrob', 'style-direction', 'analysis.lookArchetype.styleDirection', 'wand.and.stars', '#63CCFA', false, 30),
  ('clean-cut-heartthrob', 'avoid', 'analysis.lookArchetype.avoid', 'xmark.circle.fill', '#FFB020', false, 40)
on conflict (archetype_id, section_id) do update set
  title_key = excluded.title_key,
  icon_name = excluded.icon_name,
  tint = excluded.tint,
  is_default_expanded = excluded.is_default_expanded,
  sort_order = excluded.sort_order;

with bullet_seed(section_id, bullet_id, title_key, icon_name, sort_order) as (
  values
    ('why-this-fits', 'harmony', 'analysis.lookArchetype.why.harmony', 'checkmark.circle.fill', 10),
    ('why-this-fits', 'skin-hair', 'analysis.lookArchetype.why.skinHair', 'checkmark.circle.fill', 20),
    ('why-this-fits', 'soft-impression', 'analysis.lookArchetype.why.softImpression', 'checkmark.circle.fill', 30),
    ('best-features', 'skin', 'analysis.lookArchetype.feature.skin', 'sparkle', 10),
    ('best-features', 'hair', 'analysis.lookArchetype.feature.hair', 'sparkle', 20),
    ('best-features', 'symmetry', 'analysis.lookArchetype.feature.symmetry', 'sparkle', 30),
    ('style-direction', 'natural-light', 'analysis.lookArchetype.style.naturalLight', 'sun.max.fill', 10),
    ('style-direction', 'neat-hair', 'analysis.lookArchetype.style.neatHair', 'comb.fill', 20),
    ('style-direction', 'clean-top', 'analysis.lookArchetype.style.cleanTop', 'tshirt.fill', 30),
    ('style-direction', 'natural-smile', 'analysis.lookArchetype.style.naturalSmile', 'face.smiling', 40),
    ('avoid', 'dark-light', 'analysis.lookArchetype.avoid.darkLight', 'xmark.circle.fill', 10),
    ('avoid', 'blank-expression', 'analysis.lookArchetype.avoid.blankExpression', 'xmark.circle.fill', 20),
    ('avoid', 'heavy-bangs', 'analysis.lookArchetype.avoid.heavyBangs', 'xmark.circle.fill', 30)
),
section_rows as (
  select
    sections.id as section_row_id,
    bullet_seed.bullet_id,
    bullet_seed.title_key,
    bullet_seed.icon_name,
    bullet_seed.sort_order
  from bullet_seed
  join public.look_archetype_sections sections
    on sections.archetype_id = 'clean-cut-heartthrob'
    and sections.section_id = bullet_seed.section_id
)
insert into public.look_archetype_bullets (
  section_row_id, bullet_id, title_key, icon_name, sort_order
)
select section_row_id, bullet_id, title_key, icon_name, sort_order
from section_rows
on conflict (section_row_id, bullet_id) do update set
  title_key = excluded.title_key,
  icon_name = excluded.icon_name,
  sort_order = excluded.sort_order;

create table if not exists public.analysis_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete cascade,
  client_install_id uuid not null default gen_random_uuid(),
  photo_id uuid references public.photos(id) on delete set null,
  photo_ids uuid[] not null default '{}'::uuid[],
  face_scan_capture_id uuid references public.face_scan_captures(id) on delete set null,
  mode_id text not null references public.analysis_modes(id),
  source public.scan_source not null default 'upload',
  status public.analysis_run_status not null default 'queued',
  model_provider public.ai_provider_name,
  model_name text,
  overall_score numeric(4,2),
  overall_progress numeric(5,4),
  potential_score numeric(4,2),
  potential_progress numeric(5,4),
  summary_key text,
  summary_text text,
  look_archetype_id text references public.look_archetypes(id),
  onboarding_context jsonb not null default '{}'::jsonb,
  is_free_trial_result boolean not null default false,
  raw_provider_response jsonb,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.analysis_runs
  add column if not exists face_scan_capture_id uuid references public.face_scan_captures(id) on delete set null;

alter table if exists public.analysis_runs
  add column if not exists onboarding_context jsonb not null default '{}'::jsonb;

alter table if exists public.analysis_runs
  add column if not exists is_free_trial_result boolean not null default false;

create index if not exists analysis_runs_user_created_idx
  on public.analysis_runs (user_id, created_at desc);

create index if not exists analysis_runs_client_created_idx
  on public.analysis_runs (client_install_id, created_at desc);

create index if not exists analysis_runs_mode_created_idx
  on public.analysis_runs (mode_id, created_at desc);

create index if not exists analysis_runs_photo_id_idx
  on public.analysis_runs (photo_id);

create index if not exists analysis_runs_face_scan_capture_id_idx
  on public.analysis_runs (face_scan_capture_id);

create index if not exists analysis_runs_look_archetype_id_idx
  on public.analysis_runs (look_archetype_id);

create table if not exists public.analysis_score_rings (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.analysis_runs(id) on delete cascade,
  metric_id text not null,
  title_key text not null,
  score numeric(5,4) not null,
  display_value text not null,
  tint text,
  sort_order integer not null,
  unique (run_id, metric_id)
);

create table if not exists public.analysis_metrics (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.analysis_runs(id) on delete cascade,
  mode_id text not null references public.analysis_modes(id),
  section text not null,
  metric_id text not null,
  title_key text not null,
  value_text text,
  numeric_value numeric,
  unit text,
  status_text text,
  detail_key text,
  detail_text text,
  icon_name text not null,
  value_tint text,
  sort_order integer not null,
  unique (run_id, section, metric_id)
);

create index if not exists analysis_metrics_run_section_idx
  on public.analysis_metrics (run_id, section, sort_order);

create index if not exists analysis_metrics_mode_id_idx
  on public.analysis_metrics (mode_id);

create table if not exists public.growth_opportunities (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.analysis_runs(id) on delete cascade,
  item_id text not null,
  title_key text,
  body_key text,
  body_text text,
  category text not null,
  sort_order integer not null,
  unique (run_id, item_id)
);

create table if not exists public.glow_up_coach_items (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.analysis_runs(id) on delete cascade,
  section text not null check (section in ('facial_analysis', 'needs_work', 'strengths')),
  item_id text not null,
  title_key text not null,
  assessment_key text,
  assessment_text text,
  action_key text,
  action_text text,
  icon_name text not null,
  is_default_expanded boolean not null default false,
  sort_order integer not null,
  unique (run_id, section, item_id)
);

create table if not exists public.localized_strings (
  key text not null,
  locale text not null check (locale in ('en', 'ko', 'ja', 'de', 'es-419', 'zh-Hant', 'pt-BR', 'fr', 'it', 'id', 'tr', 'ar')),
  value text not null,
  namespace text,
  updated_at timestamptz not null default now(),
  primary key (key, locale)
);

create table if not exists public.user_progress_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  snapshot_date date not null default current_date,
  scans_count integer not null default 0,
  avg_score numeric(4,2),
  best_score numeric(4,2),
  last_score numeric(4,2),
  created_at timestamptz not null default now(),
  unique (user_id, snapshot_date)
);

create or replace view public.user_analysis_summary
with (security_invoker = true) as
select
  runs.user_id,
  count(*) filter (where runs.status = 'completed')::integer as analyses_count,
  max(runs.created_at) filter (where runs.status = 'completed') as last_analysis_at,
  avg(runs.overall_score) filter (where runs.status = 'completed')::numeric(4,2) as average_score,
  max(runs.overall_score) filter (where runs.status = 'completed')::numeric(4,2) as best_score,
  (
    array_agg(runs.overall_score order by runs.created_at desc)
    filter (where runs.status = 'completed' and runs.overall_score is not null)
  )[1]::numeric(4,2) as last_score
from public.analysis_runs runs
group by runs.user_id;

-- Storage bucket for uploaded face photos.
insert into storage.buckets (id, name, public)
values ('face-photos', 'face-photos', false)
on conflict (id) do nothing;

alter table public.profiles enable row level security;
alter table public.user_onboarding_preferences enable row level security;
alter table public.user_usage enable row level security;
alter table public.photos enable row level security;
alter table public.face_scan_captures enable row level security;
alter table public.face_geometry_snapshots enable row level security;
alter table public.face_metric_measurements enable row level security;
alter table public.analysis_modes enable row level security;
alter table public.look_archetypes enable row level security;
alter table public.look_archetype_traits enable row level security;
alter table public.look_archetype_sections enable row level security;
alter table public.look_archetype_bullets enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.analysis_score_rings enable row level security;
alter table public.analysis_metrics enable row level security;
alter table public.growth_opportunities enable row level security;
alter table public.glow_up_coach_items enable row level security;
alter table public.localized_strings enable row level security;
alter table public.user_progress_snapshots enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
on public.profiles for select
using ((select auth.uid()) = id);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
on public.profiles for update
using ((select auth.uid()) = id)
with check ((select auth.uid()) = id);

drop policy if exists "Users can read own onboarding preferences" on public.user_onboarding_preferences;
create policy "Users can read own onboarding preferences"
on public.user_onboarding_preferences for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own onboarding preferences" on public.user_onboarding_preferences;
create policy "Users can insert own onboarding preferences"
on public.user_onboarding_preferences for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can update own onboarding preferences" on public.user_onboarding_preferences;
create policy "Users can update own onboarding preferences"
on public.user_onboarding_preferences for update
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can delete own onboarding preferences" on public.user_onboarding_preferences;
create policy "Users can delete own onboarding preferences"
on public.user_onboarding_preferences for delete
using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.user_onboarding_preferences to authenticated;

drop policy if exists "Users can read own usage" on public.user_usage;
create policy "Users can read own usage"
on public.user_usage for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own photos" on public.photos;
create policy "Users can read own photos"
on public.photos for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own face scan captures" on public.face_scan_captures;
create policy "Users can read own face scan captures"
on public.face_scan_captures for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own face geometry snapshots" on public.face_geometry_snapshots;
create policy "Users can read own face geometry snapshots"
on public.face_geometry_snapshots for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_geometry_snapshots.capture_id and captures.user_id = (select auth.uid())
));

drop policy if exists "Users can read own face metric measurements" on public.face_metric_measurements;
create policy "Users can read own face metric measurements"
on public.face_metric_measurements for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_metric_measurements.capture_id and captures.user_id = (select auth.uid())
));

drop policy if exists "Users can read own analysis runs" on public.analysis_runs;
create policy "Users can read own analysis runs"
on public.analysis_runs for select
using ((select auth.uid()) = user_id);

drop policy if exists "Public can read enabled analysis modes" on public.analysis_modes;
create policy "Public can read enabled analysis modes"
on public.analysis_modes for select
using (is_enabled = true);

drop policy if exists "Public can read look archetypes" on public.look_archetypes;
create policy "Public can read look archetypes"
on public.look_archetypes for select
using (true);

drop policy if exists "Public can read look archetype traits" on public.look_archetype_traits;
create policy "Public can read look archetype traits"
on public.look_archetype_traits for select
using (true);

drop policy if exists "Public can read look archetype sections" on public.look_archetype_sections;
create policy "Public can read look archetype sections"
on public.look_archetype_sections for select
using (true);

drop policy if exists "Public can read look archetype bullets" on public.look_archetype_bullets;
create policy "Public can read look archetype bullets"
on public.look_archetype_bullets for select
using (true);

drop policy if exists "Public can read localized strings" on public.localized_strings;
create policy "Public can read localized strings"
on public.localized_strings for select
using (true);

drop policy if exists "Users can read own score rings" on public.analysis_score_rings;
create policy "Users can read own score rings"
on public.analysis_score_rings for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = analysis_score_rings.run_id and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own analysis metrics" on public.analysis_metrics;
create policy "Users can read own analysis metrics"
on public.analysis_metrics for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = analysis_metrics.run_id and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own growth opportunities" on public.growth_opportunities;
create policy "Users can read own growth opportunities"
on public.growth_opportunities for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = growth_opportunities.run_id and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own coach items" on public.glow_up_coach_items;
create policy "Users can read own coach items"
on public.glow_up_coach_items for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = glow_up_coach_items.run_id and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own progress snapshots" on public.user_progress_snapshots;
create policy "Users can read own progress snapshots"
on public.user_progress_snapshots for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own storage objects" on storage.objects;
create policy "Users can read own storage objects"
on storage.objects for select
using (
  bucket_id = 'face-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Users can upload own storage objects" on storage.objects;
create policy "Users can upload own storage objects"
on storage.objects for insert
with check (
  bucket_id = 'face-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

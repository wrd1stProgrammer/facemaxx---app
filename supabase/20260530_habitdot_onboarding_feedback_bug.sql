-- Habitdot onboarding analytics, feedback, and bug reports.
-- The iOS app writes through FastAPI using X-Facemaxx-Install-Id; direct client writes remain protected by RLS.

create extension if not exists pgcrypto;

create table if not exists public.habitdot_onboarding_responses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  locale text,
  country_code text,
  inferred_country_code text,
  time_zone text,
  app_version text,
  build_number text,
  platform text not null default 'ios',
  source text check (
    source is null
    or source in ('app-store', 'tiktok', 'instagram', 'google', 'x', 'friend', 'youtube', 'other')
  ),
  selected_first_habit text,
  selected_theme text,
  common_reminder_hour integer check (common_reminder_hour is null or common_reminder_hour between 0 and 23),
  common_reminder_minute integer check (common_reminder_minute is null or common_reminder_minute between 0 and 59),
  survey jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  completed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists habitdot_onboarding_install_created_idx
  on public.habitdot_onboarding_responses (client_install_id, created_at desc);

create index if not exists habitdot_onboarding_source_created_idx
  on public.habitdot_onboarding_responses (source, created_at desc);

create index if not exists habitdot_onboarding_country_created_idx
  on public.habitdot_onboarding_responses (coalesce(country_code, inferred_country_code), created_at desc);

create table if not exists public.habitdot_feedback (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  kind text not null default 'feedback' check (kind in ('feedback', 'contact', 'bug')),
  subject text,
  message text not null check (char_length(message) between 1 and 4000),
  contact_email text,
  locale text,
  country_code text,
  inferred_country_code text,
  time_zone text,
  app_version text,
  build_number text,
  platform text not null default 'ios',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists habitdot_feedback_kind_created_idx
  on public.habitdot_feedback (kind, created_at desc);

create index if not exists habitdot_feedback_install_created_idx
  on public.habitdot_feedback (client_install_id, created_at desc);

create table if not exists public.habitdot_bug_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  subject text,
  message text not null check (char_length(message) between 1 and 4000),
  contact_email text,
  locale text,
  country_code text,
  inferred_country_code text,
  time_zone text,
  app_version text,
  build_number text,
  platform text not null default 'ios',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists habitdot_bug_reports_created_idx
  on public.habitdot_bug_reports (created_at desc);

create index if not exists habitdot_bug_reports_install_created_idx
  on public.habitdot_bug_reports (client_install_id, created_at desc);

alter table public.habitdot_onboarding_responses enable row level security;
alter table public.habitdot_feedback enable row level security;
alter table public.habitdot_bug_reports enable row level security;

drop policy if exists "Users can read own Habitdot onboarding" on public.habitdot_onboarding_responses;
create policy "Users can read own Habitdot onboarding"
on public.habitdot_onboarding_responses for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own Habitdot onboarding" on public.habitdot_onboarding_responses;
create policy "Users can insert own Habitdot onboarding"
on public.habitdot_onboarding_responses for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read own Habitdot feedback" on public.habitdot_feedback;
create policy "Users can read own Habitdot feedback"
on public.habitdot_feedback for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own Habitdot feedback" on public.habitdot_feedback;
create policy "Users can insert own Habitdot feedback"
on public.habitdot_feedback for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read own Habitdot bug reports" on public.habitdot_bug_reports;
create policy "Users can read own Habitdot bug reports"
on public.habitdot_bug_reports for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own Habitdot bug reports" on public.habitdot_bug_reports;
create policy "Users can insert own Habitdot bug reports"
on public.habitdot_bug_reports for insert
with check ((select auth.uid()) = user_id);

grant select, insert on public.habitdot_onboarding_responses to authenticated;
grant select, insert on public.habitdot_feedback to authenticated;
grant select, insert on public.habitdot_bug_reports to authenticated;

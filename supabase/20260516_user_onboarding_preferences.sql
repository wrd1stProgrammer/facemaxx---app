-- Persist onboarding choices per authenticated user and snapshot them on analysis runs.

alter table if exists public.profiles
  drop constraint if exists profiles_locale_check;

alter table if exists public.profiles
  add constraint profiles_locale_check
  check (locale in ('en', 'ko', 'ja', 'de', 'es-419', 'zh-Hant', 'pt-BR', 'fr', 'it', 'id', 'tr', 'ar'));

alter table if exists public.localized_strings
  drop constraint if exists localized_strings_locale_check;

alter table if exists public.localized_strings
  add constraint localized_strings_locale_check
  check (locale in ('en', 'ko', 'ja', 'de', 'es-419', 'zh-Hant', 'pt-BR', 'fr', 'it', 'id', 'tr', 'ar'));

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
        'proportions',
        'progress',
        'photos',
        'profile'
      ]::text[]
    )
);

create index if not exists user_onboarding_preferences_completed_idx
  on public.user_onboarding_preferences (completed_at desc);

alter table if exists public.user_onboarding_preferences
  add column if not exists age integer;

alter table if exists public.user_onboarding_preferences
  drop constraint if exists user_onboarding_preferences_age_check;

alter table if exists public.user_onboarding_preferences
  add constraint user_onboarding_preferences_age_check
  check (age is null or age between 13 and 70);

alter table if exists public.analysis_runs
  add column if not exists onboarding_context jsonb not null default '{}'::jsonb;

alter table public.user_onboarding_preferences enable row level security;

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

revoke all on function public.handle_new_user() from public, anon, authenticated;

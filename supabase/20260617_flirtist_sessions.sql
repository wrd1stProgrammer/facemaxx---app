create extension if not exists pgcrypto;

create table if not exists public.flirtist_sessions (
  id text primary key,
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  mode text not null check (mode in ('reply_coach', 'score_analysis')),
  source text not null check (source in ('manual', 'screenshot')),
  locale text not null default 'en-US',
  language text not null check (language in ('en', 'ko')),
  title text not null,
  input_text text,
  image_storage_path text,
  image_url text,
  image_mime_type text,
  chat_preview jsonb not null default '[]'::jsonb,
  reply_coaching jsonb,
  analysis_card jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists flirtist_sessions_user_created_idx
  on public.flirtist_sessions (user_id, created_at desc);

create index if not exists flirtist_sessions_install_created_idx
  on public.flirtist_sessions (client_install_id, created_at desc);

create index if not exists flirtist_sessions_mode_created_idx
  on public.flirtist_sessions (mode, created_at desc);

create table if not exists public.flirtist_coach_messages (
  id uuid primary key default gen_random_uuid(),
  session_id text references public.flirtist_sessions(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  role text not null check (role in ('user', 'assistant')),
  message text not null check (char_length(message) between 1 and 4000),
  locale text not null default 'en-US',
  language text not null check (language in ('en', 'ko')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists flirtist_coach_messages_session_created_idx
  on public.flirtist_coach_messages (session_id, created_at asc);

create index if not exists flirtist_coach_messages_install_created_idx
  on public.flirtist_coach_messages (client_install_id, created_at desc);

alter table public.flirtist_sessions enable row level security;
alter table public.flirtist_coach_messages enable row level security;

drop policy if exists "Users can read own Flirtist sessions" on public.flirtist_sessions;
create policy "Users can read own Flirtist sessions"
on public.flirtist_sessions for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own Flirtist sessions" on public.flirtist_sessions;
create policy "Users can insert own Flirtist sessions"
on public.flirtist_sessions for insert
with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read own Flirtist coach messages" on public.flirtist_coach_messages;
create policy "Users can read own Flirtist coach messages"
on public.flirtist_coach_messages for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can insert own Flirtist coach messages" on public.flirtist_coach_messages;
create policy "Users can insert own Flirtist coach messages"
on public.flirtist_coach_messages for insert
with check ((select auth.uid()) = user_id);

grant select, insert on public.flirtist_sessions to authenticated;
grant select, insert on public.flirtist_coach_messages to authenticated;

alter table public.flirtist_sessions
  add column if not exists image_url text;

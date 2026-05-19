-- Facemaxx face scan capture data model.
-- Run this on an existing Supabase project that already has the base schema.

create extension if not exists pgcrypto;

do $$
begin
  create type public.face_capture_backend as enum ('arkit_true_depth', 'vision_landmarks', 'manual_upload');
exception
  when duplicate_object then null;
end $$;

create table if not exists public.face_scan_captures (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
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

alter table if exists public.analysis_runs
  add column if not exists face_scan_capture_id uuid references public.face_scan_captures(id) on delete set null;

alter table public.face_scan_captures enable row level security;
alter table public.face_geometry_snapshots enable row level security;
alter table public.face_metric_measurements enable row level security;

drop policy if exists "Users can read own face scan captures" on public.face_scan_captures;
create policy "Users can read own face scan captures"
on public.face_scan_captures for select
using (auth.uid() = user_id);

drop policy if exists "Users can read own face geometry snapshots" on public.face_geometry_snapshots;
create policy "Users can read own face geometry snapshots"
on public.face_geometry_snapshots for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_geometry_snapshots.capture_id and captures.user_id = auth.uid()
));

drop policy if exists "Users can read own face metric measurements" on public.face_metric_measurements;
create policy "Users can read own face metric measurements"
on public.face_metric_measurements for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_metric_measurements.capture_id and captures.user_id = auth.uid()
));

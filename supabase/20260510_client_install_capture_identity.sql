-- Allows the pre-auth MVP app to save capture data through FastAPI without
-- requiring every row to reference auth.users/profiles yet.

alter table if exists public.photos
  alter column user_id drop not null;

alter table if exists public.photos
  add column if not exists client_install_id uuid;

update public.photos
set client_install_id = gen_random_uuid()
where client_install_id is null;

alter table if exists public.photos
  alter column client_install_id set default gen_random_uuid(),
  alter column client_install_id set not null;

create index if not exists photos_client_install_created_idx
  on public.photos (client_install_id, created_at desc);

alter table if exists public.face_scan_captures
  alter column user_id drop not null;

alter table if exists public.face_scan_captures
  add column if not exists client_install_id uuid;

update public.face_scan_captures
set client_install_id = gen_random_uuid()
where client_install_id is null;

alter table if exists public.face_scan_captures
  alter column client_install_id set default gen_random_uuid(),
  alter column client_install_id set not null;

create index if not exists face_scan_captures_client_created_idx
  on public.face_scan_captures (client_install_id, created_at desc);

alter table if exists public.analysis_runs
  alter column user_id drop not null;

alter table if exists public.analysis_runs
  add column if not exists client_install_id uuid;

update public.analysis_runs
set client_install_id = gen_random_uuid()
where client_install_id is null;

alter table if exists public.analysis_runs
  alter column client_install_id set default gen_random_uuid(),
  alter column client_install_id set not null;

create index if not exists analysis_runs_client_created_idx
  on public.analysis_runs (client_install_id, created_at desc);

create table if not exists public.habitdot_install_metrics (
  client_install_id uuid primary key,
  paywall_view_count integer not null default 0 check (paywall_view_count >= 0),
  first_paywall_viewed_at timestamptz,
  last_paywall_viewed_at timestamptz,
  last_locale text,
  last_country_code text,
  last_inferred_country_code text,
  last_time_zone text,
  last_app_version text,
  last_build_number text,
  platform text not null default 'ios',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists habitdot_install_metrics_paywall_last_idx
  on public.habitdot_install_metrics (last_paywall_viewed_at desc);

alter table public.habitdot_install_metrics enable row level security;

revoke all on public.habitdot_install_metrics from anon, authenticated;

create or replace function public.increment_habitdot_paywall_view(
  p_client_install_id uuid,
  p_locale text default null,
  p_country_code text default null,
  p_inferred_country_code text default null,
  p_time_zone text default null,
  p_app_version text default null,
  p_build_number text default null,
  p_platform text default 'ios'
)
returns integer
language plpgsql
set search_path = public
as $$
declare
  v_count integer;
begin
  insert into public.habitdot_install_metrics (
    client_install_id,
    paywall_view_count,
    first_paywall_viewed_at,
    last_paywall_viewed_at,
    last_locale,
    last_country_code,
    last_inferred_country_code,
    last_time_zone,
    last_app_version,
    last_build_number,
    platform,
    created_at,
    updated_at
  )
  values (
    p_client_install_id,
    1,
    now(),
    now(),
    nullif(p_locale, ''),
    nullif(p_country_code, ''),
    nullif(p_inferred_country_code, ''),
    nullif(p_time_zone, ''),
    nullif(p_app_version, ''),
    nullif(p_build_number, ''),
    coalesce(nullif(p_platform, ''), 'ios'),
    now(),
    now()
  )
  on conflict (client_install_id) do update
  set paywall_view_count = public.habitdot_install_metrics.paywall_view_count + 1,
      last_paywall_viewed_at = now(),
      last_locale = coalesce(excluded.last_locale, public.habitdot_install_metrics.last_locale),
      last_country_code = coalesce(excluded.last_country_code, public.habitdot_install_metrics.last_country_code),
      last_inferred_country_code = coalesce(
        excluded.last_inferred_country_code,
        public.habitdot_install_metrics.last_inferred_country_code
      ),
      last_time_zone = coalesce(excluded.last_time_zone, public.habitdot_install_metrics.last_time_zone),
      last_app_version = coalesce(excluded.last_app_version, public.habitdot_install_metrics.last_app_version),
      last_build_number = coalesce(excluded.last_build_number, public.habitdot_install_metrics.last_build_number),
      platform = coalesce(excluded.platform, public.habitdot_install_metrics.platform),
      updated_at = now()
  returning paywall_view_count into v_count;

  return v_count;
end;
$$;

revoke all on function public.increment_habitdot_paywall_view(
  uuid,
  text,
  text,
  text,
  text,
  text,
  text,
  text
) from public;

grant execute on function public.increment_habitdot_paywall_view(
  uuid,
  text,
  text,
  text,
  text,
  text,
  text,
  text
) to service_role;

create table if not exists public.purchase_accounts (
  app_user_id text primary key,
  user_id uuid references public.profiles(id) on delete set null,
  client_install_id uuid,
  pro_subscription_active boolean not null default false,
  pro_subscription_product_id text,
  pro_subscription_expires_at timestamptz,
  subscription_scan_period text check (subscription_scan_period in ('week', 'month')),
  subscription_scan_limit integer not null default 0 check (subscription_scan_limit >= 0),
  subscription_scans_remaining integer not null default 0 check (subscription_scans_remaining >= 0),
  subscription_quota_reset_at timestamptz,
  consumable_pro_scans_remaining integer not null default 1 check (consumable_pro_scans_remaining >= 0),
  revenuecat_original_app_user_id text,
  last_synced_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists purchase_accounts_user_id_idx
  on public.purchase_accounts (user_id);

create index if not exists purchase_accounts_client_install_id_idx
  on public.purchase_accounts (client_install_id);

create table if not exists public.revenuecat_events (
  event_id text primary key,
  app_user_id text not null references public.purchase_accounts(app_user_id) on delete cascade,
  event_type text not null,
  product_id text,
  raw_event jsonb not null default '{}'::jsonb,
  received_at timestamptz not null default now()
);

create table if not exists public.revenuecat_credit_transactions (
  transaction_id text primary key,
  app_user_id text not null references public.purchase_accounts(app_user_id) on delete cascade,
  product_id text not null,
  credits_granted integer not null check (credits_granted > 0),
  raw_transaction jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.ensure_purchase_account(
  p_app_user_id text,
  p_user_id uuid default null,
  p_client_install_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.purchase_accounts (app_user_id, user_id, client_install_id)
  values (p_app_user_id, p_user_id, p_client_install_id)
  on conflict (app_user_id) do update set
    user_id = coalesce(excluded.user_id, public.purchase_accounts.user_id),
    client_install_id = coalesce(excluded.client_install_id, public.purchase_accounts.client_install_id),
    updated_at = now();
end;
$$;

create or replace function public.subscription_quota_reset_at(
  p_period text,
  p_expires_at timestamptz default null
)
returns timestamptz
language plpgsql
stable
as $$
begin
  if p_expires_at is not null then
    return p_expires_at;
  end if;

  if p_period = 'month' then
    return now() + interval '1 month';
  end if;

  return now() + interval '7 days';
end;
$$;

create or replace function public.refresh_purchase_account_quota(p_app_user_id text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  account public.purchase_accounts%rowtype;
begin
  select *
  into account
  from public.purchase_accounts
  where app_user_id = p_app_user_id
  for update;

  if not found then
    return;
  end if;

  if account.pro_subscription_active
     and account.pro_subscription_expires_at is not null
     and account.pro_subscription_expires_at <= now() then
    update public.purchase_accounts
    set pro_subscription_active = false,
        subscription_scans_remaining = 0,
        updated_at = now()
    where app_user_id = p_app_user_id;
    return;
  end if;

  if account.pro_subscription_active
     and account.subscription_scan_limit > 0
     and account.subscription_quota_reset_at is not null
     and account.subscription_quota_reset_at <= now() then
    update public.purchase_accounts
    set subscription_scans_remaining = subscription_scan_limit,
        subscription_quota_reset_at = public.subscription_quota_reset_at(
          subscription_scan_period,
          pro_subscription_expires_at
        ),
        updated_at = now()
    where app_user_id = p_app_user_id;
  end if;
end;
$$;

create or replace function public.consume_pro_scan_credit(
  p_app_user_id text,
  p_user_id uuid default null,
  p_client_install_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  account public.purchase_accounts%rowtype;
  subscription_is_active boolean;
begin
  perform public.ensure_purchase_account(p_app_user_id, p_user_id, p_client_install_id);
  perform public.refresh_purchase_account_quota(p_app_user_id);

  select *
  into account
  from public.purchase_accounts
  where app_user_id = p_app_user_id
  for update;

  subscription_is_active :=
    account.pro_subscription_active
    and (
      account.pro_subscription_expires_at is null
      or account.pro_subscription_expires_at > now()
    );

  if subscription_is_active and account.subscription_scans_remaining > 0 then
    update public.purchase_accounts
    set subscription_scans_remaining = subscription_scans_remaining - 1,
        updated_at = now()
    where app_user_id = p_app_user_id
    returning * into account;

    return jsonb_build_object(
      'allowed', true,
      'subscription_active', true,
      'subscription_scans_remaining', account.subscription_scans_remaining,
      'consumable_pro_scans_remaining', account.consumable_pro_scans_remaining,
      'credits_remaining', account.subscription_scans_remaining + account.consumable_pro_scans_remaining,
      'consumed_source', 'subscription'
    );
  end if;

  if account.consumable_pro_scans_remaining > 0 then
    update public.purchase_accounts
    set consumable_pro_scans_remaining = consumable_pro_scans_remaining - 1,
        updated_at = now()
    where app_user_id = p_app_user_id
    returning * into account;

    return jsonb_build_object(
      'allowed', true,
      'subscription_active', subscription_is_active,
      'subscription_scans_remaining', account.subscription_scans_remaining,
      'consumable_pro_scans_remaining', account.consumable_pro_scans_remaining,
      'credits_remaining', account.subscription_scans_remaining + account.consumable_pro_scans_remaining,
      'consumed_source', 'consumable'
    );
  end if;

  return jsonb_build_object(
    'allowed', false,
    'subscription_active', subscription_is_active,
    'subscription_scans_remaining', account.subscription_scans_remaining,
    'consumable_pro_scans_remaining', account.consumable_pro_scans_remaining,
    'credits_remaining', account.subscription_scans_remaining + account.consumable_pro_scans_remaining,
    'consumed_source', null
  );
end;
$$;

create or replace function public.refund_pro_scan_credit(
  p_app_user_id text,
  p_consumed_source text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_consumed_source = 'subscription' then
    update public.purchase_accounts
    set subscription_scans_remaining = least(subscription_scan_limit, subscription_scans_remaining + 1),
        updated_at = now()
    where app_user_id = p_app_user_id;
    return;
  end if;

  if p_consumed_source = 'consumable' then
    update public.purchase_accounts
    set consumable_pro_scans_remaining = consumable_pro_scans_remaining + 1,
        updated_at = now()
    where app_user_id = p_app_user_id;
  end if;
end;
$$;

create or replace function public.set_pro_subscription_status(
  p_app_user_id text,
  p_active boolean,
  p_product_id text default null,
  p_quota_limit integer default 0,
  p_quota_period text default null,
  p_expires_at timestamptz default null,
  p_original_app_user_id text default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  account public.purchase_accounts%rowtype;
  should_reset_quota boolean;
begin
  perform public.ensure_purchase_account(p_app_user_id);

  select *
  into account
  from public.purchase_accounts
  where app_user_id = p_app_user_id
  for update;

  if not p_active then
    update public.purchase_accounts
    set pro_subscription_active = false,
        pro_subscription_product_id = p_product_id,
        pro_subscription_expires_at = p_expires_at,
        subscription_scan_period = p_quota_period,
        subscription_scan_limit = greatest(0, coalesce(p_quota_limit, 0)),
        subscription_scans_remaining = 0,
        subscription_quota_reset_at = p_expires_at,
        revenuecat_original_app_user_id = coalesce(p_original_app_user_id, revenuecat_original_app_user_id),
        last_synced_at = now(),
        updated_at = now()
    where app_user_id = p_app_user_id;
    return;
  end if;

  should_reset_quota :=
    not account.pro_subscription_active
    or account.pro_subscription_product_id is distinct from p_product_id
    or account.pro_subscription_expires_at is null
    or p_expires_at is null
    or p_expires_at > account.pro_subscription_expires_at
    or account.subscription_quota_reset_at is null
    or account.subscription_quota_reset_at <= now();

  update public.purchase_accounts
  set pro_subscription_active = true,
      pro_subscription_product_id = p_product_id,
      pro_subscription_expires_at = p_expires_at,
      subscription_scan_period = p_quota_period,
      subscription_scan_limit = greatest(0, coalesce(p_quota_limit, 0)),
      subscription_scans_remaining = case
        when should_reset_quota then greatest(0, coalesce(p_quota_limit, 0))
        else least(subscription_scans_remaining, greatest(0, coalesce(p_quota_limit, 0)))
      end,
      subscription_quota_reset_at = public.subscription_quota_reset_at(p_quota_period, p_expires_at),
      revenuecat_original_app_user_id = coalesce(p_original_app_user_id, revenuecat_original_app_user_id),
      last_synced_at = now(),
      updated_at = now()
  where app_user_id = p_app_user_id;
end;
$$;

create or replace function public.grant_pro_scan_credits(
  p_app_user_id text,
  p_product_id text,
  p_transaction_id text,
  p_credits integer,
  p_raw_transaction jsonb default '{}'::jsonb
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  inserted_count integer;
begin
  perform public.ensure_purchase_account(p_app_user_id);

  insert into public.revenuecat_credit_transactions (
    transaction_id,
    app_user_id,
    product_id,
    credits_granted,
    raw_transaction
  )
  values (
    p_transaction_id,
    p_app_user_id,
    p_product_id,
    p_credits,
    coalesce(p_raw_transaction, '{}'::jsonb)
  )
  on conflict (transaction_id) do nothing;

  get diagnostics inserted_count = row_count;

  if inserted_count = 1 then
    update public.purchase_accounts
    set consumable_pro_scans_remaining = consumable_pro_scans_remaining + p_credits,
        last_synced_at = now(),
        updated_at = now()
    where app_user_id = p_app_user_id;
    return true;
  end if;

  return false;
end;
$$;

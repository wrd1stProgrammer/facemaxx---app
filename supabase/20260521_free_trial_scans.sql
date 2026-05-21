alter table public.purchase_accounts
  add column if not exists free_trial_scan_available boolean not null default true,
  add column if not exists free_trial_scan_consumed_at timestamptz;

alter table public.analysis_runs
  add column if not exists is_free_trial_result boolean not null default false;

alter table public.user_onboarding_preferences
  drop constraint if exists user_onboarding_preferences_goal_ids_check;

alter table public.user_onboarding_preferences
  add constraint user_onboarding_preferences_goal_ids_check
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
  );

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
      'free_trial_scan_available', account.free_trial_scan_available,
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
      'free_trial_scan_available', account.free_trial_scan_available,
      'subscription_scans_remaining', account.subscription_scans_remaining,
      'consumable_pro_scans_remaining', account.consumable_pro_scans_remaining,
      'credits_remaining', account.subscription_scans_remaining + account.consumable_pro_scans_remaining,
      'consumed_source', 'consumable'
    );
  end if;

  if p_user_id is not null and not subscription_is_active and account.free_trial_scan_available then
    update public.purchase_accounts
    set free_trial_scan_available = false,
        free_trial_scan_consumed_at = now(),
        updated_at = now()
    where app_user_id = p_app_user_id
    returning * into account;

    return jsonb_build_object(
      'allowed', true,
      'subscription_active', false,
      'free_trial_scan_available', false,
      'subscription_scans_remaining', account.subscription_scans_remaining,
      'consumable_pro_scans_remaining', account.consumable_pro_scans_remaining,
      'credits_remaining', account.subscription_scans_remaining + account.consumable_pro_scans_remaining,
      'consumed_source', 'free_trial'
    );
  end if;

  return jsonb_build_object(
    'allowed', false,
    'subscription_active', subscription_is_active,
    'free_trial_scan_available', account.free_trial_scan_available,
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
  if p_consumed_source = 'free_trial' then
    update public.purchase_accounts
    set free_trial_scan_available = true,
        free_trial_scan_consumed_at = null,
        updated_at = now()
    where app_user_id = p_app_user_id;
    return;
  end if;

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

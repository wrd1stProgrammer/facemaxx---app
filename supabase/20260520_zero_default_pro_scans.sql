alter table public.purchase_accounts
  alter column consumable_pro_scans_remaining set default 0;

update public.purchase_accounts
set consumable_pro_scans_remaining = 0,
    updated_at = now()
where consumable_pro_scans_remaining = 1
  and pro_subscription_active = false
  and pro_subscription_product_id is null
  and not exists (
    select 1
    from public.revenuecat_credit_transactions tx
    where tx.app_user_id = purchase_accounts.app_user_id
  );

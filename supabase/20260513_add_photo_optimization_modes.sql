insert into public.analysis_modes (
  id, title_key, icon_name, badge_key, badge_type, badge_color, is_highlighted, sort_order, is_enabled
) values
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

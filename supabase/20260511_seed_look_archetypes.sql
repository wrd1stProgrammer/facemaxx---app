insert into public.look_archetypes (
  id, type_name, title_key, subtitle_key, body_key, share_badge_key
) values
  (
    'clean-cut-heartthrob',
    'Clean-cut Heartthrob',
    'analysis.lookArchetype.title',
    'analysis.lookArchetype.typeSubtitle',
    'analysis.lookArchetype.typeBody',
    'analysis.lookArchetype.shareReady'
  ),
  (
    'cold-handsome-type',
    'Cold Handsome Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'soft-boy-next-door',
    'Soft Boy Next Door',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'k-pop-idol-type',
    'K-pop Idol Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'model-like-sharp-type',
    'Model-like Sharp Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'athletic-masculine-type',
    'Athletic Masculine Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'warm-approachable-type',
    'Warm Approachable Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'dark-academia-type',
    'Dark Academia Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'pretty-boy-type',
    'Pretty Boy Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  ),
  (
    'charismatic-leader-type',
    'Charismatic Leader Type',
    'analysis.lookArchetype.title',
    null,
    null,
    'analysis.lookArchetype.shareReady'
  )
on conflict (id) do update set
  type_name = excluded.type_name,
  title_key = excluded.title_key,
  subtitle_key = excluded.subtitle_key,
  body_key = excluded.body_key,
  share_badge_key = excluded.share_badge_key,
  updated_at = now();

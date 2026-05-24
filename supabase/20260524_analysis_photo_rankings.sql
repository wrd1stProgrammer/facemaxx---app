create table if not exists public.analysis_photo_rankings (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.analysis_runs(id) on delete cascade,
  photo_id uuid references public.photos(id) on delete set null,
  candidate_index integer not null check (candidate_index >= 1),
  rank integer not null check (rank >= 1),
  score numeric(4,2),
  verdict text,
  reason_text text,
  description_text text,
  best_use_text text,
  fun_label_text text,
  strengths text[] not null default '{}'::text[],
  weakness_text text,
  fix_text text,
  caption_idea_text text,
  vibe_tags text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  unique (run_id, candidate_index),
  unique (run_id, rank)
);

create index if not exists analysis_photo_rankings_run_rank_idx
  on public.analysis_photo_rankings (run_id, rank);

create index if not exists analysis_photo_rankings_photo_id_idx
  on public.analysis_photo_rankings (photo_id);

alter table public.analysis_photo_rankings enable row level security;

drop policy if exists "Users can read own photo rankings" on public.analysis_photo_rankings;
create policy "Users can read own photo rankings"
on public.analysis_photo_rankings for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = analysis_photo_rankings.run_id
    and runs.user_id = (select auth.uid())
));

insert into public.analysis_photo_rankings (
  run_id,
  photo_id,
  candidate_index,
  rank,
  score,
  verdict,
  reason_text,
  description_text,
  best_use_text,
  fun_label_text,
  strengths,
  weakness_text,
  fix_text,
  caption_idea_text,
  vibe_tags,
  metadata,
  sort_order
)
select
  runs.id,
  runs.photo_ids[parsed.candidate_index],
  parsed.candidate_index,
  parsed.rank,
  case
    when (item.value ->> 'score') ~ '^[[:space:]]*[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)[[:space:]]*$'
      then (item.value ->> 'score')::numeric
    else null
  end,
  item.value ->> 'verdict',
  item.value ->> 'reason_text',
  item.value ->> 'description_text',
  item.value ->> 'best_use_text',
  item.value ->> 'fun_label_text',
  coalesce((
    select array_agg(strength)
    from jsonb_array_elements_text(
      case
        when jsonb_typeof(item.value -> 'strengths') = 'array' then item.value -> 'strengths'
        else '[]'::jsonb
      end
    ) as strength
  ), '{}'::text[]),
  item.value ->> 'weakness_text',
  item.value ->> 'fix_text',
  item.value ->> 'caption_idea_text',
  coalesce((
    select array_agg(tag)
    from jsonb_array_elements_text(
      case
        when jsonb_typeof(item.value -> 'vibe_tags') = 'array' then item.value -> 'vibe_tags'
        else '[]'::jsonb
      end
    ) as tag
  ), '{}'::text[]),
  item.value,
  item.ordinality::integer * 10
from public.analysis_runs runs
cross join lateral jsonb_array_elements(
  case
    when jsonb_typeof(runs.raw_provider_response -> 'photo_rankings') = 'array'
      then runs.raw_provider_response -> 'photo_rankings'
    else '[]'::jsonb
  end
)
  with ordinality as item(value, ordinality)
cross join lateral (
  select
    case
      when (item.value ->> 'candidate_index') ~ '^[[:space:]]*[0-9]+[[:space:]]*$'
        then (item.value ->> 'candidate_index')::integer
      else null
    end as candidate_index,
    case
      when (item.value ->> 'rank') ~ '^[[:space:]]*[0-9]+[[:space:]]*$'
        then (item.value ->> 'rank')::integer
      else null
    end as rank
) parsed
where item.value ? 'candidate_index'
  and item.value ? 'rank'
  and parsed.candidate_index >= 1
  and parsed.rank >= 1
on conflict (run_id, candidate_index) do nothing;

alter table if exists public.analysis_runs
  add column if not exists photo_ids uuid[] not null default '{}'::uuid[];

update public.analysis_runs
set photo_ids = array[photo_id]
where photo_id is not null
  and (photo_ids is null or cardinality(photo_ids) = 0);

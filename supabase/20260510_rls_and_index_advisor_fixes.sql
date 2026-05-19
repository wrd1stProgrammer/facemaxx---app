-- Advisor fixes after initial Facemaxx schema migration.

revoke all on function public.handle_new_user() from public, anon, authenticated;

create index if not exists photos_user_id_idx
  on public.photos (user_id);

create index if not exists face_scan_captures_photo_id_idx
  on public.face_scan_captures (photo_id);

create index if not exists analysis_runs_photo_id_idx
  on public.analysis_runs (photo_id);

create index if not exists analysis_runs_face_scan_capture_id_idx
  on public.analysis_runs (face_scan_capture_id);

create index if not exists analysis_runs_look_archetype_id_idx
  on public.analysis_runs (look_archetype_id);

create index if not exists analysis_metrics_mode_id_idx
  on public.analysis_metrics (mode_id);

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
on public.profiles for select
using ((select auth.uid()) = id);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
on public.profiles for update
using ((select auth.uid()) = id)
with check ((select auth.uid()) = id);

drop policy if exists "Users can read own usage" on public.user_usage;
create policy "Users can read own usage"
on public.user_usage for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own photos" on public.photos;
create policy "Users can read own photos"
on public.photos for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own face scan captures" on public.face_scan_captures;
create policy "Users can read own face scan captures"
on public.face_scan_captures for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own face geometry snapshots" on public.face_geometry_snapshots;
create policy "Users can read own face geometry snapshots"
on public.face_geometry_snapshots for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_geometry_snapshots.capture_id
    and captures.user_id = (select auth.uid())
));

drop policy if exists "Users can read own face metric measurements" on public.face_metric_measurements;
create policy "Users can read own face metric measurements"
on public.face_metric_measurements for select
using (exists (
  select 1 from public.face_scan_captures captures
  where captures.id = face_metric_measurements.capture_id
    and captures.user_id = (select auth.uid())
));

drop policy if exists "Users can read own analysis runs" on public.analysis_runs;
create policy "Users can read own analysis runs"
on public.analysis_runs for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own score rings" on public.analysis_score_rings;
create policy "Users can read own score rings"
on public.analysis_score_rings for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = analysis_score_rings.run_id
    and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own analysis metrics" on public.analysis_metrics;
create policy "Users can read own analysis metrics"
on public.analysis_metrics for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = analysis_metrics.run_id
    and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own growth opportunities" on public.growth_opportunities;
create policy "Users can read own growth opportunities"
on public.growth_opportunities for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = growth_opportunities.run_id
    and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own coach items" on public.glow_up_coach_items;
create policy "Users can read own coach items"
on public.glow_up_coach_items for select
using (exists (
  select 1 from public.analysis_runs runs
  where runs.id = glow_up_coach_items.run_id
    and runs.user_id = (select auth.uid())
));

drop policy if exists "Users can read own progress snapshots" on public.user_progress_snapshots;
create policy "Users can read own progress snapshots"
on public.user_progress_snapshots for select
using ((select auth.uid()) = user_id);

drop policy if exists "Users can read own storage objects" on storage.objects;
create policy "Users can read own storage objects"
on storage.objects for select
using (
  bucket_id = 'face-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Users can upload own storage objects" on storage.objects;
create policy "Users can upload own storage objects"
on storage.objects for insert
with check (
  bucket_id = 'face-photos'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create table if not exists public.analysis_metric_templates (
  mode_id text not null references public.analysis_modes(id) on delete cascade,
  section text not null,
  metric_id text not null,
  title_key text not null,
  icon_name text not null,
  sort_order integer not null,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (mode_id, section, metric_id)
);

create index if not exists analysis_metric_templates_mode_section_idx
  on public.analysis_metric_templates (mode_id, section, sort_order);

insert into public.analysis_metric_templates (
  mode_id, section, metric_id, title_key, icon_name, sort_order, is_enabled
) values
  ('dating-profile-score', 'dating_profile', 'main-photo-suitability', 'analysis.photoOptimization.metric.mainPhotoSuitability', 'heart.fill', 10, true),
  ('dating-profile-score', 'dating_profile', 'first-swipe-read', 'analysis.photoOptimization.metric.firstSwipeRead', 'sparkles', 20, true),
  ('dating-profile-score', 'dating_profile', 'approachability', 'analysis.photoOptimization.metric.approachability', 'bubble.left.and.bubble.right.fill', 30, true),
  ('dating-profile-score', 'dating_profile', 'confidence-signal', 'analysis.photoOptimization.metric.confidenceSignal', 'bolt.fill', 40, true),
  ('dating-profile-score', 'dating_profile', 'trust-signal', 'analysis.photoOptimization.metric.trustSignal', 'checkmark.seal.fill', 50, true),
  ('dating-profile-score', 'dating_profile', 'style-signal', 'analysis.photoOptimization.metric.styleSignal', 'person.crop.square.fill', 60, true),
  ('dating-profile-score', 'dating_profile', 'conversation-hook', 'analysis.photoOptimization.metric.conversationHook', 'text.bubble.fill', 70, true),
  ('dating-profile-score', 'dating_profile', 'photo-context', 'analysis.photoOptimization.metric.photoContext', 'rectangle.stack.fill', 80, true),
  ('dating-profile-score', 'dating_profile', 'red-flag-risk', 'analysis.photoOptimization.metric.redFlagRisk', 'exclamationmark.triangle.fill', 90, true),
  ('dating-profile-score', 'profile_plan', 'photo-mix', 'analysis.photoOptimization.metric.photoMix', 'rectangle.stack.fill', 100, true),
  ('dating-profile-score', 'profile_plan', 'profile-role', 'analysis.photoOptimization.metric.profileRole', 'person.crop.square.fill', 110, true),
  ('dating-profile-score', 'profile_plan', 'message-bait', 'analysis.photoOptimization.metric.messageBait', 'text.bubble.fill', 120, true),
  ('dating-profile-score', 'profile_plan', 'missing-shot', 'analysis.photoOptimization.metric.missingShot', 'camera.fill', 130, true),
  ('dating-profile-score', 'profile_plan', 'opener-angle', 'analysis.photoOptimization.metric.openerAngle', 'wand.and.stars', 140, true),
  ('dating-profile-score', 'profile_plan', 'avoid-profile', 'analysis.photoOptimization.metric.avoidProfile', 'xmark.octagon.fill', 150, true),
  ('instagram-profile-score', 'instagram_profile', 'profile-crop', 'analysis.photoOptimization.metric.profileCrop', 'crop', 10, true),
  ('instagram-profile-score', 'instagram_profile', 'thumbnail-impact', 'analysis.photoOptimization.metric.thumbnailImpact', 'viewfinder', 20, true),
  ('instagram-profile-score', 'instagram_profile', 'profile-icon-energy', 'analysis.photoOptimization.metric.profileIconEnergy', 'person.crop.square.fill', 30, true),
  ('instagram-profile-score', 'instagram_profile', 'first-impression', 'analysis.photoOptimization.metric.firstImpression', 'sparkles', 40, true),
  ('instagram-profile-score', 'instagram_profile', 'feed-fit', 'analysis.photoOptimization.metric.feedFit', 'square.grid.3x3.fill', 50, true),
  ('instagram-profile-score', 'instagram_profile', 'story-thumbnail', 'analysis.photoOptimization.metric.storyThumbnail', 'circle.grid.cross.fill', 60, true),
  ('instagram-profile-score', 'instagram_profile', 'scroll-stop-power', 'analysis.photoOptimization.metric.scrollStopPower', 'bolt.fill', 70, true),
  ('instagram-profile-score', 'instagram_profile', 'visual-consistency', 'analysis.photoOptimization.metric.visualConsistency', 'slider.horizontal.3', 80, true),
  ('instagram-profile-score', 'instagram_profile', 'color-mood', 'analysis.photoOptimization.metric.colorMood', 'slider.horizontal.3', 90, true),
  ('instagram-profile-score', 'content_plan', 'caption-direction', 'analysis.photoOptimization.metric.captionDirection', 'text.bubble.fill', 100, true),
  ('instagram-profile-score', 'content_plan', 'grid-anchor', 'analysis.photoOptimization.metric.gridAnchor', 'square.grid.3x3.fill', 110, true),
  ('instagram-profile-score', 'content_plan', 'story-reply-trigger', 'analysis.photoOptimization.metric.storyReplyTrigger', 'text.bubble.fill', 120, true),
  ('instagram-profile-score', 'content_plan', 'carousel-use', 'analysis.photoOptimization.metric.carouselUse', 'rectangle.stack.fill', 130, true),
  ('instagram-profile-score', 'content_plan', 'posting-rhythm', 'analysis.photoOptimization.metric.postingRhythm', 'calendar', 140, true),
  ('instagram-profile-score', 'content_plan', 'filter-risk', 'analysis.photoOptimization.metric.filterRisk', 'exclamationmark.triangle.fill', 150, true),
  ('instagram-profile-score', 'content_plan', 'posting-fix', 'analysis.photoOptimization.metric.postingFix', 'wand.and.stars', 160, true)
on conflict (mode_id, section, metric_id) do update set
  title_key = excluded.title_key,
  icon_name = excluded.icon_name,
  sort_order = excluded.sort_order,
  is_enabled = excluded.is_enabled,
  updated_at = now();

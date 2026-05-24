-- Keep photo-by-photo detail chips compact and prevent internal scan terms
-- from being persisted in user-facing photo-ranking copy.

do $$
declare
  internal_terms_pattern text := '(face[[:space:]]*mesh|mesh([[:space:]]*data)?|wireframe|landmark(s|[[:space:]]*overlay)?|overlay|arkit|apple[[:space:]]+vision|vision[[:space:]]+framework|geometry[[:space:]]+(metadata|data)|scan[[:space:]]+(payload|data)|메시|메쉬|오버레이|랜드마크|와이어프레임|기하(학)?[[:space:]]*데이터|스캔[[:space:]]*데이터)';
  fallback_text text := '원본 사진 기준으로 조명, 각도, 표정, 얼굴 가독성을 다시 확인하는 것이 좋습니다.';
begin
  if to_regclass('public.analysis_photo_rankings') is not null then
    with normalized as (
      select
        id,
        coalesce(strengths, '{}'::text[]) as strengths,
        coalesce(vibe_tags, '{}'::text[]) as vibe_tags
      from public.analysis_photo_rankings
    )
    update public.analysis_photo_rankings rankings
    set
      strengths = case
        when cardinality(normalized.strengths) > 0
          then coalesce(normalized.strengths[1:least(cardinality(normalized.strengths), 3)], '{}'::text[])
        else '{}'::text[]
      end,
      vibe_tags = case
        when 3 - least(cardinality(normalized.strengths), 3) > 0 and cardinality(normalized.vibe_tags) > 0
          then coalesce(normalized.vibe_tags[1:(3 - least(cardinality(normalized.strengths), 3))], '{}'::text[])
        else '{}'::text[]
      end
    from normalized
    where rankings.id = normalized.id;

    update public.analysis_photo_rankings
    set
      verdict = case when verdict ~* internal_terms_pattern then null else verdict end,
      reason_text = case when reason_text ~* internal_terms_pattern then fallback_text else reason_text end,
      description_text = case when description_text ~* internal_terms_pattern then fallback_text else description_text end,
      best_use_text = case when best_use_text ~* internal_terms_pattern then fallback_text else best_use_text end,
      fun_label_text = case when fun_label_text ~* internal_terms_pattern then null else fun_label_text end,
      weakness_text = case when weakness_text ~* internal_terms_pattern then fallback_text else weakness_text end,
      fix_text = case when fix_text ~* internal_terms_pattern then fallback_text else fix_text end,
      caption_idea_text = case when caption_idea_text ~* internal_terms_pattern then null else caption_idea_text end
    where (
      coalesce(verdict, '') || ' ' ||
      coalesce(reason_text, '') || ' ' ||
      coalesce(description_text, '') || ' ' ||
      coalesce(best_use_text, '') || ' ' ||
      coalesce(fun_label_text, '') || ' ' ||
      coalesce(weakness_text, '') || ' ' ||
      coalesce(fix_text, '') || ' ' ||
      coalesce(caption_idea_text, '')
    ) ~* internal_terms_pattern;

    alter table public.analysis_photo_rankings
      drop constraint if exists analysis_photo_rankings_chip_count_check;

    alter table public.analysis_photo_rankings
      add constraint analysis_photo_rankings_chip_count_check
      check (
        coalesce(cardinality(strengths), 0) + coalesce(cardinality(vibe_tags), 0) <= 3
      );

    alter table public.analysis_photo_rankings
      drop constraint if exists analysis_photo_rankings_no_internal_terms_check;

    alter table public.analysis_photo_rankings
      add constraint analysis_photo_rankings_no_internal_terms_check
      check (
        not ((
            coalesce(verdict, '') || ' ' ||
            coalesce(reason_text, '') || ' ' ||
            coalesce(description_text, '') || ' ' ||
            coalesce(best_use_text, '') || ' ' ||
            coalesce(fun_label_text, '') || ' ' ||
            coalesce(weakness_text, '') || ' ' ||
            coalesce(fix_text, '') || ' ' ||
            coalesce(caption_idea_text, '')
          ) ~* '(face[[:space:]]*mesh|mesh([[:space:]]*data)?|wireframe|landmark(s|[[:space:]]*overlay)?|overlay|arkit|apple[[:space:]]+vision|vision[[:space:]]+framework|geometry[[:space:]]+(metadata|data)|scan[[:space:]]+(payload|data)|메시|메쉬|오버레이|랜드마크|와이어프레임|기하(학)?[[:space:]]*데이터|스캔[[:space:]]*데이터)'
        )
      );
  end if;
end $$;

from __future__ import annotations

import json
from typing import Any


TITLE_KEYS = {
    "rings": {
        "symmetry": "analysis.results.ring.symmetry",
        "skin": "analysis.results.ring.skin",
        "jawline": "analysis.results.ring.jawline",
        "eye-area": "analysis.results.ring.eyeArea",
        "cheekbones": "analysis.results.ring.cheekbones",
        "eyebrows": "analysis.results.ring.eyebrows",
        "glow": "analysis.results.ring.glow",
        "hair": "analysis.results.ring.hair",
        "harmony": "analysis.results.ring.harmony",
        "clarity": "analysis.photoOptimization.ring.clarity",
        "expression": "analysis.photoOptimization.ring.expression",
        "lighting": "analysis.photoOptimization.ring.lighting",
        "composition": "analysis.photoOptimization.ring.composition",
        "background": "analysis.photoOptimization.ring.background",
        "presence": "analysis.photoOptimization.ring.presence",
        "front": "analysis.photoOptimization.ring.front",
        "left": "analysis.photoOptimization.ring.left",
        "right": "analysis.photoOptimization.ring.right",
        "high-angle": "analysis.photoOptimization.ring.highAngle",
        "low-angle": "analysis.photoOptimization.ring.lowAngle",
        "first-impression": "analysis.photoOptimization.ring.firstImpression",
        "approachability": "analysis.photoOptimization.ring.approachability",
        "confidence": "analysis.photoOptimization.ring.confidence",
        "trust": "analysis.photoOptimization.ring.trust",
        "style": "analysis.photoOptimization.ring.style",
        "conversation": "analysis.photoOptimization.ring.conversation",
        "visual-impact": "analysis.photoOptimization.ring.visualImpact",
        "crop": "analysis.photoOptimization.ring.crop",
        "feed-fit": "analysis.photoOptimization.ring.feedFit",
        "shareability": "analysis.photoOptimization.ring.shareability",
        "vibe": "analysis.photoOptimization.ring.vibe",
    },
    "aesthetics": {
        "symmetry": "analysis.results.metric.symmetry",
        "canthal-tilt": "analysis.results.metric.canthalTilt",
        "gonial-angle": "analysis.results.metric.gonialAngle",
        "skin-quality": "analysis.results.metric.skinQuality",
        "cheekbone-projection": "analysis.results.metric.cheekboneProjection",
        "jawline-definition": "analysis.results.metric.jawlineDefinition",
        "estimated-age": "analysis.results.fun.estimatedAge",
        "smile-score": "analysis.results.fun.smileScore",
        "mood": "analysis.results.fun.mood",
        "glasses": "analysis.results.fun.glasses",
        "facial-hair": "analysis.results.fun.facialHair",
        "face-depth-width-ratio": "analysis.aestheticsResults.proportion.faceDepthWidthRatio",
        "face-contour-width-height-ratio": "analysis.aestheticsResults.proportion.faceContourWidthHeightRatio",
    },
    "proportions": {
        "face-shape": "analysis.aestheticsResults.shape.faceShape",
        "eye-shape": "analysis.aestheticsResults.shape.eyeShape",
        "eyebrow-shape": "analysis.aestheticsResults.shape.eyebrowShape",
        "lip-shape": "analysis.aestheticsResults.shape.lipShape",
        "canthal-tilt": "analysis.aestheticsResults.proportion.canthalTilt",
        "eye-spacing-ratio": "analysis.aestheticsResults.proportion.eyeSpacingRatio",
        "face-width-height-ratio": "analysis.aestheticsResults.proportion.faceWidthHeightRatio",
        "midface-ratio": "analysis.aestheticsResults.proportion.midfaceRatio",
        "philtrum-chin-ratio": "analysis.aestheticsResults.proportion.philtrumToChinRatio",
        "eye-width-face-ratio": "analysis.aestheticsResults.proportion.eyeWidthFaceRatio",
        "upper-lower-lip-ratio": "analysis.aestheticsResults.proportion.upperLipToLowerLip",
        "eye-width-height-ratio": "analysis.aestheticsResults.proportion.eyeWidthHeightRatio",
        "lower-full-face-ratio": "analysis.aestheticsResults.proportion.lowerToFullFaceRatio",
        "eye-mouth-angle": "analysis.aestheticsResults.proportion.eyeToMouthAngle",
        "face-depth-width-ratio": "analysis.aestheticsResults.proportion.faceDepthWidthRatio",
        "face-contour-width-height-ratio": "analysis.aestheticsResults.proportion.faceContourWidthHeightRatio",
    },
    "coach": {
        "symmetry": "analysis.glowUpCoach.item.symmetry",
        "skin": "analysis.glowUpCoach.item.skin",
        "jawline": "analysis.glowUpCoach.item.jawline",
        "eye-area": "analysis.glowUpCoach.item.eyeArea",
        "cheekbones": "analysis.glowUpCoach.item.cheekbones",
        "eyebrows": "analysis.glowUpCoach.item.eyebrows",
        "glow": "analysis.glowUpCoach.item.glow",
        "hair": "analysis.glowUpCoach.item.hair",
        "confidence": "analysis.glowUpCoach.item.confidence",
        "expression-confidence": "analysis.glowUpCoach.item.expressionConfidence",
        "face-width-height-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-width-to-height-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-length-width-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-length-to-width-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "camera-angle": "analysis.glowUpCoach.item.cameraAngle",
        "lighting": "analysis.glowUpCoach.item.lighting",
        "grooming": "analysis.glowUpCoach.item.grooming",
        "photo-presence": "analysis.glowUpCoach.item.photoPresence",
        "skin-quality": "analysis.glowUpCoach.item.skinQuality",
    },
    "photo_optimization": {
        "best-pick-readiness": "analysis.photoOptimization.metric.bestPickReadiness",
        "face-visibility": "analysis.photoOptimization.metric.faceVisibility",
        "expression-warmth": "analysis.photoOptimization.metric.expressionWarmth",
        "lighting-quality": "analysis.photoOptimization.metric.lightingQuality",
        "composition": "analysis.photoOptimization.metric.composition",
        "background-control": "analysis.photoOptimization.metric.backgroundControl",
        "winning-move": "analysis.photoOptimization.metric.winningMove",
        "retake-light": "analysis.photoOptimization.metric.retakeLight",
        "edit-cleanup": "analysis.photoOptimization.metric.editCleanup",
        "best-angle": "analysis.photoOptimization.metric.bestAngle",
        "front-read": "analysis.photoOptimization.metric.frontRead",
        "left-read": "analysis.photoOptimization.metric.leftRead",
        "right-read": "analysis.photoOptimization.metric.rightRead",
        "camera-height": "analysis.photoOptimization.metric.cameraHeight",
        "avoid-angle": "analysis.photoOptimization.metric.avoidAngle",
        "retake-plan": "analysis.photoOptimization.metric.retakePlan",
        "main-photo-suitability": "analysis.photoOptimization.metric.mainPhotoSuitability",
        "approachability": "analysis.photoOptimization.metric.approachability",
        "confidence-signal": "analysis.photoOptimization.metric.confidenceSignal",
        "trust-signal": "analysis.photoOptimization.metric.trustSignal",
        "conversation-hook": "analysis.photoOptimization.metric.conversationHook",
        "photo-mix": "analysis.photoOptimization.metric.photoMix",
        "avoid-profile": "analysis.photoOptimization.metric.avoidProfile",
        "profile-crop": "analysis.photoOptimization.metric.profileCrop",
        "first-impression": "analysis.photoOptimization.metric.firstImpression",
        "feed-fit": "analysis.photoOptimization.metric.feedFit",
        "story-thumbnail": "analysis.photoOptimization.metric.storyThumbnail",
        "visual-consistency": "analysis.photoOptimization.metric.visualConsistency",
        "caption-direction": "analysis.photoOptimization.metric.captionDirection",
        "posting-fix": "analysis.photoOptimization.metric.postingFix",
    },
}


ANALYSIS_JSON_CONTRACT = """
Return valid JSON only, with no Markdown fences.
Required top-level shape:
{
  "mode_id": string,
  "provider": string,
  "model_name": string,
  "overall_score": number 0..10 | null,
  "overall_progress": number 0..1 | null,
  "potential_score": number 0..10 | null,
  "potential_progress": number 0..1 | null,
  "summary_text": string | null,
  "photo_rankings": [
    {"candidate_index": number, "rank": number, "score": number | null, "verdict": string, "reason_text": string}
  ],
  "rings": [
    {"metric_id": string, "title_key": string, "score": number 0..1, "display_value": "8.3", "tint": "#7EF0A1", "sort_order": number}
  ],
  "metrics": [
    {
      "section": string,
      "metric_id": string,
      "title_key": string,
      "value_text": "6.8° · Positive",
      "numeric_value": number | null,
      "unit": string | null,
      "status_text": string | null,
      "detail_text": string,
      "icon_name": string,
      "value_tint": "#34D15C",
      "sort_order": number
    }
  ],
  "growth_opportunities": [
    {"item_id": string, "title_key": string | null, "body_text": string, "category": string, "sort_order": number}
  ],
  "coach_items": [
    {
      "section": "facial_analysis" | "needs_work" | "strengths",
      "item_id": string,
      "title_key": string,
      "assessment_text": string,
      "action_text": string,
      "icon_name": string,
      "is_default_expanded": boolean,
      "sort_order": number
    }
  ],
  "look_archetype": {
    "archetype_id": string,
    "title_key": "analysis.lookArchetype.title",
    "type_name": string,
    "subtitle_text": string,
    "body_text": string,
    "share_badge_key": "analysis.lookArchetype.shareReady",
    "traits": [{"trait_id": string, "title_key": string, "title_text": string | null, "tint": string, "sort_order": number}],
    "sections": [
      {
        "section_id": string,
        "title_key": string,
        "title_text": string | null,
        "icon_name": string,
        "tint": string,
        "is_default_expanded": boolean,
        "sort_order": number,
        "bullets": [{"bullet_id": string, "title_key": string, "title_text": string, "icon_name": string, "sort_order": number}]
      }
    ]
  } | null
}
"""


SUPPORTED_LOCALE_NAMES = {
    "en": "natural American English",
    "ko": "natural Korean",
    "ja": "natural Japanese",
    "de": "natural German",
    "es-419": "natural Latin American Spanish",
    "zh-Hant": "natural Traditional Chinese",
    "pt-BR": "natural Brazilian Portuguese",
    "fr": "natural French",
    "it": "natural Italian",
    "id": "natural Indonesian",
    "tr": "natural Turkish",
    "ar": "natural Arabic",
}


MODE_PROMPT_SPECS = {
    "proportions": """
Mode-specific output:
- Return shapes metrics in section "shapes" and ratio metrics in section "proportions".
- Include exactly these shape metric_id values: face-shape, eye-shape, eyebrow-shape, lip-shape.
- Include these proportion metric_id values in order when visible/estimable: canthal-tilt, eye-spacing-ratio, face-width-height-ratio, midface-ratio, philtrum-chin-ratio, eye-width-face-ratio, upper-lower-lip-ratio, eye-width-height-ratio, lower-full-face-ratio, eye-mouth-angle, face-depth-width-ratio, face-contour-width-height-ratio.
- For values that are estimated from a single 2D photo rather than directly measured, say so in detail_text without weakening the report. Never leave value_text/detail_text blank.
- Explain ratios as coaching context, not as a harsh score. Make each detail_text say what the measurement means, what the visible read suggests, and how to retake or present the face better.
""",
    "aesthetics": """
Mode-specific output:
- Return 9 rings, at least 6 detailed_metrics, at least 3 fun_metrics, 2-3 growth_opportunities, potential score, and a complete summary_text.
- Rings must use these metric_id values: symmetry, skin, jawline, eye-area, cheekbones, eyebrows, glow, hair, harmony.
- detailed_metrics should cover visible structure, skin/texture, jawline, eye area, cheekbone/volume, hair/grooming or harmony when visible.
- fun_metrics can be lighter, but still useful: estimated age impression, smile/readability, mood, glasses, facial hair, or photo vibe.
- summary_text must be 4-5 compact sentences, not one line. Include the strongest visible impression, the limiting factor, and the highest-impact next improvement.
- Every detail_text must be 2-4 compact sentences with visible evidence first, then what it means for the overall impression, then one practical coaching/photo implication.
- In Korean, summary_text should usually be about 180-280 characters and each detail_text about 90-170 characters. Do not answer with one short sentence.
- Every metric must include value_text with a compact right-side label such as "7.7 · 균형 좋음", "8.1 · 강점", or "6.4 · 개선 여지" so the collapsed row has a useful preview.
- Keep the tone premium and specific; avoid generic praise and avoid repeating the same wording across metrics.
""",
    "glow-up-coach": """
Mode-specific output:
- Return a rich FaceKit-style Glow Up report.
- Include exactly 9 facial_analysis coach items in this order: symmetry, skin, jawline, eye-area, cheekbones, eyebrows, glow, hair, confidence.
- Include 2-4 needs_work items with one expanded by default; include expression-confidence and include face-width-height-ratio or face-length-width-ratio when face proportions/framing are relevant.
- Other useful needs_work item_id values: camera-angle, lighting, grooming, photo-presence.
- Include 2-4 strengths using known IDs such as skin-quality, symmetry, hair, jawline, cheekbones, glow, or eye-area.
- Each coach item must have a known item_id from TITLE_KEYS["coach"] and an exact matching title_key from that map. Do not invent title_key strings.
""",
    "look-archetype": """
Mode-specific output:
- Return one memorable type from this family or a close variant: Clean-cut Heartthrob, Cold Handsome Type, Soft Boy Next Door, K-pop Idol Type, Model-like Sharp Type, Athletic Masculine Type, Warm Approachable Type, Dark Academia Type, Pretty Boy Type, Charismatic Leader Type.
- Include why it fits, best features, style direction, avoid, and concise signature style traits. Do not label traits as SNS/share traits.
- Make the archetype feel specific to the photo, not a generic personality label.
""",
    "best-photo-selector": """
Mode-specific output:
- Treat this as a premium selector report for the attached photo candidate or candidates.
- If multiple photos are attached, compare them by candidate number and identify the best current main-pick candidate in summary_text and metrics. Do not claim you compared unseen photos.
- If multiple photos are attached, return photo_rankings with exactly one item per visible candidate. rank 1 is the best current main-pick candidate.
- Return 6 rings using metric_id values: clarity, expression, lighting, composition, background, presence.
- Return metrics in section "photo_selection" with item IDs best-pick-readiness, face-visibility, expression-warmth, lighting-quality, composition, background-control.
- Return metrics in section "improvement_plan" with winning-move and 2-3 practical retake/edit actions.
""",
    "best-angle-finder": """
Mode-specific output:
- Infer the most flattering angle from the attached face geometry and photo perspective.
- If multiple photos are attached, compare the candidate angles and name the strongest candidate angle by candidate number in summary_text or detail_text.
- Return 6 rings using metric_id values: front, left, right, high-angle, low-angle, presence.
- For every visible score in this mode, keep score fields normalized as 0..1 for progress, but write display_value/value_text as a 10-point number such as "8.3", not "0.83".
- Return metrics in section "angle_breakdown" with best-angle, front-read, left-read, right-read, camera-height.
- Return metrics in section "capture_plan" with avoid-angle and retake-plan.
""",
    "dating-profile-score": """
Mode-specific output:
- Evaluate the attached photo or photos for dating-app profile use.
- If multiple photos are attached, compare them as profile candidates and identify which candidate should lead or support the set.
- If exactly two photos are attached, make summary_text and at least two metric/detail_text fields explicitly compare "Photo 1" versus "Photo 2" or "1번 사진" versus "2번 사진"; clearly state which one is better as the lead profile photo and why.
- If multiple photos are attached, return photo_rankings with exactly one item per visible candidate. rank 1 is the strongest lead dating-profile photo.
- Return 6 rings using metric_id values: first-impression, approachability, confidence, trust, style, conversation.
- Return metrics in section "dating_profile" with main-photo-suitability, approachability, confidence-signal, trust-signal, conversation-hook.
- Return metrics in section "profile_plan" with photo-mix and avoid-profile.
- Use these icon_name values for those metrics: main-photo-suitability=heart.fill, approachability=bubble.left.and.bubble.right.fill, confidence-signal=bolt.fill, trust-signal=checkmark.seal.fill, conversation-hook=text.bubble.fill, photo-mix=rectangle.stack.fill, avoid-profile=exclamationmark.triangle.fill.
- Prioritize warmth, clarity, authenticity, swipe-stopping value, and profile set strategy.
- Make the report feel useful rather than generic: say which photo is the lead, which should support, what each photo communicates in the first second, and what one missing photo/context would make the profile stronger.
- For each dating_profile detail_text, write 2-4 sentences and include a concrete dating-app implication such as lead-photo choice, trust signal, conversation hook, or retake direction.
""",
    "instagram-profile-score": """
Mode-specific output:
- Evaluate the attached photo or photos for Instagram/SNS use.
- If multiple photos are attached, compare thumbnail/crop/feed value by candidate number and identify the strongest use case.
- Return 6 rings using metric_id values: visual-impact, crop, lighting, feed-fit, shareability, vibe.
- Return metrics in section "instagram_profile" with profile-crop, first-impression, feed-fit, story-thumbnail, visual-consistency.
- Return metrics in section "content_plan" with caption-direction and posting-fix.
- Prioritize thumbnail readability, crop, styling, and visual coherence.
- Use calibrated scoring. Do not return all 10s unless the photo is genuinely exceptional across crop, lighting, visual impact, feed fit, shareability, and vibe.
- If any visible issue exists such as harsh lighting, weak crop, clutter, blur, awkward expression, or inconsistent color, at least one ring should be below 9.0 and overall_score should reflect that.
- If you think in percent internally, convert it before returning: overall_score/potential_score are 0..10 and ring score/progress fields are 0..1.
""",
}


MODE_TITLE_KEY_GROUPS = {
    "proportions": ("proportions",),
    "aesthetics": ("rings", "aesthetics"),
    "glow-up-coach": ("coach",),
    "look-archetype": ("rings", "aesthetics"),
    "best-photo-selector": ("rings", "photo_optimization"),
    "best-angle-finder": ("rings", "photo_optimization"),
    "dating-profile-score": ("rings", "photo_optimization"),
    "instagram-profile-score": ("rings", "photo_optimization"),
}


def _title_key_scope(mode_id: str) -> dict[str, dict[str, str]]:
    groups = MODE_TITLE_KEY_GROUPS.get(mode_id, ("rings", "aesthetics"))
    return {group: TITLE_KEYS[group] for group in groups}


def _onboarding_context_block(onboarding_context: dict[str, Any] | None) -> str:
    if not onboarding_context:
        return "User onboarding context: not provided."

    context = {
        "selected_goal_ids": onboarding_context.get("selected_goal_ids") or [],
        "selected_goal_labels": onboarding_context.get("selected_goal_labels") or [],
        "gender_id": onboarding_context.get("gender_id"),
        "gender_context": onboarding_context.get("gender_context"),
        "age": onboarding_context.get("age"),
        "age_range_id": onboarding_context.get("age_range_id"),
        "age_context": onboarding_context.get("age_context"),
    }
    return f"""
User onboarding context:
{json.dumps(context, ensure_ascii=False, default=str)}

Use this only as personalization context:
- Prioritize analysis and improvement advice around selected_goal_ids before less relevant topics.
- Exact age, age range, and self-selected gender can influence wording, styling direction, and recommendation priority, but must not become identity inference or a hard scoring rule.
- Do not infer or verify gender, age, ethnicity, health, or other sensitive identity from the image.
- For self-selected male, styling suggestions may mention grooming, jaw/hair framing, and stronger profile-photo direction when visually relevant.
- For self-selected female, styling suggestions may mention framing, hair/skin presentation, and profile-photo polish when visually relevant.
- For self-selected other or missing gender, keep wording neutral and unisex.
- For age ranges, adapt advice to feel age-appropriate and practical, without stereotyping or lowering scores because of age.
"""


def build_face_analysis_prompt(
    mode_id: str,
    locale: str,
    face_metrics: list[dict[str, Any]] | None = None,
    photo_count: int = 1,
    onboarding_context: dict[str, Any] | None = None,
) -> str:
    language = SUPPORTED_LOCALE_NAMES.get(locale, "natural American English")
    metric_block = json.dumps(face_metrics or [], ensure_ascii=False, default=str)
    if photo_count > 1:
        photo_context = f"Analyze {photo_count} attached user photos in candidate order."
    elif photo_count == 1:
        photo_context = "Analyze one user photo."
    else:
        photo_context = "Analyze the request using the available face geometry values; no photo image was attached."
    return f"""
You are Facemaxx, a premium AI face analysis and glow-up report engine.
Write the prompt reasoning internally in English, but write all user-facing summary_text,
value_text labels, status_text, detail_text, assessment_text, action_text, body_text,
subtitle_text, and title_text in {language}.

{photo_context}
Mode: {mode_id}.
Locale: {locale}.

{_onboarding_context_block(onboarding_context)}

Use the attached image or images when available. When multiple images are attached, treat them as photo candidates numbered by attachment order and compare only those attached photos. Use these measured face geometry values as grounded context. If there are multiple images, these geometry values describe the primary photo / candidate 1 unless the data clearly says otherwise.
If a visual impression conflicts with geometry, prefer the geometry for numeric ratios and the image for styling/aesthetic interpretation:
{metric_block}

Product constraints:
- Be specific and useful, but do not claim medical, ethnic, biometric identity, attractiveness certainty, or diagnosis.
- Scores are appearance-coaching scores, not objective human worth.
- Use natural language that feels like a premium mobile report: concise, but not shallow.
- Never use the words dummy, placeholder, mock, fake, simulated, test scan, 더미, 가짜, or 임시 in any user-facing field. Treat the input as a real user photo report.
- Do not mention internal implementation details such as ARKit, Vision, generated mesh, local cache, model fallback, or scan payload in user-facing copy.
- Do not mention the AI model/provider name in user-facing copy.
- User-facing copy must sound native in {language}. Avoid literal translation, awkward borrowed English, and overlong sentences.
- Every numeric display should include a short interpretation label, e.g. "6.8° · Positive", "1.71 · Balanced", "0.46 · Normal Range".
- overall_score and potential_score must be on a 0..10 scale. Never return 81, 92, or other 100-point values in those fields.
- overall_progress, potential_progress, and ring score fields must be on a 0..1 progress scale.
- Score displays must be on a 10-point visible scale. If a score field is 0.83 for progress, display_value/value_text must be "8.3", not "0.83".
- Every expandable metric must have a meaningful detail_text. Do not leave it blank and do not repeat the title.
- For metric detail_text, write 2-4 compact sentences: what was measured, what the user's result suggests, and one practical photo/style/coaching implication. For Korean, write natural Korean, not translated machine-sounding fragments.
- For summary_text, write 3-5 sentences with a clear overall read, top strengths, and the most useful next improvement. Avoid generic praise.
- For glow-up-coach summary_text specifically, write 4-6 sentences. Make it feel like a complete FaceKit-style coaching read: overall impression, strongest facial signals, what currently limits the look in photos, the highest-impact next steps, and a grounded closing note.
- For proportions detail_text, include the measurement logic or ratio meaning, the interpretation range/context, and why the user's value reads balanced/strong/soft/etc.
- For aesthetics detail_text, refer to visible evidence from the photo when possible, then explain how it affects the overall impression.
- For coach_items, assessment_text and action_text must each be specific enough to stand alone. Use labels like "Assessment:" and "Plan:" in English, or "평가:" and "플랜:" in Korean.
- Avoid one-word labels such as "Good", "Balanced", "Normal" as the entire explanation. Those are allowed in value_text/status_text only.
- Keep icons to SF Symbol names already common in the app: face.smiling, eye.fill, mouth.fill, arrow.left.and.right.circle, rectangle.fill, sun.max.fill, eye.circle.fill, rectangle.portrait, viewfinder, circle.lefthalf.filled, drop.fill, triangle.fill, calendar, eyeglasses, mustache.fill, sparkles, comb.fill, heart.fill, bolt.fill, bubble.left.and.bubble.right.fill, checkmark.seal.fill, text.bubble.fill, rectangle.stack.fill, exclamationmark.triangle.fill, star.fill, wand.and.stars, xmark.octagon.fill, crop, rectangle.dashed, camera.fill, person.crop.square.fill, arrow.turn.up.left, arrow.turn.up.right, square.grid.3x3.fill, slider.horizontal.3.

{MODE_PROMPT_SPECS.get(mode_id, MODE_PROMPT_SPECS["aesthetics"])}

Quality examples for expandable detail_text:
- "Face width ÷ face height. Your value sits close to the balanced range, so the face reads proportionate rather than overly long or overly wide. This supports a clean, stable impression in front-facing photos."
- "평가: 피부 톤이 비교적 균일하고 큰 붉은기나 잡티가 강하게 보이지 않습니다. 플랜: 자연광에서 촬영하면 피부 결이 더 깔끔하게 보이고, 보습감 있는 베이스 관리가 장점을 더 살립니다."

Use these exact title_key values when possible:
{json.dumps(_title_key_scope(mode_id), ensure_ascii=False)}

{ANALYSIS_JSON_CONTRACT}
"""

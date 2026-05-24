from app.schemas.analysis import (
    AnalysisMetric,
    AnalysisResultPayload,
    GlowUpCoachItem,
    GrowthOpportunity,
    LookArchetypeBullet,
    LookArchetypeResult,
    LookArchetypeSection,
    LookArchetypeTrait,
    PhotoCandidateRanking,
    ScoreRing,
)
from app.services.ai.base import ProviderAnalysisRequest


class DummyFaceAnalysisProvider:
    name = "dummy"
    model_name = "facemaxx-dummy-v1"

    async def analyze(self, request: ProviderAnalysisRequest) -> AnalysisResultPayload:
        if request.mode_id == "proportions":
            return self._proportions_payload()
        if request.mode_id == "aesthetics":
            return self._aesthetics_payload()
        if request.mode_id == "glow-up-coach":
            return self._glow_up_payload()
        if request.mode_id == "look-archetype":
            return self._look_archetype_payload()
        if request.mode_id == "best-photo-selector":
            return self._best_photo_selector_payload()
        if request.mode_id == "best-angle-finder":
            return self._best_angle_finder_payload()
        if request.mode_id == "dating-profile-score":
            return self._dating_profile_score_payload()
        if request.mode_id == "instagram-profile-score":
            return self._instagram_profile_score_payload()

        return AnalysisResultPayload(mode_id=request.mode_id, provider=self.name, model_name=self.model_name)

    def _base(self, mode_id: str) -> AnalysisResultPayload:
        return AnalysisResultPayload(
            mode_id=mode_id,
            provider=self.name,
            model_name=self.model_name,
            overall_score=7.4,
            overall_progress=0.74,
            potential_score=8.7,
            potential_progress=0.87,
            summary_key="analysis.results.summaryBody",
        )

    def _proportions_payload(self) -> AnalysisResultPayload:
        payload = self._base("proportions")
        payload.metrics = [
            AnalysisMetric(section="shapes", metric_id="face-shape", title_key="analysis.aestheticsResults.shape.faceShape", value_text="Oval", detail_key="analysis.aestheticsResults.shape.faceShapeDetail", icon_name="face.smiling", sort_order=10),
            AnalysisMetric(section="shapes", metric_id="eye-shape", title_key="analysis.aestheticsResults.shape.eyeShape", value_text="Downturned", detail_key="analysis.aestheticsResults.shape.eyeShapeDetail", icon_name="eye.fill", sort_order=20),
            AnalysisMetric(section="shapes", metric_id="eyebrow-shape", title_key="analysis.aestheticsResults.shape.eyebrowShape", value_text="Arch (Outer tail)", detail_key="analysis.aestheticsResults.shape.eyebrowShapeDetail", icon_name="eyebrow", sort_order=30),
            AnalysisMetric(section="shapes", metric_id="lip-shape", title_key="analysis.aestheticsResults.shape.lipShape", value_text="Upturned", detail_key="analysis.aestheticsResults.shape.lipShapeDetail", icon_name="mouth", sort_order=40),
            AnalysisMetric(section="proportions", metric_id="canthal-tilt", title_key="analysis.aestheticsResults.proportion.canthalTilt", value_text="6.8° · Positive", numeric_value=6.8, unit="degree", status_text="Positive", detail_key="analysis.aestheticsResults.proportion.canthalTiltDetail", icon_name="arrow.left.and.right.circle", value_tint="#34D15C", sort_order=50),
            AnalysisMetric(section="proportions", metric_id="eye-spacing-ratio", title_key="analysis.aestheticsResults.proportion.eyeSpacingRatio", value_text="0.46 · Normal Range", numeric_value=0.46, unit="ratio", status_text="Normal Range", detail_key="analysis.aestheticsResults.proportion.eyeSpacingRatioDetail", icon_name="eye.fill", value_tint="#34D15C", sort_order=60),
            AnalysisMetric(section="proportions", metric_id="face-width-height-ratio", title_key="analysis.aestheticsResults.proportion.faceWidthHeightRatio", value_text="1.71 · Balanced", numeric_value=1.71, unit="ratio", status_text="Balanced", detail_key="analysis.aestheticsResults.proportion.faceWidthHeightRatioDetail", icon_name="rectangle.fill", value_tint="#34D15C", sort_order=70),
            AnalysisMetric(section="proportions", metric_id="midface-ratio", title_key="analysis.aestheticsResults.proportion.midfaceRatio", value_text="0.90 · Balanced", numeric_value=0.90, unit="ratio", status_text="Balanced", detail_key="analysis.aestheticsResults.proportion.midfaceRatioDetail", icon_name="sun.max.circle", sort_order=80),
            AnalysisMetric(section="proportions", metric_id="philtrum-chin-ratio", title_key="analysis.aestheticsResults.proportion.philtrumToChinRatio", value_text="1:2.0 · Youthful", detail_key="analysis.aestheticsResults.proportion.philtrumToChinRatioDetail", icon_name="mouth", value_tint="#34D15C", sort_order=90),
            AnalysisMetric(section="proportions", metric_id="eye-width-face-ratio", title_key="analysis.aestheticsResults.proportion.eyeWidthFaceRatio", value_text="0.23 · Balanced", numeric_value=0.23, unit="ratio", status_text="Balanced", detail_key="analysis.aestheticsResults.proportion.eyeWidthFaceRatioDetail", icon_name="eye.circle.fill", value_tint="#34D15C", sort_order=100),
            AnalysisMetric(section="proportions", metric_id="upper-lower-lip-ratio", title_key="analysis.aestheticsResults.proportion.upperLipToLowerLip", value_text="1:1.4 · Balanced", detail_key="analysis.aestheticsResults.proportion.upperLipToLowerLipDetail", icon_name="mouth", value_tint="#34D15C", sort_order=110),
            AnalysisMetric(section="proportions", metric_id="eye-width-height-ratio", title_key="analysis.aestheticsResults.proportion.eyeWidthHeightRatio", value_text="2.9 · Elongated", numeric_value=2.9, unit="ratio", status_text="Elongated", detail_key="analysis.aestheticsResults.proportion.eyeWidthHeightRatioDetail", icon_name="eye.fill", value_tint="#34D15C", sort_order=120),
            AnalysisMetric(section="proportions", metric_id="lower-full-face-ratio", title_key="analysis.aestheticsResults.proportion.lowerToFullFaceRatio", value_text="0.69 · Normal Range", numeric_value=0.69, unit="ratio", status_text="Normal Range", detail_key="analysis.aestheticsResults.proportion.lowerToFullFaceRatioDetail", icon_name="rectangle.portrait", value_tint="#34D15C", sort_order=130),
            AnalysisMetric(section="proportions", metric_id="eye-mouth-angle", title_key="analysis.aestheticsResults.proportion.eyeToMouthAngle", value_text="45.7° · Balanced", numeric_value=45.7, unit="degree", status_text="Balanced", detail_key="analysis.aestheticsResults.proportion.eyeToMouthAngleDetail", icon_name="angle", value_tint="#34D15C", sort_order=140),
            AnalysisMetric(section="proportions", metric_id="face-depth-width-ratio", title_key="analysis.aestheticsResults.proportion.faceDepthWidthRatio", value_text="0.64 · Dimensional", numeric_value=0.64, unit="ratio", status_text="Dimensional", detail_key="analysis.aestheticsResults.proportion.faceDepthWidthRatioDetail", icon_name="viewfinder", value_tint="#A7A7B2", sort_order=150),
            AnalysisMetric(section="proportions", metric_id="face-contour-width-height-ratio", title_key="analysis.aestheticsResults.proportion.faceContourWidthHeightRatio", value_text="1.58 · Compact frame", numeric_value=1.58, unit="ratio", status_text="Compact frame", detail_key="analysis.aestheticsResults.proportion.faceContourWidthHeightRatioDetail", icon_name="rectangle.portrait", value_tint="#A7A7B2", sort_order=160),
        ]
        return payload

    def _aesthetics_payload(self) -> AnalysisResultPayload:
        payload = self._base("aesthetics")
        payload.summary_text = (
            "The overall read is clean and balanced, with stronger symmetry and eye-area clarity than the neutral expression first suggests. "
            "The face has a calm, approachable impression, while lighting and expression are the main areas limiting stronger presence in photos. "
            "Jawline and skin read stable, but a brighter front-facing retake would make the contours and texture look more intentional. "
            "The highest-impact next step is simple: eye-level light, a relaxed expression, and slightly cleaner hair framing."
        )
        payload.rings = [
            ScoreRing(metric_id="symmetry", title_key="analysis.results.ring.symmetry", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="skin", title_key="analysis.results.ring.skin", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="jawline", title_key="analysis.results.ring.jawline", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="eye-area", title_key="analysis.results.ring.eyeArea", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="cheekbones", title_key="analysis.results.ring.cheekbones", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=50),
            ScoreRing(metric_id="eyebrows", title_key="analysis.results.ring.eyebrows", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=60),
            ScoreRing(metric_id="glow", title_key="analysis.results.ring.glow", score=0.67, display_value="6.7", tint="#7EF0A1", sort_order=70),
            ScoreRing(metric_id="hair", title_key="analysis.results.ring.hair", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=80),
            ScoreRing(metric_id="harmony", title_key="analysis.results.ring.harmony", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=90),
        ]
        payload.metrics = [
            AnalysisMetric(section="detailed_metrics", metric_id="symmetry", title_key="analysis.results.metric.symmetry", value_text="7.7 · Above average", numeric_value=7.7, unit="score", status_text="Above average", detail_key="analysis.results.metric.symmetryDetail", icon_name="circle.lefthalf.filled", sort_order=10),
            AnalysisMetric(section="detailed_metrics", metric_id="canthal-tilt", title_key="analysis.results.metric.canthalTilt", value_text="6.8° · Positive", numeric_value=6.8, unit="degree", status_text="Positive", detail_key="analysis.results.metric.canthalTiltDetail", icon_name="arrow.left.and.right.circle", sort_order=20),
            AnalysisMetric(section="detailed_metrics", metric_id="gonial-angle", title_key="analysis.results.metric.gonialAngle", value_text="120° · Defined", numeric_value=120, unit="degree", status_text="Defined", detail_key="analysis.results.metric.gonialAngleDetail", icon_name="angle", sort_order=30),
            AnalysisMetric(section="detailed_metrics", metric_id="skin-quality", title_key="analysis.results.metric.skinQuality", value_text="0.46 · Normal Range", numeric_value=0.46, unit="ratio", status_text="Normal Range", detail_key="analysis.results.metric.skinQualityDetail", icon_name="drop.fill", sort_order=40),
            AnalysisMetric(section="detailed_metrics", metric_id="cheekbone-projection", title_key="analysis.results.metric.cheekboneProjection", value_text="Moderate · Balanced", status_text="Balanced", detail_key="analysis.results.metric.cheekboneProjectionDetail", icon_name="face.smiling", sort_order=50),
            AnalysisMetric(section="detailed_metrics", metric_id="jawline-definition", title_key="analysis.results.metric.jawlineDefinition", value_text="Good definition · Positive", status_text="Positive", detail_key="analysis.results.metric.jawlineDefinitionDetail", icon_name="triangle.fill", sort_order=60),
            AnalysisMetric(section="fun_metrics", metric_id="estimated-age", title_key="analysis.results.fun.estimatedAge", value_text="18-24 · Youthful", status_text="Youthful", detail_key="analysis.results.fun.estimatedAgeDetail", icon_name="calendar", sort_order=70),
            AnalysisMetric(section="fun_metrics", metric_id="smile-score", title_key="analysis.results.fun.smileScore", value_text="0.52 · Neutral expression", numeric_value=0.52, status_text="Neutral expression", detail_key="analysis.results.fun.smileScoreDetail", icon_name="face.smiling", sort_order=80),
            AnalysisMetric(section="fun_metrics", metric_id="mood", title_key="analysis.results.fun.mood", value_text="Calm/Neutral · Relaxed", status_text="Relaxed", detail_key="analysis.results.fun.moodDetail", icon_name="face.smiling", sort_order=90),
            AnalysisMetric(section="fun_metrics", metric_id="glasses", title_key="analysis.results.fun.glasses", value_text="No · Clear face", status_text="Clear face", detail_key="analysis.results.fun.glassesDetail", icon_name="eyeglasses", sort_order=100),
            AnalysisMetric(section="fun_metrics", metric_id="facial-hair", title_key="analysis.results.fun.facialHair", value_text="None visible · Clean", status_text="Clean", detail_key="analysis.results.fun.facialHairDetail", icon_name="mustache.fill", sort_order=110),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="lighting", title_key="analysis.results.action.lighting", body_key="analysis.results.action.lightingBody", category="lighting", sort_order=10),
            GrowthOpportunity(item_id="grooming", title_key="analysis.results.action.grooming", body_key="analysis.results.action.groomingBody", category="grooming", sort_order=20),
        ]
        payload.look_archetype = self._look_archetype_payload().look_archetype
        return payload

    def _glow_up_payload(self) -> AnalysisResultPayload:
        payload = self._base("glow-up-coach")
        payload.summary_key = "analysis.glowUpCoach.summaryBody"
        payload.coach_items = [
            GlowUpCoachItem(section="facial_analysis", item_id="symmetry", title_key="analysis.glowUpCoach.item.symmetry", assessment_key="analysis.glowUpCoach.item.symmetryAssessment", action_key="analysis.glowUpCoach.item.symmetryAction", icon_name="circle.lefthalf.filled", sort_order=10),
            GlowUpCoachItem(section="facial_analysis", item_id="skin", title_key="analysis.glowUpCoach.item.skin", assessment_key="analysis.glowUpCoach.item.skinAssessment", action_key="analysis.glowUpCoach.item.skinAction", icon_name="drop.fill", sort_order=20),
            GlowUpCoachItem(section="facial_analysis", item_id="jawline", title_key="analysis.glowUpCoach.item.jawline", assessment_key="analysis.glowUpCoach.item.jawlineAssessment", action_key="analysis.glowUpCoach.item.jawlineAction", icon_name="triangle.fill", sort_order=30),
            GlowUpCoachItem(section="facial_analysis", item_id="eye-area", title_key="analysis.glowUpCoach.item.eyeArea", assessment_key="analysis.glowUpCoach.item.eyeAreaAssessment", action_key="analysis.glowUpCoach.item.eyeAreaAction", icon_name="eye.fill", sort_order=40),
            GlowUpCoachItem(section="facial_analysis", item_id="cheekbones", title_key="analysis.glowUpCoach.item.cheekbones", assessment_key="analysis.glowUpCoach.item.cheekbonesAssessment", action_key="analysis.glowUpCoach.item.cheekbonesAction", icon_name="face.smiling", sort_order=50),
            GlowUpCoachItem(section="facial_analysis", item_id="eyebrows", title_key="analysis.glowUpCoach.item.eyebrows", assessment_key="analysis.glowUpCoach.item.eyebrowsAssessment", action_key="analysis.glowUpCoach.item.eyebrowsAction", icon_name="eyebrow", sort_order=60),
            GlowUpCoachItem(section="facial_analysis", item_id="glow", title_key="analysis.glowUpCoach.item.glow", assessment_key="analysis.glowUpCoach.item.glowAssessment", action_key="analysis.glowUpCoach.item.glowAction", icon_name="sparkles", sort_order=70),
            GlowUpCoachItem(section="facial_analysis", item_id="hair", title_key="analysis.glowUpCoach.item.hair", assessment_key="analysis.glowUpCoach.item.hairAssessment", action_key="analysis.glowUpCoach.item.hairAction", icon_name="comb.fill", sort_order=80),
            GlowUpCoachItem(section="facial_analysis", item_id="confidence", title_key="analysis.glowUpCoach.item.confidence", assessment_key="analysis.glowUpCoach.item.confidenceAssessment", action_key="analysis.glowUpCoach.item.confidenceAction", icon_name="heart.fill", sort_order=90),
            GlowUpCoachItem(section="needs_work", item_id="expression-confidence", title_key="analysis.glowUpCoach.item.expressionConfidence", assessment_key="analysis.glowUpCoach.item.expressionConfidenceAssessment", action_key="analysis.glowUpCoach.item.expressionConfidenceAction", icon_name="exclamationmark.triangle.fill", is_default_expanded=True, sort_order=100),
            GlowUpCoachItem(section="strengths", item_id="skin-quality", title_key="analysis.glowUpCoach.item.skinQuality", assessment_key="analysis.glowUpCoach.item.skinQualityAssessment", action_key="analysis.glowUpCoach.item.skinQualityAction", icon_name="star.fill", sort_order=200),
        ]
        return payload

    def _look_archetype_payload(self) -> AnalysisResultPayload:
        payload = self._base("look-archetype")
        payload.look_archetype = LookArchetypeResult(
            archetype_id="clean-cut-heartthrob",
            title_key="analysis.lookArchetype.title",
            type_name="Clean Sharp",
            secondary_type_name="Warm Natural",
            subtitle_text="A clean, structured first impression softened by an approachable natural read.",
            body_text=(
                "The strongest read is polished and direct, but not cold. Clean facial framing, balanced features, "
                "and a softer expression make minimal styling and natural-light photos work better than heavy filters."
            ),
            share_badge_key="analysis.lookArchetype.shareReady",
            traits=[
                LookArchetypeTrait(trait_id="clean", title_key="analysis.lookArchetype.trait.clean", title_text="Clean", tint="#34D15C", sort_order=10),
                LookArchetypeTrait(trait_id="sharp", title_key="analysis.lookArchetype.trait.sharp", title_text="Sharp", tint="#A78BFA", sort_order=20),
                LookArchetypeTrait(trait_id="natural", title_key="analysis.lookArchetype.trait.natural", title_text="Natural", tint="#63CCFA", sort_order=30),
                LookArchetypeTrait(trait_id="approachable", title_key="analysis.lookArchetype.trait.approachable", title_text="Approachable", tint="#1F91FF", sort_order=40),
            ],
            sections=[
                LookArchetypeSection(section_id="impression-summary", title_key="analysis.lookArchetype.impressionSummary", title_text="First impression summary", icon_name="person.crop.rectangle.stack.fill", tint="#A78BFA", is_default_expanded=True, sort_order=10, bullets=[
                    LookArchetypeBullet(bullet_id="primary-read", title_key="analysis.lookArchetype.bullet.primaryRead", title_text="The photo reads clean and composed first, with enough softness to avoid looking distant.", icon_name="sparkles", sort_order=10),
                    LookArchetypeBullet(bullet_id="secondary-read", title_key="analysis.lookArchetype.bullet.secondaryRead", title_text="The secondary impression is warmer and more natural, especially when the expression stays relaxed.", icon_name="leaf.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="best-use", title_key="analysis.lookArchetype.bullet.bestUse", title_text="This works best for profile photos that need a sharp but trustworthy first second.", icon_name="person.crop.square.fill", sort_order=30),
                ]),
                LookArchetypeSection(section_id="why-this-fits", title_key="analysis.lookArchetype.whyThisFits", title_text="Why this fits", icon_name="checkmark.seal.fill", tint="#34D15C", is_default_expanded=True, sort_order=20, bullets=[
                    LookArchetypeBullet(bullet_id="harmony", title_key="analysis.lookArchetype.why.harmony", title_text="The overall face read is balanced enough that simple styling looks intentional rather than plain.", icon_name="checkmark.circle.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="hair-frame", title_key="analysis.lookArchetype.why.hairFrame", title_text="Hair and face framing create the strongest clean-sharp signal in the current photo.", icon_name="checkmark.circle.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="soft-impression", title_key="analysis.lookArchetype.why.softImpression", title_text="A relaxed expression keeps the sharpness from feeling too cold or severe.", icon_name="checkmark.circle.fill", sort_order=30),
                ]),
                LookArchetypeSection(section_id="best-features", title_key="analysis.lookArchetype.bestFeatures", title_text="Best image assets", icon_name="star.fill", tint="#1F91FF", is_default_expanded=False, sort_order=30, bullets=[
                    LookArchetypeBullet(bullet_id="structure", title_key="analysis.lookArchetype.feature.structure", title_text="The face structure supports a neat, minimal look without needing loud styling.", icon_name="sparkle", sort_order=10),
                    LookArchetypeBullet(bullet_id="readability", title_key="analysis.lookArchetype.feature.readability", title_text="The face is easy to read quickly, which is useful for dating and social thumbnails.", icon_name="sparkle", sort_order=20),
                    LookArchetypeBullet(bullet_id="natural-warmth", title_key="analysis.lookArchetype.feature.naturalWarmth", title_text="The softer secondary read gives the look more approachability.", icon_name="sparkle", sort_order=30),
                ]),
                LookArchetypeSection(section_id="style-direction", title_key="analysis.lookArchetype.styleDirection", title_text="Style direction", icon_name="wand.and.stars", tint="#63CCFA", is_default_expanded=False, sort_order=40, bullets=[
                    LookArchetypeBullet(bullet_id="natural-light", title_key="analysis.lookArchetype.style.naturalLight", title_text="Use window light or soft outdoor light so the clean read stays premium.", icon_name="sun.max.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="neat-hair", title_key="analysis.lookArchetype.style.neatHair", title_text="Keep the hair outline controlled; too much cover hides the sharp-natural mix.", icon_name="comb.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="clean-top", title_key="analysis.lookArchetype.style.cleanTop", title_text="Black, white, navy, charcoal, and muted blue will support the archetype best.", icon_name="tshirt.fill", sort_order=30),
                    LookArchetypeBullet(bullet_id="natural-smile", title_key="analysis.lookArchetype.style.naturalSmile", title_text="A small relaxed smile will make the look feel more magnetic than a blank expression.", icon_name="face.smiling", sort_order=40),
                ]),
                LookArchetypeSection(section_id="photo-playbook", title_key="analysis.lookArchetype.photoPlaybook", title_text="Photo playbook", icon_name="camera.viewfinder", tint="#FFB84D", is_default_expanded=False, sort_order=50, bullets=[
                    LookArchetypeBullet(bullet_id="camera-height", title_key="analysis.lookArchetype.photo.cameraHeight", title_text="Shoot from eye level or slightly above; low angles reduce the clean-sharp read.", icon_name="camera.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="crop", title_key="analysis.lookArchetype.photo.crop", title_text="Keep the crop simple with visible hair and jaw framing, not too tight around the face.", icon_name="crop", sort_order=20),
                    LookArchetypeBullet(bullet_id="expression", title_key="analysis.lookArchetype.photo.expression", title_text="Use a calm direct gaze with a softer mouth; that is where the archetype looks strongest.", icon_name="eye.fill", sort_order=30),
                ]),
                LookArchetypeSection(section_id="avoid", title_key="analysis.lookArchetype.avoid", title_text="What weakens the read", icon_name="xmark.octagon.fill", tint="#FF7A45", is_default_expanded=False, sort_order=60, bullets=[
                    LookArchetypeBullet(bullet_id="dark-light", title_key="analysis.lookArchetype.avoid.darkLight", title_text="Very dark lighting makes the clean details harder to read.", icon_name="xmark.circle.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="blank-expression", title_key="analysis.lookArchetype.avoid.blankExpression", title_text="A completely blank expression can make the sharpness feel colder than intended.", icon_name="xmark.circle.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="heavy-bangs", title_key="analysis.lookArchetype.avoid.heavyBangs", title_text="Heavy front hair coverage hides the face structure that gives this type its strength.", icon_name="xmark.circle.fill", sort_order=30),
                ]),
            ],
        )
        return payload

    def _best_photo_selector_payload(self) -> AnalysisResultPayload:
        payload = self._base("best-photo-selector")
        payload.overall_score = 7.6
        payload.overall_progress = 0.76
        payload.potential_score = 8.4
        payload.potential_progress = 0.84
        payload.summary_text = (
            "Candidate 2 is the strongest main-pick option because it reads fastest at thumbnail size. "
            "It has the cleanest face visibility and the least visual friction, so it feels like the safest lead. "
            "Candidate 1 is the friendly backup with decent expression, but the frame is less polished. "
            "Candidate 3 has a cooler vibe, yet the light and crop make it feel more like a retake than a lead."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(
                candidate_index=2,
                rank=1,
                score=8.1,
                verdict="Best main pick",
                reason_text="Cleanest face visibility, balanced crop, and strongest first read.",
                description_text="This frame gives the most direct read of the face: the eyes are easy to find, the crop feels intentional, and the background does not fight for attention.",
                best_use_text="Lead profile photo, first slide, or main thumbnail.",
                fun_label_text="Main-character crop",
                strengths=["Fast face read", "Clean crop", "Low distraction"],
                weakness_text="The expression is solid but could be warmer.",
                fix_text="Retake the same setup with a small half-smile and slightly brighter eye light.",
                caption_idea_text="Clean frame, clear read.",
                vibe_tags=["clean", "confident", "profile-ready"],
            ),
            PhotoCandidateRanking(
                candidate_index=1,
                rank=2,
                score=7.2,
                verdict="Friendly backup",
                reason_text="Good expression, but framing and background control are weaker.",
                description_text="This one feels more casual and approachable, but the crop gives less polish and the background makes the face work harder to stand out.",
                best_use_text="Second or third photo when you want a softer backup.",
                fun_label_text="Friend-approved backup",
                strengths=["Approachable", "Natural", "Usable expression"],
                weakness_text="It does not pop as quickly in a small thumbnail.",
                fix_text="Crop tighter around the face and simplify the background before using it as a lead.",
                caption_idea_text="Keep it casual.",
                vibe_tags=["warm", "casual", "backup"],
            ),
            PhotoCandidateRanking(
                candidate_index=3,
                rank=3,
                score=6.4,
                verdict="Retake candidate",
                reason_text="Lighting and facial clarity need the most work.",
                description_text="The idea is usable, but the light flattens the face and the crop makes the photo feel less deliberate than the others.",
                best_use_text="Skip for now; use only after a cleaner retake.",
                fun_label_text="Good idea, bad lighting",
                strengths=["Potential vibe", "Different mood"],
                weakness_text="The face is not readable fast enough for a main image.",
                fix_text="Retake near soft window light with the camera at eye level and less background space.",
                caption_idea_text="Save the vibe, redo the light.",
                vibe_tags=["moody", "retake", "needs-polish"],
            ),
        ]
        payload.rings = [
            ScoreRing(metric_id="clarity", title_key="analysis.photoOptimization.ring.clarity", score=0.81, display_value="8.1", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="expression", title_key="analysis.photoOptimization.ring.expression", score=0.72, display_value="7.2", tint="#FFB020", sort_order=20),
            ScoreRing(metric_id="lighting", title_key="analysis.photoOptimization.ring.lighting", score=0.74, display_value="7.4", tint="#FFB020", sort_order=30),
            ScoreRing(metric_id="composition", title_key="analysis.photoOptimization.ring.composition", score=0.78, display_value="7.8", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="background", title_key="analysis.photoOptimization.ring.background", score=0.63, display_value="6.3", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="presence", title_key="analysis.photoOptimization.ring.presence", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="photo_selection", metric_id="best-pick-readiness", title_key="analysis.photoOptimization.metric.bestPickReadiness", value_text="Main-photo ready", status_text="Strong candidate", detail_text="Clear face visibility and balanced framing make Candidate 2 usable as the lead photo. Lighting and crop are strong enough for a main thumbnail, while the fastest upgrade is a warmer expression and one tighter export preview.", icon_name="checkmark.seal.fill", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="photo_selection", metric_id="face-visibility", title_key="analysis.photoOptimization.metric.faceVisibility", value_text="High", numeric_value=8.8, unit="score", status_text="Clear", detail_text="Facial features are easy to read without heavy shadows or obstruction. Candidate 1 is softer but slower at thumbnail size, while Candidate 3 needs cleaner light before it can compete as a lead.", icon_name="face.smiling", value_tint="#34D15C", sort_order=20),
            AnalysisMetric(section="photo_selection", metric_id="expression-warmth", title_key="analysis.photoOptimization.metric.expressionWarmth", value_text="Calm, slightly reserved", numeric_value=7.6, unit="score", status_text="Good", detail_text="The expression works, but a small natural smile would add more approachability. Keep the same angle and crop, then retake a few frames with brighter eye light so the final pick feels more alive without looking forced.", icon_name="face.smiling.inverse", sort_order=30),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="winning-move", body_text="Use Candidate 2 as the current lead, then retake the same setup with a warmer half-smile for the upgrade attempt.", category="photo_selection", sort_order=10),
            GrowthOpportunity(item_id="thumbnail-test", body_text="Export the top two photos as tiny circles and pick the one where the eyes and face outline read fastest.", category="photo_selection", sort_order=20),
            GrowthOpportunity(item_id="background", body_text="Use a simpler background or crop tighter so the photo reads instantly at thumbnail size.", category="photo_selection", sort_order=30),
            GrowthOpportunity(item_id="lighting", body_text="Move closer to soft front window light to add catchlights without flattening the face.", category="photo_selection", sort_order=40),
            GrowthOpportunity(item_id="final-check", body_text="Avoid choosing the coolest vibe if the face is slower to read; main photos should win in one second.", category="photo_selection", sort_order=50),
        ]
        return payload

    def _best_angle_finder_payload(self) -> AnalysisResultPayload:
        payload = self._base("best-angle-finder")
        payload.overall_score = 7.4
        payload.overall_progress = 0.74
        payload.potential_score = 8.2
        payload.potential_progress = 0.82
        payload.summary_text = (
            "Your strongest next angle is a slight three-quarter view with the camera near "
            "eye level. It keeps the face balanced while adding more jawline and cheekbone "
            "definition than a straight-on shot. Avoid a low camera angle because it makes "
            "the lower face carry too much visual weight. For the next set, shoot front, "
            "left three-quarter, and right three-quarter in the same light so the best "
            "side is obvious rather than guessed."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(candidate_index=2, rank=1, score=8.0, verdict="Best angle", reason_text="The slight three-quarter turn gives the cleanest structure without losing eye contact.", description_text="This angle gives the face more dimension: the jawline separates better, the cheekbone shadow is cleaner, and the gaze still feels direct.", best_use_text="Use as the default profile-photo angle.", fun_label_text="Jawline angle", strengths=["Dimensional", "Clear eyes", "Strong contour"], weakness_text="Too much turn would make it look staged.", fix_text="Keep the turn subtle, about 10-15 degrees, and keep the chin neutral.", vibe_tags=["sharp", "dimensional", "profile-ready"]),
            PhotoCandidateRanking(candidate_index=1, rank=2, score=7.1, verdict="Honest front read", reason_text="Clear and recognizable, but flatter than the three-quarter option.", description_text="The front angle is straightforward and trustworthy, but it compresses facial depth and makes the image feel more ID-style.", best_use_text="Use when you want a clean, direct photo.", fun_label_text="Clean passport energy", strengths=["Recognizable", "Balanced", "Simple"], weakness_text="Less contour and less visual drama.", fix_text="Add soft side light or a tiny shoulder turn to avoid a flat read.", vibe_tags=["honest", "clean", "safe"]),
            PhotoCandidateRanking(candidate_index=3, rank=3, score=5.9, verdict="Avoid as lead", reason_text="The angle puts too much weight under the chin and weakens eye emphasis.", description_text="This angle pulls attention away from the eyes and makes the lower face carry more visual weight than needed.", best_use_text="Avoid for lead photos; use only as an experimental casual shot.", fun_label_text="Low-angle warning", strengths=["Different mood"], weakness_text="It reduces the clean structure that the better angle shows.", fix_text="Raise the phone to eye level and step back slightly to reduce distortion.", vibe_tags=["risky", "retake", "low-angle"]),
        ]
        payload.rings = [
            ScoreRing(metric_id="front", title_key="analysis.photoOptimization.ring.front", score=0.71, display_value="7.1", tint="#FFB020", sort_order=10),
            ScoreRing(metric_id="left", title_key="analysis.photoOptimization.ring.left", score=0.80, display_value="8.0", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="right", title_key="analysis.photoOptimization.ring.right", score=0.80, display_value="8.0", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="high-angle", title_key="analysis.photoOptimization.ring.highAngle", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="low-angle", title_key="analysis.photoOptimization.ring.lowAngle", score=0.58, display_value="5.8", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="presence", title_key="analysis.photoOptimization.ring.presence", score=0.76, display_value="7.6", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="angle_breakdown", metric_id="best-angle", title_key="analysis.photoOptimization.metric.bestAngle", value_text="Left three-quarter", status_text="Best read", detail_text="Turn the face about 10-15 degrees from center and keep the phone close to eye level. This keeps the eyes readable while creating just enough cheekbone shadow and jawline separation. Avoid turning so far that the photo becomes a side-profile pose.", icon_name="viewfinder", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="angle_breakdown", metric_id="front-read", title_key="analysis.photoOptimization.metric.frontRead", value_text="Balanced but flatter", numeric_value=7.6, unit="score", status_text="Usable", detail_text="Straight-on framing is clear and honest, but it compresses facial depth. Use it when you want a clean ID-style read, not when you want the most dimensional profile photo. A tiny shoulder turn keeps the trust signal while adding shape.", icon_name="person.crop.square", sort_order=20),
            AnalysisMetric(section="angle_breakdown", metric_id="camera-height", title_key="analysis.photoOptimization.metric.cameraHeight", value_text="Eye level to slightly above", status_text="Recommended", detail_text="Keep the lens around eye height, then raise it a few centimeters if you want a softer social-photo look. Avoid pushing the phone below the chin because that shifts attention away from the eyes. Step back slightly before zooming or cropping so the lower face does not distort.", icon_name="camera.viewfinder", value_tint="#34D15C", sort_order=30),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="camera-height", body_text="Keep the camera at eye level and avoid tilting the phone upward from below the chin.", category="angle", sort_order=10),
            GrowthOpportunity(item_id="three-quarter", body_text="Use a slight three-quarter turn rather than a dramatic side angle for the best balance of structure and recognizability.", category="angle", sort_order=20),
            GrowthOpportunity(item_id="chin", body_text="Keep the chin neutral or slightly forward; dropping it too much can close the eye area.", category="angle", sort_order=30),
            GrowthOpportunity(item_id="shoulder", body_text="Drop the near shoulder slightly so the angle looks intentional instead of stiff.", category="angle", sort_order=40),
            GrowthOpportunity(item_id="comparison-set", body_text="Shoot front, left three-quarter, and right three-quarter in the same light before deciding the winner.", category="angle", sort_order=50),
        ]
        return payload

    def _dating_profile_score_payload(self) -> AnalysisResultPayload:
        payload = self._base("dating-profile-score")
        payload.overall_score = 7.2
        payload.overall_progress = 0.72
        payload.potential_score = 8.0
        payload.potential_progress = 0.80
        payload.summary_text = (
            "Photo 2 is the stronger lead dating-profile photo because it reads clearer, "
            "warmer, and more trustworthy in the first swipe. Photo 1 can still work as a "
            "mysterious backup, but it needs more expression and context before it can carry "
            "the profile. The current set has a good face read but a low story signal, so the "
            "fastest upgrade is one lifestyle photo that gives people something easy to ask about."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(candidate_index=2, rank=1, score=7.8, verdict="Stronger lead photo", reason_text="Clearer first read, warmer expression, and better trust signal for a dating profile.", description_text="Photo 2 feels easier to trust in the first second because the face is readable and the expression is calmer. It gives enough confidence without looking too staged.", best_use_text="Lead dating profile photo.", fun_label_text="Dateable lead", strengths=["Clear face", "Trust signal", "Calm confidence"], weakness_text="It still needs more story or lifestyle context.", fix_text="Pair it with one hobby or place-based photo so the profile has something to message about.", caption_idea_text="Low-key, but easy to talk to.", vibe_tags=["warm", "trustworthy", "lead"]),
            PhotoCandidateRanking(candidate_index=1, rank=2, score=6.7, verdict="Backup candidate", reason_text="Usable, but the expression and context are less inviting than Photo 2.", description_text="Photo 1 is not bad, but it feels more closed off. The face is visible, yet the photo does not give enough emotional or lifestyle signal for a dating lead.", best_use_text="Use later in the set, not first.", fun_label_text="Mysterious backup", strengths=["Composed", "Simple"], weakness_text="Low conversation value and less warmth.", fix_text="Retake with brighter light, a softer expression, and one visible context clue.", caption_idea_text="Needs a hook.", vibe_tags=["reserved", "backup", "low-context"]),
        ]
        payload.rings = [
            ScoreRing(metric_id="first-impression", title_key="analysis.photoOptimization.ring.firstImpression", score=0.76, display_value="7.6", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="approachability", title_key="analysis.photoOptimization.ring.approachability", score=0.70, display_value="7.0", tint="#FFB020", sort_order=20),
            ScoreRing(metric_id="confidence", title_key="analysis.photoOptimization.ring.confidence", score=0.78, display_value="7.8", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="trust", title_key="analysis.photoOptimization.ring.trust", score=0.80, display_value="8.0", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="style", title_key="analysis.photoOptimization.ring.style", score=0.71, display_value="7.1", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="conversation", title_key="analysis.photoOptimization.ring.conversation", score=0.58, display_value="5.8", tint="#FFB020", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="dating_profile", metric_id="main-photo-suitability", title_key="analysis.photoOptimization.metric.mainPhotoSuitability", value_text="Photo 2 leads", numeric_value=8.2, unit="score", status_text="Strong lead", detail_text="Photo 2 should be the lead because the face reads quickly, the expression feels easier to approach, and the first-swipe signal is clearer. Photo 1 is usable as a backup, but it gives more mystery than warmth. Green flag: the stronger photo looks natural rather than overproduced.", icon_name="heart.fill", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="dating_profile", metric_id="first-swipe-read", title_key="analysis.photoOptimization.metric.firstSwipeRead", value_text="Fast good read", numeric_value=7.7, unit="score", status_text="Swipe-safe", detail_text="The first-second read is clean enough that people understand the face and vibe without studying the image. Photo 2 wins because it feels open faster, while Photo 1 asks the viewer to work harder. Keep this as the quick-read anchor, then add context in the next slot.", icon_name="sparkles", value_tint="#34D15C", sort_order=20),
            AnalysisMetric(section="dating_profile", metric_id="approachability", title_key="analysis.photoOptimization.metric.approachability", value_text="Photo 2 warmer", numeric_value=7.8, unit="score", status_text="Good", detail_text="Photo 2 feels more open, which makes it safer as the first impression on a dating app. Photo 1 reads more reserved, so it can create curiosity but may not invite the first message. A softer smile or brighter eye-level light would turn the approachable read up fast.", icon_name="bubble.left.and.bubble.right.fill", sort_order=30),
            AnalysisMetric(section="dating_profile", metric_id="confidence-signal", title_key="analysis.photoOptimization.metric.confidenceSignal", value_text="Composed", numeric_value=8.1, unit="score", status_text="Strong", detail_text="The stronger photo gives calm confidence without looking like it is trying too hard. That is good lead-photo energy because it feels steady and self-possessed. Use the more serious shot only after the profile has already shown warmth, or it can become the risk of looking closed off.", icon_name="bolt.fill", value_tint="#34D15C", sort_order=40),
            AnalysisMetric(section="dating_profile", metric_id="trust-signal", title_key="analysis.photoOptimization.metric.trustSignal", value_text="Clear and authentic", numeric_value=8.4, unit="score", status_text="Strong", detail_text="The clearer photo keeps the face readable and the styling natural, which makes the profile feel more current and believable. This is the trust anchor of the set: it tells people they are seeing the real version of you. Keep filters light and avoid hiding the eyes, because that would lower the trust signal quickly.", icon_name="checkmark.seal.fill", value_tint="#34D15C", sort_order=50),
            AnalysisMetric(section="dating_profile", metric_id="style-signal", title_key="analysis.photoOptimization.metric.styleSignal", value_text="Clean but quiet", numeric_value=7.1, unit="score", status_text="Needs signature", detail_text="The styling reads clean, but it does not yet give a strong personal signature. A stronger outfit detail, cleaner neckline, or more intentional background would make the profile feel less generic. This is where one small style cue can turn a normal selfie into a memorable lead.", icon_name="person.crop.square.fill", value_tint="#FFB020", sort_order=60),
            AnalysisMetric(section="dating_profile", metric_id="conversation-hook", title_key="analysis.photoOptimization.metric.conversationHook", value_text="Limited context", numeric_value=6.4, unit="score", status_text="Needs hook", detail_text="Both photos show the face, but neither gives someone an easy opener. The profile needs one message bait: a cafe, travel spot, outfit detail, hobby, or activity that makes the first line obvious. Right now the face is doing the work; add a small story cue so the match has something to react to.", icon_name="text.bubble.fill", value_tint="#FFB020", sort_order=70),
            AnalysisMetric(section="dating_profile", metric_id="photo-context", title_key="analysis.photoOptimization.metric.photoContext", value_text="Low story signal", numeric_value=6.2, unit="score", status_text="Add context", detail_text="The face is readable, but the image does not reveal much about environment, lifestyle, or personality. That makes the profile feel clean but slightly low-context. Add one photo where the location or activity answers the question: what would someone ask you about?", icon_name="rectangle.stack.fill", value_tint="#FFB020", sort_order=80),
            AnalysisMetric(section="dating_profile", metric_id="red-flag-risk", title_key="analysis.photoOptimization.metric.redFlagRisk", value_text="Expression risk", numeric_value=6.8, unit="score", status_text="Watch warmth", detail_text="The main risk is not the face quality; it is the chance that multiple serious photos make the profile feel colder than intended. One composed shot is fine, but a full set of neutral expressions can read distant. Balance it with one warmer expression and one social or activity frame.", icon_name="exclamationmark.triangle.fill", value_tint="#FFB020", sort_order=90),
            AnalysisMetric(section="profile_plan", metric_id="photo-mix", title_key="analysis.photoOptimization.metric.photoMix", value_text="Pair with lifestyle and social proof", status_text="Recommended", detail_text="Use Photo 2 first, place Photo 1 later as the quieter backup, then add one full-body or outfit frame and one activity shot. That gives the profile a clean script: face clarity, style context, then something to talk about. The missing slot is not another selfie; it is a photo that shows where your energy lives.", icon_name="rectangle.stack.fill", sort_order=100),
            AnalysisMetric(section="profile_plan", metric_id="profile-role", title_key="analysis.photoOptimization.metric.profileRole", value_text="Lead plus backup", status_text="Set role", detail_text="Photo 2 should play the lead role because it explains your face fastest. Photo 1 can be the backup that adds a slightly more reserved mood. Do not let both photos perform the same job; each slot should answer a different question.", icon_name="person.crop.square.fill", sort_order=110),
            AnalysisMetric(section="profile_plan", metric_id="message-bait", title_key="analysis.photoOptimization.metric.messageBait", value_text="Needs one bait", status_text="Add opener", detail_text="The profile needs one built-in opener that does not feel forced. A visible hobby, coffee spot, travel frame, pet, book, gym, outfit, or food context gives the other person an easy first line. Keep it natural: the best bait looks like real life, not a staged prop.", icon_name="text.bubble.fill", value_tint="#FFB020", sort_order=120),
            AnalysisMetric(section="profile_plan", metric_id="missing-shot", title_key="analysis.photoOptimization.metric.missingShot", value_text="Lifestyle slot missing", status_text="High impact", detail_text="The missing photo is a lifestyle or activity shot that shows movement, place, or social context. Without it, the set can feel like a collection of face checks instead of a profile. Add one image where the background helps tell the story.", icon_name="camera.fill", value_tint="#34D15C", sort_order=130),
            AnalysisMetric(section="profile_plan", metric_id="opener-angle", title_key="analysis.photoOptimization.metric.openerAngle", value_text="Use a simple prompt", status_text="Easy win", detail_text="A good opener angle would be something someone can comment on in one sentence. Think: a specific place, a low-key hobby, or a visible detail in the photo. The goal is not to be funny on command; it is to make starting the conversation obvious.", icon_name="wand.and.stars", sort_order=140),
            AnalysisMetric(section="profile_plan", metric_id="avoid-profile", title_key="analysis.photoOptimization.metric.avoidProfile", value_text="Avoid all-neutral expressions", status_text="Profile risk", detail_text="Do not let every photo carry the same serious expression, because the profile can start to feel colder than intended. Keep one composed shot, but balance it with a warmer frame and one context-heavy image. The quick fix is simple: brighter light, relaxed mouth, and a background that says more than a blank wall.", icon_name="xmark.octagon.fill", value_tint="#FFB020", sort_order=150),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="warmth", body_text="Retake the lead photo with a natural smile and slightly brighter eye-level light.", category="dating_profile", sort_order=10),
            GrowthOpportunity(item_id="conversation-hook", body_text="Add one photo that shows a hobby, place, or outfit detail someone can easily ask about.", category="dating_profile", sort_order=20),
            GrowthOpportunity(item_id="message-bait", body_text="Add one small visual prompt that makes the first message obvious without looking staged.", category="dating_profile", sort_order=30),
            GrowthOpportunity(item_id="profile-script", body_text="Build the set as face clarity, style context, lifestyle proof, then one warmer social frame.", category="dating_profile", sort_order=40),
        ]
        return payload

    def _instagram_profile_score_payload(self) -> AnalysisResultPayload:
        payload = self._base("instagram-profile-score")
        payload.overall_score = 7.3
        payload.overall_progress = 0.73
        payload.potential_score = 8.1
        payload.potential_progress = 0.81
        payload.summary_text = (
            "This photo has strong profile-grid potential because the face reads clearly "
            "and the overall vibe is clean. It works best as a profile icon or grid anchor "
            "after a slightly tighter crop. Stronger color consistency and a cleaner "
            "background would make it feel more intentional in the feed. The best move is "
            "to treat it as the polished anchor, then support it with one brighter lifestyle "
            "post and one story-friendly frame that invites replies."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(candidate_index=1, rank=1, score=7.6, verdict="Best profile/grid anchor", reason_text="Strongest thumbnail clarity and cleanest profile icon read.", description_text="This photo works because the face reads quickly and the vibe is clean enough for a profile grid. It feels like an anchor image rather than a random upload.", best_use_text="Profile icon, pinned post, or first grid anchor.", fun_label_text="Profile icon energy", strengths=["Readable thumbnail", "Clean vibe", "Grid anchor"], weakness_text="The color story needs more consistency.", fix_text="Use a tighter crop and match exposure with nearby posts.", caption_idea_text="Keep the caption short and confident.", vibe_tags=["clean", "anchor", "profile-ready"]),
            PhotoCandidateRanking(candidate_index=2, rank=2, score=6.6, verdict="Story support", reason_text="Usable for stories, but weaker as a permanent grid lead.", description_text="This candidate has a more casual feel, which can work in stories, but it does not have enough crop control or feed polish to lead the grid.", best_use_text="Story, close friends, or secondary carousel slide.", fun_label_text="Story-reply bait", strengths=["Casual", "More spontaneous"], weakness_text="Less polished in a square crop.", fix_text="Brighten the face and crop out extra background before posting.", caption_idea_text="A casual one-liner works better than a long caption.", vibe_tags=["casual", "story", "support"]),
        ]
        payload.rings = [
            ScoreRing(metric_id="visual-impact", title_key="analysis.photoOptimization.ring.visualImpact", score=0.77, display_value="7.7", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="crop", title_key="analysis.photoOptimization.ring.crop", score=0.72, display_value="7.2", tint="#FFB020", sort_order=20),
            ScoreRing(metric_id="lighting", title_key="analysis.photoOptimization.ring.lighting", score=0.76, display_value="7.6", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="feed-fit", title_key="analysis.photoOptimization.ring.feedFit", score=0.69, display_value="6.9", tint="#FFB020", sort_order=40),
            ScoreRing(metric_id="shareability", title_key="analysis.photoOptimization.ring.shareability", score=0.66, display_value="6.6", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="vibe", title_key="analysis.photoOptimization.ring.vibe", score=0.79, display_value="7.9", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="instagram_profile", metric_id="profile-crop", title_key="analysis.photoOptimization.metric.profileCrop", value_text="Tight square crop works", numeric_value=7.8, unit="score", status_text="Good", detail_text="Crop closer around the face and shoulders so the circular profile thumbnail stays readable. This has profile-icon energy because the face remains the main signal even at small size. Keep a little headroom, but remove background space that does not help the first impression.", icon_name="crop", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="instagram_profile", metric_id="thumbnail-impact", title_key="analysis.photoOptimization.metric.thumbnailImpact", value_text="Reads small", numeric_value=7.6, unit="score", status_text="Useful", detail_text="The face remains readable when the image shrinks, which matters for profile icons, stories, and grid previews. The crop should keep the eyes high enough that the thumbnail does not feel heavy. A slightly tighter square export would make the visual hit faster.", icon_name="viewfinder", value_tint="#34D15C", sort_order=20),
            AnalysisMetric(section="instagram_profile", metric_id="profile-icon-energy", title_key="analysis.photoOptimization.metric.profileIconEnergy", value_text="Clean icon energy", numeric_value=7.9, unit="score", status_text="Strong", detail_text="This has profile-icon energy because the face and vibe are easy to understand at a glance. It feels polished enough for a main profile image without becoming overly edited. Keep the background quiet so the face stays the icon, not the setting.", icon_name="person.crop.square.fill", value_tint="#34D15C", sort_order=30),
            AnalysisMetric(section="instagram_profile", metric_id="first-impression", title_key="analysis.photoOptimization.metric.firstImpression", value_text="Clean and composed", numeric_value=8.1, unit="score", status_text="Strong", detail_text="The image gives a polished first read without feeling overly staged. It works as a grid anchor because the vibe is clean, calm, and easy to understand on a fast scroll. To make it more scroll-stopping, push a little more light into the eyes and crop with more intention.", icon_name="sparkles", value_tint="#34D15C", sort_order=40),
            AnalysisMetric(section="instagram_profile", metric_id="feed-fit", title_key="analysis.photoOptimization.metric.feedFit", value_text="Fits a clean personal grid", numeric_value=7.6, unit="score", status_text="Good", detail_text="This photo fits best beside neutral, bright, and minimally cluttered posts. If nearby posts are much warmer, darker, or louder, it may look like a feed-filler instead of a planned anchor. Use the same brightness preset on the posts around it so the grid feels intentional.", icon_name="square.grid.3x3.fill", sort_order=50),
            AnalysisMetric(section="instagram_profile", metric_id="story-thumbnail", title_key="analysis.photoOptimization.metric.storyThumbnail", value_text="Readable at small size", numeric_value=8.0, unit="score", status_text="Good", detail_text="The face stays recognizable in small circular previews, so it can work as a story-reply bait image if the expression feels inviting. A brighter eye area would make the thumbnail read faster. Use it for a story when you want a clean, low-effort reply trigger rather than a loud post.", icon_name="circle.grid.cross.fill", sort_order=60),
            AnalysisMetric(section="instagram_profile", metric_id="scroll-stop-power", title_key="analysis.photoOptimization.metric.scrollStopPower", value_text="Subtle not loud", numeric_value=6.9, unit="score", status_text="Improve", detail_text="The image is clean, but the scroll-stop power is more subtle than bold. It may work well for a profile icon but need stronger light, contrast, or expression to stop someone mid-feed. The quick upgrade is brighter eyes and a crop that removes empty background.", icon_name="bolt.fill", value_tint="#FFB020", sort_order=70),
            AnalysisMetric(section="instagram_profile", metric_id="visual-consistency", title_key="analysis.photoOptimization.metric.visualConsistency", value_text="Needs color lock", numeric_value=7.2, unit="score", status_text="Improve", detail_text="A consistent exposure and color temperature would help this image match a curated feed. Keep skin tone natural and avoid filters that make the background warmer than the face. The soft-launch crop works better if the color story is locked before posting.", icon_name="slider.horizontal.3", value_tint="#FFB020", sort_order=80),
            AnalysisMetric(section="instagram_profile", metric_id="color-mood", title_key="analysis.photoOptimization.metric.colorMood", value_text="Neutral mood", numeric_value=7.4, unit="score", status_text="Good base", detail_text="The color mood is neutral enough to fit a clean profile, but it needs a consistent preset to feel intentional. If nearby posts are brighter, lift exposure slightly; if the grid is darker, keep this as a calm anchor. Do not let the edit make the face less clear.", icon_name="slider.horizontal.3", sort_order=90),
            AnalysisMetric(section="content_plan", metric_id="caption-direction", title_key="analysis.photoOptimization.metric.captionDirection", value_text="Simple, confident caption", status_text="Recommended", detail_text="Use a short caption that matches the clean visual style rather than explaining the photo. A minimal line, a dry one-liner, or a location-only caption fits better than a long paragraph. The caption angle should make the photo feel effortless, not like a campaign.", icon_name="text.bubble.fill", sort_order=100),
            AnalysisMetric(section="content_plan", metric_id="grid-anchor", title_key="analysis.photoOptimization.metric.gridAnchor", value_text="Use as anchor", status_text="Grid role", detail_text="This photo should act as a grid anchor rather than a filler post. Place it near a brighter lifestyle or outfit image so the feed alternates between face clarity and context. If three similar close-up images sit together, the profile can feel repetitive.", icon_name="square.grid.3x3.fill", sort_order=110),
            AnalysisMetric(section="content_plan", metric_id="story-reply-trigger", title_key="analysis.photoOptimization.metric.storyReplyTrigger", value_text="Needs reply cue", status_text="Story idea", detail_text="For story use, add a small prompt or context that makes replies easier. The image can work as a low-key story, but a location tag, simple question, or visible activity would make it more interactive. Keep the text minimal so it does not cover the face.", icon_name="text.bubble.fill", value_tint="#FFB020", sort_order=120),
            AnalysisMetric(section="content_plan", metric_id="carousel-use", title_key="analysis.photoOptimization.metric.carouselUse", value_text="Good first slide", status_text="Carousel", detail_text="This can lead a carousel if the next slide adds place, outfit, or behind-the-scenes context. As a single post it is clean; as a carousel opener it can feel more intentional. Do not follow it with another nearly identical face crop.", icon_name="rectangle.stack.fill", sort_order=130),
            AnalysisMetric(section="content_plan", metric_id="posting-rhythm", title_key="analysis.photoOptimization.metric.postingRhythm", value_text="Pair with brighter post", status_text="Sequence", detail_text="Post it after a brighter or more active image so the grid rhythm does not become too quiet. The photo has a calm profile read, so it needs contrast around it. Think anchor, then movement, then detail.", icon_name="calendar", sort_order=140),
            AnalysisMetric(section="content_plan", metric_id="filter-risk", title_key="analysis.photoOptimization.metric.filterRisk", value_text="Avoid heavy filter", status_text="Risk", detail_text="The biggest edit risk is using a filter that flattens skin tone or reduces eye clarity. Keep the face natural and use exposure, crop, and background cleanup before color effects. A clean edit will outperform a dramatic one here.", icon_name="exclamationmark.triangle.fill", value_tint="#FFB020", sort_order=150),
            AnalysisMetric(section="content_plan", metric_id="posting-fix", title_key="analysis.photoOptimization.metric.postingFix", value_text="Tighten crop and reduce background noise", status_text="Highest impact", detail_text="A tighter crop plus subtle background cleanup will improve profile-thumbnail impact. Post it near a brighter lifestyle photo or outfit shot so the grid has rhythm instead of three similar face images in a row. The quick retake fix is eye-level light, a cleaner edge around the hair, and a crop preview checked in both square and circle.", icon_name="wand.and.stars", value_tint="#34D15C", sort_order=160),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="crop", body_text="Export a square and circular preview before posting so the face stays readable in both grid and profile views.", category="instagram_profile", sort_order=10),
            GrowthOpportunity(item_id="color", body_text="Use one consistent brightness and color-temperature preset across nearby feed photos.", category="instagram_profile", sort_order=20),
            GrowthOpportunity(item_id="story-reply", body_text="For stories, add one tiny prompt or location cue that invites replies without covering the face.", category="instagram_profile", sort_order=30),
            GrowthOpportunity(item_id="grid-rhythm", body_text="Place this near a brighter lifestyle post so the grid has rhythm instead of repeated close-ups.", category="instagram_profile", sort_order=40),
        ]
        return payload

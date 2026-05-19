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
            type_name="Clean-cut Heartthrob",
            subtitle_key="analysis.lookArchetype.typeSubtitle",
            body_key="analysis.lookArchetype.typeBody",
            share_badge_key="analysis.lookArchetype.shareReady",
            traits=[
                LookArchetypeTrait(trait_id="clean", title_key="analysis.lookArchetype.trait.clean", tint="#34D15C", sort_order=10),
                LookArchetypeTrait(trait_id="youthful", title_key="analysis.lookArchetype.trait.youthful", tint="#1F91FF", sort_order=20),
                LookArchetypeTrait(trait_id="approachable", title_key="analysis.lookArchetype.trait.approachable", tint="#63CCFA", sort_order=30),
            ],
            sections=[
                LookArchetypeSection(section_id="why-this-fits", title_key="analysis.lookArchetype.whyThisFits", icon_name="checkmark.seal.fill", tint="#34D15C", is_default_expanded=True, sort_order=10, bullets=[
                    LookArchetypeBullet(bullet_id="harmony", title_key="analysis.lookArchetype.why.harmony", icon_name="checkmark.circle.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="skin-hair", title_key="analysis.lookArchetype.why.skinHair", icon_name="checkmark.circle.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="soft-impression", title_key="analysis.lookArchetype.why.softImpression", icon_name="checkmark.circle.fill", sort_order=30),
                ]),
                LookArchetypeSection(section_id="best-features", title_key="analysis.lookArchetype.bestFeatures", icon_name="star.fill", tint="#1F91FF", is_default_expanded=False, sort_order=20, bullets=[
                    LookArchetypeBullet(bullet_id="skin", title_key="analysis.lookArchetype.feature.skin", icon_name="sparkle", sort_order=10),
                    LookArchetypeBullet(bullet_id="hair", title_key="analysis.lookArchetype.feature.hair", icon_name="sparkle", sort_order=20),
                    LookArchetypeBullet(bullet_id="symmetry", title_key="analysis.lookArchetype.feature.symmetry", icon_name="sparkle", sort_order=30),
                ]),
                LookArchetypeSection(section_id="style-direction", title_key="analysis.lookArchetype.styleDirection", icon_name="wand.and.stars", tint="#63CCFA", is_default_expanded=False, sort_order=30, bullets=[
                    LookArchetypeBullet(bullet_id="natural-light", title_key="analysis.lookArchetype.style.naturalLight", icon_name="sun.max.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="neat-hair", title_key="analysis.lookArchetype.style.neatHair", icon_name="comb.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="clean-top", title_key="analysis.lookArchetype.style.cleanTop", icon_name="tshirt.fill", sort_order=30),
                    LookArchetypeBullet(bullet_id="natural-smile", title_key="analysis.lookArchetype.style.naturalSmile", icon_name="face.smiling", sort_order=40),
                ]),
                LookArchetypeSection(section_id="avoid", title_key="analysis.lookArchetype.avoid", icon_name="xmark.circle.fill", tint="#FFB020", is_default_expanded=False, sort_order=40, bullets=[
                    LookArchetypeBullet(bullet_id="dark-light", title_key="analysis.lookArchetype.avoid.darkLight", icon_name="xmark.circle.fill", sort_order=10),
                    LookArchetypeBullet(bullet_id="blank-expression", title_key="analysis.lookArchetype.avoid.blankExpression", icon_name="xmark.circle.fill", sort_order=20),
                    LookArchetypeBullet(bullet_id="heavy-bangs", title_key="analysis.lookArchetype.avoid.heavyBangs", icon_name="xmark.circle.fill", sort_order=30),
                ]),
            ],
        )
        return payload

    def _best_photo_selector_payload(self) -> AnalysisResultPayload:
        payload = self._base("best-photo-selector")
        payload.overall_score = 8.1
        payload.overall_progress = 0.81
        payload.potential_score = 9.0
        payload.potential_progress = 0.90
        payload.summary_text = (
            "Candidate 2 is the strongest main-pick option: it has the clearest face read, "
            "the most balanced crop, and the least visual friction. Candidate 1 is usable "
            "but less polished, while candidate 3 needs cleaner light before it can lead."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(candidate_index=2, rank=1, score=8.6, verdict="Best main pick", reason_text="Cleanest face visibility, balanced crop, and strongest first read."),
            PhotoCandidateRanking(candidate_index=1, rank=2, score=7.8, verdict="Usable backup", reason_text="Good expression, but framing and background control are weaker."),
            PhotoCandidateRanking(candidate_index=3, rank=3, score=7.1, verdict="Retake candidate", reason_text="Lighting and facial clarity need the most work."),
        ]
        payload.rings = [
            ScoreRing(metric_id="clarity", title_key="analysis.photoOptimization.ring.clarity", score=0.86, display_value="8.6", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="expression", title_key="analysis.photoOptimization.ring.expression", score=0.78, display_value="7.8", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="lighting", title_key="analysis.photoOptimization.ring.lighting", score=0.82, display_value="8.2", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="composition", title_key="analysis.photoOptimization.ring.composition", score=0.80, display_value="8.0", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="background", title_key="analysis.photoOptimization.ring.background", score=0.69, display_value="6.9", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="presence", title_key="analysis.photoOptimization.ring.presence", score=0.83, display_value="8.3", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="photo_selection", metric_id="best-pick-readiness", title_key="analysis.photoOptimization.metric.bestPickReadiness", value_text="Main-photo ready", status_text="Strong candidate", detail_text="Clear face visibility and balanced framing make this usable as the lead photo.", icon_name="checkmark.seal.fill", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="photo_selection", metric_id="face-visibility", title_key="analysis.photoOptimization.metric.faceVisibility", value_text="High", numeric_value=8.8, unit="score", status_text="Clear", detail_text="Facial features are easy to read without heavy shadows or obstruction.", icon_name="face.smiling", value_tint="#34D15C", sort_order=20),
            AnalysisMetric(section="photo_selection", metric_id="expression-warmth", title_key="analysis.photoOptimization.metric.expressionWarmth", value_text="Calm, slightly reserved", numeric_value=7.6, unit="score", status_text="Good", detail_text="The expression works, but a small natural smile would add more approachability.", icon_name="face.smiling.inverse", sort_order=30),
            AnalysisMetric(section="photo_selection", metric_id="lighting-quality", title_key="analysis.photoOptimization.metric.lightingQuality", value_text="Soft and usable", numeric_value=8.2, unit="score", status_text="Good", detail_text="Lighting supports facial structure without flattening the face.", icon_name="sun.max.fill", value_tint="#34D15C", sort_order=40),
            AnalysisMetric(section="photo_selection", metric_id="composition", title_key="analysis.photoOptimization.metric.composition", value_text="Balanced crop", numeric_value=8.0, unit="score", status_text="Good", detail_text="The crop keeps the face central and leaves enough space for a natural profile-photo read.", icon_name="crop", sort_order=50),
            AnalysisMetric(section="photo_selection", metric_id="background-control", title_key="analysis.photoOptimization.metric.backgroundControl", value_text="Slightly busy", numeric_value=6.9, unit="score", status_text="Improve", detail_text="A cleaner background would increase polish and make the face stand out faster.", icon_name="rectangle.dashed", value_tint="#FFB020", sort_order=60),
            AnalysisMetric(section="improvement_plan", metric_id="winning-move", title_key="analysis.photoOptimization.metric.winningMove", value_text="Retake with warmer expression", status_text="Highest impact", detail_text="Keep this angle and lighting, then add a relaxed half-smile for a stronger first impression.", icon_name="sparkles", value_tint="#34D15C", sort_order=70),
            AnalysisMetric(section="improvement_plan", metric_id="retake-light", title_key="analysis.photoOptimization.metric.retakeLight", value_text="Window light from front-left", status_text="Retake tip", detail_text="Use soft natural light at eye level to keep detail while adding catchlights.", icon_name="sun.max.fill", sort_order=80),
            AnalysisMetric(section="improvement_plan", metric_id="edit-cleanup", title_key="analysis.photoOptimization.metric.editCleanup", value_text="Reduce background distractions", status_text="Edit tip", detail_text="A mild background blur or tighter crop would improve focus without making the image look overedited.", icon_name="wand.and.stars", sort_order=90),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="expression", body_text="Try three quick retakes with a natural half-smile and choose the frame where the eyes look most engaged.", category="photo_selection", sort_order=10),
            GrowthOpportunity(item_id="background", body_text="Use a simpler background or crop tighter so the photo reads instantly at thumbnail size.", category="photo_selection", sort_order=20),
        ]
        return payload

    def _best_angle_finder_payload(self) -> AnalysisResultPayload:
        payload = self._base("best-angle-finder")
        payload.overall_score = 7.9
        payload.overall_progress = 0.79
        payload.potential_score = 8.9
        payload.potential_progress = 0.89
        payload.summary_text = (
            "Your strongest next angle is a slight three-quarter view with the camera near "
            "eye level. It keeps the face balanced while adding more jawline and cheekbone "
            "definition than a straight-on shot. Avoid a low camera angle because it makes "
            "the lower face carry too much visual weight."
        )
        payload.rings = [
            ScoreRing(metric_id="front", title_key="analysis.photoOptimization.ring.front", score=0.76, display_value="7.6", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="left", title_key="analysis.photoOptimization.ring.left", score=0.84, display_value="8.4", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="right", title_key="analysis.photoOptimization.ring.right", score=0.80, display_value="8.0", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="high-angle", title_key="analysis.photoOptimization.ring.highAngle", score=0.72, display_value="7.2", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="low-angle", title_key="analysis.photoOptimization.ring.lowAngle", score=0.58, display_value="5.8", tint="#FFB020", sort_order=50),
            ScoreRing(metric_id="presence", title_key="analysis.photoOptimization.ring.presence", score=0.82, display_value="8.2", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="angle_breakdown", metric_id="best-angle", title_key="analysis.photoOptimization.metric.bestAngle", value_text="Left three-quarter", status_text="Best read", detail_text="Turn the face about 10-15 degrees from center to add dimension while preserving symmetry.", icon_name="viewfinder", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="angle_breakdown", metric_id="front-read", title_key="analysis.photoOptimization.metric.frontRead", value_text="Balanced but flatter", numeric_value=7.6, unit="score", status_text="Usable", detail_text="Straight-on framing is clear, but it shows less facial depth than a slight turn.", icon_name="person.crop.square", sort_order=20),
            AnalysisMetric(section="angle_breakdown", metric_id="left-read", title_key="analysis.photoOptimization.metric.leftRead", value_text="Most flattering", numeric_value=8.4, unit="score", status_text="Strong", detail_text="A subtle left turn improves cheekbone shadow and jawline separation.", icon_name="arrow.turn.up.left", value_tint="#34D15C", sort_order=30),
            AnalysisMetric(section="angle_breakdown", metric_id="right-read", title_key="analysis.photoOptimization.metric.rightRead", value_text="Also strong", numeric_value=8.0, unit="score", status_text="Good", detail_text="The right side remains balanced, though it has slightly less contour than the left.", icon_name="arrow.turn.up.right", sort_order=40),
            AnalysisMetric(section="angle_breakdown", metric_id="camera-height", title_key="analysis.photoOptimization.metric.cameraHeight", value_text="Eye level to slightly above", status_text="Recommended", detail_text="Keep the lens around eye height, then raise it a few centimeters if you want a softer profile-photo look.", icon_name="camera.viewfinder", value_tint="#34D15C", sort_order=50),
            AnalysisMetric(section="capture_plan", metric_id="avoid-angle", title_key="analysis.photoOptimization.metric.avoidAngle", value_text="Low-angle close-up", status_text="Avoid", detail_text="Low angles reduce eye-area emphasis and can make the jaw and neck look heavier.", icon_name="xmark.circle.fill", value_tint="#FFB020", sort_order=60),
            AnalysisMetric(section="capture_plan", metric_id="retake-plan", title_key="analysis.photoOptimization.metric.retakePlan", value_text="Shoot 12-frame angle set", status_text="Next step", detail_text="Take four front, four left three-quarter, and four right three-quarter shots in the same lighting, then compare expression and jawline clarity.", icon_name="camera.fill", sort_order=70),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="camera-height", body_text="Keep the camera at eye level and avoid tilting the phone upward from below the chin.", category="angle", sort_order=10),
            GrowthOpportunity(item_id="three-quarter", body_text="Use a slight three-quarter turn rather than a dramatic side angle for the best balance of structure and recognizability.", category="angle", sort_order=20),
        ]
        return payload

    def _dating_profile_score_payload(self) -> AnalysisResultPayload:
        payload = self._base("dating-profile-score")
        payload.overall_score = 7.8
        payload.overall_progress = 0.78
        payload.potential_score = 8.8
        payload.potential_progress = 0.88
        payload.summary_text = (
            "Photo 2 is the stronger lead dating-profile photo because it reads clearer, "
            "warmer, and more trustworthy at first glance. Photo 1 can still work as a "
            "supporting backup, but it needs more expression and context to create an easy "
            "conversation hook. Lead with the cleaner, more approachable frame, then support "
            "it with one lifestyle photo."
        )
        payload.photo_rankings = [
            PhotoCandidateRanking(candidate_index=2, rank=1, score=8.2, verdict="Stronger lead photo", reason_text="Clearer first read, warmer expression, and better trust signal for a dating profile."),
            PhotoCandidateRanking(candidate_index=1, rank=2, score=7.3, verdict="Backup candidate", reason_text="Usable, but the expression and context are less inviting than Photo 2."),
        ]
        payload.rings = [
            ScoreRing(metric_id="first-impression", title_key="analysis.photoOptimization.ring.firstImpression", score=0.79, display_value="7.9", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="approachability", title_key="analysis.photoOptimization.ring.approachability", score=0.73, display_value="7.3", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="confidence", title_key="analysis.photoOptimization.ring.confidence", score=0.81, display_value="8.1", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="trust", title_key="analysis.photoOptimization.ring.trust", score=0.84, display_value="8.4", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="style", title_key="analysis.photoOptimization.ring.style", score=0.75, display_value="7.5", tint="#7EF0A1", sort_order=50),
            ScoreRing(metric_id="conversation", title_key="analysis.photoOptimization.ring.conversation", score=0.64, display_value="6.4", tint="#FFB020", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="dating_profile", metric_id="main-photo-suitability", title_key="analysis.photoOptimization.metric.mainPhotoSuitability", value_text="Photo 2 leads", numeric_value=8.2, unit="score", status_text="Strong lead", detail_text="Photo 2 should lead because the face reads clearer and the expression feels more approachable. Photo 1 is credible as a backup, but it is less warm for a first swipe.", icon_name="heart.fill", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="dating_profile", metric_id="approachability", title_key="analysis.photoOptimization.metric.approachability", value_text="Photo 2 warmer", numeric_value=7.8, unit="score", status_text="Good", detail_text="Photo 2 gives a softer and easier first impression. Photo 1 feels more reserved, so it needs a relaxed smile or brighter setting to compete.", icon_name="bubble.left.and.bubble.right.fill", sort_order=20),
            AnalysisMetric(section="dating_profile", metric_id="confidence-signal", title_key="analysis.photoOptimization.metric.confidenceSignal", value_text="Composed", numeric_value=8.1, unit="score", status_text="Strong", detail_text="The stronger photo keeps a steady, confident read without feeling overproduced. Use Photo 1 only after the lead shot has already established warmth.", icon_name="bolt.fill", value_tint="#34D15C", sort_order=30),
            AnalysisMetric(section="dating_profile", metric_id="trust-signal", title_key="analysis.photoOptimization.metric.trustSignal", value_text="Clear and authentic", numeric_value=8.4, unit="score", status_text="Strong", detail_text="Photo 2 keeps the face readable and the styling natural, which makes the profile feel more trustworthy. Photo 1 can support the set, but it should not carry the first impression because it feels less open.", icon_name="checkmark.seal.fill", value_tint="#34D15C", sort_order=40),
            AnalysisMetric(section="dating_profile", metric_id="conversation-hook", title_key="analysis.photoOptimization.metric.conversationHook", value_text="Limited context", numeric_value=6.4, unit="score", status_text="Needs hook", detail_text="Both photos show the face, but neither gives a clear lifestyle detail someone can ask about. Add one activity, travel, outfit, or cafe-style frame so the profile has an easy first-message hook.", icon_name="text.bubble.fill", value_tint="#FFB020", sort_order=50),
            AnalysisMetric(section="profile_plan", metric_id="photo-mix", title_key="analysis.photoOptimization.metric.photoMix", value_text="Pair with lifestyle and social proof", status_text="Recommended", detail_text="Lead with Photo 2, place Photo 1 later as a backup, then add one full-body frame and one activity shot. This creates a warmer sequence than using two similar close-up portraits back to back.", icon_name="rectangle.stack.fill", sort_order=60),
            AnalysisMetric(section="profile_plan", metric_id="avoid-profile", title_key="analysis.photoOptimization.metric.avoidProfile", value_text="Avoid all-neutral expressions", status_text="Profile risk", detail_text="If every photo has the same reserved expression, the profile can feel less warm than you intend.", icon_name="exclamationmark.triangle.fill", value_tint="#FFB020", sort_order=70),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="warmth", body_text="Retake the lead photo with a natural smile and slightly brighter eye-level light.", category="dating_profile", sort_order=10),
            GrowthOpportunity(item_id="conversation-hook", body_text="Add one photo that shows a hobby, place, or outfit detail someone can easily ask about.", category="dating_profile", sort_order=20),
        ]
        return payload

    def _instagram_profile_score_payload(self) -> AnalysisResultPayload:
        payload = self._base("instagram-profile-score")
        payload.overall_score = 8.0
        payload.overall_progress = 0.80
        payload.potential_score = 9.1
        payload.potential_progress = 0.91
        payload.summary_text = (
            "This photo has strong profile-grid potential because the face reads clearly "
            "and the overall vibe is clean. It works best as a profile image or story "
            "thumbnail after a slightly tighter crop. Stronger color consistency and a "
            "cleaner background would make it feel more intentional in a feed."
        )
        payload.rings = [
            ScoreRing(metric_id="visual-impact", title_key="analysis.photoOptimization.ring.visualImpact", score=0.81, display_value="8.1", tint="#7EF0A1", sort_order=10),
            ScoreRing(metric_id="crop", title_key="analysis.photoOptimization.ring.crop", score=0.78, display_value="7.8", tint="#7EF0A1", sort_order=20),
            ScoreRing(metric_id="lighting", title_key="analysis.photoOptimization.ring.lighting", score=0.82, display_value="8.2", tint="#7EF0A1", sort_order=30),
            ScoreRing(metric_id="feed-fit", title_key="analysis.photoOptimization.ring.feedFit", score=0.76, display_value="7.6", tint="#7EF0A1", sort_order=40),
            ScoreRing(metric_id="shareability", title_key="analysis.photoOptimization.ring.shareability", score=0.74, display_value="7.4", tint="#7EF0A1", sort_order=50),
            ScoreRing(metric_id="vibe", title_key="analysis.photoOptimization.ring.vibe", score=0.83, display_value="8.3", tint="#7EF0A1", sort_order=60),
        ]
        payload.metrics = [
            AnalysisMetric(section="instagram_profile", metric_id="profile-crop", title_key="analysis.photoOptimization.metric.profileCrop", value_text="Tight square crop works", numeric_value=7.8, unit="score", status_text="Good", detail_text="Crop closer around the face and shoulders so the profile thumbnail stays readable.", icon_name="crop", value_tint="#34D15C", sort_order=10),
            AnalysisMetric(section="instagram_profile", metric_id="first-impression", title_key="analysis.photoOptimization.metric.firstImpression", value_text="Clean and composed", numeric_value=8.1, unit="score", status_text="Strong", detail_text="The image gives a polished first read without feeling overly staged.", icon_name="sparkles", value_tint="#34D15C", sort_order=20),
            AnalysisMetric(section="instagram_profile", metric_id="feed-fit", title_key="analysis.photoOptimization.metric.feedFit", value_text="Fits a clean personal grid", numeric_value=7.6, unit="score", status_text="Good", detail_text="It will work best alongside neutral, bright, and minimally cluttered posts.", icon_name="square.grid.3x3.fill", sort_order=30),
            AnalysisMetric(section="instagram_profile", metric_id="story-thumbnail", title_key="analysis.photoOptimization.metric.storyThumbnail", value_text="Readable at small size", numeric_value=8.0, unit="score", status_text="Good", detail_text="The face remains recognizable in small circular previews.", icon_name="circle.grid.cross.fill", sort_order=40),
            AnalysisMetric(section="instagram_profile", metric_id="visual-consistency", title_key="analysis.photoOptimization.metric.visualConsistency", value_text="Needs color lock", numeric_value=7.2, unit="score", status_text="Improve", detail_text="A consistent exposure and color temperature would help the image match a curated feed.", icon_name="slider.horizontal.3", value_tint="#FFB020", sort_order=50),
            AnalysisMetric(section="content_plan", metric_id="caption-direction", title_key="analysis.photoOptimization.metric.captionDirection", value_text="Simple, confident caption", status_text="Recommended", detail_text="Use a short caption that matches the clean visual style rather than explaining the photo.", icon_name="text.bubble.fill", sort_order=60),
            AnalysisMetric(section="content_plan", metric_id="posting-fix", title_key="analysis.photoOptimization.metric.postingFix", value_text="Tighten crop and reduce background noise", status_text="Highest impact", detail_text="A closer crop plus subtle background cleanup will improve profile-thumbnail impact.", icon_name="wand.and.stars", value_tint="#34D15C", sort_order=70),
        ]
        payload.growth_opportunities = [
            GrowthOpportunity(item_id="crop", body_text="Export a square and circular preview before posting so the face stays readable in both grid and profile views.", category="instagram_profile", sort_order=10),
            GrowthOpportunity(item_id="color", body_text="Use one consistent brightness and color-temperature preset across nearby feed photos.", category="instagram_profile", sort_order=20),
        ]
        return payload

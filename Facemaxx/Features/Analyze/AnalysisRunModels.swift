import Foundation
import SwiftUI

struct SavedFaceCaptureResponse {
    let photo: PhotoUploadResponse
    let scan: FaceScanCaptureResponse?
}

struct CreateAnalysisRunPayload: Encodable {
    let modeID: String
    let photoID: UUID?
    let photoIDs: [UUID]?
    let faceScanCaptureID: UUID?
    let source: String
    let locale: String
    let onboardingContext: OnboardingAnalysisContextPayload?

    enum CodingKeys: String, CodingKey {
        case modeID = "mode_id"
        case photoID = "photo_id"
        case photoIDs = "photo_ids"
        case faceScanCaptureID = "face_scan_capture_id"
        case source
        case locale
        case onboardingContext = "onboarding_context"
    }
}

struct AnalysisRunResponse: Codable {
    let id: UUID
    let status: String
    let modeID: String
    let isFreeTrialResult: Bool
    let photoID: UUID?
    let photoIDs: [UUID]?
    let faceScanCaptureID: UUID?
    let createdAt: String?
    let completedAt: String?
    let result: AnalysisResultPayload?

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case modeID = "mode_id"
        case isFreeTrialResult = "is_free_trial_result"
        case photoID = "photo_id"
        case photoIDs = "photo_ids"
        case faceScanCaptureID = "face_scan_capture_id"
        case createdAt = "created_at"
        case completedAt = "completed_at"
        case result
    }

    init(
        id: UUID,
        status: String,
        modeID: String,
        isFreeTrialResult: Bool = false,
        photoID: UUID?,
        photoIDs: [UUID]?,
        faceScanCaptureID: UUID?,
        createdAt: String?,
        completedAt: String?,
        result: AnalysisResultPayload?
    ) {
        self.id = id
        self.status = status
        self.modeID = modeID
        self.isFreeTrialResult = isFreeTrialResult
        self.photoID = photoID
        self.photoIDs = photoIDs
        self.faceScanCaptureID = faceScanCaptureID
        self.createdAt = createdAt
        self.completedAt = completedAt
        self.result = result
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        status = try container.decode(String.self, forKey: .status)
        modeID = try container.decode(String.self, forKey: .modeID)
        isFreeTrialResult = try container.decodeIfPresent(Bool.self, forKey: .isFreeTrialResult) ?? false
        photoID = try container.decodeIfPresent(UUID.self, forKey: .photoID)
        photoIDs = try container.decodeIfPresent([UUID].self, forKey: .photoIDs)
        faceScanCaptureID = try container.decodeIfPresent(UUID.self, forKey: .faceScanCaptureID)
        createdAt = try container.decodeIfPresent(String.self, forKey: .createdAt)
        completedAt = try container.decodeIfPresent(String.self, forKey: .completedAt)
        result = try container.decodeIfPresent(AnalysisResultPayload.self, forKey: .result)
    }
}

struct AnalysisHistoryItemResponse: Codable, Identifiable, Hashable {
    let id: UUID
    let status: String
    let modeID: String
    let isFreeTrialResult: Bool
    let photoID: UUID?
    let photoIDs: [UUID]?
    let faceScanCaptureID: UUID?
    let overallScore: Double?
    let summaryText: String?
    let createdAt: String?
    let completedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case modeID = "mode_id"
        case isFreeTrialResult = "is_free_trial_result"
        case photoID = "photo_id"
        case photoIDs = "photo_ids"
        case faceScanCaptureID = "face_scan_capture_id"
        case overallScore = "overall_score"
        case summaryText = "summary_text"
        case createdAt = "created_at"
        case completedAt = "completed_at"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        status = try container.decode(String.self, forKey: .status)
        modeID = try container.decode(String.self, forKey: .modeID)
        isFreeTrialResult = try container.decodeIfPresent(Bool.self, forKey: .isFreeTrialResult) ?? false
        photoID = try container.decodeIfPresent(UUID.self, forKey: .photoID)
        photoIDs = try container.decodeIfPresent([UUID].self, forKey: .photoIDs)
        faceScanCaptureID = try container.decodeIfPresent(UUID.self, forKey: .faceScanCaptureID)
        overallScore = try container.decodeIfPresent(Double.self, forKey: .overallScore)
        summaryText = try container.decodeIfPresent(String.self, forKey: .summaryText)
        createdAt = try container.decodeIfPresent(String.self, forKey: .createdAt)
        completedAt = try container.decodeIfPresent(String.self, forKey: .completedAt)
    }
}

extension AnalysisRunResponse {
    var createdDate: Date? {
        Date.facemaxxISO8601(createdAt)
    }
}

extension AnalysisHistoryItemResponse {
    var createdDate: Date {
        Date.facemaxxISO8601(createdAt) ?? Date()
    }

    var score100: Int? {
        guard let overallScore, overallScore.isFinite else { return nil }
        let normalized: Double
        if overallScore <= 1 {
            normalized = overallScore * 100
        } else if overallScore <= 10 {
            normalized = overallScore * 10
        } else {
            normalized = overallScore
        }
        return Int(normalized.rounded()).clamped(to: 0...100)
    }
}

extension Date {
    static func facemaxxISO8601(_ rawValue: String?) -> Date? {
        guard let rawValue else { return nil }
        let fractionalFormatter = ISO8601DateFormatter()
        fractionalFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractionalFormatter.date(from: rawValue) {
            return date
        }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: rawValue)
    }
}

private extension Int {
    func clamped(to range: ClosedRange<Int>) -> Int {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

private extension Double {
    var roundedToSingleDecimal: Double {
        (self * 10).rounded() / 10
    }

    func clamped(to range: ClosedRange<Double>) -> Double {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

struct AnalysisResultPayload: Codable {
    let modeID: String
    let provider: String
    let modelName: String?
    let overallScore: Double?
    let overallProgress: Double?
    let potentialScore: Double?
    let potentialProgress: Double?
    let summaryText: String?
    let rings: [AnalysisScoreRing]
    let metrics: [AnalysisResultMetric]
    let growthOpportunities: [AnalysisGrowthOpportunity]
    let photoRankings: [AnalysisPhotoRanking]?
    let coachItems: [AnalysisCoachItem]
    let lookArchetype: AnalysisLookArchetype?

    enum CodingKeys: String, CodingKey {
        case modeID = "mode_id"
        case provider
        case modelName = "model_name"
        case overallScore = "overall_score"
        case overallProgress = "overall_progress"
        case potentialScore = "potential_score"
        case potentialProgress = "potential_progress"
        case summaryText = "summary_text"
        case rings
        case metrics
        case growthOpportunities = "growth_opportunities"
        case photoRankings = "photo_rankings"
        case coachItems = "coach_items"
        case lookArchetype = "look_archetype"
    }
}

extension AnalysisResultPayload {
    var facemaxxOverallScore10: Double? {
        Self.normalizedScore10(from: overallScore)
    }

    var facemaxxPotentialScore10: Double? {
        let normalizedOverall = facemaxxOverallScore10
        let normalizedPotential = Self.normalizedScore10(from: potentialScore)
            ?? Self.normalizedProgress10(from: potentialProgress)
            ?? normalizedOverall.map { min(10, $0 + 0.8) }

        guard let normalizedPotential else { return nil }
        guard let normalizedOverall else {
            return normalizedPotential.roundedToSingleDecimal
        }

        let minimumPotential = min(10, normalizedOverall + 0.4)
        return max(normalizedPotential, minimumPotential).clamped(to: 0...10).roundedToSingleDecimal
    }

    var facemaxxOverallProgress: Double {
        ((facemaxxOverallScore10 ?? 7.4) / 10).clamped(to: 0...1)
    }

    var facemaxxPotentialProgress: Double {
        ((facemaxxPotentialScore10 ?? 8.7) / 10).clamped(to: 0...1)
    }

    var facemaxxPhotoRankings: [AnalysisPhotoRanking] {
        photoRankings ?? []
    }

    private static func normalizedScore10(from value: Double?) -> Double? {
        guard let value, value.isFinite else { return nil }
        let normalized: Double
        if value <= 1 {
            normalized = value * 10
        } else if value <= 10 {
            normalized = value
        } else {
            normalized = value / 10
        }
        return normalized.clamped(to: 0...10).roundedToSingleDecimal
    }

    private static func normalizedProgress10(from value: Double?) -> Double? {
        guard let value, value.isFinite else { return nil }
        let normalized = value <= 1 ? value * 10 : value
        return normalized.clamped(to: 0...10).roundedToSingleDecimal
    }
}

struct AnalysisScoreRing: Codable, Identifiable {
    let metricID: String
    let titleKey: String
    let score: Double
    let displayValue: String
    let tint: String?
    let sortOrder: Int

    var id: String { metricID }

    enum CodingKeys: String, CodingKey {
        case metricID = "metric_id"
        case titleKey = "title_key"
        case score
        case displayValue = "display_value"
        case tint
        case sortOrder = "sort_order"
    }
}

struct AnalysisResultMetric: Codable, Identifiable {
    let section: String
    let metricID: String
    let titleKey: String
    let valueText: String?
    let numericValue: Double?
    let unit: String?
    let statusText: String?
    let detailText: String?
    let iconName: String
    let valueTint: String?
    let sortOrder: Int

    var id: String { "\(section)-\(metricID)" }

    enum CodingKeys: String, CodingKey {
        case section
        case metricID = "metric_id"
        case titleKey = "title_key"
        case valueText = "value_text"
        case numericValue = "numeric_value"
        case unit
        case statusText = "status_text"
        case detailText = "detail_text"
        case iconName = "icon_name"
        case valueTint = "value_tint"
        case sortOrder = "sort_order"
    }
}

struct AnalysisGrowthOpportunity: Codable, Identifiable {
    let itemID: String
    let titleKey: String?
    let bodyText: String?
    let category: String
    let sortOrder: Int

    var id: String { itemID }

    enum CodingKeys: String, CodingKey {
        case itemID = "item_id"
        case titleKey = "title_key"
        case bodyText = "body_text"
        case category
        case sortOrder = "sort_order"
    }
}

struct AnalysisPhotoRanking: Codable, Identifiable {
    let candidateIndex: Int
    let rank: Int
    let score: Double?
    let verdict: String?
    let reasonText: String?
    let descriptionText: String?
    let bestUseText: String?
    let funLabelText: String?
    let strengths: [String]
    let weaknessText: String?
    let fixText: String?
    let captionIdeaText: String?
    let vibeTags: [String]

    var id: Int { candidateIndex }

    enum CodingKeys: String, CodingKey {
        case candidateIndex = "candidate_index"
        case rank
        case score
        case verdict
        case reasonText = "reason_text"
        case descriptionText = "description_text"
        case bestUseText = "best_use_text"
        case funLabelText = "fun_label_text"
        case strengths
        case weaknessText = "weakness_text"
        case fixText = "fix_text"
        case captionIdeaText = "caption_idea_text"
        case vibeTags = "vibe_tags"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        candidateIndex = try container.decode(Int.self, forKey: .candidateIndex)
        rank = try container.decode(Int.self, forKey: .rank)
        score = try container.decodeIfPresent(Double.self, forKey: .score)
        verdict = try container.decodeIfPresent(String.self, forKey: .verdict)
        reasonText = try container.decodeIfPresent(String.self, forKey: .reasonText)
        descriptionText = try container.decodeIfPresent(String.self, forKey: .descriptionText)
        bestUseText = try container.decodeIfPresent(String.self, forKey: .bestUseText)
        funLabelText = try container.decodeIfPresent(String.self, forKey: .funLabelText)
        strengths = try container.decodeIfPresent([String].self, forKey: .strengths) ?? []
        weaknessText = try container.decodeIfPresent(String.self, forKey: .weaknessText)
        fixText = try container.decodeIfPresent(String.self, forKey: .fixText)
        captionIdeaText = try container.decodeIfPresent(String.self, forKey: .captionIdeaText)
        vibeTags = try container.decodeIfPresent([String].self, forKey: .vibeTags) ?? []
    }
}

struct AnalysisCoachItem: Codable, Identifiable {
    let section: String
    let itemID: String
    let titleKey: String
    let assessmentText: String?
    let actionText: String?
    let iconName: String
    let isDefaultExpanded: Bool
    let sortOrder: Int

    var id: String { itemID }

    enum CodingKeys: String, CodingKey {
        case section
        case itemID = "item_id"
        case titleKey = "title_key"
        case assessmentText = "assessment_text"
        case actionText = "action_text"
        case iconName = "icon_name"
        case isDefaultExpanded = "is_default_expanded"
        case sortOrder = "sort_order"
    }
}

struct AnalysisLookArchetype: Codable {
    let archetypeID: String
    let titleKey: String
    let typeName: String
    let secondaryTypeName: String?
    let subtitleText: String?
    let bodyText: String?
    let shareBadgeKey: String?
    let traits: [AnalysisLookArchetypeTrait]
    let sections: [AnalysisLookArchetypeSection]

    enum CodingKeys: String, CodingKey {
        case archetypeID = "archetype_id"
        case titleKey = "title_key"
        case typeName = "type_name"
        case secondaryTypeName = "secondary_type_name"
        case subtitleText = "subtitle_text"
        case bodyText = "body_text"
        case shareBadgeKey = "share_badge_key"
        case traits
        case sections
    }
}

struct AnalysisLookArchetypeTrait: Codable, Identifiable {
    let traitID: String
    let titleKey: String
    let titleText: String?
    let tint: String
    let sortOrder: Int

    var id: String { traitID }

    enum CodingKeys: String, CodingKey {
        case traitID = "trait_id"
        case titleKey = "title_key"
        case titleText = "title_text"
        case tint
        case sortOrder = "sort_order"
    }
}

struct AnalysisLookArchetypeSection: Codable, Identifiable {
    let sectionID: String
    let titleKey: String
    let titleText: String?
    let iconName: String
    let tint: String
    let isDefaultExpanded: Bool
    let sortOrder: Int
    let bullets: [AnalysisLookArchetypeBullet]

    var id: String { sectionID }

    enum CodingKeys: String, CodingKey {
        case sectionID = "section_id"
        case titleKey = "title_key"
        case titleText = "title_text"
        case iconName = "icon_name"
        case tint
        case isDefaultExpanded = "is_default_expanded"
        case sortOrder = "sort_order"
        case bullets
    }
}

struct AnalysisLookArchetypeBullet: Codable, Identifiable {
    let bulletID: String
    let titleKey: String
    let titleText: String?
    let iconName: String
    let sortOrder: Int

    var id: String { bulletID }

    enum CodingKeys: String, CodingKey {
        case bulletID = "bullet_id"
        case titleKey = "title_key"
        case titleText = "title_text"
        case iconName = "icon_name"
        case sortOrder = "sort_order"
    }
}

extension Color {
    init(facemaxxHex hex: String?) {
        guard let hex else {
            self = FXTheme.green
            return
        }

        let value = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard value.count == 6, let intValue = UInt64(value, radix: 16) else {
            self = FXTheme.green
            return
        }

        self = Color(
            red: Double((intValue >> 16) & 0xFF) / 255.0,
            green: Double((intValue >> 8) & 0xFF) / 255.0,
            blue: Double(intValue & 0xFF) / 255.0
        )
    }
}

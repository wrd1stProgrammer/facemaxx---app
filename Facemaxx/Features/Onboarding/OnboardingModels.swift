import Foundation
import SwiftUI

enum OnboardingState {
    static let completedStorageKey = "facemaxx.onboarding.completed"
    static let preferencesStorageKey = "facemaxx.onboarding.preferences"
}

enum AppReviewDemoMode {
    static let enabledStorageKey = "facemaxx.appReviewDemo.enabled"
    static let accessCode = "Bjr5101!"
    static let demoHeaderValue = "1"
    static let demoPhotoNames = ["demo1", "demo2", "demo3"]
    static let defaultModeID = "best-photo-selector"
    static let unlimitedScanDisplayCount = 999_999
    static let longPressDuration: Double = 5

    static var isEnabled: Bool {
        UserDefaults.standard.bool(forKey: enabledStorageKey)
    }

    static func activate() {
        UserDefaults.standard.set(true, forKey: enabledStorageKey)
    }

    static func deactivate() {
        UserDefaults.standard.set(false, forKey: enabledStorageKey)
    }

    static func matchesAccessCode(_ code: String) -> Bool {
        code.trimmingCharacters(in: .whitespacesAndNewlines) == accessCode
    }

    static var onboardingPreferences: OnboardingPreferences {
        OnboardingPreferences(
            selectedGoalIDs: [
                "proportions",
                "symmetry",
                "photos",
                "profile",
                "glow",
                "progress"
            ],
            genderID: nil,
            age: nil,
            ageRangeID: "18-24",
            discoverySourceID: "app-review",
            completedAt: Date()
        )
    }
}

enum AIAnalysisConsentStore {
    static let grantedStorageKey = "facemaxx.aiAnalysisConsent.granted"
    static let promptSeenStorageKey = "facemaxx.aiAnalysisConsent.promptSeen"

    static var isGranted: Bool {
        UserDefaults.standard.bool(forKey: grantedStorageKey)
    }

    static var hasSeenPrompt: Bool {
        UserDefaults.standard.bool(forKey: promptSeenStorageKey)
    }

    static func grant() {
        UserDefaults.standard.set(true, forKey: grantedStorageKey)
        UserDefaults.standard.set(true, forKey: promptSeenStorageKey)
    }

    static func markPromptSeen() {
        UserDefaults.standard.set(true, forKey: promptSeenStorageKey)
    }

    static func revoke() {
        UserDefaults.standard.set(false, forKey: grantedStorageKey)
        UserDefaults.standard.set(true, forKey: promptSeenStorageKey)
    }
}

struct AIAnalysisConsentSheet: View {
    let primaryButtonKey: LocalizedStringKey
    let onAgree: () -> Void
    let onNotNow: () -> Void

    var body: some View {
        ZStack {
            FXTheme.background
                .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 12) {
                        Image(systemName: "sparkles.rectangle.stack.fill")
                            .font(.system(size: 34, weight: .heavy))
                            .foregroundStyle(FXTheme.premiumBlue)

                        Text("privacy.aiConsent.title")
                            .font(.system(size: 28, weight: .black))
                            .foregroundStyle(FXTheme.textPrimary)
                            .lineLimit(2)
                            .minimumScaleFactor(0.78)

                        Text("privacy.aiConsent.body")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(FXTheme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("privacy.aiConsent.dataTitle")
                            .font(.system(size: 16, weight: .black))
                            .foregroundStyle(FXTheme.textPrimary)

                        AIAnalysisConsentBullet(textKey: "privacy.aiConsent.data.photo")
                        AIAnalysisConsentBullet(textKey: "privacy.aiConsent.data.geometry")
                        AIAnalysisConsentBullet(textKey: "privacy.aiConsent.data.measurements")
                    }
                    .padding(16)
                    .fxCard(cornerRadius: 24)

                    VStack(alignment: .leading, spacing: 10) {
                        Text("privacy.aiConsent.providerTitle")
                            .font(.system(size: 15, weight: .black))
                            .foregroundStyle(FXTheme.textPrimary)

                        Label("privacy.aiConsent.providerValue", systemImage: "server.rack")
                            .font(.system(size: 14, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 9)
                            .background(FXTheme.pill, in: Capsule(style: .continuous))

                        Text("privacy.aiConsent.usage")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(FXTheme.textMuted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(16)
                    .fxCard(cornerRadius: 24)

                    VStack(spacing: 12) {
                        Button(action: onAgree) {
                            Text(primaryButtonKey)
                                .font(.system(size: 17, weight: .black))
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .frame(height: 56)
                                .background(FXTheme.premiumBlue, in: Capsule(style: .continuous))
                        }
                        .buttonStyle(.plain)

                        Button(action: onNotNow) {
                            Text("privacy.aiConsent.notNow")
                                .font(.system(size: 16, weight: .heavy))
                                .foregroundStyle(FXTheme.textSecondary)
                                .frame(maxWidth: .infinity)
                                .frame(height: 48)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 26)
                .padding(.bottom, 24)
            }
            .scrollIndicators(.hidden)
        }
        .preferredColorScheme(.dark)
    }
}

private struct AIAnalysisConsentBullet: View {
    let textKey: LocalizedStringKey

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(FXTheme.green)
                .padding(.top, 2)

            Text(textKey)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct OnboardingGoal: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey

    @MainActor
    static let all: [OnboardingGoal] = [
        OnboardingGoal(id: "proportions", titleKey: "onboarding.faceFocus.proportions"),
        OnboardingGoal(id: "symmetry", titleKey: "onboarding.faceFocus.symmetry"),
        OnboardingGoal(id: "jawline", titleKey: "onboarding.faceFocus.jawline"),
        OnboardingGoal(id: "photos", titleKey: "onboarding.faceFocus.photos"),
        OnboardingGoal(id: "profile", titleKey: "onboarding.faceFocus.profile"),
        OnboardingGoal(id: "glow", titleKey: "onboarding.faceFocus.glowUp"),
        OnboardingGoal(id: "progress", titleKey: "onboarding.faceFocus.progress")
    ]
}

struct OnboardingChoice: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
}

enum OnboardingChoices {
    @MainActor
    static let discoverySources: [OnboardingChoice] = [
        OnboardingChoice(id: "app-store", titleKey: "onboarding.source.appStore"),
        OnboardingChoice(id: "tiktok", titleKey: "onboarding.source.tiktok"),
        OnboardingChoice(id: "instagram", titleKey: "onboarding.source.instagram"),
        OnboardingChoice(id: "youtube", titleKey: "onboarding.source.youtube"),
        OnboardingChoice(id: "google", titleKey: "onboarding.source.google"),
        OnboardingChoice(id: "friend", titleKey: "onboarding.source.friend"),
        OnboardingChoice(id: "other", titleKey: "onboarding.source.other")
    ]

    @MainActor
    static let genders: [OnboardingChoice] = [
        OnboardingChoice(id: "male", titleKey: "onboarding.about.gender.male"),
        OnboardingChoice(id: "female", titleKey: "onboarding.about.gender.female"),
        OnboardingChoice(id: "other", titleKey: "onboarding.about.gender.other")
    ]

    @MainActor
    static let ageRanges: [OnboardingChoice] = [
        OnboardingChoice(id: "18-24", titleKey: "onboarding.about.age.18-24"),
        OnboardingChoice(id: "25-34", titleKey: "onboarding.about.age.25-34"),
        OnboardingChoice(id: "35-44", titleKey: "onboarding.about.age.35-44"),
        OnboardingChoice(id: "45+", titleKey: "onboarding.about.age.45plus")
    ]
}

struct OnboardingPreferences: Codable, Equatable {
    let selectedGoalIDs: [String]
    let genderID: String?
    let age: Int?
    let ageRangeID: String?
    let discoverySourceID: String?
    let completedAt: Date

    enum CodingKeys: String, CodingKey {
        case selectedGoalIDs
        case genderID
        case age
        case ageRangeID
        case discoverySourceID
        case completedAt
    }

    init(
        selectedGoalIDs: [String],
        genderID: String?,
        age: Int? = nil,
        ageRangeID: String? = nil,
        discoverySourceID: String? = nil,
        completedAt: Date
    ) {
        self.selectedGoalIDs = selectedGoalIDs
        self.genderID = genderID
        self.age = age
        self.ageRangeID = ageRangeID ?? age.map(Self.ageRangeID)
        self.discoverySourceID = discoverySourceID
        self.completedAt = completedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        selectedGoalIDs = try container.decodeIfPresent([String].self, forKey: .selectedGoalIDs) ?? []
        genderID = try container.decodeIfPresent(String.self, forKey: .genderID)
        age = try container.decodeIfPresent(Int.self, forKey: .age)
        let storedAgeRangeID = try container.decodeIfPresent(String.self, forKey: .ageRangeID)
        ageRangeID = storedAgeRangeID ?? age.map(Self.ageRangeID)
        discoverySourceID = try container.decodeIfPresent(String.self, forKey: .discoverySourceID)
        completedAt = try container.decodeIfPresent(Date.self, forKey: .completedAt) ?? Date()
    }

    private static func ageRangeID(for age: Int) -> String {
        switch age {
        case ..<25:
            "18-24"
        case 25..<35:
            "25-34"
        case 35..<45:
            "35-44"
        default:
            "45+"
        }
    }
}

struct OnboardingPreferencesRemotePayload: Encodable {
    let selectedGoalIDs: [String]
    let genderID: String?
    let age: Int?
    let ageRangeID: String?
    let completedAt: String
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case selectedGoalIDs = "selected_goal_ids"
        case genderID = "gender_id"
        case age
        case ageRangeID = "age_range_id"
        case completedAt = "completed_at"
        case metadata
    }
}

struct OnboardingAnalysisContextPayload: Codable {
    let selectedGoalIDs: [String]
    let genderID: String?
    let age: Int?
    let ageRangeID: String?
    let completedAt: String

    enum CodingKeys: String, CodingKey {
        case selectedGoalIDs = "selected_goal_ids"
        case genderID = "gender_id"
        case age
        case ageRangeID = "age_range_id"
        case completedAt = "completed_at"
    }
}

struct OnboardingPreferencesRemoteResponse: Decodable {
    let selectedGoalIDs: [String]
    let genderID: String?
    let age: Int?
    let ageRangeID: String?
    let completedAt: String?
    let metadata: [String: String]
    let persisted: Bool

    enum CodingKeys: String, CodingKey {
        case selectedGoalIDs = "selected_goal_ids"
        case genderID = "gender_id"
        case age
        case ageRangeID = "age_range_id"
        case completedAt = "completed_at"
        case metadata
        case persisted
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        selectedGoalIDs = try container.decodeIfPresent([String].self, forKey: .selectedGoalIDs) ?? []
        genderID = try container.decodeIfPresent(String.self, forKey: .genderID)
        age = try container.decodeIfPresent(Int.self, forKey: .age)
        ageRangeID = try container.decodeIfPresent(String.self, forKey: .ageRangeID)
        completedAt = try container.decodeIfPresent(String.self, forKey: .completedAt)
        metadata = (try? container.decode([String: String].self, forKey: .metadata)) ?? [:]
        persisted = try container.decodeIfPresent(Bool.self, forKey: .persisted) ?? false
    }

    var localPreferences: OnboardingPreferences? {
        guard persisted else { return nil }
        return OnboardingPreferences(
            selectedGoalIDs: selectedGoalIDs,
            genderID: genderID,
            age: age,
            ageRangeID: ageRangeID,
            discoverySourceID: metadata["discovery_source"],
            completedAt: Date.facemaxxISO8601(completedAt) ?? Date()
        )
    }
}

extension OnboardingPreferences {
    var remotePayload: OnboardingPreferencesRemotePayload {
        var metadata = [
            "app": "ios",
            "source": "onboarding"
        ]
        if let discoverySourceID {
            metadata["discovery_source"] = discoverySourceID
        }

        return OnboardingPreferencesRemotePayload(
            selectedGoalIDs: selectedGoalIDs,
            genderID: genderID,
            age: age,
            ageRangeID: ageRangeID,
            completedAt: Self.iso8601String(from: completedAt),
            metadata: metadata
        )
    }

    var analysisContextPayload: OnboardingAnalysisContextPayload {
        OnboardingAnalysisContextPayload(
            selectedGoalIDs: selectedGoalIDs,
            genderID: genderID,
            age: age,
            ageRangeID: ageRangeID,
            completedAt: Self.iso8601String(from: completedAt)
        )
    }

    private static func iso8601String(from date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }
}

enum OnboardingPreferencesStore {
    static func save(_ preferences: OnboardingPreferences) {
        guard let data = try? JSONEncoder().encode(preferences) else { return }
        UserDefaults.standard.set(data, forKey: OnboardingState.preferencesStorageKey)
    }

    static func load() -> OnboardingPreferences? {
        guard let data = UserDefaults.standard.data(forKey: OnboardingState.preferencesStorageKey) else {
            return nil
        }
        return try? JSONDecoder().decode(OnboardingPreferences.self, from: data)
    }

    static func clear() {
        UserDefaults.standard.removeObject(forKey: OnboardingState.preferencesStorageKey)
        UserDefaults.standard.set(false, forKey: OnboardingState.completedStorageKey)
    }
}

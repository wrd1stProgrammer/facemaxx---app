import SwiftUI

struct AnalysisMode: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let iconName: String
    let badgeKey: LocalizedStringKey
    let badgeColor: Color
    let isHighlighted: Bool

    var requiresMultiplePhotos: Bool {
        minimumPhotoCount > 1
    }

    var isProScanMode: Bool {
        Self.isProScanMode(modeID: id)
    }

    static func isProScanMode(modeID: String?) -> Bool {
        modeID != nil
    }

    var minimumPhotoCount: Int {
        Self.minimumPhotoCount(modeID: id)
    }

    static func requiresMultiplePhotos(modeID: String?) -> Bool {
        minimumPhotoCount(modeID: modeID) > 1
    }

    static func minimumPhotoCount(modeID: String?) -> Int {
        guard let modeID else { return 1 }

        switch modeID {
        case "best-photo-selector", "best-angle-finder":
            return 3
        case "dating-profile-score", "instagram-profile-score":
            return 2
        default:
            return 1
        }
    }

    @MainActor static let allModes = [
        AnalysisMode(
            id: "proportions",
            titleKey: "analysis.mode.proportions",
            iconName: "chart.bar.fill",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "aesthetics",
            titleKey: "analysis.mode.aesthetics",
            iconName: "brain.head.profile",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "glow-up-coach",
            titleKey: "analysis.mode.glowUpCoach",
            iconName: "sparkles",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "look-archetype",
            titleKey: "analysis.mode.lookArchetype",
            iconName: "theatermasks.fill",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "best-photo-selector",
            titleKey: "analysis.mode.bestPhotoSelector",
            iconName: "checkmark.seal.fill",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "best-angle-finder",
            titleKey: "analysis.mode.bestAngleFinder",
            iconName: "viewfinder",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "dating-profile-score",
            titleKey: "analysis.mode.datingProfileScore",
            iconName: "heart.fill",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        ),
        AnalysisMode(
            id: "instagram-profile-score",
            titleKey: "analysis.mode.instagramProfileScore",
            iconName: "square.grid.3x3.fill",
            badgeKey: "analysis.badge.proScan",
            badgeColor: Color(red: 0.38, green: 0.46, blue: 1.00),
            isHighlighted: false
        )
    ]
}

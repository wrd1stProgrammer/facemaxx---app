import SwiftUI

struct TrendsCard: View {
    let summary: HomeProgressSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("progress.trendsTitle")
                .font(.system(size: 26, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)

            VStack(spacing: 12) {
                TrendRow(
                    iconName: "chart.line.uptrend.xyaxis",
                    titleKey: "progress.lastScore",
                    subtitleText: summary.scoreDeltaText,
                    valueText: summary.latestScoreText,
                    tint: FXTheme.green
                )
                TrendRow(
                    iconName: "trophy.fill",
                    titleKey: "progress.bestScore",
                    subtitleKey: "progress.allTime",
                    valueText: summary.bestScoreText,
                    tint: FXTheme.green
                )
                TrendRow(
                    iconName: "chart.bar.fill",
                    titleKey: "progress.averageScore",
                    subtitleKey: "progress.overall",
                    valueText: summary.averageScoreText,
                    tint: FXTheme.blue
                )
                TrendRow(
                    iconName: "brain.head.profile",
                    titleKey: "progress.bestMode",
                    subtitleKey: "progress.changed",
                    valueKey: LocalizedStringKey(summary.bestModeKey),
                    tint: FXTheme.yellow
                )
                TrendRow(
                    iconName: "star.fill",
                    titleKey: "progress.bestFeature",
                    subtitleText: summary.bestFeatureScoreText,
                    valueKey: LocalizedStringKey(summary.bestFeatureKey),
                    tint: FXTheme.purple
                )
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 20)
        .padding(.bottom, 18)
        .fxCard(cornerRadius: 30)
    }
}

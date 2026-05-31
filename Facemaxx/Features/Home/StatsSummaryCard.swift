import SwiftUI

struct StatsSummaryCard: View {
    let summary: HomeDashboardSummary
    @Binding var selectedPeriod: HomeStatsPeriod

    private var changeValueText: String {
        guard let scoreChange = summary.scoreChange else { return "--" }
        if scoreChange > 0 {
            return "+\(scoreChange)"
        }
        return "\(scoreChange)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center) {
                Text("home.yourStats")
                    .font(.headline.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer()

                HStack(spacing: 8) {
                    ForEach(HomeStatsPeriod.allCases) { period in
                        Button {
                            withAnimation(.smooth(duration: 0.22)) {
                                selectedPeriod = period
                            }
                        } label: {
                            Text(LocalizedStringKey(period.titleKey))
                                .lineLimit(1)
                                .fixedSize(horizontal: true, vertical: false)
                                .minimumScaleFactor(0.72)
                                .foregroundStyle(selectedPeriod == period ? FXTheme.textPrimary : FXTheme.textMuted)
                                .frame(minWidth: selectedPeriod == period ? 44 : 30)
                                .padding(.vertical, 7)
                                .background {
                                    if selectedPeriod == period {
                                        Capsule(style: .continuous)
                                            .fill(FXTheme.premiumBlue.opacity(0.36))
                                    }
                                }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .font(.system(size: 12, weight: .heavy, design: .rounded))
            }

            HStack(spacing: 0) {
                StatValueColumn(iconName: "flame.fill", iconColor: FXTheme.orange, value: "\(summary.streakDays)", titleKey: "home.stat.streak")
                StatValueColumn(iconName: "chart.bar.fill", iconColor: FXTheme.cyan, value: "\(summary.totalScans)", titleKey: "home.stat.scans")
                StatValueColumn(iconName: "target", iconColor: FXTheme.green, value: summary.averageScoreText, titleKey: "home.stat.avg")
                StatValueColumn(iconName: summary.scoreChange ?? 0 >= 0 ? "arrow.up.right" : "arrow.down.right", iconColor: summary.scoreChange ?? 0 >= 0 ? FXTheme.green : FXTheme.orange, value: changeValueText, titleKey: "home.stat.change")
            }
            .padding(.vertical, 12)
            .fxCard(cornerRadius: 22, fill: FXTheme.cardElevated, stroke: Color.white.opacity(0.035))

            Text(LocalizedStringKey(summary.hasAnalysis ? "home.statsMessage.active" : "home.statsMessage"))
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FXTheme.textMuted)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(18)
        .fxCard(cornerRadius: 34)
    }
}

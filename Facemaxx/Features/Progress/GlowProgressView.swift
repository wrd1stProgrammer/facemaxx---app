import SwiftUI

struct GlowProgressView: View {
    @StateObject private var activityStore = HomeActivityStore.shared
    @State private var isHistoryPresented = false

    private var summary: HomeProgressSummary {
        activityStore.progressSummary()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("progress.title")
                        .font(.system(size: 32, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)

                    Text("progress.subtitle")
                        .font(.title3.weight(.medium))
                        .foregroundStyle(FXTheme.textSecondary)
                }
                .padding(.top, 70)

                HStack(spacing: 12) {
                    ProgressMetricCard(
                        titleKey: "progress.currentStreak",
                        valueText: "\(summary.streakDays)",
                        suffixKey: "progress.daysSuffix",
                        iconName: "flame.fill",
                        iconColor: FXTheme.orange
                    )

                    Button {
                        isHistoryPresented = true
                    } label: {
                        ProgressMetricCard(
                            titleKey: "progress.analyses",
                            valueText: "\(summary.analysisCount)",
                            iconName: "calendar",
                            iconColor: Color(red: 0.37, green: 0.45, blue: 1.00)
                        )
                    }
                    .buttonStyle(.plain)
                }

                AestheticsProgressCard(points: summary.chartPoints)
                TrendsCard(summary: summary)
                AnalysisHistoryButton {
                    isHistoryPresented = true
                }
            }
            .padding(.horizontal, 16)
            .safeAreaPadding(.bottom, 118)
        }
        .fullScreenCover(isPresented: $isHistoryPresented) {
            AnalysisHistoryView()
        }
        .onAppear {
            activityStore.reload()
        }
        .onReceive(NotificationCenter.default.publisher(for: HomeActivityStore.didUpdateNotification)) { _ in
            activityStore.reload()
        }
        .scrollIndicators(.hidden)
        .background(FXTheme.background)
    }
}

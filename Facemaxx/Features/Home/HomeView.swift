import SwiftUI

struct HomeView: View {
    let onStartScan: () -> Void

    @StateObject private var activityStore = HomeActivityStore.shared
    @State private var selectedStatsPeriod = HomeStatsPeriod.month

    private var scoreSummary: HomeDashboardSummary {
        activityStore.dashboard(period: .all)
    }

    private var statsSummary: HomeDashboardSummary {
        activityStore.dashboard(period: selectedStatsPeriod)
    }

    init(
        onStartScan: @escaping () -> Void = {}
    ) {
        self.onStartScan = onStartScan
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("home.title")
                        .font(.title.bold())
                        .foregroundStyle(FXTheme.textPrimary)

                    Text("home.welcome")
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                }
                .padding(.top, 42)

                ScoreSummaryCard(
                    summary: scoreSummary
                )
                StatsSummaryCard(
                    summary: statsSummary,
                    selectedPeriod: $selectedStatsPeriod
                )
                NoScanTodayCard(
                    hasScanToday: scoreSummary.hasScanToday,
                    startScanAction: onStartScan
                )
            }
            .padding(.horizontal, 16)
            .safeAreaPadding(.bottom, 118)
        }
        .scrollIndicators(.hidden)
        .background(FXTheme.background)
        .onReceive(NotificationCenter.default.publisher(for: HomeActivityStore.didUpdateNotification)) { _ in
            activityStore.reload()
        }
    }
}

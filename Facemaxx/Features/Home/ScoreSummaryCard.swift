import SwiftUI
import UIKit

struct ScoreSummaryCard: View {
    let summary: HomeDashboardSummary

    @Environment(\.locale) private var locale
    @State private var latestFaceImage: UIImage?
    @ScaledMetric(relativeTo: .largeTitle) private var scoreSize = 64

    private let metricColumns = Array(
        repeating: GridItem(.flexible(), spacing: 10),
        count: 3
    )

    private var scanDateText: String {
        guard let latestActivityAt = summary.latestActivityAt else {
            return String(localized: "home.scanDate.empty", locale: locale)
        }
        return latestActivityAt.formatted(
            Date.FormatStyle()
                .month(.abbreviated)
                .day()
                .locale(locale)
        )
    }

    private var scoreChangeColor: Color {
        guard let scoreChange = summary.scoreChange else { return FXTheme.textMuted }
        return scoreChange >= 0 ? FXTheme.green : FXTheme.orange
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("home.latestReport")
                        .font(.system(size: 12, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)
                        .textCase(.uppercase)

                    Text("\(String(localized: "home.scanDatePrefix", locale: locale)) \(scanDateText)")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)
                }

                Spacer(minLength: 14)

                VerifiedBadge(scanCount: summary.totalScans)
            }

            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 9) {
                    Text("home.overallScore")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)

                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(summary.latestScoreText)
                            .font(.system(size: scoreSize, weight: .heavy, design: .rounded))
                            .minimumScaleFactor(0.72)
                            .foregroundStyle(FXTheme.textPrimary)

                        Text("/100")
                            .font(.title3.weight(.bold))
                            .foregroundStyle(FXTheme.textMuted)
                    }

                    Text(summary.scoreChangeText)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(scoreChangeColor)
                }

                Spacer(minLength: 10)

                HomeFaceScanThumbnail(
                    image: latestFaceImage
                )
            }

            LazyVGrid(columns: metricColumns, spacing: 12) {
                ForEach(summary.overviewMetrics) { metric in
                    MetricPill(
                        iconName: metric.iconName,
                        value: metric.valueText ?? metric.score100.map(String.init) ?? "--",
                        titleKey: LocalizedStringKey(metric.displayTitleKey),
                        sourceKey: metric.sourceTitleKey.map { LocalizedStringKey($0) }
                    )
                }
            }
        }
        .padding(20)
        .fxCard(cornerRadius: 34)
        .task(id: summary.latestPhotoID) {
            await loadLatestFaceImage(photoID: summary.latestPhotoID)
        }
    }

    @MainActor
    private func loadLatestFaceImage(photoID: UUID?) async {
        guard let photoID else {
            latestFaceImage = nil
            return
        }

        if let cachedImage = PhotoImageCache.shared.image(id: photoID) {
            latestFaceImage = cachedImage
            return
        }

        do {
            let image = try await FacemaxxAPIClient.shared.fetchPhotoImage(id: photoID)
            latestFaceImage = image
        } catch {
            latestFaceImage = nil
        }
    }
}

private struct HomeDetailedMetricsPanel: View {
    let metrics: [HomeDashboardMetric]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("home.detailMetrics.title")
                    .font(.headline.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer()

                Text("home.detailMetrics.score")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(FXTheme.textMuted)
            }

            Text("home.detailMetrics.subtitle")
                .font(.caption.weight(.semibold))
                .foregroundStyle(FXTheme.textMuted)

            VStack(spacing: 12) {
                if metrics.isEmpty {
                    Text("home.detailMetrics.empty")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 6)
                } else {
                    ForEach(metrics) { metric in
                        HomeDetailedMetricRow(metric: metric)

                        if metric.id != metrics.last?.id {
                            Divider()
                                .overlay(Color.white.opacity(0.08))
                        }
                    }
                }
            }
        }
        .padding(.top, 2)
    }
}

private struct HomeDetailedMetricRow: View {
    let metric: HomeDashboardMetric

    private var tint: Color {
        Color(facemaxxHex: metric.tintHex)
    }

    private var progress: CGFloat {
        CGFloat(metric.score100 ?? 0) / 100
    }

    private var valueText: String {
        if let score100 = metric.score100 {
            return "\(score100)"
        }
        return metric.valueText ?? "--"
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: metric.iconName)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(tint)
                .frame(width: 32, height: 32)
                .background {
                    Circle()
                        .fill(tint.opacity(0.14))
                }

            VStack(alignment: .leading, spacing: 7) {
                HStack(alignment: .center, spacing: 8) {
                    Text(LocalizedStringKey(metric.displayTitleKey))
                        .font(.system(size: 14.5, weight: .bold))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.82)
                        .layoutPriority(1)

                    Spacer(minLength: 8)

                    Text(valueText)
                        .font(.system(size: 15, weight: .heavy, design: .rounded))
                        .foregroundStyle(metric.score100 == nil ? FXTheme.textSecondary : FXTheme.textPrimary)
                        .monospacedDigit()
                        .multilineTextAlignment(.trailing)
                        .lineLimit(1)
                        .minimumScaleFactor(0.86)
                        .frame(width: 44, alignment: .trailing)
                }

                if metric.score100 != nil {
                    GeometryReader { proxy in
                        ZStack(alignment: .leading) {
                            Capsule(style: .continuous)
                                .fill(Color.white.opacity(0.08))

                            Capsule(style: .continuous)
                                .fill(tint)
                                .frame(width: max(6, proxy.size.width * progress))
                        }
                    }
                    .frame(height: 7)
                } else if let metricValue = metric.valueText {
                    Text(metricValue)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(FXTheme.textMuted)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

private struct HomeFaceScanThumbnail: View {
    let image: UIImage?

    private let side: CGFloat = 112

    var body: some View {
        Group {
            if let image {
                ZStack {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(width: side, height: side)
                        .clipped()
                        .overlay {
                            RoundedRectangle(cornerRadius: 26, style: .continuous)
                                .stroke(Color.white.opacity(0.09), lineWidth: 1)
                        }
                }
                .frame(width: side, height: side)
                .clipShape(.rect(cornerRadius: 26, style: .continuous))
                .contentShape(.rect(cornerRadius: 26, style: .continuous))
                .shadow(color: .black.opacity(0.28), radius: 14, y: 8)
                .accessibilityLabel("analysis.selectedPhoto")
            } else {
                FaceScanMaskView()
                    .frame(width: side, height: side)
            }
        }
    }
}

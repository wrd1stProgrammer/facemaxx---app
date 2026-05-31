import SwiftUI
import UIKit

struct AnalysisHistoryView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    @AppStorage(AppLanguage.storageKey) private var selectedLanguageID = AppLanguage.system.rawValue
    @StateObject private var activityStore = HomeActivityStore.shared
    @State private var items: [AnalysisHistoryDisplayItem] = []
    @State private var selectedItem: AnalysisHistoryDisplayItem?
    @State private var isLoadingRemote = false

    private var activeLocale: Locale {
        let storedLocale = AppLanguage.storedValue(for: selectedLanguageID).locale
        return selectedLanguageID == AppLanguage.system.rawValue ? locale : storedLocale
    }

    var body: some View {
        ZStack {
            FXTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                header

                ScrollView {
                    LazyVStack(spacing: 18) {
                        if items.isEmpty && isLoadingRemote {
                            ProgressView()
                                .tint(FXTheme.textPrimary)
                                .padding(.top, 80)
                        } else if items.isEmpty {
                            Text("progress.history.empty")
                                .font(.headline.weight(.bold))
                                .foregroundStyle(FXTheme.textSecondary)
                                .padding(.top, 80)
                        } else {
                            ForEach(items) { item in
                                Button {
                                    selectedItem = item
                                } label: {
                                    AnalysisHistoryCard(item: item, locale: activeLocale)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 14)
                    .safeAreaPadding(.bottom, 120)
                }
                .scrollIndicators(.hidden)
            }
        }
        .onAppear {
            reloadLocalItems()
            Task { await loadRemoteItems() }
        }
        .fullScreenCover(item: $selectedItem) { item in
            AnalysisHistoryDetailView(item: item)
        }
    }

    private var header: some View {
        ZStack {
            Text("progress.history.title")
                .font(.headline.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)

            HStack {
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.headline.weight(.heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(width: 46, height: 46)
                        .background {
                            Circle()
                                .fill(FXTheme.cardElevated.opacity(0.85))
                                .stroke(Color.white.opacity(0.08), lineWidth: 1)
                        }
                }
                .buttonStyle(.plain)

                Spacer()
            }
            .padding(.horizontal, 16)
        }
        .frame(height: 58)
        .padding(.top, 8)
    }

    private func reloadLocalItems() {
        items = activityStore.analysisHistoryItems().map { AnalysisHistoryDisplayItem(local: $0) }
    }

    @MainActor
    private func loadRemoteItems() async {
        isLoadingRemote = true
        defer { isLoadingRemote = false }

        do {
            let remoteItems = try await FacemaxxAPIClient.shared.listAnalysisRuns(limit: 80)
                .map { AnalysisHistoryDisplayItem(remote: $0) }
            items = merge(
                local: activityStore.analysisHistoryItems().map { AnalysisHistoryDisplayItem(local: $0) },
                remote: remoteItems
            )
        } catch {
            print("Facemaxx history fetch failed: \(error.localizedDescription)")
        }
    }

    private func merge(local: [AnalysisHistoryDisplayItem], remote: [AnalysisHistoryDisplayItem]) -> [AnalysisHistoryDisplayItem] {
        var byID: [UUID: AnalysisHistoryDisplayItem] = [:]
        local.forEach { byID[$0.id] = $0 }
        remote.forEach { byID[$0.id] = $0 }
        return byID.values.sorted { $0.createdAt > $1.createdAt }
    }
}

private struct AnalysisHistoryCard: View {
    let item: AnalysisHistoryDisplayItem
    let locale: Locale

    var body: some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.white.opacity(0.11))

                Image(systemName: item.iconName)
                    .font(.title.weight(.heavy))
                    .foregroundStyle(FXTheme.textSecondary)
            }
            .frame(width: 66, height: 66)

            VStack(alignment: .leading, spacing: 4) {
                Text(item.titleText(locale: locale))
                    .font(.title3.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Text(item.modeLabel(locale: locale))
                    .font(.headline.weight(.medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Text(item.dateText(locale: locale))
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(FXTheme.textMuted)
            }

            Spacer(minLength: 8)
        }
        .padding(.horizontal, 20)
        .frame(maxWidth: .infinity, minHeight: 104)
        .fxCard(cornerRadius: 28)
        .accessibilityElement(children: .combine)
    }
}

private struct AnalysisHistoryDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.locale) private var locale
    @AppStorage(AppLanguage.storageKey) private var selectedLanguageID = AppLanguage.system.rawValue
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService
    let item: AnalysisHistoryDisplayItem

    @State private var response: AnalysisRunResponse?
    @State private var image: UIImage?
    @State private var supplementalImages: [UIImage] = []
    @State private var isLoading = false
    @State private var didFail = false
    @State private var isProPaywallPresented = false

    private var activeLocale: Locale {
        let storedLocale = AppLanguage.storedValue(for: selectedLanguageID).locale
        return selectedLanguageID == AppLanguage.system.rawValue ? locale : storedLocale
    }

    var body: some View {
        ZStack {
            FXTheme.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 22) {
                    detailHeader

                    if isLoading && response == nil {
                        ProgressView()
                            .tint(FXTheme.textPrimary)
                            .padding(.top, 80)
                    } else if didFail && response?.result == nil {
                        Text("analysis.result.failed")
                            .font(.headline.weight(.bold))
                            .foregroundStyle(FXTheme.textSecondary)
                            .padding(.top, 80)
                    } else if let result = response?.result {
                        AnalysisResultContent(
                            modeID: AnalysisHistoryDisplayItem.normalizedModeID(response?.modeID ?? item.modeID),
                            result: result,
                            image: image,
                            supplementalImages: supplementalImages,
                            scanPayload: nil,
                            scanOverlayImage: nil,
                            reduceMotion: reduceMotion,
                            isFreeTrialResult: response?.isFreeTrialResult == true,
                            unlockAction: { isProPaywallPresented = true }
                        )
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 18)
                .safeAreaPadding(.bottom, 172)
            }
            .scrollIndicators(.hidden)
        }
        .task {
            await load()
        }
        .fullScreenCover(isPresented: $isProPaywallPresented) {
            ProScanPaywallView()
                .environmentObject(purchaseService)
        }
    }

    private var detailHeader: some View {
        ZStack {
            Text(item.shortModeLabel(locale: activeLocale))
                .font(.title3.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)

            HStack {
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.title2.weight(.heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(width: 54, height: 54)
                        .background {
                            Circle()
                                .fill(FXTheme.cardElevated.opacity(0.85))
                                .stroke(Color.white.opacity(0.08), lineWidth: 1)
                        }
                }
                .buttonStyle(.plain)

                Spacer()
            }
        }
        .frame(height: 62)
    }

    @MainActor
    private func load() async {
        if let cached = AnalysisJSONCache.shared.response(id: item.id) {
            response = cached
        }

        loadCachedImages(for: resolvedPhotoIDs(from: response))

        guard response?.result == nil || needsImages(for: resolvedPhotoIDs(from: response)) else { return }

        isLoading = true
        didFail = false
        defer { isLoading = false }

        do {
            if response?.result == nil {
                response = try await FacemaxxAPIClient.shared.getAnalysisRun(item.id)
            }
            let ids = resolvedPhotoIDs(from: response)
            if needsImages(for: ids) {
                try await loadImages(for: ids)
            }
        } catch {
            didFail = true
            print("Facemaxx history detail load failed: \(error.localizedDescription)")
        }
    }

    private func resolvedPhotoIDs(from response: AnalysisRunResponse?) -> [UUID] {
        let responsePhotoIDs = response?.photoIDs ?? []
        let preferredPhotoIDs = responsePhotoIDs.isEmpty ? item.photoIDs : responsePhotoIDs
        return AnalysisHistoryDisplayItem.normalizedPhotoIDs(
            primary: response?.photoID ?? item.photoID,
            photoIDs: preferredPhotoIDs
        )
    }

    private func needsImages(for ids: [UUID]) -> Bool {
        guard !ids.isEmpty else { return false }
        return image == nil || supplementalImages.count < max(0, ids.count - 1)
    }

    @MainActor
    private func loadCachedImages(for ids: [UUID]) {
        let cachedImages = ids.map { PhotoImageCache.shared.image(id: $0) }
        if let primaryImage = cachedImages.first ?? nil {
            image = primaryImage
        }
        supplementalImages = cachedImages.dropFirst().compactMap { $0 }
    }

    @MainActor
    private func loadImages(for ids: [UUID]) async throws {
        guard !ids.isEmpty else { return }
        var loadedImages: [UIImage] = []
        for (index, id) in ids.enumerated() {
            do {
                loadedImages.append(try await FacemaxxAPIClient.shared.fetchPhotoImage(id: id))
            } catch {
                if index == 0 {
                    throw error
                }
            }
        }
        guard !loadedImages.isEmpty else { return }
        image = loadedImages.first
        supplementalImages = Array(loadedImages.dropFirst())
    }
}

struct AnalysisHistoryDisplayItem: Identifiable, Hashable {
    let id: UUID
    let modeID: String
    let photoID: UUID?
    let photoIDs: [UUID]
    let faceScanCaptureID: UUID?
    let score100: Int?
    let createdAt: Date

    init(local item: AnalysisHistoryItem) {
        self.id = item.id
        self.modeID = Self.normalizedModeID(item.modeID)
        self.photoID = item.photoID
        self.photoIDs = item.photoIDs
        self.faceScanCaptureID = item.faceScanCaptureID
        self.score100 = item.score100
        self.createdAt = item.createdAt
    }

    init(remote item: AnalysisHistoryItemResponse) {
        self.id = item.id
        self.modeID = Self.normalizedModeID(item.modeID)
        self.photoID = item.photoID
        self.photoIDs = Self.normalizedPhotoIDs(primary: item.photoID, photoIDs: item.photoIDs)
        self.faceScanCaptureID = item.faceScanCaptureID
        self.score100 = item.score100
        self.createdAt = item.createdDate
    }

    func titleText(locale: Locale) -> String {
        if let score100 {
            return String(
                format: String(localized: "progress.history.scoreFormat", locale: locale),
                locale: locale,
                Double(score100) / 10
            )
        }
        return String(localized: "progress.history.textAnalysis", locale: locale)
    }

    func modeLabel(locale: Locale) -> String {
        String(
            format: String(localized: "progress.history.modeFormat", locale: locale),
            locale: locale,
            shortModeLabel(locale: locale)
        )
    }

    func shortModeLabel(locale: Locale) -> String {
        switch modeID {
        case "proportions":
            return String(localized: "analysis.mode.proportions", locale: locale)
        case "aesthetics":
            return String(localized: "analysis.mode.aesthetics", locale: locale)
        case "glow-up-coach":
            return String(localized: "analysis.mode.glowUpCoach", locale: locale)
        case "look-archetype":
            return String(localized: "analysis.mode.lookArchetype", locale: locale)
        case "best-photo-selector":
            return String(localized: "analysis.mode.bestPhotoSelector", locale: locale)
        case "best-angle-finder":
            return String(localized: "analysis.mode.bestAngleFinder", locale: locale)
        case "dating-profile-score":
            return String(localized: "analysis.mode.datingProfileScore", locale: locale)
        case "instagram-profile-score":
            return String(localized: "analysis.mode.instagramProfileScore", locale: locale)
        default:
            return modeID
        }
    }

    var iconName: String {
        switch modeID {
        case "glow-up-coach":
            return "sparkles"
        case "look-archetype":
            return "theatermasks.fill"
        case "best-photo-selector":
            return "checkmark.seal.fill"
        case "best-angle-finder":
            return "viewfinder"
        case "dating-profile-score":
            return "heart.fill"
        case "instagram-profile-score":
            return "square.grid.3x3.fill"
        case "aesthetics":
            return "brain.head.profile"
        default:
            return "chart.bar.fill"
        }
    }

    func dateText(locale: Locale) -> String {
        AnalysisHistoryDateFormatter.string(from: createdAt, locale: locale)
    }

    static func normalizedPhotoIDs(primary: UUID?, photoIDs: [UUID]?) -> [UUID] {
        var ids = photoIDs ?? []
        if let primary, !ids.contains(primary) {
            ids.insert(primary, at: 0)
        }
        return ids
    }

    static func normalizedModeID(_ rawValue: String) -> String {
        let normalized = rawValue
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: "_", with: "-")
        switch normalized {
        case "glowupcoach":
            return "glow-up-coach"
        case "lookarchetype":
            return "look-archetype"
        case "bestphotoselector":
            return "best-photo-selector"
        case "bestanglefinder":
            return "best-angle-finder"
        case "datingprofilescore":
            return "dating-profile-score"
        case "instagramprofilescore":
            return "instagram-profile-score"
        default:
            return normalized
        }
    }
}

private enum AnalysisHistoryDateFormatter {
    static func string(from date: Date, locale: Locale) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        formatter.locale = locale
        return formatter.string(from: date)
    }
}

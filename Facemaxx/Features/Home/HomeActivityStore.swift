import Foundation

enum HomeStatsPeriod: String, CaseIterable, Identifiable {
    case week
    case month
    case threeMonths
    case all

    var id: String { rawValue }

    var titleKey: String {
        switch self {
        case .week:
            "home.period.1W"
        case .month:
            "home.period.1M"
        case .threeMonths:
            "home.period.3M"
        case .all:
            "home.period.all"
        }
    }

    var dayCount: Int? {
        switch self {
        case .week:
            7
        case .month:
            30
        case .threeMonths:
            90
        case .all:
            nil
        }
    }
}

struct HomeDashboardSummary {
    var latestActivityAt: Date?
    var latestAnalysisAt: Date?
    var latestPhotoID: UUID?
    var latestFaceScanCaptureID: UUID?
    var latestScore100: Int?
    var scoreChange: Int?
    var totalScans: Int
    var averageScore100: Int?
    var streakDays: Int
    var hasScanToday: Bool
    var balanceScore: Int?
    var structureScore: Int?
    var photoReadinessScore: Int?
    var detailMetrics: [HomeDashboardMetric]
    var resolvedOverviewMetrics: [HomeDashboardMetric]

    static let empty = HomeDashboardSummary(
        latestActivityAt: nil,
        latestAnalysisAt: nil,
        latestPhotoID: nil,
        latestFaceScanCaptureID: nil,
        latestScore100: nil,
        scoreChange: nil,
        totalScans: 0,
        averageScore100: nil,
        streakDays: 0,
        hasScanToday: false,
        balanceScore: nil,
        structureScore: nil,
        photoReadinessScore: nil,
        detailMetrics: [],
        resolvedOverviewMetrics: []
    )

    var hasAnalysis: Bool {
        latestScore100 != nil
    }

    var latestScoreText: String {
        latestScore100.map(String.init) ?? "--"
    }

    var scoreChangeText: String {
        guard let scoreChange else { return "--" }
        if scoreChange > 0 {
            return "↗ +\(scoreChange)"
        }
        if scoreChange < 0 {
            return "↘ \(scoreChange)"
        }
        return "→ 0"
    }

    var averageScoreText: String {
        averageScore100.map(String.init) ?? "--"
    }

    var balanceText: String {
        balanceScore.map(String.init) ?? "--"
    }

    var structureText: String {
        structureScore.map(String.init) ?? "--"
    }

    var photoReadinessText: String {
        photoReadinessScore.map(String.init) ?? "--"
    }

    var overviewMetrics: [HomeDashboardMetric] {
        if !resolvedOverviewMetrics.isEmpty {
            return Array(resolvedOverviewMetrics.prefix(6))
        }

        let primaryMetrics = [
            HomeDashboardMetric(
                id: "balance",
                titleKey: "home.metric.balance",
                valueText: balanceScore.map { "\($0)" },
                score100: balanceScore,
                iconName: "circle.hexagongrid.fill",
                tintHex: "#8EEF9E"
            ),
            HomeDashboardMetric(
                id: "structure",
                titleKey: "home.metric.structure",
                valueText: structureScore.map { "\($0)" },
                score100: structureScore,
                iconName: "viewfinder",
                tintHex: "#8FA8FF"
            ),
            HomeDashboardMetric(
                id: "photo-readiness",
                titleKey: "home.metric.photoReadiness",
                valueText: photoReadinessScore.map { "\($0)" },
                score100: photoReadinessScore,
                iconName: "camera.fill",
                tintHex: "#8EEF9E"
            )
        ]

        let supplementalMetrics = [
            overviewMetric(
                id: "symmetry",
                titleKey: "home.metric.symmetry",
                iconName: "circle.lefthalf.filled",
                matching: ["symmetry", "harmony", "mesh-symmetry", "shape-score"]
            ),
            overviewMetric(
                id: "proportions",
                titleKey: "home.metric.proportions",
                iconName: "ruler.fill",
                matching: ["proportion", "ratio", "facial-index", "face-width-height"]
            ),
            overviewMetric(
                id: "first-impression",
                titleKey: "home.metric.firstImpression",
                iconName: "sparkles",
                matching: ["first-impression", "presence", "visual-impact", "approachability", "confidence"]
            )
        ]

        return Array((primaryMetrics + supplementalMetrics).prefix(6))
    }

    var visibleDetailMetrics: [HomeDashboardMetric] {
        if !detailMetrics.isEmpty {
            return Array(detailMetrics.prefix(6))
        }

        return [
            HomeDashboardMetric(
                id: "balance",
                titleKey: "home.metric.balance",
                valueText: balanceScore.map { "\($0)" },
                score100: balanceScore,
                iconName: "circle.hexagongrid.fill",
                tintHex: "#64CFFF"
            ),
            HomeDashboardMetric(
                id: "structure",
                titleKey: "home.metric.structure",
                valueText: structureScore.map { "\($0)" },
                score100: structureScore,
                iconName: "viewfinder",
                tintHex: "#9EB8FF"
            ),
            HomeDashboardMetric(
                id: "photo-readiness",
                titleKey: "home.metric.photoReadiness",
                valueText: photoReadinessScore.map { "\($0)" },
                score100: photoReadinessScore,
                iconName: "camera.fill",
                tintHex: "#7EF0A1"
            )
        ].filter { $0.score100 != nil || $0.valueText != nil }
    }

    private func overviewMetric(
        id: String,
        titleKey: String,
        iconName: String,
        matching tokens: [String]
    ) -> HomeDashboardMetric {
        if let metric = detailMetrics.first(where: { metric in
            let searchText = "\(metric.id) \(metric.titleKey)".lowercased()
            return tokens.contains { searchText.contains($0) }
        }) {
            return HomeDashboardMetric(
                id: id,
                titleKey: titleKey,
                valueText: metric.score100.map(String.init) ?? metric.valueText,
                score100: metric.score100,
                iconName: iconName,
                tintHex: metric.tintHex
            )
        }

        return HomeDashboardMetric(
            id: id,
            titleKey: titleKey,
            valueText: nil,
            score100: nil,
            iconName: iconName,
            tintHex: nil
        )
    }
}

struct HomeDashboardMetric: Codable, Identifiable, Hashable {
    let id: String
    let titleKey: String
    let valueText: String?
    let score100: Int?
    let iconName: String
    let tintHex: String?
    let sourceModeID: String?

    init(
        id: String,
        titleKey: String,
        valueText: String?,
        score100: Int?,
        iconName: String,
        tintHex: String?,
        sourceModeID: String? = nil
    ) {
        self.id = id
        self.titleKey = titleKey
        self.valueText = valueText
        self.score100 = score100
        self.iconName = iconName
        self.tintHex = tintHex
        self.sourceModeID = sourceModeID
    }

    var displayTitleKey: String {
        Self.displayTitleKey(for: titleKey, id: id)
    }

    var sourceTitleKey: String? {
        guard let sourceModeID else { return nil }

        switch sourceModeID {
        case "proportions":
            return "analysis.mode.proportions"
        case "aesthetics":
            return "analysis.mode.aesthetics"
        case "glow-up-coach":
            return "analysis.mode.glowUpCoach"
        case "look-archetype":
            return "analysis.mode.lookArchetype"
        case "best-photo-selector":
            return "analysis.mode.bestPhotoSelector"
        case "best-angle-finder":
            return "analysis.mode.bestAngleFinder"
        case "dating-profile-score":
            return "analysis.mode.datingProfileScore"
        case "instagram-profile-score":
            return "analysis.mode.instagramProfileScore"
        default:
            return nil
        }
    }

    private static func displayTitleKey(for titleKey: String, id: String) -> String {
        let normalizedID = id.lowercased()
        let normalizedKey = titleKey.lowercased()

        if normalizedKey == "analysis.aestheticsresults.shapescore"
            || normalizedKey.hasSuffix(".shapescore")
            || normalizedID.contains("shape-score") {
            return "home.detailMetric.shapeScore"
        }

        if normalizedKey.contains("facewidthheightratio")
            || normalizedID.contains("face-width-height-ratio") {
            return "analysis.aestheticsResults.proportion.faceWidthHeightRatio"
        }

        if normalizedKey.contains("facedepthwidthratio")
            || normalizedID.contains("face-depth-width-ratio") {
            return "analysis.aestheticsResults.proportion.faceDepthWidthRatio"
        }

        if normalizedKey.contains("eyespacingratio")
            || normalizedID.contains("eye-spacing-ratio") {
            return "analysis.aestheticsResults.proportion.eyeSpacingRatio"
        }

        return titleKey
    }
}

struct HomeProgressChartPoint: Identifiable {
    let id: UUID
    let score100: Int
    let createdAt: Date
}

struct AnalysisHistoryItem: Identifiable, Hashable {
    let id: UUID
    let modeID: String
    let photoID: UUID?
    let photoIDs: [UUID]
    let faceScanCaptureID: UUID?
    let score100: Int?
    let createdAt: Date
}

struct HomeProgressSummary {
    var streakDays: Int
    var analysisCount: Int
    var latestScore100: Int?
    var scoreDelta100: Int?
    var bestScore100: Int?
    var averageScore100: Int?
    var bestModeKey: String
    var bestFeatureKey: String
    var bestFeatureScore100: Int?
    var chartPoints: [HomeProgressChartPoint]

    static let empty = HomeProgressSummary(
        streakDays: 0,
        analysisCount: 0,
        latestScore100: nil,
        scoreDelta100: nil,
        bestScore100: nil,
        averageScore100: nil,
        bestModeKey: "progress.none",
        bestFeatureKey: "progress.none",
        bestFeatureScore100: nil,
        chartPoints: []
    )

    var latestScoreText: String {
        Self.score10Text(latestScore100)
    }

    var scoreDeltaText: String {
        guard let scoreDelta100 else { return "--" }
        let value = Double(scoreDelta100) / 10
        if value > 0 {
            return String(format: "+%.1f", value)
        }
        return String(format: "%.1f", value)
    }

    var bestScoreText: String {
        Self.score10Text(bestScore100)
    }

    var averageScoreText: String {
        Self.score10Text(averageScore100)
    }

    var bestFeatureScoreText: String {
        Self.score10Text(bestFeatureScore100)
    }

    private static func score10Text(_ score100: Int?) -> String {
        guard let score100 else { return "--" }
        return String(format: "%.1f", Double(score100) / 10)
    }
}

@MainActor
final class HomeActivityStore: ObservableObject {
    static let shared = HomeActivityStore()
    static let didUpdateNotification = Notification.Name("facemaxx.homeActivityStore.didUpdate")

    @Published private var records: [HomeActivityRecord] = []

    private static let storageKey = "facemaxx.home.activity.records"
    private let calendar = Calendar.autoupdatingCurrent

    private init() {
        reload()
    }

    func reload() {
        records = Self.loadRecords()
    }

    func dashboard(period: HomeStatsPeriod) -> HomeDashboardSummary {
        let scopedRecords = records.filtered(for: period)
        let analysisRecords = scopedRecords
            .filter { $0.kind == .analysis && $0.score100 != nil }
            .sorted { $0.createdAt > $1.createdAt }
        let latestAnalysis = records
            .filter { $0.kind == .analysis && $0.score100 != nil }
            .sorted { $0.createdAt > $1.createdAt }
            .first
        let latestActivity = records.sorted { $0.createdAt > $1.createdAt }.first

        let latestScore = latestAnalysis?.score100
        let previousScore = records
            .filter { $0.kind == .analysis && $0.score100 != nil && $0.id != latestAnalysis?.id }
            .sorted { $0.createdAt > $1.createdAt }
            .first?
            .score100

        let averageScore = analysisRecords.averageScore
        let scanCount = scopedRecords.uniqueScanCount

        return HomeDashboardSummary(
            latestActivityAt: latestActivity?.createdAt,
            latestAnalysisAt: latestAnalysis?.createdAt,
            latestPhotoID: latestAnalysis?.photoID ?? latestActivity?.photoID,
            latestFaceScanCaptureID: latestAnalysis?.faceScanCaptureID ?? latestActivity?.faceScanCaptureID,
            latestScore100: latestScore,
            scoreChange: latestScore.flatMap { latest in previousScore.map { latest - $0 } },
            totalScans: scanCount,
            averageScore100: averageScore,
            streakDays: records.streakDays(calendar: calendar),
            hasScanToday: records.contains { calendar.isDateInToday($0.createdAt) },
            balanceScore: latestAnalysis?.balanceScore ?? latestAnalysis?.harmonyScore,
            structureScore: latestAnalysis?.structureScore ?? latestAnalysis?.dimorphismScore,
            photoReadinessScore: latestAnalysis?.photoReadinessScore ?? latestAnalysis?.angularityScore,
            detailMetrics: latestAnalysis?.detailMetrics ?? [],
            resolvedOverviewMetrics: overviewMetrics(from: analysisRecords)
        )
    }

    func progressSummary() -> HomeProgressSummary {
        let analysisRecords = records
            .filter { $0.kind == .analysis && $0.score100 != nil }
            .sorted { $0.createdAt > $1.createdAt }
        guard !analysisRecords.isEmpty else {
            var empty = HomeProgressSummary.empty
            empty.streakDays = records.streakDays(calendar: calendar)
            empty.analysisCount = 0
            return empty
        }

        let latest = analysisRecords.first
        let previous = analysisRecords.dropFirst().first
        let scores = analysisRecords.compactMap(\.score100)
        let modeKey = bestModeKey(from: analysisRecords)
        let feature = bestFeature(from: latest)
        let chartPoints = dailyAverageChartPoints(from: analysisRecords).suffix(30)

        return HomeProgressSummary(
            streakDays: records.streakDays(calendar: calendar),
            analysisCount: analysisRecords.count,
            latestScore100: latest?.score100,
            scoreDelta100: latest?.score100.flatMap { latestScore in
                previous?.score100.map { latestScore - $0 }
            },
            bestScore100: scores.max(),
            averageScore100: scores.average,
            bestModeKey: modeKey,
            bestFeatureKey: feature.key,
            bestFeatureScore100: feature.score,
            chartPoints: Array(chartPoints)
        )
    }

    private func dailyAverageChartPoints(from records: [HomeActivityRecord]) -> [HomeProgressChartPoint] {
        let groupedByDay = Dictionary(grouping: records) { record in
            calendar.startOfDay(for: record.createdAt)
        }

        return groupedByDay.keys
            .sorted()
            .compactMap { day -> HomeProgressChartPoint? in
                guard let dayRecords = groupedByDay[day] else { return nil }
                let scores = dayRecords.compactMap(\.score100)
                guard let averageScore = scores.average else { return nil }
                let representativeID = dayRecords
                    .sorted { $0.createdAt > $1.createdAt }
                    .first?
                    .id ?? UUID()
                return HomeProgressChartPoint(
                    id: representativeID,
                    score100: averageScore,
                    createdAt: day
                )
            }
    }

    func analysisHistoryItems(limit: Int = 80) -> [AnalysisHistoryItem] {
        records
            .filter { $0.kind == .analysis }
            .sorted { $0.createdAt > $1.createdAt }
            .prefix(limit)
            .compactMap { record in
                guard let modeID = record.modeID else { return nil }
                return AnalysisHistoryItem(
                    id: record.id,
                    modeID: modeID,
                    photoID: record.photoID,
                    photoIDs: record.analysisPhotoIDs,
                    faceScanCaptureID: record.faceScanCaptureID,
                    score100: record.score100,
                    createdAt: record.createdAt
                )
            }
    }

    func recordCapture(photo: PhotoUploadResponse, scan: FaceScanCaptureResponse?) {
        let record = HomeActivityRecord(
            id: scan?.id ?? photo.id,
            kind: .capture,
            photoID: photo.id,
            photoIDs: nil,
            faceScanCaptureID: scan?.id,
            modeID: nil,
            score100: nil,
            balanceScore: nil,
            structureScore: nil,
            photoReadinessScore: nil,
            detailMetrics: nil,
            harmonyScore: nil,
            dimorphismScore: nil,
            angularityScore: nil,
            createdAt: Date()
        )
        upsert(record)
    }

    func recordAnalysisRun(_ response: AnalysisRunResponse) {
        guard let result = response.result else { return }
        let scores = HomeAnalysisScores(result: result)
        let record = HomeActivityRecord(
            id: response.id,
            kind: .analysis,
            photoID: response.photoID,
            photoIDs: response.photoIDs,
            faceScanCaptureID: response.faceScanCaptureID,
            modeID: response.modeID,
            score100: scores.overall,
            balanceScore: scores.balance,
            structureScore: scores.structure,
            photoReadinessScore: scores.photoReadiness,
            detailMetrics: scores.detailMetrics,
            harmonyScore: scores.balance,
            dimorphismScore: scores.structure,
            angularityScore: scores.photoReadiness,
            createdAt: response.createdDate ?? Date()
        )
        upsert(record)
    }

    private func upsert(_ record: HomeActivityRecord) {
        var nextRecords = records.filter { $0.id != record.id }
        nextRecords.append(record)
        nextRecords.sort { $0.createdAt > $1.createdAt }
        records = Array(nextRecords.prefix(80))
        Self.saveRecords(records)
        NotificationCenter.default.post(name: Self.didUpdateNotification, object: nil)
    }

    private static func loadRecords() -> [HomeActivityRecord] {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let records = try? JSONDecoder().decode([HomeActivityRecord].self, from: data) else {
            return []
        }
        return records.sorted { $0.createdAt > $1.createdAt }
    }

    private static func saveRecords(_ records: [HomeActivityRecord]) {
        guard let data = try? JSONEncoder().encode(records) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }

    private func bestModeKey(from analysisRecords: [HomeActivityRecord]) -> String {
        let groupedScores = Dictionary(grouping: analysisRecords) { $0.modeID ?? "" }
            .mapValues { records in records.compactMap(\.score100) }
            .filter { !$0.key.isEmpty && !$0.value.isEmpty }
        guard let bestModeID = groupedScores.max(by: { lhs, rhs in
            (lhs.value.average ?? 0) < (rhs.value.average ?? 0)
        })?.key else {
            return "progress.none"
        }

        switch bestModeID {
        case "proportions":
            return "analysis.mode.proportions"
        case "aesthetics":
            return "analysis.mode.aesthetics"
        case "glow-up-coach":
            return "analysis.mode.glowUpCoach"
        case "look-archetype":
            return "analysis.mode.lookArchetype"
        case "best-photo-selector":
            return "analysis.mode.bestPhotoSelector"
        case "best-angle-finder":
            return "analysis.mode.bestAngleFinder"
        case "dating-profile-score":
            return "analysis.mode.datingProfileScore"
        case "instagram-profile-score":
            return "analysis.mode.instagramProfileScore"
        default:
            return "progress.none"
        }
    }

    private func bestFeature(from record: HomeActivityRecord?) -> (key: String, score: Int?) {
        guard let record else { return ("progress.none", nil) }
        let candidates: [(String, Int?)] = [
            ("home.metric.balance", record.balanceScore ?? record.harmonyScore),
            ("home.metric.structure", record.structureScore ?? record.dimorphismScore),
            ("home.metric.photoReadiness", record.photoReadinessScore ?? record.angularityScore)
        ]
        guard let best = candidates
            .compactMap({ key, score in score.map { (key, $0) } })
            .max(by: { $0.1 < $1.1 }) else {
            return ("progress.none", nil)
        }
        return best
    }

    private func overviewMetrics(from analysisRecords: [HomeActivityRecord]) -> [HomeDashboardMetric] {
        [
            latestPrimaryMetric(
                id: "balance",
                titleKey: "home.metric.balance",
                iconName: "circle.hexagongrid.fill",
                tintHex: "#8EEF9E",
                in: analysisRecords
            ) { record in
                record.balanceScore ?? record.harmonyScore
            },
            latestPrimaryMetric(
                id: "structure",
                titleKey: "home.metric.structure",
                iconName: "viewfinder",
                tintHex: "#8FA8FF",
                in: analysisRecords
            ) { record in
                record.structureScore ?? record.dimorphismScore
            },
            latestPrimaryMetric(
                id: "photo-readiness",
                titleKey: "home.metric.photoReadiness",
                iconName: "camera.fill",
                tintHex: "#8EEF9E",
                in: analysisRecords
            ) { record in
                record.photoReadinessScore ?? record.angularityScore
            },
            latestDetailMetric(
                id: "symmetry",
                titleKey: "home.metric.symmetry",
                iconName: "circle.lefthalf.filled",
                matching: ["symmetry", "harmony", "mesh-symmetry", "shape-score"],
                in: analysisRecords
            ),
            latestDetailMetric(
                id: "proportions",
                titleKey: "home.metric.proportions",
                iconName: "ruler.fill",
                matching: ["proportion", "ratio", "facial-index", "face-width-height"],
                in: analysisRecords
            ) { record in
                record.modeID == "proportions" ? record.score100 : nil
            },
            latestDetailMetric(
                id: "first-impression",
                titleKey: "home.metric.firstImpression",
                iconName: "sparkles",
                matching: ["first-impression", "presence", "visual-impact", "approachability", "confidence"],
                in: analysisRecords
            )
        ]
    }

    private func latestPrimaryMetric(
        id: String,
        titleKey: String,
        iconName: String,
        tintHex: String,
        in analysisRecords: [HomeActivityRecord],
        score: (HomeActivityRecord) -> Int?
    ) -> HomeDashboardMetric {
        for record in analysisRecords {
            if let score = score(record) {
                return HomeDashboardMetric(
                    id: id,
                    titleKey: titleKey,
                    valueText: "\(score)",
                    score100: score,
                    iconName: iconName,
                    tintHex: tintHex,
                    sourceModeID: record.modeID
                )
            }
        }

        return HomeDashboardMetric(
            id: id,
            titleKey: titleKey,
            valueText: nil,
            score100: nil,
            iconName: iconName,
            tintHex: tintHex
        )
    }

    private func latestDetailMetric(
        id: String,
        titleKey: String,
        iconName: String,
        matching tokens: [String],
        in analysisRecords: [HomeActivityRecord],
        fallbackScore: ((HomeActivityRecord) -> Int?)? = nil
    ) -> HomeDashboardMetric {
        for record in analysisRecords {
            if let matchedMetric = record.detailMetrics?.first(where: { metric in
                guard metric.score100 != nil || metric.valueText != nil else { return false }
                let searchText = "\(metric.id) \(metric.titleKey)".lowercased()
                return tokens.contains { searchText.contains($0) }
            }) {
                return HomeDashboardMetric(
                    id: id,
                    titleKey: titleKey,
                    valueText: matchedMetric.score100.map(String.init) ?? matchedMetric.valueText,
                    score100: matchedMetric.score100,
                    iconName: iconName,
                    tintHex: matchedMetric.tintHex,
                    sourceModeID: record.modeID
                )
            }

            if let score = fallbackScore?(record) {
                return HomeDashboardMetric(
                    id: id,
                    titleKey: titleKey,
                    valueText: "\(score)",
                    score100: score,
                    iconName: iconName,
                    tintHex: "#8FA8FF",
                    sourceModeID: record.modeID
                )
            }
        }

        return HomeDashboardMetric(
            id: id,
            titleKey: titleKey,
            valueText: nil,
            score100: nil,
            iconName: iconName,
            tintHex: nil
        )
    }
}

private struct HomeAnalysisScores {
    let overall: Int?
    let balance: Int?
    let structure: Int?
    let photoReadiness: Int?
    let detailMetrics: [HomeDashboardMetric]

    init(result: AnalysisResultPayload) {
        let ringScores = result.rings.reduce(into: [String: Int]()) { partialResult, ring in
            partialResult[ring.metricID] = Self.score100(from: ring.score)
        }

        let metricScores = result.metrics.reduce(into: [String: Int]()) { partialResult, metric in
            if let numericValue = metric.numericValue,
               Self.isScoreLikeMetric(metric) {
                partialResult[metric.metricID] = Self.score100(from: numericValue)
            }
        }

        let ringAverage = result.rings.compactMap { Self.score100(from: $0.score) }.average
        let metricAverage = result.metrics.compactMap(\.numericValue).compactMap { Self.score100(from: $0) }.average

        overall = Self.score100(from: result.overallScore)
            ?? ringAverage
            ?? metricAverage
        balance = [
            ringScores["harmony"],
            ringScores["symmetry"],
            ringScores["proportions"],
            metricScores["symmetry"],
            metricScores["mesh-symmetry-score"],
            metricScores["facial-index"]
        ]
            .compactMap { $0 }
            .average
            ?? ringScores["symmetry"]
        structure = [
            ringScores["jawline"],
            ringScores["cheekbones"],
            ringScores["eye-area"],
            metricScores["jawline-definition"],
            metricScores["cheekbone-projection"]
        ]
            .compactMap { $0 }
            .average
        photoReadiness = [
            ringScores["presence"],
            ringScores["clarity"],
            ringScores["expression"],
            ringScores["lighting"],
            ringScores["composition"],
            ringScores["background"],
            ringScores["visual-impact"],
            ringScores["crop"],
            ringScores["feed-fit"],
            ringScores["shareability"],
            ringScores["vibe"],
            ringScores["front"],
            ringScores["left"],
            ringScores["right"],
            ringScores["high-angle"],
            ringScores["low-angle"],
            ringScores["first-impression"],
            ringScores["confidence"],
            ringScores["approachability"],
            ringScores["trust"],
            ringScores["style"],
            ringScores["conversation"],
            metricScores["best-pick-readiness"],
            metricScores["face-visibility"],
            metricScores["expression-warmth"],
            metricScores["lighting-quality"],
            metricScores["composition"],
            metricScores["background-control"],
            metricScores["front-read"],
            metricScores["left-read"],
            metricScores["right-read"],
            metricScores["main-photo-suitability"],
            metricScores["confidence-signal"],
            metricScores["trust-signal"],
            metricScores["conversation-hook"],
            metricScores["first-impression"],
            metricScores["profile-crop"],
            metricScores["feed-fit"],
            metricScores["story-thumbnail"],
            metricScores["visual-consistency"]
        ]
            .compactMap { $0 }
            .average
        detailMetrics = Self.detailMetrics(from: result, ringScores: ringScores, metricScores: metricScores)
    }

    private static func score100(from value: Double?) -> Int? {
        guard let value, value.isFinite else { return nil }
        let normalized: Double
        if value <= 1 {
            normalized = value * 100
        } else if value <= 10 {
            normalized = value * 10
        } else {
            normalized = value
        }
        return Int(normalized.rounded()).clamped(to: 0...100)
    }

    private static func isScoreLikeMetric(_ metric: AnalysisResultMetric) -> Bool {
        if metric.unit?.lowercased() == "score" {
            return true
        }

        let scoreLikeIDs: Set<String> = [
            "symmetry",
            "mesh-symmetry-score",
            "best-pick-readiness",
            "face-visibility",
            "expression-warmth",
            "lighting-quality",
            "composition",
            "background-control",
            "front-read",
            "left-read",
            "right-read",
            "main-photo-suitability",
            "approachability",
            "confidence-signal",
            "trust-signal",
            "conversation-hook",
            "profile-crop",
            "first-impression",
            "feed-fit",
            "story-thumbnail",
            "visual-consistency"
        ]
        return scoreLikeIDs.contains(metric.metricID)
    }

    private static func detailMetrics(
        from result: AnalysisResultPayload,
        ringScores: [String: Int],
        metricScores: [String: Int]
    ) -> [HomeDashboardMetric] {
        var seenIDs = Set<String>()

        let metricDetails = result.metrics
            .sorted { $0.sortOrder < $1.sortOrder }
            .compactMap { metric -> HomeDashboardMetric? in
                guard seenIDs.insert("metric-\(metric.section)-\(metric.metricID)").inserted else { return nil }
                let score = metricScores[metric.metricID]
                guard score != nil else { return nil }
                return HomeDashboardMetric(
                    id: "metric-\(metric.section)-\(metric.metricID)",
                    titleKey: metric.titleKey,
                    valueText: metric.valueText ?? metric.statusText,
                    score100: score,
                    iconName: metric.iconName,
                    tintHex: metric.valueTint
                )
            }

        let ringDetails = result.rings
            .sorted { $0.sortOrder < $1.sortOrder }
            .compactMap { ring -> HomeDashboardMetric? in
                guard seenIDs.insert("ring-\(ring.metricID)").inserted else { return nil }
                return HomeDashboardMetric(
                    id: "ring-\(ring.metricID)",
                    titleKey: ring.titleKey,
                    valueText: ring.displayValue,
                    score100: ringScores[ring.metricID],
                    iconName: iconName(for: ring.metricID),
                    tintHex: ring.tint
                )
            }

        return Array((metricDetails + ringDetails).prefix(8))
    }

    private static func iconName(for metricID: String) -> String {
        switch metricID {
        case "symmetry", "harmony", "proportions":
            return "circle.hexagongrid.fill"
        case "jawline", "cheekbones":
            return "viewfinder"
        case "eye-area", "eyebrows":
            return "eye.fill"
        case "skin":
            return "drop.fill"
        case "hair":
            return "scissors"
        case "glow", "presence", "visual-impact", "vibe":
            return "sparkles"
        case "clarity", "lighting", "composition", "crop", "feed-fit":
            return "camera.fill"
        case "confidence", "approachability", "trust", "style", "conversation", "first-impression":
            return "person.crop.circle.fill"
        default:
            return "chart.bar.fill"
        }
    }
}

private struct HomeActivityRecord: Codable, Identifiable {
    enum Kind: String, Codable {
        case capture
        case analysis
    }

    let id: UUID
    let kind: Kind
    let photoID: UUID?
    let photoIDs: [UUID]?
    let faceScanCaptureID: UUID?
    let modeID: String?
    let score100: Int?
    let balanceScore: Int?
    let structureScore: Int?
    let photoReadinessScore: Int?
    let detailMetrics: [HomeDashboardMetric]?
    let harmonyScore: Int?
    let dimorphismScore: Int?
    let angularityScore: Int?
    let createdAt: Date

    var scanIdentity: String {
        if let photoID {
            return "photo-\(photoID.uuidString)"
        }
        if let faceScanCaptureID {
            return "scan-\(faceScanCaptureID.uuidString)"
        }
        return "record-\(id.uuidString)"
    }

    var analysisPhotoIDs: [UUID] {
        let ids = photoIDs ?? []
        guard let photoID, !ids.contains(photoID) else { return ids }
        return [photoID] + ids
    }
}

private extension Array where Element == HomeActivityRecord {
    func filtered(for period: HomeStatsPeriod) -> [HomeActivityRecord] {
        guard let dayCount = period.dayCount,
              let startDate = Calendar.autoupdatingCurrent.date(byAdding: .day, value: -dayCount + 1, to: Date()) else {
            return self
        }
        return filter { $0.createdAt >= startDate }
    }

    var uniqueScanCount: Int {
        Set(map(\.scanIdentity)).count
    }

    var averageScore: Int? {
        compactMap(\.score100).average
    }

    func streakDays(calendar: Calendar) -> Int {
        let days = Set(map { calendar.startOfDay(for: $0.createdAt) })
        guard !days.isEmpty else { return 0 }

        var cursor = calendar.startOfDay(for: Date())
        if !days.contains(cursor),
           let yesterday = calendar.date(byAdding: .day, value: -1, to: cursor),
           days.contains(yesterday) {
            cursor = yesterday
        }

        var streak = 0
        while days.contains(cursor) {
            streak += 1
            guard let previousDay = calendar.date(byAdding: .day, value: -1, to: cursor) else {
                break
            }
            cursor = previousDay
        }
        return streak
    }
}

private extension Array where Element == Int {
    var average: Int? {
        guard !isEmpty else { return nil }
        return Int((Double(reduce(0, +)) / Double(count)).rounded())
    }
}

private extension Int {
    func clamped(to range: ClosedRange<Int>) -> Int {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

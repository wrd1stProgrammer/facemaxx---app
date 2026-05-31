import Foundation

final class AnalysisJSONCache: @unchecked Sendable {
    static let shared = AnalysisJSONCache()

    private let directory: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private let queue = DispatchQueue(label: "com.facemaxx.analysis-json-cache")

    private init() {
        let baseURL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        directory = baseURL.appendingPathComponent("Facemaxx/analysis-runs", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    func store(_ response: AnalysisRunResponse) {
        queue.sync {
            guard let data = try? encoder.encode(AnalysisRunCacheEnvelope(response: response)) else { return }
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try? data.write(to: url(for: response.id), options: [.atomic])
        }
    }

    func response(id: UUID) -> AnalysisRunResponse? {
        queue.sync {
            guard let data = try? Data(contentsOf: url(for: id)),
                  let envelope = try? decoder.decode(AnalysisRunCacheEnvelope.self, from: data) else {
                return nil
            }
            return envelope.response
        }
    }

    func clear() {
        queue.sync {
            try? FileManager.default.removeItem(at: directory)
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        }
    }

    private func url(for id: UUID) -> URL {
        directory.appendingPathComponent("\(id.uuidString).json")
    }
}

private struct AnalysisRunCacheEnvelope: Codable {
    let cachedAt: Date
    let response: AnalysisRunResponse

    init(response: AnalysisRunResponse) {
        self.cachedAt = Date()
        self.response = response
    }
}

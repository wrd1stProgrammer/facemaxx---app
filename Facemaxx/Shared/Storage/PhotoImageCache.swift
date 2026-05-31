import Foundation
import UIKit

final class PhotoImageCache: @unchecked Sendable {
    static let shared = PhotoImageCache()

    private let directory: URL
    private let queue = DispatchQueue(label: "com.facemaxx.photo-image-cache")

    private init() {
        let baseURL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        directory = baseURL.appendingPathComponent("Facemaxx/photos", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    func image(id: UUID) -> UIImage? {
        queue.sync {
            guard let data = try? Data(contentsOf: url(for: id)) else { return nil }
            return UIImage(data: data)
        }
    }

    func store(_ image: UIImage, id: UUID) {
        guard let data = image.jpegData(compressionQuality: 0.92) else { return }
        store(data, id: id)
    }

    func store(_ data: Data, id: UUID) {
        queue.sync {
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try? data.write(to: url(for: id), options: [.atomic])
        }
    }

    func clear() {
        queue.sync {
            try? FileManager.default.removeItem(at: directory)
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        }
    }

    private func url(for id: UUID) -> URL {
        directory.appendingPathComponent("\(id.uuidString).jpg")
    }
}

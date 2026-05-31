import Foundation
import UIKit

final class FacemaxxAPIClient: @unchecked Sendable {
    static let shared = FacemaxxAPIClient()

    private let baseURL: URL
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(
        baseURL: URL = FacemaxxAPIClient.defaultBaseURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func saveCameraCapture(_ result: FaceCameraCaptureResult) async throws -> SavedFaceCaptureResponse {
        let photo = try await uploadPhoto(result.image)
        print("Facemaxx API photo upload saved: \(photo.id)")

        guard var scanPayload = result.scanPayload else {
            print("Facemaxx API skipped face scan save: no geometry payload was captured.")
            return SavedFaceCaptureResponse(photo: photo, scan: nil)
        }

        scanPayload.photoId = photo.id
        let response = try await createFaceScan(scanPayload)
        print("Facemaxx API face scan saved: \(response.id), metrics: \(response.metrics.count)")
        return SavedFaceCaptureResponse(photo: photo, scan: response)
    }

    func uploadPhoto(_ image: UIImage) async throws -> PhotoUploadResponse {
        guard AIAnalysisConsentStore.isGranted else {
            throw FacemaxxAPIError.missingAIAnalysisConsent
        }

        let uploadImage = try PhotoUploadImage(image: image)

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: endpoint("v1/photos/upload"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        await applyIdentityHeaders(to: &request)

        request.httpBody = MultipartFormData(boundary: boundary)
            .addField(name: "width", value: String(uploadImage.width))
            .addField(name: "height", value: String(uploadImage.height))
            .addFile(
                name: "file",
                filename: "facemaxx-face-scan.jpg",
                mimeType: "image/jpeg",
                data: uploadImage.data
            )
            .data

        let data = try await validatedResponseData(for: request)
        let photo = try decoder.decode(PhotoUploadResponse.self, from: data)
        PhotoImageCache.shared.store(uploadImage.data, id: photo.id)
        return photo
    }

    func createFaceScan(_ payload: FaceScanCapturePayload) async throws -> FaceScanCaptureResponse {
        guard AIAnalysisConsentStore.isGranted else {
            throw FacemaxxAPIError.missingAIAnalysisConsent
        }

        var request = URLRequest(url: endpoint("v1/face-scans"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        await applyIdentityHeaders(to: &request)
        request.httpBody = try encoder.encode(payload)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(FaceScanCaptureResponse.self, from: data)
    }

    func createAnalysisRun(_ payload: CreateAnalysisRunPayload) async throws -> AnalysisRunResponse {
        guard AIAnalysisConsentStore.isGranted else {
            throw FacemaxxAPIError.missingAIAnalysisConsent
        }

        var request = URLRequest(url: endpoint("v1/analysis-runs"))
        request.httpMethod = "POST"
        request.timeoutInterval = 600
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        await applyIdentityHeaders(to: &request)
        request.httpBody = try encoder.encode(payload)

        let data = try await validatedResponseData(for: request)
        let response = try decoder.decode(AnalysisRunResponse.self, from: data)
        AnalysisJSONCache.shared.store(response)
        return response
    }

    func fetchProScanStatus() async throws -> ProScanStatusResponse {
        var request = URLRequest(url: endpoint("v1/pro-scans/status"))
        request.httpMethod = "GET"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(ProScanStatusResponse.self, from: data)
    }

    func syncProScanStatus() async throws -> ProScanStatusResponse {
        var request = URLRequest(url: endpoint("v1/pro-scans/sync"))
        request.httpMethod = "POST"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(ProScanStatusResponse.self, from: data)
    }

    func redeemReviewerProScanCode(_ code: String) async throws -> ReviewerProScanGrantResponse {
        var request = URLRequest(url: endpoint("v1/pro-scans/reviewer-grant"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        await applyIdentityHeaders(to: &request)
        request.httpBody = try encoder.encode(ReviewerProScanGrantRequest(code: code))

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(ReviewerProScanGrantResponse.self, from: data)
    }

    func saveOnboardingPreferences(_ preferences: OnboardingPreferences) async throws -> OnboardingPreferencesRemoteResponse {
        var request = URLRequest(url: endpoint("v1/onboarding/preferences"))
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        await applyIdentityHeaders(to: &request)
        request.httpBody = try encoder.encode(preferences.remotePayload)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(OnboardingPreferencesRemoteResponse.self, from: data)
    }

    func fetchOnboardingPreferences() async throws -> OnboardingPreferencesRemoteResponse {
        var request = URLRequest(url: endpoint("v1/onboarding/preferences"))
        request.httpMethod = "GET"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode(OnboardingPreferencesRemoteResponse.self, from: data)
    }

    func listAnalysisRuns(limit: Int = 60) async throws -> [AnalysisHistoryItemResponse] {
        var components = URLComponents(url: endpoint("v1/analysis-runs"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "limit", value: String(limit))
        ]
        guard let url = components?.url else {
            throw FacemaxxAPIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        return try decoder.decode([AnalysisHistoryItemResponse].self, from: data)
    }

    func getAnalysisRun(_ id: UUID) async throws -> AnalysisRunResponse {
        if let cached = AnalysisJSONCache.shared.response(id: id) {
            return cached
        }

        var request = URLRequest(url: endpoint("v1/analysis-runs/\(id.uuidString)"))
        request.httpMethod = "GET"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        let response = try decoder.decode(AnalysisRunResponse.self, from: data)
        AnalysisJSONCache.shared.store(response)
        return response
    }

    func deleteAccount() async throws {
        var request = URLRequest(url: endpoint("v1/account"))
        request.httpMethod = "DELETE"
        await applyIdentityHeaders(to: &request)
        _ = try await validatedResponseData(for: request)
    }

    func fetchPhotoImage(id: UUID) async throws -> UIImage {
        if let cached = PhotoImageCache.shared.image(id: id) {
            return cached
        }

        var request = URLRequest(url: endpoint("v1/photos/\(id.uuidString)/image"))
        request.httpMethod = "GET"
        await applyIdentityHeaders(to: &request)

        let data = try await validatedResponseData(for: request)
        guard let image = UIImage(data: data) else {
            throw FacemaxxAPIError.invalidResponse
        }
        PhotoImageCache.shared.store(data, id: id)
        return image
    }

    private func endpoint(_ path: String) -> URL {
        baseURL.appendingPathComponent(path)
    }

    @discardableResult
    private func applyIdentityHeaders(to request: inout URLRequest, forceRefresh: Bool = false) async -> Bool {
        request.setValue(FacemaxxInstallIdentity.currentID.uuidString, forHTTPHeaderField: "X-Facemaxx-Install-Id")
        if AppReviewDemoMode.isEnabled {
            request.setValue(AppReviewDemoMode.demoHeaderValue, forHTTPHeaderField: "X-Facemaxx-Reviewer-Demo")
            request.setValue(AppReviewDemoMode.accessCode, forHTTPHeaderField: "X-Facemaxx-Reviewer-Code")
        } else {
            request.setValue(nil, forHTTPHeaderField: "X-Facemaxx-Reviewer-Demo")
            request.setValue(nil, forHTTPHeaderField: "X-Facemaxx-Reviewer-Code")
        }

        if let accessToken = await FacemaxxAuthService.shared.validAccessToken(forceRefresh: forceRefresh) {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
            return true
        }
        request.setValue(nil, forHTTPHeaderField: "Authorization")
        return false
    }

    private func validatedResponseData(for request: URLRequest) async throws -> Data {
        if let url = request.url {
            print("Facemaxx API request: \(request.httpMethod ?? "GET") \(url.absoluteString)")
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let error as URLError where error.code == .timedOut {
            throw FacemaxxAPIError.timeout
        } catch {
            throw FacemaxxAPIError.network(error.localizedDescription)
        }
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FacemaxxAPIError.invalidResponse
        }

        if httpResponse.statusCode == 401,
           request.value(forHTTPHeaderField: "Authorization") != nil {
            var retryRequest = request
            let hasRefreshedToken = await applyIdentityHeaders(to: &retryRequest, forceRefresh: true)
            if hasRefreshedToken,
               retryRequest.value(forHTTPHeaderField: "Authorization") != request.value(forHTTPHeaderField: "Authorization") {
                print("Facemaxx API retry after auth refresh: \(retryRequest.httpMethod ?? "GET") \(retryRequest.url?.absoluteString ?? "")")
                let retryData: Data
                let retryResponse: URLResponse
                do {
                    (retryData, retryResponse) = try await session.data(for: retryRequest)
                } catch let error as URLError where error.code == .timedOut {
                    throw FacemaxxAPIError.timeout
                } catch {
                    throw FacemaxxAPIError.network(error.localizedDescription)
                }
                guard let retryHTTPResponse = retryResponse as? HTTPURLResponse else {
                    throw FacemaxxAPIError.invalidResponse
                }

                guard (200..<300).contains(retryHTTPResponse.statusCode) else {
                    let body = String(data: retryData, encoding: .utf8)
                    throw FacemaxxAPIError.server(statusCode: retryHTTPResponse.statusCode, body: body)
                }

                return retryData
            }
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8)
            throw FacemaxxAPIError.server(statusCode: httpResponse.statusCode, body: body)
        }

        return data
    }

    private static var defaultBaseURL: URL {
        if let value = Bundle.main.object(forInfoDictionaryKey: "FacemaxxAPIBaseURL") as? String,
           let url = URL(string: value),
           !value.contains("$(") {
            return url
        }

        return URL(string: "https://facemaxx.nostalgia-drive.com")!
    }
}

enum FacemaxxAPIError: LocalizedError {
    case missingAIAnalysisConsent
    case imageEncodingFailed
    case invalidResponse
    case timeout
    case network(String)
    case server(statusCode: Int, body: String?)

    var errorDescription: String? {
        switch self {
        case .missingAIAnalysisConsent:
            String(localized: "privacy.aiConsent.error.required")
        case .imageEncodingFailed:
            "Failed to encode the captured image."
        case .invalidResponse:
            "The server returned an invalid response."
        case .timeout:
            String(localized: "network.error.timeout")
        case let .network(message):
            String(format: String(localized: "network.error.messageFormat"), message)
        case let .server(statusCode, body):
            "Server error \(statusCode): \(body ?? "No response body")"
        }
    }
}

private struct PhotoUploadImage {
    private static let maxPixelDimension: CGFloat = 1600
    private static let compressionQuality: CGFloat = 0.84

    let data: Data
    let width: Int
    let height: Int

    init(image: UIImage) throws {
        let preparedImage = image.facemaxxPreparedForUpload(maxPixelDimension: Self.maxPixelDimension)
        guard let data = preparedImage.jpegData(compressionQuality: Self.compressionQuality) else {
            throw FacemaxxAPIError.imageEncodingFailed
        }

        self.data = data
        if let cgImage = preparedImage.cgImage {
            self.width = cgImage.width
            self.height = cgImage.height
        } else {
            self.width = Int(preparedImage.size.width * preparedImage.scale)
            self.height = Int(preparedImage.size.height * preparedImage.scale)
        }
    }
}

private extension UIImage {
    func facemaxxPreparedForUpload(maxPixelDimension: CGFloat) -> UIImage {
        let pixelSize = CGSize(width: size.width * scale, height: size.height * scale)
        let longestSide = max(pixelSize.width, pixelSize.height)
        let resizeScale = longestSide > maxPixelDimension ? maxPixelDimension / longestSide : 1
        let targetSize = CGSize(
            width: max(1, (pixelSize.width * resizeScale).rounded()),
            height: max(1, (pixelSize.height * resizeScale).rounded())
        )

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true

        return UIGraphicsImageRenderer(size: targetSize, format: format).image { _ in
            UIColor.black.setFill()
            UIRectFill(CGRect(origin: .zero, size: targetSize))
            draw(in: CGRect(origin: .zero, size: targetSize))
        }
    }
}

enum FacemaxxInstallIdentity {
    private static let storageKey = "facemaxx.install.id"

    static var currentID: UUID {
        let defaults = UserDefaults.standard
        if let rawValue = defaults.string(forKey: storageKey),
           let id = UUID(uuidString: rawValue) {
            return id
        }

        let id = UUID()
        defaults.set(id.uuidString, forKey: storageKey)
        return id
    }
}

private struct MultipartFormData {
    private let boundary: String
    private(set) var data = Data()

    init(boundary: String) {
        self.boundary = boundary
    }

    func addField(name: String, value: String) -> MultipartFormData {
        var copy = self
        copy.data.appendString("--\(boundary)\r\n")
        copy.data.appendString("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        copy.data.appendString("\(value)\r\n")
        return copy
    }

    func addFile(name: String, filename: String, mimeType: String, data fileData: Data) -> MultipartFormData {
        var copy = self
        copy.data.appendString("--\(boundary)\r\n")
        copy.data.appendString("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        copy.data.appendString("Content-Type: \(mimeType)\r\n\r\n")
        copy.data.append(fileData)
        copy.data.appendString("\r\n--\(boundary)--\r\n")
        return copy
    }
}

private extension Data {
    mutating func appendString(_ string: String) {
        append(Data(string.utf8))
    }
}

import Foundation
import UIKit

struct FaceCameraCaptureResult {
    let image: UIImage
    let scanOverlayImage: UIImage?
    let scanPayload: FaceScanCapturePayload?

    init(
        image: UIImage,
        scanOverlayImage: UIImage?,
        scanPayload: FaceScanCapturePayload?
    ) {
        self.image = image
        self.scanOverlayImage = scanOverlayImage
        self.scanPayload = scanPayload
    }
}

struct FaceScanCapturePayload: Encodable {
    var photoId: UUID?
    var source = "camera"
    var captureBackend: String
    var deviceModel: String?
    var osVersion: String?
    var appVersion: String?
    var imageWidth: Int?
    var imageHeight: Int?
    var isFrontCamera = true
    var isMirrored = true
    var trackingState: String?
    var metadata: [String: String]
    var geometry: FaceGeometrySubmissionPayload

    enum CodingKeys: String, CodingKey {
        case photoId = "photo_id"
        case source
        case captureBackend = "capture_backend"
        case deviceModel = "device_model"
        case osVersion = "os_version"
        case appVersion = "app_version"
        case imageWidth = "image_width"
        case imageHeight = "image_height"
        case isFrontCamera = "is_front_camera"
        case isMirrored = "is_mirrored"
        case trackingState = "tracking_state"
        case metadata
        case geometry
    }
}

struct FaceGeometrySubmissionPayload: Encodable {
    var provider: String
    var coordinateSpace: String
    var vertices: [[Double]]
    var triangleIndices: [Int]
    var blendShapes: [String: Double]
    var faceTransform: [Double]?
    var cameraTransform: [Double]?
    var cameraIntrinsics: [Double]?
    var landmarks2D: [String: [[Double]]]?
    var quality: [String: Double]

    enum CodingKeys: String, CodingKey {
        case provider
        case coordinateSpace = "coordinate_space"
        case vertices
        case triangleIndices = "triangle_indices"
        case blendShapes = "blend_shapes"
        case faceTransform = "face_transform"
        case cameraTransform = "camera_transform"
        case cameraIntrinsics = "camera_intrinsics"
        case landmarks2D = "landmarks_2d"
        case quality
    }
}

enum FaceScanPayloadBuilder {
    @MainActor
    static func payload(
        for image: UIImage,
        source: String,
        isFrontCamera: Bool,
        basePayload: FaceScanCapturePayload?,
        preferredRegion: CGRect? = nil
    ) -> FaceScanCapturePayload? {
        let landmarks = FaceResultScanOverlay.detectLandmarks(from: image)
        let pixelWidth = Int(image.size.width * image.scale)
        let pixelHeight = Int(image.size.height * image.scale)

        if var payload = basePayload {
            payload.source = source
            payload.imageWidth = pixelWidth
            payload.imageHeight = pixelHeight
            payload.isMirrored = false
            payload.metadata["selection"] = "square_region"
            payload.metadata["selection_source"] = source
            if let preferredRegion {
                payload.metadata["preferred_region"] = metadataValue(for: preferredRegion)
            }
            if let landmarks {
                payload.geometry.landmarks2D = landmarks
                payload.geometry.quality["landmarkRegionCount"] = Double(landmarks.count)
                payload.geometry.quality["preferredRegion"] = preferredRegion == nil ? 0 : 1
            }
            return payload
        }

        guard let landmarks else { return nil }
        return FaceScanCapturePayload(
            source: source,
            captureBackend: "vision_landmarks",
            deviceModel: UIDevice.current.model,
            osVersion: "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)",
            appVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String,
            imageWidth: pixelWidth,
            imageHeight: pixelHeight,
            isFrontCamera: isFrontCamera,
            isMirrored: false,
            trackingState: "vision_face_detected",
            metadata: [
                "capture_mode": source == "upload" ? "photo_library_vision_selected_region" : "camera_vision_selected_region",
                "client": "ios",
                "selection": "square_region",
                "preferred_region": preferredRegion.map(metadataValue(for:)) ?? ""
            ].filter { !$0.value.isEmpty },
            geometry: FaceGeometrySubmissionPayload(
                provider: "vision_landmarks",
                coordinateSpace: "vision_normalized_2d",
                vertices: [],
                triangleIndices: [],
                blendShapes: [:],
                faceTransform: nil,
                cameraTransform: nil,
                cameraIntrinsics: nil,
                landmarks2D: landmarks,
                quality: [
                    "landmarkRegionCount": Double(landmarks.count),
                    "preferredRegion": preferredRegion == nil ? 0 : 1
                ]
            )
        )
    }

    private static func metadataValue(for rect: CGRect) -> String {
        [
            rect.minX,
            rect.minY,
            rect.width,
            rect.height
        ]
        .map { String(format: "%.5f", Double($0)) }
        .joined(separator: ",")
    }
}

struct PhotoUploadResponse: Decodable {
    let id: UUID
    let storageBucket: String
    let storagePath: String
    let mimeType: String?
    let width: Int?
    let height: Int?
    let sha256: String?

    enum CodingKeys: String, CodingKey {
        case id
        case storageBucket = "storage_bucket"
        case storagePath = "storage_path"
        case mimeType = "mime_type"
        case width
        case height
        case sha256
    }
}

struct FaceScanCaptureResponse: Decodable {
    let id: UUID
    let photoId: UUID?
    let geometrySaved: Bool
    let metrics: [FaceMetricMeasurementResponse]

    enum CodingKeys: String, CodingKey {
        case id
        case photoId = "photo_id"
        case geometrySaved = "geometry_saved"
        case metrics
    }
}

struct FaceMetricMeasurementResponse: Decodable {
    let metricGroup: String
    let metricId: String
    let numericValue: Double?
    let unit: String?
    let displayValue: String?
    let interpretationLabelEn: String?
    let interpretationLabelKo: String?

    enum CodingKeys: String, CodingKey {
        case metricGroup = "metric_group"
        case metricId = "metric_id"
        case numericValue = "numeric_value"
        case unit
        case displayValue = "display_value"
        case interpretationLabelEn = "interpretation_label_en"
        case interpretationLabelKo = "interpretation_label_ko"
    }
}

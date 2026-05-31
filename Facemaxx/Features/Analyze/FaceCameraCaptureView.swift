import SwiftUI
import UIKit
import CoreImage
import Metal
import SceneKit
import simd
@preconcurrency import AVFoundation
@preconcurrency import ARKit
@preconcurrency import Vision

struct FaceCameraCaptureView: UIViewControllerRepresentable {
    let onPhotoCaptured: (FaceCameraCaptureResult) -> Void
    let onCancel: () -> Void

    func makeUIViewController(context: Context) -> FaceCameraViewController {
        let controller = FaceCameraViewController()
        controller.onPhotoCaptured = onPhotoCaptured
        controller.onCancel = onCancel
        return controller
    }

    func updateUIViewController(_ uiViewController: FaceCameraViewController, context: Context) {
        uiViewController.onPhotoCaptured = onPhotoCaptured
        uiViewController.onCancel = onCancel
    }

    static func dismantleUIViewController(_ uiViewController: FaceCameraViewController, coordinator: ()) {
        uiViewController.stopCamera()
    }
}

final class FaceCameraViewController: UIViewController, @unchecked Sendable {
    private static let ciContext = CIContext()

    var onPhotoCaptured: ((FaceCameraCaptureResult) -> Void)?
    var onCancel: (() -> Void)?

    nonisolated(unsafe) private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "com.facemaxx.camera.session")
    private let visionQueue = DispatchQueue(label: "com.facemaxx.camera.vision")
    nonisolated(unsafe) private let videoOutput = AVCaptureVideoDataOutput()
    nonisolated(unsafe) private let photoOutput = AVCapturePhotoOutput()

    private var arSceneView: ARSCNView?
    private var isUsingARFaceTracking = false
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let overlayView = FaceCameraOverlayView()
    private let chromeView = FaceCameraChromeView()

    nonisolated(unsafe) private var isSessionConfigured = false
    nonisolated(unsafe) private var isSessionStarting = false
    nonisolated(unsafe) private var lastVisionTime = 0.0
    nonisolated(unsafe) private var visionOrientation: CGImagePropertyOrientation = .leftMirrored
    nonisolated(unsafe) private var photoDelegates: [UUID: FaceCameraPhotoDelegate] = [:]
    nonisolated(unsafe) private var latestGeometryPayload: FaceGeometrySubmissionPayload?
    nonisolated(unsafe) private var latestTrackingState: String?

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        if Self.canUseARFaceTracking {
            setUpARFacePreview()
        } else {
            setUpCameraPreview()
        }
        setUpOverlay()
        setUpChrome()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        arSceneView?.frame = view.bounds
        previewLayer?.frame = view.bounds
        configurePreviewConnection()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        requestCameraAccessThenStart()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        stopCamera()
    }

    func stopCamera() {
        if isUsingARFaceTracking {
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.arSceneView?.session.pause()
                self.chromeView.setFaceDetected(false)
            }
            return
        }

        sessionQueue.async { [weak self] in
            guard let self else { return }
            self.videoOutput.setSampleBufferDelegate(nil, queue: nil)
            if self.session.isRunning {
                self.session.stopRunning()
            }
            self.isSessionStarting = false
        }

        DispatchQueue.main.async { [weak self] in
            self?.overlayView.update(with: .empty)
            self?.chromeView.setFaceDetected(false)
        }
    }

    private func setUpARFacePreview() {
        let sceneView = ARSCNView(frame: view.bounds)
        sceneView.translatesAutoresizingMaskIntoConstraints = false
        sceneView.backgroundColor = .black
        sceneView.scene = SCNScene()
        sceneView.delegate = self
        sceneView.isUserInteractionEnabled = false
        sceneView.automaticallyUpdatesLighting = false
        sceneView.rendersContinuously = true
        view.addSubview(sceneView)

        NSLayoutConstraint.activate([
            sceneView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            sceneView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            sceneView.topAnchor.constraint(equalTo: view.topAnchor),
            sceneView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        arSceneView = sceneView
        isUsingARFaceTracking = true
    }

    private func setUpCameraPreview() {
        let previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        previewLayer.frame = view.bounds
        view.layer.addSublayer(previewLayer)
        self.previewLayer = previewLayer
    }

    private func setUpOverlay() {
        overlayView.translatesAutoresizingMaskIntoConstraints = false
        overlayView.backgroundColor = .clear
        overlayView.isUserInteractionEnabled = false
        overlayView.isHidden = isUsingARFaceTracking
        view.addSubview(overlayView)

        NSLayoutConstraint.activate([
            overlayView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            overlayView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            overlayView.topAnchor.constraint(equalTo: view.topAnchor),
            overlayView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
    }

    private func setUpChrome() {
        chromeView.translatesAutoresizingMaskIntoConstraints = false
        chromeView.onClose = { [weak self] in
            guard let self else { return }
            self.stopCamera()
            self.onCancel?()
        }
        chromeView.onCapture = { [weak self] in
            self?.capturePhoto()
        }
        view.addSubview(chromeView)

        NSLayoutConstraint.activate([
            chromeView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            chromeView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            chromeView.topAnchor.constraint(equalTo: view.topAnchor),
            chromeView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
    }

    private func requestCameraAccessThenStart() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            startCameraBackend()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self else { return }
                    if granted {
                        self.startCameraBackend()
                    } else {
                        self.presentCameraError(String(localized: "analysis.camera.permissionMessage"))
                    }
                }
            }
        default:
            presentCameraError(String(localized: "analysis.camera.permissionMessage"))
        }
    }

    private func startCameraBackend() {
        if isUsingARFaceTracking {
            startARFaceSession()
        } else {
            configureAndStartSession()
        }
    }

    private func startARFaceSession() {
        guard ARFaceTrackingConfiguration.isSupported else {
            isUsingARFaceTracking = false
            arSceneView?.removeFromSuperview()
            arSceneView = nil
            setUpCameraPreview()
            overlayView.isHidden = false
            view.bringSubviewToFront(overlayView)
            view.bringSubviewToFront(chromeView)
            configureAndStartSession()
            return
        }

        let configuration = ARFaceTrackingConfiguration()
        configuration.isLightEstimationEnabled = true
        arSceneView?.session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
    }

    private func configureAndStartSession() {
        sessionQueue.async { [weak self] in
            guard let self else { return }
            guard !self.isSessionStarting else { return }
            self.isSessionStarting = true

            do {
                if !self.isSessionConfigured {
                    try self.configureSession()
                    self.isSessionConfigured = true
                }

                self.videoOutput.setSampleBufferDelegate(self, queue: self.visionQueue)
                Self.configure(connection: self.videoOutput.connection(with: .video))
                Self.configure(connection: self.photoOutput.connection(with: .video))

                if !self.session.isRunning {
                    self.session.startRunning()
                }

                DispatchQueue.main.async { [weak self] in
                    self?.configurePreviewConnection()
                }
                self.isSessionStarting = false
            } catch {
                self.isSessionStarting = false
                DispatchQueue.main.async { [weak self] in
                    self?.presentCameraError(error.localizedDescription)
                }
            }
        }
    }

    nonisolated private func configureSession() throws {
        session.beginConfiguration()
        defer { session.commitConfiguration() }

        session.sessionPreset = .high

        guard let camera = Self.frontCamera() else {
            throw FaceCameraError.frontCameraUnavailable
        }

        let cameraInput = try AVCaptureDeviceInput(device: camera)
        guard session.canAddInput(cameraInput) else {
            throw FaceCameraError.frontCameraUnavailable
        }
        session.addInput(cameraInput)

        videoOutput.alwaysDiscardsLateVideoFrames = true
        if videoOutput.availableVideoPixelFormatTypes.contains(kCVPixelFormatType_420YpCbCr8BiPlanarFullRange) {
            videoOutput.videoSettings = [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange
            ]
        }
        videoOutput.setSampleBufferDelegate(self, queue: visionQueue)

        guard session.canAddOutput(videoOutput) else {
            throw FaceCameraError.frontCameraUnavailable
        }
        session.addOutput(videoOutput)

        guard session.canAddOutput(photoOutput) else {
            throw FaceCameraError.frontCameraUnavailable
        }
        session.addOutput(photoOutput)
    }

    private func configurePreviewConnection() {
        Self.configure(connection: previewLayer?.connection)
    }

    nonisolated private static func configure(connection: AVCaptureConnection?) {
        guard let connection else { return }

        if connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }

        if connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = true
        }
    }

    nonisolated private static func configurePhoto(connection: AVCaptureConnection?) {
        guard let connection else { return }

        if connection.isVideoRotationAngleSupported(90) {
            connection.videoRotationAngle = 90
        }

        if connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = false
        }
    }

    nonisolated private static func frontCamera() -> AVCaptureDevice? {
        AVCaptureDevice.default(.builtInTrueDepthCamera, for: .video, position: .front)
        ?? AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front)
    }

    private static var canUseARFaceTracking: Bool {
        ARFaceTrackingConfiguration.isSupported
    }

    private func capturePhoto() {
        if isUsingARFaceTracking, let arSceneView {
            chromeView.setCaptureEnabled(false)
            let displayImages = currentARDisplayImages(from: arSceneView)
            let image = displayImages.cleanImage ?? currentARCameraImage() ?? displayImages.scanOverlayImage
            let scanOverlayImage = displayImages.scanOverlayImage
            chromeView.setCaptureEnabled(true)
            let result = makeCaptureResult(from: image, scanOverlayImage: scanOverlayImage)
            stopCamera()
            onPhotoCaptured?(result)
            return
        }

        chromeView.setCaptureEnabled(false)

        sessionQueue.async { [weak self] in
            guard let self else { return }
            guard self.session.isRunning else {
                DispatchQueue.main.async { [weak self] in
                    self?.chromeView.setCaptureEnabled(true)
                    self?.presentCameraError(String(localized: "analysis.camera.processingFailedMessage"))
                }
                return
            }

            Self.configurePhoto(connection: self.photoOutput.connection(with: .video))

            let delegateID = UUID()
            let delegate = FaceCameraPhotoDelegate { [weak self] image in
                guard let self else { return }

                self.sessionQueue.async {
                    self.photoDelegates[delegateID] = nil
                }

                DispatchQueue.main.async {
                    self.chromeView.setCaptureEnabled(true)
                    guard let image else {
                        self.presentCameraError(String(localized: "analysis.camera.processingFailedMessage"))
                        return
                    }
                    let uprightImage = image.fxm_upright()
                    let result = self.makeCaptureResult(from: uprightImage, scanOverlayImage: nil)
                    self.stopCamera()
                    self.onPhotoCaptured?(result)
                }
            }

            self.photoDelegates[delegateID] = delegate
            self.photoOutput.capturePhoto(with: AVCapturePhotoSettings(), delegate: delegate)
        }
    }

    private func currentARCameraImage() -> UIImage? {
        guard let pixelBuffer = arSceneView?.session.currentFrame?.capturedImage else {
            return nil
        }

        let ciImage = CIImage(cvPixelBuffer: pixelBuffer).oriented(.right)
        guard let cgImage = Self.ciContext.createCGImage(ciImage, from: ciImage.extent) else {
            return nil
        }

        return UIImage(cgImage: cgImage, scale: UIScreen.main.scale, orientation: .up)
    }

    private func currentARDisplayImages(from sceneView: ARSCNView) -> (cleanImage: UIImage?, scanOverlayImage: UIImage) {
        let scanOverlayImage = sceneView.snapshot().fxm_upright()
        let rootNodes = sceneView.scene.rootNode.childNodes
        let previousHiddenStates = rootNodes.map { ($0, $0.isHidden) }

        rootNodes.forEach { $0.isHidden = true }
        let cleanImage = sceneView.snapshot().fxm_upright()
        previousHiddenStates.forEach { node, isHidden in
            node.isHidden = isHidden
        }

        return (cleanImage, scanOverlayImage)
    }

    private func presentCameraError(_ message: String) {
        guard presentedViewController == nil else { return }

        let alert = UIAlertController(
            title: String(localized: "analysis.camera.errorTitle"),
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: String(localized: "analysis.camera.close"), style: .default) { [weak self] _ in
            self?.onCancel?()
        })
        present(alert, animated: true)
    }

    private func makeCaptureResult(from image: UIImage, scanOverlayImage: UIImage?) -> FaceCameraCaptureResult {
        var geometry = latestGeometryPayload
        let landmarks2D = Self.visionLandmarks2D(from: image)

        if var existingGeometry = geometry {
            existingGeometry.landmarks2D = existingGeometry.landmarks2D ?? landmarks2D
            existingGeometry.quality["landmarkRegionCount"] = Double(landmarks2D?.count ?? 0)
            geometry = existingGeometry
        } else if let landmarks2D {
            geometry = FaceGeometrySubmissionPayload(
                provider: "vision_landmarks",
                coordinateSpace: "vision_normalized_2d",
                vertices: [],
                triangleIndices: [],
                blendShapes: [:],
                faceTransform: nil,
                cameraTransform: nil,
                cameraIntrinsics: nil,
                landmarks2D: landmarks2D,
                quality: [
                    "landmarkRegionCount": Double(landmarks2D.count)
                ]
            )
        }

        guard let geometry else {
            return FaceCameraCaptureResult(image: image, scanOverlayImage: scanOverlayImage, scanPayload: nil)
        }

        let scale = image.scale
        let payload = FaceScanCapturePayload(
            captureBackend: geometry.provider,
            deviceModel: UIDevice.current.model,
            osVersion: "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)",
            appVersion: Self.appVersionString,
            imageWidth: Int(image.size.width * scale),
            imageHeight: Int(image.size.height * scale),
            isFrontCamera: true,
            isMirrored: false,
            trackingState: latestTrackingState,
            metadata: [
                "capture_mode": isUsingARFaceTracking ? "arkit_true_depth" : "avfoundation_vision",
                "client": "ios"
            ],
            geometry: geometry
        )

        return FaceCameraCaptureResult(image: image, scanOverlayImage: scanOverlayImage, scanPayload: payload)
    }

    nonisolated private func processVisionFrame(_ sampleBuffer: CMSampleBuffer) {
        let now = CACurrentMediaTime()
        guard now - lastVisionTime > 1.0 / 15.0 else { return }
        lastVisionTime = now

        var payload = Self.visionPayload(from: sampleBuffer, orientation: visionOrientation)
        if payload == nil {
            let fallbackOrientations: [CGImagePropertyOrientation] = [
                .leftMirrored,
                .rightMirrored,
                .upMirrored,
                .left,
                .right,
                .up
            ].filter { $0 != visionOrientation }

            for orientation in fallbackOrientations {
                if let fallbackPayload = Self.visionPayload(from: sampleBuffer, orientation: orientation) {
                    visionOrientation = orientation
                    payload = fallbackPayload
                    break
                }
            }
        }

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            if let payload {
                let screenState = self.screenOverlayState(from: payload)
                self.latestGeometryPayload = Self.visionGeometryPayload(from: payload)
                self.latestTrackingState = "vision_face_detected"
                self.chromeView.setFaceDetected(true)
                self.overlayView.update(with: screenState)
            } else {
                self.latestGeometryPayload = nil
                self.latestTrackingState = "no_face"
                self.chromeView.setFaceDetected(false)
                self.overlayView.update(with: .empty)
            }
        }
    }

    private func screenOverlayState(from payload: VisionFaceOverlayPayload) -> FaceCameraOverlayState {
        guard let previewLayer else {
            return FaceCameraOverlayState(
                isFaceDetected: true,
                faceRect: payload.faceBox.rect(in: view.bounds.size),
                faceOutlinePoints: payload.faceOutlinePoints.map { $0.point(in: view.bounds.size) },
                landmarkPoints: payload.points.map { $0.point(in: view.bounds.size) },
                meshSegments: payload.segments.map {
                    FaceCameraSegment(
                        start: $0.start.point(in: view.bounds.size),
                        end: $0.end.point(in: view.bounds.size)
                    )
                }
            )
        }

        let faceRect = previewLayer.layerRectConverted(fromMetadataOutputRect: payload.faceBox)
        let outlinePoints = payload.faceOutlinePoints.map { previewLayer.layerPoint(fromMetadataPoint: $0) }
        let landmarkPoints = payload.points.map { previewLayer.layerPoint(fromMetadataPoint: $0) }
        let meshSegments = payload.segments.map {
            FaceCameraSegment(
                start: previewLayer.layerPoint(fromMetadataPoint: $0.start),
                end: previewLayer.layerPoint(fromMetadataPoint: $0.end)
            )
        }

        return FaceCameraOverlayState(
            isFaceDetected: true,
            faceRect: faceRect,
            faceOutlinePoints: outlinePoints,
            landmarkPoints: landmarkPoints,
            meshSegments: meshSegments
        )
    }

    nonisolated private static func visionPayload(
        from sampleBuffer: CMSampleBuffer,
        orientation: CGImagePropertyOrientation
    ) -> VisionFaceOverlayPayload? {
        let request = VNDetectFaceLandmarksRequest()
        let handler = VNImageRequestHandler(
            cmSampleBuffer: sampleBuffer,
            orientation: orientation,
            options: [:]
        )

        do {
            try handler.perform([request])
            return request.results?
                .max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height })
                .flatMap(overlayPayload(from:))
        } catch {
            return nil
        }
    }

    nonisolated private static func overlayPayload(from observation: VNFaceObservation) -> VisionFaceOverlayPayload? {
        let outlinePoints = faceOutlinePoints(from: observation)
        let faceBox = fittedFaceBox(from: observation, outlinePoints: outlinePoints)
        guard faceBox.width > 0.05, faceBox.height > 0.05 else { return nil }

        let landmarkMesh = landmarkOverlay(from: observation)
        let fittedMesh = fittedFaceMesh(from: observation, landmarks: landmarkMesh.points)

        return VisionFaceOverlayPayload(
            faceBox: faceBox,
            faceOutlinePoints: outlinePoints,
            points: landmarkMesh.points,
            segments: fittedMesh.segments + landmarkMesh.segments,
            landmarks2D: landmarkRegions2D(from: observation)
        )
    }

    nonisolated private static func displayRect(fromVisionBoundingBox box: CGRect) -> CGRect {
        CGRect(
            x: box.minX,
            y: 1 - box.maxY,
            width: box.width,
            height: box.height
        ).clampedToUnitRect()
    }

    nonisolated private static func fittedFaceBox(
        from observation: VNFaceObservation,
        outlinePoints: [CGPoint]
    ) -> CGRect {
        let fallback = displayRect(fromVisionBoundingBox: observation.boundingBox).clampedToUnitRect()
        guard let outlineBounds = outlinePoints.boundingRect,
              outlineBounds.width > 0.03,
              outlineBounds.height > 0.03 else {
            return fallback
        }

        let sideExpansion = outlineBounds.width * 0.08
        let topExpansion = outlineBounds.height * 0.22
        let bottomExpansion = outlineBounds.height * 0.05
        return CGRect(
            x: outlineBounds.minX - sideExpansion,
            y: outlineBounds.minY - topExpansion,
            width: outlineBounds.width + sideExpansion * 2,
            height: outlineBounds.height + topExpansion + bottomExpansion
        ).clampedToUnitRect()
    }

    nonisolated private static func landmarkOverlay(from observation: VNFaceObservation) -> (points: [CGPoint], segments: [FaceCameraSegment]) {
        guard let landmarks = observation.landmarks else { return ([], []) }

        let regions: [(VNFaceLandmarkRegion2D?, Bool)] = [
            (landmarks.faceContour, false),
            (landmarks.leftEyebrow, false),
            (landmarks.rightEyebrow, false),
            (landmarks.leftEye, true),
            (landmarks.rightEye, true),
            (landmarks.nose, false),
            (landmarks.noseCrest, false),
            (landmarks.medianLine, false),
            (landmarks.outerLips, true),
            (landmarks.innerLips, true),
            (landmarks.leftPupil, true),
            (landmarks.rightPupil, true)
        ]

        var allPoints: [CGPoint] = []
        var allSegments: [FaceCameraSegment] = []

        for (region, closed) in regions {
            let points = landmarkPoints(from: region, in: observation.boundingBox)
            allPoints.append(contentsOf: points)
            allSegments.append(contentsOf: segments(from: points, closed: closed))
        }

        return (allPoints, allSegments)
    }

    nonisolated private static func landmarkRegions2D(from observation: VNFaceObservation) -> [String: [[Double]]] {
        guard let landmarks = observation.landmarks else { return [:] }

        let regions: [(String, VNFaceLandmarkRegion2D?)] = [
            ("faceContour", landmarks.faceContour),
            ("leftEyebrow", landmarks.leftEyebrow),
            ("rightEyebrow", landmarks.rightEyebrow),
            ("leftEye", landmarks.leftEye),
            ("rightEye", landmarks.rightEye),
            ("nose", landmarks.nose),
            ("noseCrest", landmarks.noseCrest),
            ("medianLine", landmarks.medianLine),
            ("outerLips", landmarks.outerLips),
            ("innerLips", landmarks.innerLips),
            ("leftPupil", landmarks.leftPupil),
            ("rightPupil", landmarks.rightPupil)
        ]

        var payload: [String: [[Double]]] = [:]
        for (name, region) in regions {
            let points = landmarkPoints(from: region, in: observation.boundingBox)
            guard !points.isEmpty else { continue }
            payload[name] = points.map { [Double($0.x), Double($0.y)] }
        }
        return payload
    }

    nonisolated private static func faceOutlinePoints(from observation: VNFaceObservation) -> [CGPoint] {
        let contour = landmarkPoints(from: observation.landmarks?.faceContour, in: observation.boundingBox)
        guard !contour.isEmpty else {
            let rect = displayRect(fromVisionBoundingBox: observation.boundingBox)
            return [
                CGPoint(x: rect.midX, y: rect.minY),
                CGPoint(x: rect.maxX, y: rect.midY),
                CGPoint(x: rect.midX, y: rect.maxY),
                CGPoint(x: rect.minX, y: rect.midY)
            ].map { $0.clampedToUnitRect() }
        }
        return contour
    }

    nonisolated private static func landmarkPoints(from region: VNFaceLandmarkRegion2D?, in boundingBox: CGRect) -> [CGPoint] {
        guard let region else { return [] }
        return region.normalizedPoints.map { point in
            CGPoint(
                x: boundingBox.minX + point.x * boundingBox.width,
                y: 1 - (boundingBox.minY + point.y * boundingBox.height)
            ).clampedToUnitRect()
        }
    }

    nonisolated private static func fittedFaceMesh(
        from observation: VNFaceObservation,
        landmarks: [CGPoint]
    ) -> (points: [CGPoint], segments: [FaceCameraSegment]) {
        let outline = faceOutlinePoints(from: observation)
        let faceRect = fittedFaceBox(from: observation, outlinePoints: outline)
        let outlineBounds = outline.boundingRect ?? faceRect
        let meshRect = faceRect

        let centerX = noseCenter(from: observation) ?? landmarks.boundingRect?.midX ?? meshRect.midX
        let rowCount = 18
        var rows: [[CGPoint]] = []

        for rowIndex in 0..<rowCount {
            let rowProgress = CGFloat(rowIndex) / CGFloat(rowCount - 1)
            let y = meshRect.minY + meshRect.height * (0.04 + rowProgress * 0.90)
            let normalizedY = (rowProgress - 0.48) / 0.56
            let widthScale = sqrt(max(0, 1 - normalizedY * normalizedY))
            let contourWidth = estimatedFaceWidth(
                at: rowProgress,
                meshWidth: meshRect.width,
                contourWidth: outlineBounds.width
            ) * widthScale
            let columns = max(5, Int(round(8 + 8 * widthScale)))
            let rowCenterX = centerX + meshRect.width * (rowProgress - 0.48) * 0.025
            var rowPoints: [CGPoint] = []

            for columnIndex in 0...columns {
                let columnProgress = CGFloat(columnIndex) / CGFloat(columns)
                let stagger = rowIndex.isMultiple(of: 2) ? 0 : (1 / CGFloat(max(columns, 1))) * 0.32
                let xProgress = min(1, max(0, columnProgress + stagger))
                let x = rowCenterX + (xProgress - 0.5) * contourWidth
                rowPoints.append(CGPoint(x: x, y: y).clampedToUnitRect())
            }

            rows.append(rowPoints)
        }

        var points = rows.flatMap { $0 }
        points.append(contentsOf: landmarks)

        var segments: [FaceCameraSegment] = []
        for row in rows {
            segments.append(contentsOf: Self.segments(from: row, closed: false))
        }

        for rowIndex in 1..<rows.count {
            let previous = rows[rowIndex - 1]
            let current = rows[rowIndex]
            for currentPoint in current {
                for point in nearestTwoOverlayPoints(to: currentPoint, in: previous) {
                    segments.append(FaceCameraSegment(start: currentPoint, end: point))
                }
            }
        }

        return (points, segments)
    }

    nonisolated private static func estimatedFaceWidth(
        at rowProgress: CGFloat,
        meshWidth: CGFloat,
        contourWidth: CGFloat
    ) -> CGFloat {
        let base = min(meshWidth, max(contourWidth, meshWidth * 0.78))
        switch rowProgress {
        case 0.00..<0.16:
            return base * (0.42 + rowProgress * 2.0)
        case 0.16..<0.72:
            return base * 0.92
        default:
            let lowerProgress = (rowProgress - 0.72) / 0.28
            return base * (0.92 - lowerProgress * 0.36)
        }
    }

    nonisolated private static func noseCenter(from observation: VNFaceObservation) -> CGFloat? {
        let nosePoints = landmarkPoints(from: observation.landmarks?.nose, in: observation.boundingBox)
        return nosePoints.boundingRect?.midX
    }

    nonisolated private static func nearestTwoOverlayPoints(to point: CGPoint, in candidates: [CGPoint]) -> [CGPoint] {
        Array(candidates
            .sorted { $0.distanceSquared(to: point) < $1.distanceSquared(to: point) }
            .prefix(2))
    }

    nonisolated private static func visionGeometryPayload(from payload: VisionFaceOverlayPayload) -> FaceGeometrySubmissionPayload {
        FaceGeometrySubmissionPayload(
            provider: "vision_landmarks",
            coordinateSpace: "vision_normalized_2d",
            vertices: [],
            triangleIndices: [],
            blendShapes: [:],
            faceTransform: nil,
            cameraTransform: nil,
            cameraIntrinsics: nil,
            landmarks2D: payload.landmarks2D,
            quality: [
                "landmarkPointCount": Double(payload.points.count),
                "meshSegmentCount": Double(payload.segments.count)
            ]
        )
    }

    nonisolated private static func visionLandmarks2D(from image: UIImage) -> [String: [[Double]]]? {
        guard let cgImage = image.cgImage else { return nil }

        let request = VNDetectFaceLandmarksRequest()
        let handler = VNImageRequestHandler(
            cgImage: cgImage,
            orientation: image.fxm_cgImageOrientation,
            options: [:]
        )

        do {
            try handler.perform([request])
            guard let observation = request.results?
                .max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) else {
                return nil
            }
            let landmarks = landmarkRegions2D(from: observation)
            return landmarks.isEmpty ? nil : landmarks
        } catch {
            return nil
        }
    }

    nonisolated private static func arGeometryPayload(
        from faceAnchor: ARFaceAnchor,
        frame: ARFrame?
    ) -> FaceGeometrySubmissionPayload {
        let vertices = faceAnchor.geometry.vertices.map { vertex in
            [Double(vertex.x), Double(vertex.y), Double(vertex.z)]
        }
        let triangleIndices = faceAnchor.geometry.triangleIndices.map { Int($0) }
        let blendShapes = Dictionary(uniqueKeysWithValues: faceAnchor.blendShapes.map {
            ($0.key.rawValue, $0.value.doubleValue)
        })

        return FaceGeometrySubmissionPayload(
            provider: "arkit_true_depth",
            coordinateSpace: "arkit_face_local",
            vertices: vertices,
            triangleIndices: triangleIndices,
            blendShapes: blendShapes,
            faceTransform: matrixArray(faceAnchor.transform),
            cameraTransform: frame.map { matrixArray($0.camera.transform) },
            cameraIntrinsics: frame.map { matrixArray($0.camera.intrinsics) },
            landmarks2D: nil,
            quality: [
                "vertexCount": Double(vertices.count),
                "triangleIndexCount": Double(triangleIndices.count),
                "blendShapeCount": Double(blendShapes.count)
            ]
        )
    }

    nonisolated private static func matrixArray(_ matrix: simd_float4x4) -> [Double] {
        [
            Double(matrix.columns.0.x), Double(matrix.columns.0.y), Double(matrix.columns.0.z), Double(matrix.columns.0.w),
            Double(matrix.columns.1.x), Double(matrix.columns.1.y), Double(matrix.columns.1.z), Double(matrix.columns.1.w),
            Double(matrix.columns.2.x), Double(matrix.columns.2.y), Double(matrix.columns.2.z), Double(matrix.columns.2.w),
            Double(matrix.columns.3.x), Double(matrix.columns.3.y), Double(matrix.columns.3.z), Double(matrix.columns.3.w)
        ]
    }

    nonisolated private static func matrixArray(_ matrix: simd_float3x3) -> [Double] {
        [
            Double(matrix.columns.0.x), Double(matrix.columns.0.y), Double(matrix.columns.0.z),
            Double(matrix.columns.1.x), Double(matrix.columns.1.y), Double(matrix.columns.1.z),
            Double(matrix.columns.2.x), Double(matrix.columns.2.y), Double(matrix.columns.2.z)
        ]
    }

    nonisolated private static func trackingStateDescription(_ state: ARCamera.TrackingState?) -> String? {
        guard let state else { return nil }

        switch state {
        case .normal:
            return "normal"
        case let .limited(reason):
            return "limited_\(reason)"
        case .notAvailable:
            return "not_available"
        }
    }

    private static var appVersionString: String? {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String

        switch (version, build) {
        case let (version?, build?):
            return "\(version) (\(build))"
        case let (version?, nil):
            return version
        default:
            return nil
        }
    }

    nonisolated private static func segments(from points: [CGPoint], closed: Bool) -> [FaceCameraSegment] {
        guard points.count > 1 else { return [] }

        var segments = zip(points.dropLast(), points.dropFirst()).map {
            FaceCameraSegment(start: $0.0, end: $0.1)
        }

        if closed, let first = points.first, let last = points.last {
            segments.append(FaceCameraSegment(start: last, end: first))
        }

        return segments
    }
}

extension FaceCameraViewController: AVCaptureVideoDataOutputSampleBufferDelegate {
    nonisolated func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        processVisionFrame(sampleBuffer)
    }
}

extension FaceCameraViewController: ARSCNViewDelegate {
    nonisolated func renderer(_ renderer: SCNSceneRenderer, nodeFor anchor: ARAnchor) -> SCNNode? {
        guard let faceAnchor = anchor as? ARFaceAnchor,
              let device = renderer.device ?? MTLCreateSystemDefaultDevice(),
              let faceGeometry = ARSCNFaceGeometry(device: device, fillMesh: true) else {
            return nil
        }

        faceGeometry.update(from: faceAnchor.geometry)
        faceGeometry.materials = [Self.faceMeshMaterial()]

        let node = SCNNode(geometry: faceGeometry)
        node.renderingOrder = 10
        let frame = (renderer as? ARSCNView)?.session.currentFrame
        latestGeometryPayload = Self.arGeometryPayload(from: faceAnchor, frame: frame)
        latestTrackingState = Self.trackingStateDescription(frame?.camera.trackingState)

        DispatchQueue.main.async { [weak self] in
            self?.chromeView.setFaceDetected(true)
        }

        return node
    }

    nonisolated func renderer(_ renderer: SCNSceneRenderer, didUpdate node: SCNNode, for anchor: ARAnchor) {
        guard let faceAnchor = anchor as? ARFaceAnchor,
              let faceGeometry = node.geometry as? ARSCNFaceGeometry else {
            return
        }

        faceGeometry.update(from: faceAnchor.geometry)
        let frame = (renderer as? ARSCNView)?.session.currentFrame
        latestGeometryPayload = Self.arGeometryPayload(from: faceAnchor, frame: frame)
        latestTrackingState = Self.trackingStateDescription(frame?.camera.trackingState)

        DispatchQueue.main.async { [weak self] in
            self?.chromeView.setFaceDetected(true)
        }
    }

    nonisolated func renderer(_ renderer: SCNSceneRenderer, didRemove node: SCNNode, for anchor: ARAnchor) {
        guard anchor is ARFaceAnchor else { return }
        latestGeometryPayload = nil
        latestTrackingState = "no_face"
        DispatchQueue.main.async { [weak self] in
            self?.chromeView.setFaceDetected(false)
        }
    }

    nonisolated private static func faceMeshMaterial() -> SCNMaterial {
        let material = SCNMaterial()
        let lineColor = UIColor.white.withAlphaComponent(0.62)
        material.diffuse.contents = lineColor
        material.emission.contents = UIColor.white.withAlphaComponent(0.18)
        material.lightingModel = .constant
        material.fillMode = .lines
        material.isDoubleSided = true
        material.readsFromDepthBuffer = false
        material.writesToDepthBuffer = false
        return material
    }
}

private final class FaceCameraOverlayView: UIView {
    private var state = FaceCameraOverlayState.empty
    private var displayLink: CADisplayLink?
    private var scanProgress: CGFloat = 0

    override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        contentMode = .redraw
        startDisplayLink()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        isOpaque = false
        contentMode = .redraw
        startDisplayLink()
    }

    func update(with state: FaceCameraOverlayState) {
        self.state = state
        setNeedsDisplay()
    }

    override func willMove(toWindow newWindow: UIWindow?) {
        super.willMove(toWindow: newWindow)
        guard newWindow == nil else { return }
        displayLink?.invalidate()
        displayLink = nil
    }

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.clear(rect)

        if state.isFaceDetected {
            drawDetectedFace(in: bounds, context: context)
        } else {
            drawSearchingReticle(in: bounds, context: context)
        }
    }

    private func startDisplayLink() {
        let displayLink = CADisplayLink(target: self, selector: #selector(tick))
        displayLink.preferredFrameRateRange = CAFrameRateRange(minimum: 24, maximum: 30, preferred: 30)
        displayLink.add(to: .main, forMode: .common)
        self.displayLink = displayLink
    }

    @objc private func tick() {
        scanProgress += 0.018
        if scanProgress > 1 {
            scanProgress = 0
        }

        if state.isFaceDetected {
            setNeedsDisplay()
        }
    }

    private func drawDetectedFace(in bounds: CGRect, context: CGContext) {
        let faceRect = state.faceRect
        let expandedFace = faceRect.insetBy(
            dx: -faceRect.width * 0.045,
            dy: -faceRect.height * 0.055
        )

        drawFaceHalo(expandedFace, outline: state.faceOutlinePoints, context: context)
        drawMeshSegments(context: context)
        drawLandmarkDots(context: context)
        drawScanLine(in: expandedFace, context: context)
    }

    private func drawFaceHalo(_ rect: CGRect, outline: [CGPoint], context: CGContext) {
        context.saveGState()

        if outline.count > 3 {
            let path = UIBezierPath()
            path.move(to: outline[0])
            for point in outline.dropFirst() {
                path.addLine(to: point)
            }
            context.addPath(path.cgPath)
            context.setStrokeColor(UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.24).cgColor)
            context.setLineWidth(2.4)
            context.setLineJoin(.round)
            context.strokePath()
        } else {
            context.setStrokeColor(UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.18).cgColor)
            context.setLineWidth(2.4)
            context.strokeEllipse(in: rect)
        }

        context.setStrokeColor(UIColor.white.withAlphaComponent(0.16).cgColor)
        context.setLineWidth(1.2)
        context.strokeEllipse(in: rect)
        context.restoreGState()
    }

    private func drawMeshSegments(context: CGContext) {
        guard !state.meshSegments.isEmpty else { return }

        context.saveGState()
        context.setStrokeColor(UIColor.white.withAlphaComponent(0.48).cgColor)
        context.setLineWidth(0.56)
        context.setLineCap(.round)
        context.setLineJoin(.round)

        for segment in state.meshSegments {
            context.move(to: segment.start)
            context.addLine(to: segment.end)
        }
        context.strokePath()
        context.restoreGState()
    }

    private func drawLandmarkDots(context: CGContext) {
        guard !state.landmarkPoints.isEmpty else { return }

        context.saveGState()
        context.setFillColor(UIColor(fxColor: FXTheme.blue).withAlphaComponent(0.58).cgColor)
        for point in state.landmarkPoints {
            context.fillEllipse(in: CGRect(x: point.x - 1.25, y: point.y - 1.25, width: 2.5, height: 2.5))
        }
        context.restoreGState()
    }

    private func drawScanLine(in rect: CGRect, context: CGContext) {
        let y = rect.minY + rect.height * scanProgress
        let normalizedY = (y - rect.midY) / (rect.height * 0.5)
        let halfWidth = sqrt(max(0, 1 - normalizedY * normalizedY)) * rect.width * 0.48
        let scanRect = CGRect(
            x: rect.midX - halfWidth,
            y: y - 2,
            width: halfWidth * 2,
            height: 4
        )

        context.saveGState()
        context.setFillColor(UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.22).cgColor)
        context.addPath(UIBezierPath(roundedRect: scanRect, cornerRadius: 2).cgPath)
        context.fillPath()
        context.restoreGState()
    }

    private func drawSearchingReticle(in bounds: CGRect, context: CGContext) {
        let rect = CGRect(
            x: bounds.width * 0.22,
            y: bounds.height * 0.24,
            width: bounds.width * 0.56,
            height: bounds.height * 0.42
        )

        context.saveGState()
        context.setStrokeColor(UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.42).cgColor)
        context.setLineWidth(3)
        context.setLineDash(phase: 0, lengths: [14, 16])
        context.strokeEllipse(in: rect)
        context.restoreGState()
    }
}

private final class FaceCameraChromeView: UIView {
    var onClose: (() -> Void)?
    var onCapture: (() -> Void)?

    private let closeButton = UIButton(type: .system)
    private let modeLabel = PaddingLabel(horizontal: 14, vertical: 10)
    private let statusPill = UIView()
    private let statusDot = UIView()
    private let statusLabel = UILabel()
    private let shutterButton = CameraShutterButton()
    private let hintLabel = UILabel()

    override init(frame: CGRect) {
        super.init(frame: frame)
        setUp()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setUp()
    }

    func setFaceDetected(_ detected: Bool) {
        statusDot.backgroundColor = detected ? UIColor(fxColor: FXTheme.green) : UIColor(fxColor: FXTheme.yellow)
        statusLabel.text = String(localized: detected ? "analysis.camera.faceDetected" : "analysis.camera.searchingFace")
    }

    func setCaptureEnabled(_ enabled: Bool) {
        shutterButton.isEnabled = enabled
        shutterButton.alpha = enabled ? 1 : 0.52
    }

    private func setUp() {
        backgroundColor = .clear
        isUserInteractionEnabled = true

        setUpCloseButton()
        setUpModeLabel()
        setUpShutterButton()
        setUpStatusPill()
        setUpHintLabel()
        setFaceDetected(false)
    }

    private func setUpCloseButton() {
        closeButton.translatesAutoresizingMaskIntoConstraints = false
        closeButton.setImage(UIImage(systemName: "xmark"), for: .normal)
        closeButton.tintColor = .white
        closeButton.backgroundColor = UIColor.black.withAlphaComponent(0.42)
        closeButton.layer.cornerRadius = 22
        closeButton.layer.borderColor = UIColor.white.withAlphaComponent(0.18).cgColor
        closeButton.layer.borderWidth = 1
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        closeButton.accessibilityLabel = String(localized: "analysis.camera.close")
        addSubview(closeButton)

        NSLayoutConstraint.activate([
            closeButton.leadingAnchor.constraint(equalTo: safeAreaLayoutGuide.leadingAnchor, constant: 20),
            closeButton.topAnchor.constraint(equalTo: safeAreaLayoutGuide.topAnchor, constant: 16),
            closeButton.widthAnchor.constraint(equalToConstant: 44),
            closeButton.heightAnchor.constraint(equalToConstant: 44)
        ])
    }

    private func setUpModeLabel() {
        modeLabel.translatesAutoresizingMaskIntoConstraints = false
        modeLabel.text = String(localized: "analysis.camera.scanMode")
        modeLabel.textColor = .white
        modeLabel.font = .systemFont(ofSize: 15, weight: .heavy)
        modeLabel.backgroundColor = UIColor.black.withAlphaComponent(0.34)
        modeLabel.layer.cornerRadius = 18
        modeLabel.layer.masksToBounds = true
        modeLabel.layer.borderColor = UIColor.white.withAlphaComponent(0.16).cgColor
        modeLabel.layer.borderWidth = 1
        addSubview(modeLabel)

        NSLayoutConstraint.activate([
            modeLabel.trailingAnchor.constraint(equalTo: safeAreaLayoutGuide.trailingAnchor, constant: -20),
            modeLabel.centerYAnchor.constraint(equalTo: closeButton.centerYAnchor)
        ])
    }

    private func setUpStatusPill() {
        statusPill.translatesAutoresizingMaskIntoConstraints = false
        statusPill.backgroundColor = UIColor.black.withAlphaComponent(0.46)
        statusPill.layer.cornerRadius = 23
        statusPill.layer.borderColor = UIColor.white.withAlphaComponent(0.14).cgColor
        statusPill.layer.borderWidth = 1
        addSubview(statusPill)

        statusDot.translatesAutoresizingMaskIntoConstraints = false
        statusDot.layer.cornerRadius = 6
        statusPill.addSubview(statusDot)

        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.textColor = .white
        statusLabel.font = .systemFont(ofSize: 17, weight: .bold)
        statusPill.addSubview(statusLabel)

        NSLayoutConstraint.activate([
            statusPill.centerXAnchor.constraint(equalTo: centerXAnchor),
            statusPill.bottomAnchor.constraint(equalTo: shutterButton.topAnchor, constant: -14),
            statusPill.heightAnchor.constraint(equalToConstant: 46),

            statusDot.leadingAnchor.constraint(equalTo: statusPill.leadingAnchor, constant: 18),
            statusDot.centerYAnchor.constraint(equalTo: statusPill.centerYAnchor),
            statusDot.widthAnchor.constraint(equalToConstant: 12),
            statusDot.heightAnchor.constraint(equalToConstant: 12),

            statusLabel.leadingAnchor.constraint(equalTo: statusDot.trailingAnchor, constant: 10),
            statusLabel.trailingAnchor.constraint(equalTo: statusPill.trailingAnchor, constant: -18),
            statusLabel.centerYAnchor.constraint(equalTo: statusPill.centerYAnchor)
        ])
    }

    private func setUpShutterButton() {
        shutterButton.translatesAutoresizingMaskIntoConstraints = false
        shutterButton.addTarget(self, action: #selector(captureTapped), for: .touchUpInside)
        addSubview(shutterButton)

        NSLayoutConstraint.activate([
            shutterButton.centerXAnchor.constraint(equalTo: centerXAnchor),
            shutterButton.bottomAnchor.constraint(equalTo: safeAreaLayoutGuide.bottomAnchor, constant: -60),
            shutterButton.widthAnchor.constraint(equalToConstant: 108),
            shutterButton.heightAnchor.constraint(equalToConstant: 108)
        ])
    }

    private func setUpHintLabel() {
        hintLabel.translatesAutoresizingMaskIntoConstraints = false
        hintLabel.text = String(localized: "analysis.camera.captureHint")
        hintLabel.textColor = UIColor.white.withAlphaComponent(0.62)
        hintLabel.font = .systemFont(ofSize: 13, weight: .semibold)
        hintLabel.textAlignment = .center
        addSubview(hintLabel)

        NSLayoutConstraint.activate([
            hintLabel.leadingAnchor.constraint(greaterThanOrEqualTo: leadingAnchor, constant: 20),
            hintLabel.trailingAnchor.constraint(lessThanOrEqualTo: trailingAnchor, constant: -20),
            hintLabel.centerXAnchor.constraint(equalTo: centerXAnchor),
            hintLabel.topAnchor.constraint(equalTo: shutterButton.bottomAnchor, constant: 8)
        ])
    }

    @objc private func closeTapped() {
        onClose?()
    }

    @objc private func captureTapped() {
        onCapture?()
    }
}

private final class CameraShutterButton: UIControl {
    private let outerRing = CAShapeLayer()
    private let innerCircle = CAShapeLayer()
    private let glowRing = CAShapeLayer()

    override init(frame: CGRect) {
        super.init(frame: frame)
        setUp()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        setUp()
    }

    override var isHighlighted: Bool {
        didSet {
            UIView.animate(withDuration: 0.12) {
                self.transform = self.isHighlighted ? CGAffineTransform(scaleX: 0.94, y: 0.94) : .identity
            }
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()

        let outerRect = bounds.insetBy(dx: 15, dy: 15)
        let innerRect = bounds.insetBy(dx: 24, dy: 24)
        let glowRect = bounds.insetBy(dx: 8, dy: 8)

        outerRing.path = UIBezierPath(ovalIn: outerRect).cgPath
        innerCircle.path = UIBezierPath(ovalIn: innerRect).cgPath
        glowRing.path = UIBezierPath(ovalIn: glowRect).cgPath
    }

    private func setUp() {
        isAccessibilityElement = true
        accessibilityLabel = String(localized: "analysis.camera.capture")

        outerRing.fillColor = UIColor.clear.cgColor
        outerRing.strokeColor = UIColor.white.withAlphaComponent(0.78).cgColor
        outerRing.lineWidth = 4
        layer.addSublayer(outerRing)

        innerCircle.fillColor = UIColor.white.cgColor
        layer.addSublayer(innerCircle)

        glowRing.fillColor = UIColor.clear.cgColor
        glowRing.strokeColor = UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.45).cgColor
        glowRing.lineWidth = 1
        glowRing.shadowColor = UIColor(fxColor: FXTheme.cyan).withAlphaComponent(0.34).cgColor
        glowRing.shadowRadius = 14
        glowRing.shadowOpacity = 1
        glowRing.shadowOffset = .zero
        layer.addSublayer(glowRing)
    }
}

private final class PaddingLabel: UILabel {
    private let horizontal: CGFloat
    private let vertical: CGFloat

    init(horizontal: CGFloat, vertical: CGFloat) {
        self.horizontal = horizontal
        self.vertical = vertical
        super.init(frame: .zero)
    }

    required init?(coder: NSCoder) {
        self.horizontal = 0
        self.vertical = 0
        super.init(coder: coder)
    }

    override var intrinsicContentSize: CGSize {
        let size = super.intrinsicContentSize
        return CGSize(width: size.width + horizontal * 2, height: size.height + vertical * 2)
    }

    override func drawText(in rect: CGRect) {
        super.drawText(in: rect.insetBy(dx: horizontal, dy: vertical))
    }
}

private struct FaceCameraOverlayState: Equatable {
    static let empty = FaceCameraOverlayState()

    var isFaceDetected = false
    var faceRect: CGRect = .zero
    var faceOutlinePoints: [CGPoint] = []
    var landmarkPoints: [CGPoint] = []
    var meshSegments: [FaceCameraSegment] = []
}

private struct FaceCameraSegment: Equatable {
    var start: CGPoint
    var end: CGPoint
}

private struct VisionFaceOverlayPayload {
    let faceBox: CGRect
    let faceOutlinePoints: [CGPoint]
    let points: [CGPoint]
    let segments: [FaceCameraSegment]
    let landmarks2D: [String: [[Double]]]
}

private final class FaceCameraPhotoDelegate: NSObject, AVCapturePhotoCaptureDelegate {
    private let completion: (UIImage?) -> Void

    init(completion: @escaping (UIImage?) -> Void) {
        self.completion = completion
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        guard error == nil,
              let data = photo.fileDataRepresentation(),
              let image = UIImage(data: data) else {
            completion(nil)
            return
        }

        completion(image)
    }
}

private enum FaceCameraError: LocalizedError {
    case frontCameraUnavailable

    var errorDescription: String? {
        switch self {
        case .frontCameraUnavailable:
            String(localized: "analysis.camera.unavailableMessage")
        }
    }
}

private extension UIColor {
    convenience init(fxColor color: Color) {
        self.init(color)
    }
}

private extension CGRect {
    func rect(in size: CGSize) -> CGRect {
        CGRect(
            x: minX * size.width,
            y: minY * size.height,
            width: width * size.width,
            height: height * size.height
        )
    }

    func clampedToUnitRect() -> CGRect {
        intersection(CGRect(x: 0, y: 0, width: 1, height: 1))
    }
}

private extension CGPoint {
    func point(in size: CGSize) -> CGPoint {
        CGPoint(x: x * size.width, y: y * size.height)
    }

    func clampedToUnitRect() -> CGPoint {
        CGPoint(
            x: max(0, min(1, x)),
            y: max(0, min(1, y))
        )
    }

    func distanceSquared(to point: CGPoint) -> CGFloat {
        let dx = x - point.x
        let dy = y - point.y
        return dx * dx + dy * dy
    }
}

private extension AVCaptureVideoPreviewLayer {
    func layerPoint(fromMetadataPoint point: CGPoint) -> CGPoint {
        let rect = CGRect(x: point.x, y: point.y, width: 0.0001, height: 0.0001)
        let convertedRect = layerRectConverted(fromMetadataOutputRect: rect)
        return CGPoint(x: convertedRect.midX, y: convertedRect.midY)
    }
}

private extension Array where Element == CGPoint {
    var boundingRect: CGRect? {
        guard let first else { return nil }

        var minX = first.x
        var minY = first.y
        var maxX = first.x
        var maxY = first.y

        for point in dropFirst() {
            minX = Swift.min(minX, point.x)
            minY = Swift.min(minY, point.y)
            maxX = Swift.max(maxX, point.x)
            maxY = Swift.max(maxY, point.y)
        }

        return CGRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
    }
}

private extension UIImage {
    func fxm_upright() -> UIImage {
        guard imageOrientation != .up else { return self }

        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        let renderer = UIGraphicsImageRenderer(size: size, format: format)
        return renderer.image { _ in
            draw(in: CGRect(origin: .zero, size: size))
        }
    }

    var fxm_cgImageOrientation: CGImagePropertyOrientation {
        switch imageOrientation {
        case .up:
            return .up
        case .down:
            return .down
        case .left:
            return .left
        case .right:
            return .right
        case .upMirrored:
            return .upMirrored
        case .downMirrored:
            return .downMirrored
        case .leftMirrored:
            return .leftMirrored
        case .rightMirrored:
            return .rightMirrored
        @unknown default:
            return .up
        }
    }
}

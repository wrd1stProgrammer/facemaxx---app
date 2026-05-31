import SwiftUI
import PhotosUI
import StoreKit
import UIKit
import Vision

enum AnalysisPhotoSourceMenuCoordinateSpace {
    static let name = "analysisPhotoSourceMenu"
}

private struct StaticAnalysisShareRenderKey: EnvironmentKey {
    static let defaultValue = false
}

private extension EnvironmentValues {
    var isRenderingStaticAnalysisShare: Bool {
        get { self[StaticAnalysisShareRenderKey.self] }
        set { self[StaticAnalysisShareRenderKey.self] = newValue }
    }
}

struct AnalyzeView: View {
    private static let analysisResultID = "analysisResult"
    private static let enabledResultModeIDs: Set<String> = [
        "proportions",
        "aesthetics",
        "glow-up-coach",
        "look-archetype",
        "best-photo-selector",
        "best-angle-finder",
        "dating-profile-score",
        "instagram-profile-score"
    ]
    private static let freeTrialModeIDs: Set<String> = [
        "proportions",
        "aesthetics"
    ]

    private let initialCapture: FaceCameraCaptureResult?
    private let preloadDemoPhotos: Bool
    private let onInitialCaptureConsumed: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService
    @State private var selectedModeID: String?
    @State private var requestedModeID: String?
    @State private var selectedPhoto: UIImage?
    @State private var didPreloadDemoPhotos = false
    @State private var supplementalPhotos: [UIImage] = []
    @State private var supplementalScanOverlayPhotos: [UIImage?] = []
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var isPhotoSourceDialogPresented = false
    @State private var photoSourceMenuAnchor: CGPoint?
    @State private var isPhotoPickerPresented = false
    @State private var isCameraPresented = false
    @State private var isAddingSupplementalPhoto = false
    @State private var pendingPhotoCrop: PendingPhotoCrop?
    @State private var cropRequestAfterCameraDismissal: PendingPhotoCrop?
    @State private var captureSaveState = CaptureSaveState.idle
    @State private var uploadedPhoto: PhotoUploadResponse?
    @State private var uploadedSupplementalPhotos: [PhotoUploadResponse] = []
    @State private var faceScanResponse: FaceScanCaptureResponse?
    @State private var latestScanPayload: FaceScanCapturePayload?
    @State private var latestScanOverlayPhoto: UIImage?
    @State private var uploadPhotoTask: Task<PhotoUploadResponse, Error>?
    @State private var supplementalPhotoUploadTasks: [Task<PhotoUploadResponse, Error>] = []
    @State private var faceScanSaveTask: Task<FaceScanCaptureResponse?, Error>?
    @State private var analysisState = AnalysisRequestState.idle
    @State private var analysisFailureBodyKey: LocalizedStringKey = "analysis.analysisFailedBody"
    @State private var analysisRun: AnalysisRunResponse?
    @State private var activeAnalysisModeID: String?
    @State private var isProPaywallPresented = false
    @AppStorage(AppLanguage.storageKey) private var selectedLanguageID = AppLanguage.system.rawValue
    @AppStorage(AIAnalysisConsentStore.grantedStorageKey) private var isAIAnalysisConsentGranted = false
    @AppStorage(AIAnalysisConsentStore.promptSeenStorageKey) private var hasSeenAIAnalysisConsentPrompt = false
    @State private var isAIAnalysisConsentPresented = false
    @State private var pendingConsentAnalysisModeID: String?

    init(
        initialCapture: FaceCameraCaptureResult? = nil,
        preloadDemoPhotos: Bool = false,
        onInitialCaptureConsumed: @escaping () -> Void = {}
    ) {
        self.initialCapture = initialCapture
        self.preloadDemoPhotos = preloadDemoPhotos
        self.onInitialCaptureConsumed = onInitialCaptureConsumed
    }

    private var analysisPrerequisitesMet: Bool {
        guard selectedPhoto != nil, let selectedModeID else { return false }
        guard captureSaveState != .saving, analysisState != .running else { return false }
        guard selectedPhotoCount >= selectedModeRequiredPhotoCount else { return false }
        return Self.enabledResultModeIDs.contains(selectedModeID)
    }

    private var selectedModeRequiresProScan: Bool {
        AnalysisMode.isProScanMode(modeID: selectedModeID)
    }

    private var canStartAnalysis: Bool {
        analysisPrerequisitesMet
            && !selectedModeLockedByFreeTrial
            && (!selectedModeRequiresProScan || purchaseService.canUseProScan)
    }

    private var shouldPromptForProScan: Bool {
        analysisPrerequisitesMet
            && selectedModeRequiresProScan
            && (
                selectedModeLockedByFreeTrial
                || (!purchaseService.canUseProScan && !purchaseService.hasActiveProSubscription)
            )
    }

    private var isSubscribedWithoutScanQuota: Bool {
        analysisPrerequisitesMet
            && selectedModeRequiresProScan
            && !purchaseService.canUseProScan
            && purchaseService.hasActiveProSubscription
    }

    private var selectedModeRequiresMultiplePhotos: Bool {
        AnalysisMode.requiresMultiplePhotos(modeID: selectedModeID)
    }

    private var selectedModeLockedByFreeTrial: Bool {
        guard purchaseService.hasFreeTrialScanAvailable, let selectedModeID else { return false }
        return !Self.freeTrialModeIDs.contains(selectedModeID)
    }

    private var freeTrialLockedModeIDs: Set<String> {
        guard purchaseService.hasFreeTrialScanAvailable else { return [] }
        return Self.enabledResultModeIDs.subtracting(Self.freeTrialModeIDs)
    }

    private var selectedPhotoCount: Int {
        (selectedPhoto == nil ? 0 : 1) + visibleSupplementalPhotos.count
    }

    private var selectedModeRequiredPhotoCount: Int {
        AnalysisMode.minimumPhotoCount(modeID: selectedModeID)
    }

    private var selectedModeSupplementalPhotoLimit: Int {
        max(0, selectedModeRequiredPhotoCount - 1)
    }

    private var visibleSupplementalPhotos: [UIImage] {
        Array(supplementalPhotos.prefix(selectedModeSupplementalPhotoLimit))
    }

    private var visibleSupplementalScanOverlayPhotos: [UIImage?] {
        Array(supplementalScanOverlayPhotos.prefix(selectedModeSupplementalPhotoLimit))
    }

    private var currentAnalysisLocale: String {
        AppLanguage.storedValue(for: selectedLanguageID).analysisLocale
    }

    private var selectedLocale: Locale {
        AppLanguage.storedValue(for: selectedLanguageID).locale
    }

    private var selectedAnalysisMode: AnalysisMode? {
        AnalysisMode.allModes.first { $0.id == selectedModeID }
    }

    private var shouldMaintainDemoPhotoSet: Bool {
        preloadDemoPhotos && AppReviewDemoMode.isEnabled && selectedPhoto != nil
    }

    var body: some View {
        ZStack {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: selectedPhoto == nil ? 22 : 20) {
                        AnalysisEntryHeader()
                            .padding(.top, selectedPhoto == nil ? 24 : 14)

                        if selectedPhoto == nil {
                            AnalysisCaptureCard { anchor in
                                presentPhotoSourceMenu(anchor: anchor, isAddingSupplementalPhoto: false)
                            }
                            .transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
                        }

                        if let selectedPhoto {
                            SelectedAnalysisPhotoView(
                                image: selectedPhoto,
                                supplementalPhotos: visibleSupplementalPhotos,
                                requiredPhotoCount: selectedModeRequiredPhotoCount,
                                canAddSupplementalPhoto: selectedModeRequiresMultiplePhotos
                                    && selectedPhotoCount < selectedModeRequiredPhotoCount,
                                reduceMotion: reduceMotion,
                                addSupplementalPhotoAction: { anchor in
                                    presentPhotoSourceMenu(anchor: anchor, isAddingSupplementalPhoto: true)
                                },
                                removeSupplementalPhotoAction: removeSupplementalPhoto
                            ) {
                                clearSelectedPhoto()
                            }
                            .transition(reduceMotion ? .opacity : .scale(scale: 0.96).combined(with: .opacity))
                        }

                        AnalysisModeChooser(
                            modes: AnalysisMode.allModes,
                            selectedModeID: selectedModeID,
                            lockedModeIDs: freeTrialLockedModeIDs,
                            selectedPhotoCount: selectedPhotoCount,
                            reduceMotion: reduceMotion,
                            selectAction: select
                        )

                        AnalysisRunPanel(
                            isPrepared: analysisPrerequisitesMet,
                            canStartAnalysis: canStartAnalysis,
                            shouldOpenPaywall: shouldPromptForProScan,
                            isQuotaExhausted: isSubscribedWithoutScanQuota,
                            isFreeTrialLockedMode: selectedModeLockedByFreeTrial,
                            requiresProScan: selectedModeRequiresProScan,
                            selectedMode: selectedAnalysisMode,
                            photoCount: selectedPhotoCount,
                            requiredPhotoCount: selectedModeRequiredPhotoCount,
                            captureSaveState: captureSaveState,
                            scanBalanceText: purchaseService.scanBalanceText(locale: selectedLocale),
                            usesFreeTrialScan: purchaseService.hasFreeTrialScanAvailable
                        ) {
                            getRating(using: proxy)
                        }

                        if analysisState == .failed {
                            AnalysisFailureSection(bodyKey: analysisFailureBodyKey)
                                .id(Self.analysisResultID)
                                .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
                        } else if let result = analysisRun?.result, let requestedModeID {
                            AnalysisResultContent(
                                modeID: requestedModeID,
                                result: result,
                                image: selectedPhoto,
                                supplementalImages: visibleSupplementalPhotos,
                                supplementalScanOverlayImages: visibleSupplementalScanOverlayPhotos,
                                scanPayload: latestScanPayload,
                                scanOverlayImage: latestScanOverlayPhoto,
                                reduceMotion: reduceMotion,
                                isFreeTrialResult: analysisRun?.isFreeTrialResult == true,
                                unlockAction: { isProPaywallPresented = true }
                            )
                            .id(Self.analysisResultID)
                            .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
                        } else if analysisState != .running {
                            AnalysisPerformanceWarning()
                        }
                    }
                    .padding(.horizontal, 16)
                    .safeAreaPadding(.bottom, 172)
                    .animation(.snappy(duration: reduceMotion ? 0.01 : 0.32), value: requestedModeID)
                    .animation(.snappy(duration: reduceMotion ? 0.01 : 0.24), value: selectedModeID)
                }
                .scrollIndicators(.hidden)
            }
            .blur(radius: analysisState == .running ? 2.2 : 0)
            .allowsHitTesting(analysisState != .running)

            if analysisState == .running {
                AnalysisLoadingOverlay()
                    .transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.97)))
            }

            if let photoSourceMenuAnchor {
                GeometryReader { proxy in
                    PhotoSourceMenuOverlay(
                        anchor: photoSourceMenuAnchor,
                        containerSize: proxy.size,
                        dismissAction: dismissPhotoSourceMenu,
                        cameraAction: {
                            dismissPhotoSourceMenu()
                            isCameraPresented = true
                        },
                        galleryAction: {
                            dismissPhotoSourceMenu()
                            isPhotoPickerPresented = true
                        }
                    )
                }
                .transition(.opacity)
                .zIndex(3)
            }
        }
        .animation(.smooth(duration: reduceMotion ? 0.01 : 0.28), value: analysisState)
        .background(FXTheme.background)
        .coordinateSpace(name: AnalysisPhotoSourceMenuCoordinateSpace.name)
        .fullScreenCover(isPresented: $isProPaywallPresented) {
            ProScanPaywallView()
                .environmentObject(purchaseService)
        }
        .sheet(isPresented: $isAIAnalysisConsentPresented) {
            AIAnalysisConsentSheet(
                primaryButtonKey: pendingConsentAnalysisModeID == nil
                    ? "privacy.aiConsent.agreeContinue"
                    : "privacy.aiConsent.agreeAnalyze",
                onAgree: grantAIAnalysisConsentAndResume,
                onNotNow: deferAIAnalysisConsent
            )
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .photosPicker(
            isPresented: $isPhotoPickerPresented,
            selection: $selectedPhotoItem,
            matching: .images,
            preferredItemEncoding: .current
        )
        .fullScreenCover(
            isPresented: $isCameraPresented,
            onDismiss: {
                if let request = cropRequestAfterCameraDismissal {
                    cropRequestAfterCameraDismissal = nil
                    pendingPhotoCrop = request
                }
            }
        ) {
            FaceCameraCaptureView { result in
                let request = PendingPhotoCrop(
                    source: .camera,
                    image: result.image,
                    scanOverlayImage: result.scanOverlayImage,
                    scanPayload: result.scanPayload
                )
                cropRequestAfterCameraDismissal = request
                isCameraPresented = false
            } onCancel: {
                isCameraPresented = false
            }
        }
        .fullScreenCover(item: $pendingPhotoCrop) { request in
            SquarePhotoCropView(
                image: request.image,
                scanOverlayImage: request.scanOverlayImage,
                onCancel: {
                    pendingPhotoCrop = nil
                    selectedPhotoItem = nil
                    isAddingSupplementalPhoto = false
                },
                onChoose: { result in
                    commitPhotoCrop(result, from: request)
                }
            )
        }
        .onChange(of: selectedPhotoItem) { _, newItem in
            guard let newItem else { return }
            Task {
                await loadPhoto(from: newItem)
            }
        }
        .task {
            if selectedModeID == nil {
                selectedModeID = AnalysisMode.allModes.first?.id
            }
            consumeInitialCaptureIfNeeded()
            preloadDemoPhotosIfNeeded()
            await purchaseService.refreshEntitlementsAndServerStatus()
        }
    }

    private func presentPhotoSourceMenu(anchor: CGPoint, isAddingSupplementalPhoto: Bool) {
        guard isAIAnalysisConsentGranted else {
            pendingConsentAnalysisModeID = nil
            isAIAnalysisConsentPresented = true
            return
        }
        self.isAddingSupplementalPhoto = isAddingSupplementalPhoto
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.20)) {
            isPhotoSourceDialogPresented = true
            photoSourceMenuAnchor = anchor
        }
    }

    private func dismissPhotoSourceMenu() {
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.18)) {
            isPhotoSourceDialogPresented = false
            photoSourceMenuAnchor = nil
        }
    }

    private func select(_ mode: AnalysisMode) {
        if selectedModeID != mode.id {
            requestedModeID = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
        }

        selectedModeID = mode.id
        if shouldMaintainDemoPhotoSet {
            ensureDemoPhotosForMode(mode.id)
        } else {
            trimSupplementalPhotos(to: max(0, mode.minimumPhotoCount - 1))
        }
    }

    private func setSelectedPhoto(
        _ image: UIImage,
        scanOverlayImage: UIImage? = nil,
        scanPayload: FaceScanCapturePayload? = nil
    ) {
        uploadPhotoTask?.cancel()
        faceScanSaveTask?.cancel()
        cancelSupplementalUploadTasks()
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.28)) {
            selectedPhoto = image
            supplementalPhotos = []
            supplementalScanOverlayPhotos = []
            uploadedSupplementalPhotos = []
            supplementalPhotoUploadTasks = []
            uploadedPhoto = nil
            faceScanResponse = nil
            uploadPhotoTask = nil
            faceScanSaveTask = nil
            latestScanPayload = scanPayload
            latestScanOverlayPhoto = scanOverlayImage
            requestedModeID = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
            captureSaveState = .idle
        }
        if isAIAnalysisConsentGranted {
            prepareSelectedPhotoUpload(for: image, scanPayload: scanPayload)
        }
    }

    private func consumeInitialCaptureIfNeeded() {
        guard let initialCapture, selectedPhoto == nil else { return }
        setSelectedPhoto(
            initialCapture.image,
            scanOverlayImage: initialCapture.scanOverlayImage,
            scanPayload: initialCapture.scanPayload
        )
        onInitialCaptureConsumed()
    }

    private func preloadDemoPhotosIfNeeded() {
        guard preloadDemoPhotos, AppReviewDemoMode.isEnabled, !didPreloadDemoPhotos, selectedPhoto == nil else {
            return
        }

        let images = AppReviewDemoMode.demoPhotoNames.compactMap(Self.demoImage(named:))
        guard let primaryImage = images.first else { return }

        didPreloadDemoPhotos = true
        uploadPhotoTask?.cancel()
        faceScanSaveTask?.cancel()
        cancelSupplementalUploadTasks()

        let supplementalImages = Array(images.dropFirst().prefix(2))
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.28)) {
            selectedModeID = AppReviewDemoMode.defaultModeID
            selectedPhoto = primaryImage
            supplementalPhotos = supplementalImages
            supplementalScanOverlayPhotos = supplementalImages.map { _ in nil }
            uploadedSupplementalPhotos = []
            supplementalPhotoUploadTasks = []
            uploadedPhoto = nil
            faceScanResponse = nil
            uploadPhotoTask = nil
            faceScanSaveTask = nil
            latestScanPayload = nil
            latestScanOverlayPhoto = nil
            requestedModeID = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
            captureSaveState = .idle
        }

        if isAIAnalysisConsentGranted {
            prepareSelectedPhotoUpload(for: primaryImage)
            ensureSupplementalUploadTasksStarted(upTo: supplementalImages.count)
        }
    }

    private static func demoImage(named name: String) -> UIImage? {
        if let image = UIImage(named: name) {
            return image
        }

        guard let url = Bundle.main.url(forResource: name, withExtension: "PNG") else {
            return nil
        }
        return UIImage(contentsOfFile: url.path)
    }

    private func ensureDemoPhotosForMode(_ modeID: String?) {
        guard preloadDemoPhotos, AppReviewDemoMode.isEnabled, selectedPhoto != nil else {
            return
        }

        let requiredSupplementalCount = max(0, AnalysisMode.minimumPhotoCount(modeID: modeID) - 1)
        guard supplementalPhotos.count < requiredSupplementalCount else {
            return
        }

        let demoSupplementalImages = Array(
            AppReviewDemoMode.demoPhotoNames
                .dropFirst()
                .compactMap(Self.demoImage(named:))
        )
        guard !demoSupplementalImages.isEmpty else { return }

        let missingCount = requiredSupplementalCount - supplementalPhotos.count
        let startIndex = min(supplementalPhotos.count, demoSupplementalImages.count)
        let orderedFillImages = Array(demoSupplementalImages.dropFirst(startIndex))
        let fallbackFillImages = demoSupplementalImages
        var imagesToAppend = Array(orderedFillImages.prefix(missingCount))

        while imagesToAppend.count < missingCount, let fallbackImage = fallbackFillImages[safe: imagesToAppend.count] {
            imagesToAppend.append(fallbackImage)
        }

        guard !imagesToAppend.isEmpty else { return }

        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.22)) {
            supplementalPhotos.append(contentsOf: imagesToAppend)
            supplementalScanOverlayPhotos.append(contentsOf: imagesToAppend.map { _ in nil })
            requestedModeID = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
        }
        if isAIAnalysisConsentGranted {
            ensureSupplementalUploadTasksStarted(upTo: supplementalPhotos.count)
        }
    }

    private func clearSelectedPhoto() {
        selectedPhotoItem = nil
        cancelSupplementalUploadTasks()
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.24)) {
            selectedPhoto = nil
            supplementalPhotos = []
            supplementalScanOverlayPhotos = []
            uploadedSupplementalPhotos = []
            supplementalPhotoUploadTasks = []
            requestedModeID = nil
            captureSaveState = .idle
            uploadedPhoto = nil
            faceScanResponse = nil
            uploadPhotoTask?.cancel()
            faceScanSaveTask?.cancel()
            uploadPhotoTask = nil
            faceScanSaveTask = nil
            latestScanPayload = nil
            latestScanOverlayPhoto = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
        }
    }

    private func removeSupplementalPhoto(at index: Int) {
        guard supplementalPhotos.indices.contains(index) else { return }
        supplementalPhotoUploadTasks[safe: index]?.cancel()
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.24)) {
            supplementalPhotos.remove(at: index)
            supplementalScanOverlayPhotos.removeIfPresent(at: index)
            supplementalPhotoUploadTasks.removeIfPresent(at: index)
            uploadedSupplementalPhotos.removeIfPresent(at: index)
            requestedModeID = nil
            activeAnalysisModeID = nil
            analysisRun = nil
            analysisState = .idle
        }
    }

    private func trimSupplementalPhotos(to limit: Int) {
        let limit = max(0, limit)
        guard supplementalPhotos.count > limit else { return }

        supplementalPhotoUploadTasks.dropFirst(limit).forEach { $0.cancel() }
        withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.22)) {
            supplementalPhotos = Array(supplementalPhotos.prefix(limit))
            supplementalScanOverlayPhotos = Array(supplementalScanOverlayPhotos.prefix(limit))
            supplementalPhotoUploadTasks = Array(supplementalPhotoUploadTasks.prefix(limit))
            uploadedSupplementalPhotos = Array(uploadedSupplementalPhotos.prefix(limit))
        }
    }

    @MainActor
    private func loadPhoto(from item: PhotosPickerItem) async {
        guard let data = try? await item.loadTransferable(type: Data.self),
              let image = UIImage(data: data) else {
            return
        }

        pendingPhotoCrop = PendingPhotoCrop(
            source: .gallery,
            image: image,
            scanOverlayImage: nil,
            scanPayload: nil
        )
        selectedPhotoItem = nil
    }

    @MainActor
    private func commitPhotoCrop(_ result: SquarePhotoCropResult, from request: PendingPhotoCrop) {
        if isAddingSupplementalPhoto, selectedPhoto != nil {
            pendingPhotoCrop = nil
            selectedPhotoItem = nil
            isAddingSupplementalPhoto = false
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.24)) {
                supplementalPhotos.append(result.image)
                supplementalScanOverlayPhotos.append(result.scanOverlayImage)
                if isAIAnalysisConsentGranted {
                    supplementalPhotoUploadTasks.append(makePhotoUploadTask(for: result.image))
                }
                requestedModeID = nil
                activeAnalysisModeID = nil
                analysisRun = nil
                analysisState = .idle
            }
            return
        }

        pendingPhotoCrop = nil
        selectedPhotoItem = nil
        isAddingSupplementalPhoto = false
        let payload = FaceScanPayloadBuilder.payload(
            for: result.image,
            source: request.source.rawValue,
            isFrontCamera: request.source == .camera,
            basePayload: request.scanPayload,
            preferredRegion: result.preferredRegion
        )
        setSelectedPhoto(
            result.image,
            scanOverlayImage: result.scanOverlayImage,
            scanPayload: payload
        )
    }

    @MainActor
    private func saveCameraCapture(_ result: FaceCameraCaptureResult) async {
        captureSaveState = .saving
        do {
            let response = try await FacemaxxAPIClient.shared.saveCameraCapture(result)
            uploadedPhoto = response.photo
            faceScanResponse = response.scan
            latestScanPayload = result.scanPayload
            HomeActivityStore.shared.recordCapture(photo: response.photo, scan: response.scan)
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.22)) {
                captureSaveState = response.scan == nil ? .photoOnly : .saved
            }
        } catch {
            print("Facemaxx capture save failed: \(error.localizedDescription)")
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.22)) {
                captureSaveState = .failed
            }
        }
    }

    private func getRating(using proxy: ScrollViewProxy) {
        guard let selectedModeID else { return }

        if shouldPromptForProScan {
            isProPaywallPresented = true
            Task {
                await purchaseService.refresh()
            }
            return
        }

        guard canStartAnalysis else { return }

        guard isAIAnalysisConsentGranted else {
            pendingConsentAnalysisModeID = selectedModeID
            isAIAnalysisConsentPresented = true
            return
        }

        beginAnalysis(modeID: selectedModeID)

        Task {
            await runAnalysis(modeID: selectedModeID)

            try? await Task.sleep(nanoseconds: reduceMotion ? 10_000_000 : 160_000_000)
            await MainActor.run {
                withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.62)) {
                    proxy.scrollTo(Self.analysisResultID, anchor: .top)
                }
            }
        }
    }

    @MainActor
    private func runAnalysis(modeID: String, didRetryAfterQuotaSync: Bool = false) async {
        guard isAIAnalysisConsentGranted else {
            pendingConsentAnalysisModeID = modeID
            analysisFailureBodyKey = "privacy.aiConsent.error.required"
            analysisState = .failed
            captureSaveState = .idle
            isAIAnalysisConsentPresented = true
            return
        }

        guard let selectedPhoto else {
            analysisFailureBodyKey = "analysis.error.noCreditUsedBody"
            analysisState = .failed
            return
        }
        let requiredPhotoCount = AnalysisMode.minimumPhotoCount(modeID: modeID)
        guard selectedPhotoCount >= requiredPhotoCount else {
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.24)) {
                analysisState = .failed
                captureSaveState = .failed
                analysisFailureBodyKey = "analysis.error.noCreditUsedBody"
            }
            return
        }

        do {
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.18)) {
                captureSaveState = .saving
            }

            let photo = try await ensureUploadedPhoto(for: selectedPhoto)
            let supplementalPhotoLimit = max(0, requiredPhotoCount - 1)
            let supplementalUploads = AnalysisMode.requiresMultiplePhotos(modeID: modeID)
                ? try await ensureUploadedSupplementalPhotos(limit: supplementalPhotoLimit)
                : []
            let photoIDs = ([photo] + supplementalUploads).map(\.id)
            let scanResponse = try await ensureFaceScan(for: photo)
            if scanResponse == nil {
                withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.18)) {
                    captureSaveState = .photoOnly
                }
            }

            let response = try await FacemaxxAPIClient.shared.createAnalysisRun(
                CreateAnalysisRunPayload(
                    modeID: modeID,
                    photoID: photo.id,
                    photoIDs: AnalysisMode.requiresMultiplePhotos(modeID: modeID) ? photoIDs : nil,
                    faceScanCaptureID: scanResponse?.id,
                    source: latestScanPayload?.source ?? "upload",
                    locale: currentAnalysisLocale,
                    onboardingContext: OnboardingPreferencesStore.load()?.analysisContextPayload
                )
            )

            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.36)) {
                analysisRun = response
                requestedModeID = modeID
                analysisState = response.result == nil ? .failed : .completed
                if scanResponse != nil {
                    captureSaveState = .saved
                }
            }
            if response.result != nil, AnalysisMode.isProScanMode(modeID: modeID) {
                purchaseService.consumeProScanIfNeeded()
            }
            if response.result != nil {
                FacemaxxReviewRequester.requestAfterFirstCompletedAnalysis()
            }
            AnalysisJSONCache.shared.store(response)
            HomeActivityStore.shared.recordAnalysisRun(response)
        } catch {
            print("Facemaxx analysis failed: \(error.localizedDescription)")
            if case let FacemaxxAPIError.server(statusCode, _) = error, statusCode == 402 {
                await purchaseService.syncServerStatus()
                if !didRetryAfterQuotaSync, purchaseService.canUseProScan {
                    await runAnalysis(modeID: modeID, didRetryAfterQuotaSync: true)
                    return
                }
                isProPaywallPresented = true
                analysisFailureBodyKey = "analysis.error.proScanRequiredBody"
            } else if AnalysisMode.isProScanMode(modeID: modeID) {
                await purchaseService.refreshServerStatus()
                if isAnalysisTimeout(error) {
                    analysisFailureBodyKey = "analysis.error.timeout.body"
                } else {
                    analysisFailureBodyKey = "analysis.error.noCreditUsedBody"
                }
            } else if isAnalysisTimeout(error) {
                analysisFailureBodyKey = "analysis.error.timeout.body"
            } else {
                analysisFailureBodyKey = "analysis.analysisFailedBody"
            }
            withAnimation(.smooth(duration: reduceMotion ? 0.01 : 0.24)) {
                analysisState = .failed
                captureSaveState = .failed
            }
        }
    }

    private func isAnalysisTimeout(_ error: Error) -> Bool {
        if case FacemaxxAPIError.timeout = error {
            return true
        }
        if case let FacemaxxAPIError.server(statusCode, _) = error, statusCode == 504 {
            return true
        }
        return false
    }

    @MainActor
    private func ensureUploadedPhoto(for image: UIImage) async throws -> PhotoUploadResponse {
        if let uploadedPhoto {
            return uploadedPhoto
        }

        if let uploadPhotoTask {
            do {
                let photo = try await uploadPhotoTask.value
                uploadedPhoto = photo
                self.uploadPhotoTask = nil
                return photo
            } catch {
                self.uploadPhotoTask = nil
                faceScanSaveTask?.cancel()
                faceScanSaveTask = nil
            }
        }

        let task = makePhotoUploadTask(for: image)
        uploadPhotoTask = task
        do {
            let photo = try await task.value
            uploadedPhoto = photo
            uploadPhotoTask = nil
            return photo
        } catch {
            uploadPhotoTask = nil
            throw error
        }
    }

    @MainActor
    private func ensureUploadedSupplementalPhotos(limit: Int? = nil) async throws -> [PhotoUploadResponse] {
        let targetCount = min(max(0, limit ?? supplementalPhotos.count), supplementalPhotos.count)
        guard targetCount > 0 else { return [] }

        if uploadedSupplementalPhotos.count >= targetCount {
            return Array(uploadedSupplementalPhotos.prefix(targetCount))
        }

        ensureSupplementalUploadTasksStarted(upTo: targetCount)

        var uploaded: [PhotoUploadResponse] = []
        uploaded.reserveCapacity(targetCount)
        for index in 0..<targetCount {
            if uploadedSupplementalPhotos.indices.contains(index) {
                uploaded.append(uploadedSupplementalPhotos[index])
                continue
            }

            let image = supplementalPhotos[index]
            let task = supplementalPhotoUploadTasks.indices.contains(index)
                ? supplementalPhotoUploadTasks[index]
                : startSupplementalUploadTask(for: image, at: index)

            do {
                uploaded.append(try await task.value)
            } catch {
                if Task.isCancelled {
                    throw error
                }
                let retryTask = makePhotoUploadTask(for: image)
                supplementalPhotoUploadTasks[index] = retryTask
                uploaded.append(try await retryTask.value)
            }
        }
        uploadedSupplementalPhotos = uploaded
        return uploaded
    }

    @MainActor
    private func ensureFaceScan(for photo: PhotoUploadResponse) async throws -> FaceScanCaptureResponse? {
        if let faceScanResponse {
            return faceScanResponse
        }

        if let faceScanSaveTask {
            do {
                let scan = try await faceScanSaveTask.value
                if var payload = latestScanPayload {
                    payload.photoId = photo.id
                    latestScanPayload = payload
                }
                faceScanResponse = scan
                self.faceScanSaveTask = nil
                if let scan {
                    HomeActivityStore.shared.recordCapture(photo: photo, scan: scan)
                }
                return scan
            } catch {
                self.faceScanSaveTask = nil
                throw error
            }
        }

        guard var payload = latestScanPayload else {
            return nil
        }

        payload.photoId = photo.id
        let task = makeFaceScanTask(payload: payload)
        faceScanSaveTask = task
        do {
            let scan = try await task.value
            latestScanPayload = payload
            faceScanResponse = scan
            faceScanSaveTask = nil
            if let scan {
                HomeActivityStore.shared.recordCapture(photo: photo, scan: scan)
            }
            return scan
        } catch {
            faceScanSaveTask = nil
            throw error
        }
    }

    @MainActor
    private func prepareSelectedPhotoUpload(
        for image: UIImage,
        scanPayload: FaceScanCapturePayload? = nil
    ) {
        guard isAIAnalysisConsentGranted else { return }
        guard uploadedPhoto == nil, uploadPhotoTask == nil else {
            if let scanPayload {
                prepareFaceScanSave(for: scanPayload)
            }
            return
        }

        let uploadTask = makePhotoUploadTask(for: image)
        uploadPhotoTask = uploadTask

        if let scanPayload {
            prepareFaceScanSave(for: scanPayload)
        }
    }

    @MainActor
    private func prepareFaceScanSave(for payload: FaceScanCapturePayload) {
        guard isAIAnalysisConsentGranted else { return }
        guard faceScanResponse == nil, faceScanSaveTask == nil else { return }

        if let uploadedPhoto {
            var preparedPayload = payload
            preparedPayload.photoId = uploadedPhoto.id
            faceScanSaveTask = makeFaceScanTask(payload: preparedPayload)
        } else if let uploadPhotoTask {
            faceScanSaveTask = makeFaceScanTask(after: uploadPhotoTask, payload: payload)
        }
    }

    private func makePhotoUploadTask(for image: UIImage) -> Task<PhotoUploadResponse, Error> {
        Task(priority: .utility) {
            try await FacemaxxAPIClient.shared.uploadPhoto(image)
        }
    }

    private func makeFaceScanTask(payload: FaceScanCapturePayload) -> Task<FaceScanCaptureResponse?, Error> {
        Task(priority: .utility) {
            try await FacemaxxAPIClient.shared.createFaceScan(payload)
        }
    }

    private func makeFaceScanTask(
        after uploadTask: Task<PhotoUploadResponse, Error>,
        payload: FaceScanCapturePayload
    ) -> Task<FaceScanCaptureResponse?, Error> {
        Task(priority: .utility) {
            let photo = try await uploadTask.value
            var preparedPayload = payload
            preparedPayload.photoId = photo.id
            return try await FacemaxxAPIClient.shared.createFaceScan(preparedPayload)
        }
    }

    @MainActor
    private func ensureSupplementalUploadTasksStarted(upTo count: Int? = nil) {
        guard isAIAnalysisConsentGranted else { return }
        let targetCount = min(max(0, count ?? supplementalPhotos.count), supplementalPhotos.count)
        guard supplementalPhotoUploadTasks.count < targetCount else { return }
        for index in supplementalPhotoUploadTasks.count..<targetCount {
            supplementalPhotoUploadTasks.append(makePhotoUploadTask(for: supplementalPhotos[index]))
        }
    }

    @MainActor
    private func startSupplementalUploadTask(
        for image: UIImage,
        at index: Int
    ) -> Task<PhotoUploadResponse, Error> {
        let task = makePhotoUploadTask(for: image)
        if supplementalPhotoUploadTasks.indices.contains(index) {
            supplementalPhotoUploadTasks[index] = task
        } else {
            supplementalPhotoUploadTasks.append(task)
        }
        return task
    }

    private func cancelSupplementalUploadTasks() {
        supplementalPhotoUploadTasks.forEach { $0.cancel() }
    }

    private func beginAnalysis(modeID: String) {
        activeAnalysisModeID = modeID
        analysisRun = nil
        analysisFailureBodyKey = "analysis.analysisFailedBody"
        requestedModeID = nil
        analysisState = .running
    }

    private func grantAIAnalysisConsentAndResume() {
        AIAnalysisConsentStore.grant()
        isAIAnalysisConsentGranted = true
        hasSeenAIAnalysisConsentPrompt = true
        isAIAnalysisConsentPresented = false

        if let selectedPhoto {
            prepareSelectedPhotoUpload(for: selectedPhoto, scanPayload: latestScanPayload)
            ensureSupplementalUploadTasksStarted(upTo: supplementalPhotos.count)
        }

        guard let modeID = pendingConsentAnalysisModeID else { return }
        pendingConsentAnalysisModeID = nil
        guard canStartAnalysis else { return }
        beginAnalysis(modeID: modeID)
        Task {
            await runAnalysis(modeID: modeID)
        }
    }

    private func deferAIAnalysisConsent() {
        AIAnalysisConsentStore.markPromptSeen()
        hasSeenAIAnalysisConsentPrompt = true
        pendingConsentAnalysisModeID = nil
        isAIAnalysisConsentPresented = false
    }

}

struct AnalysisResultContent: View {
    let modeID: String
    let result: AnalysisResultPayload
    let image: UIImage?
    var supplementalImages: [UIImage] = []
    var supplementalScanOverlayImages: [UIImage?] = []
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    var isFreeTrialResult = false
    var unlockAction: () -> Void = {}

    var body: some View {
        resultBody
    }

    @ViewBuilder
    private var resultBody: some View {
        switch modeID {
        case "proportions":
            AestheticsResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: reduceMotion,
                trialAccess: TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult),
                unlockAction: unlockAction
            )
        case "aesthetics":
            ProportionsResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: reduceMotion,
                trialAccess: TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult),
                unlockAction: unlockAction
            )
        case "glow-up-coach":
            GlowUpCoachResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: reduceMotion,
                trialAccess: TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult),
                unlockAction: unlockAction
            )
        case "look-archetype":
            LookArchetypeResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: reduceMotion,
                trialAccess: TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult),
                unlockAction: unlockAction
            )
        case "best-photo-selector", "best-angle-finder", "dating-profile-score", "instagram-profile-score":
            PhotoOptimizationResultSection(
                modeID: modeID,
                result: result,
                image: image,
                supplementalImages: supplementalImages,
                supplementalScanOverlayImages: supplementalScanOverlayImages,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: reduceMotion,
                trialAccess: TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult),
                unlockAction: unlockAction
            )
        default:
            EmptyView()
        }
    }

}

private struct AnalysisFullResultShareView: View {
    let modeID: String
    let result: AnalysisResultPayload
    let image: UIImage?
    let supplementalImages: [UIImage]
    let supplementalScanOverlayImages: [UIImage?]
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let isFreeTrialResult: Bool

    private var modeTitle: String {
        NSLocalizedString(AnalysisModePresentation.titleLocalizationKey(for: modeID), comment: "")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("FACEMAXX")
                    .font(.system(size: 13, weight: .black))
                    .tracking(2.0)
                    .foregroundStyle(FXTheme.textSecondary)

                Spacer()

                Text(modeTitle)
                    .font(.system(size: 13, weight: .black))
                    .foregroundStyle(FXTheme.textPrimary.opacity(0.78))
                    .lineLimit(1)
            }
            .padding(.horizontal, 4)

            resultBody

            Text("facemaxx")
                .font(.system(size: 12, weight: .black))
                .tracking(1.4)
                .foregroundStyle(FXTheme.textMuted)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.horizontal, 4)
        }
        .padding(16)
        .frame(width: 390)
        .fixedSize(horizontal: false, vertical: true)
        .background(FXTheme.background)
    }

    @ViewBuilder
    private var resultBody: some View {
        let trialAccess = TrialResultAccess(modeID: modeID, isFreeTrialResult: isFreeTrialResult)
        switch modeID {
        case "proportions":
            AestheticsResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: true,
                trialAccess: trialAccess,
                unlockAction: {}
            )
        case "aesthetics":
            ProportionsResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: true,
                trialAccess: trialAccess,
                unlockAction: {}
            )
        case "glow-up-coach":
            GlowUpCoachResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: true,
                trialAccess: trialAccess,
                unlockAction: {}
            )
        case "look-archetype":
            LookArchetypeResultSection(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: true,
                trialAccess: trialAccess,
                unlockAction: {}
            )
        case "best-photo-selector", "best-angle-finder", "dating-profile-score", "instagram-profile-score":
            PhotoOptimizationResultSection(
                modeID: modeID,
                result: result,
                image: image,
                supplementalImages: supplementalImages,
                supplementalScanOverlayImages: supplementalScanOverlayImages,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                reduceMotion: true,
                trialAccess: trialAccess,
                unlockAction: {}
            )
        default:
            EmptyView()
        }
    }
}

private struct AnalysisShareCardView: View {
    let modeID: String
    let result: AnalysisResultPayload
    let image: UIImage?

    private var tint: Color {
        AnalysisModePresentation.tint(for: modeID)
    }

    private var modeTitle: String {
        NSLocalizedString(AnalysisModePresentation.titleLocalizationKey(for: modeID), comment: "")
    }

    private var summary: String {
        result.summaryText?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false
            ? result.summaryText ?? ""
            : NSLocalizedString("analysis.results.summaryBody", comment: "")
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.04, green: 0.045, blue: 0.05),
                    Color(red: 0.10, green: 0.10, blue: 0.12),
                    tint.opacity(0.26)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    Text("FACEMAXX")
                        .font(.system(size: 14, weight: .black))
                        .tracking(2.2)
                        .foregroundStyle(tint)

                    Spacer()

                    Text(modeTitle)
                        .font(.system(size: 15, weight: .heavy))
                        .foregroundStyle(.white.opacity(0.76))
                        .lineLimit(1)
                }

                HStack(alignment: .top, spacing: 18) {
                    sharePhoto

                    VStack(alignment: .leading, spacing: 12) {
                        Text(result.lookArchetype?.typeName ?? modeTitle)
                            .font(.system(size: 26, weight: .black))
                            .foregroundStyle(.white)
                            .lineLimit(3)
                            .minimumScaleFactor(0.72)

                        if let score = result.facemaxxOverallScore10 {
                            ShareScorePill(
                                title: NSLocalizedString("analysis.results.overall", comment: ""),
                                value: String(format: "%.1f", score),
                                tint: FacemaxxScorePalette.accent(forProgress: score / 10)
                            )
                        }

                        if let potential = result.facemaxxPotentialScore10 {
                            ShareScorePill(
                                title: NSLocalizedString("analysis.results.potentialScore", comment: ""),
                                value: String(format: "%.1f", potential),
                                tint: FacemaxxScorePalette.accent(forProgress: potential / 10)
                            )
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                Text(summary)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.82))
                    .lineSpacing(5)
                    .lineLimit(7)
                    .fixedSize(horizontal: false, vertical: true)

                Spacer(minLength: 0)

                Text("facemaxx")
                    .font(.system(size: 13, weight: .bold))
                    .tracking(1.4)
                    .foregroundStyle(.white.opacity(0.42))
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .padding(30)
        }
        .frame(width: 390, height: 560)
    }

    @ViewBuilder
    private var sharePhoto: some View {
        if let image {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
                .frame(width: 138, height: 138)
                .clipShape(.rect(cornerRadius: 30, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 30, style: .continuous)
                        .stroke(.white.opacity(0.42), lineWidth: 2)
                }
                .shadow(color: tint.opacity(0.28), radius: 18, y: 10)
        } else {
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(.white.opacity(0.10))
                .frame(width: 138, height: 138)
                .overlay {
                    Image(systemName: "person.crop.square.fill")
                        .font(.system(size: 56, weight: .light))
                        .foregroundStyle(.white.opacity(0.34))
                }
        }
    }
}

private struct TrialResultAccess {
    let modeID: String
    let isFreeTrialResult: Bool

    var primaryMetricLimit: Int? {
        isFreeTrialResult ? 3 : nil
    }

    var secondaryMetricLimit: Int? {
        isFreeTrialResult ? 0 : nil
    }

    var lookSectionLimit: Int? {
        isFreeTrialResult ? 1 : nil
    }

    var shouldShowUnlockCard: Bool {
        isFreeTrialResult
    }
}

private struct TrialLockedMetricRow: View {
    let titleKey: LocalizedStringKey
    var titleText: String? = nil
    let iconName: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(Color.white.opacity(0.075))

                    Image(systemName: FacemaxxSFSymbol.safeName(iconName))
                        .font(.system(size: 18, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary.opacity(0.88))
                }
                .frame(width: 38, height: 38)

                LocalizedOrRemoteText(key: titleKey, text: titleText)
                    .font(.system(size: 17, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.84)
                    .layoutPriority(2)

                Spacer(minLength: 8)

                HStack(spacing: 7) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 11, weight: .black))

                    Text("analysis.trial.proFeatureBadge")
                        .font(.caption2.weight(.black))
                }
                .foregroundStyle(FXTheme.premiumBlue)
                .padding(.horizontal, 9)
                .padding(.vertical, 6)
                .background(FXTheme.premiumBlue.opacity(0.13), in: Capsule(style: .continuous))

                Image(systemName: "chevron.down")
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(FXTheme.textMuted)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            FXTheme.cardElevated.opacity(0.96),
                            FXTheme.card.opacity(0.96)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        }
    }
}

private struct TrialUnlockFullResultsCard: View {
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                Text("analysis.trial.unlockTitle")
                    .font(.title3.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)

                Text("analysis.trial.unlockBody")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Button(action: action) {
                Text("analysis.trial.unlockButton")
                    .font(.headline.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .background(
                        LinearGradient(
                            colors: [FXTheme.premiumBlue, FXTheme.premiumBlue.opacity(0.72)],
                            startPoint: .leading,
                            endPoint: .trailing
                        ),
                        in: Capsule(style: .continuous)
                    )
            }
            .buttonStyle(.plain)
        }
        .padding(18)
        .background(FXTheme.cardElevated.opacity(0.96), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        }
    }
}

private struct ShareScorePill: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        HStack(spacing: 8) {
            Text(title)
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(.white.opacity(0.72))
                .lineLimit(1)

            Spacer(minLength: 6)

            Text("\(value)/10")
                .font(.system(size: 15, weight: .black))
                .monospacedDigit()
                .foregroundStyle(tint)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.white.opacity(0.10), in: Capsule(style: .continuous))
    }
}

private struct PendingPhotoCrop: Identifiable {
    enum Source: String {
        case camera
        case gallery = "upload"
    }

    let id = UUID()
    let source: Source
    let image: UIImage
    let scanOverlayImage: UIImage?
    let scanPayload: FaceScanCapturePayload?
}

@MainActor
private enum FacemaxxReviewRequester {
    private static let didRequestKey = "facemaxx.reviewPrompt.didRequestAfterFirstAnalysis"

    static func requestAfterFirstCompletedAnalysis() {
        let defaults = UserDefaults.standard
        guard !defaults.bool(forKey: didRequestKey) else { return }
        defaults.set(true, forKey: didRequestKey)

        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 1_100_000_000)
            guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive }) else {
                return
            }
            SKStoreReviewController.requestReview(in: scene)
        }
    }
}

private enum AnalysisRequestState: Equatable {
    case idle
    case running
    case completed
    case failed
}

private enum CaptureSaveState: Equatable {
    case idle
    case saving
    case saved
    case photoOnly
    case failed

    var titleKey: LocalizedStringKey {
        switch self {
        case .idle:
            ""
        case .saving:
            "analysis.captureSave.saving"
        case .saved:
            "analysis.captureSave.saved"
        case .photoOnly:
            "analysis.captureSave.photoOnly"
        case .failed:
            "analysis.captureSave.failed"
        }
    }

    var foregroundStyle: Color {
        switch self {
        case .idle:
            FXTheme.textMuted
        case .saving:
            FXTheme.cyan
        case .saved:
            FXTheme.green
        case .photoOnly:
            FXTheme.yellow
        case .failed:
            FXTheme.yellow
        }
    }
}

private extension Array {
    subscript(safe index: Index) -> Element? {
        indices.contains(index) ? self[index] : nil
    }

    mutating func removeIfPresent(at index: Index) {
        guard indices.contains(index) else { return }
        remove(at: index)
    }
}

private enum AnalysisModePresentation {
    static func titleLocalizationKey(for modeID: String) -> String {
        switch modeID {
        case "proportions":
            "analysis.mode.proportions"
        case "aesthetics":
            "analysis.mode.aesthetics"
        case "glow-up-coach":
            "analysis.mode.glowUpCoach"
        case "look-archetype":
            "analysis.mode.lookArchetype"
        case "best-photo-selector":
            "analysis.mode.bestPhotoSelector"
        case "best-angle-finder":
            "analysis.mode.bestAngleFinder"
        case "dating-profile-score":
            "analysis.mode.datingProfileScore"
        case "instagram-profile-score":
            "analysis.mode.instagramProfileScore"
        default:
            "analysis.mode.default"
        }
    }

    static func tint(for modeID: String) -> Color {
        switch modeID {
        case "proportions":
            FXTheme.cyan
        case "aesthetics":
            Color(red: 0.68, green: 0.83, blue: 0.70)
        case "glow-up-coach":
            Color(red: 0.28, green: 0.82, blue: 0.44)
        case "look-archetype":
            Color(red: 0.76, green: 0.72, blue: 0.94)
        case "best-photo-selector":
            Color(red: 0.97, green: 0.45, blue: 0.64)
        case "best-angle-finder":
            Color(red: 0.96, green: 0.69, blue: 0.32)
        case "dating-profile-score":
            Color(red: 0.94, green: 0.42, blue: 0.60)
        case "instagram-profile-score":
            Color(red: 0.58, green: 0.74, blue: 0.98)
        default:
            FXTheme.cyan
        }
    }

    static func categoryKey(for modeID: String) -> LocalizedStringKey {
        switch modeID {
        case "proportions":
            "analysis.mode.category.structure"
        case "aesthetics":
            "analysis.mode.category.balance"
        case "glow-up-coach":
            "analysis.mode.category.coaching"
        case "look-archetype":
            "analysis.mode.category.style"
        case "best-photo-selector":
            "analysis.mode.category.photo"
        case "best-angle-finder":
            "analysis.mode.category.angle"
        case "dating-profile-score":
            "analysis.mode.category.profile"
        case "instagram-profile-score":
            "analysis.mode.category.social"
        default:
            "analysis.mode.category.analysis"
        }
    }

    static func descriptionKey(for modeID: String) -> LocalizedStringKey {
        switch modeID {
        case "proportions":
            "analysis.mode.description.proportions"
        case "aesthetics":
            "analysis.mode.description.aesthetics"
        case "glow-up-coach":
            "analysis.mode.description.glowUpCoach"
        case "look-archetype":
            "analysis.mode.description.lookArchetype"
        case "best-photo-selector":
            "analysis.mode.description.bestPhotoSelector"
        case "best-angle-finder":
            "analysis.mode.description.bestAngleFinder"
        case "dating-profile-score":
            "analysis.mode.description.datingProfileScore"
        case "instagram-profile-score":
            "analysis.mode.description.instagramProfileScore"
        default:
            "analysis.mode.description.default"
        }
    }

    static func requirementKey(for count: Int) -> LocalizedStringKey {
        switch count {
        case 2:
            "analysis.mode.requirement.twoPhotos"
        case 3:
            "analysis.mode.requirement.threePhotos"
        default:
            "analysis.mode.requirement.onePhoto"
        }
    }
}

private struct AnalysisEntryHeader: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("analysis.title")
                .font(.system(size: 31, weight: .black))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.78)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct AnalysisCaptureCard: View {
    let action: (CGPoint) -> Void

    var body: some View {
        HStack(spacing: 13) {
            ZStack {
                Circle()
                    .fill(FXTheme.cyan.opacity(0.16))

                Image(systemName: "camera.fill")
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(FXTheme.cyan)
            }
            .frame(width: 44, height: 44)

            VStack(alignment: .leading, spacing: 5) {
                Text("analysis.uploadPhoto")
                    .font(.headline.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Text("analysis.captureCard.body")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 8)

            Image(systemName: "arrow.up.right")
                .font(.system(size: 14, weight: .black))
                .foregroundStyle(FXTheme.textPrimary.opacity(0.72))
                .frame(width: 32, height: 32)
                .background(Color.white.opacity(0.07), in: Circle())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            FXTheme.card,
            in: RoundedRectangle(cornerRadius: 24, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        )
        .contentShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .gesture(
            SpatialTapGesture(coordinateSpace: .named(AnalysisPhotoSourceMenuCoordinateSpace.name))
                .onEnded { value in
                    action(value.location)
                }
        )
        .accessibilityAddTraits(.isButton)
    }
}

private struct PhotoSourceMenuOverlay: View {
    let anchor: CGPoint
    let containerSize: CGSize
    let dismissAction: () -> Void
    let cameraAction: () -> Void
    let galleryAction: () -> Void

    private var menuWidth: CGFloat {
        min(254, max(1, containerSize.width - 48))
    }

    private let menuHeight: CGFloat = 176

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.black.opacity(0.001)
                .ignoresSafeArea()
                .onTapGesture(perform: dismissAction)

            PhotoSourceMenuCard(
                pointerOffset: pointerOffset,
                cameraAction: cameraAction,
                galleryAction: galleryAction
            )
            .frame(width: menuWidth, height: menuHeight)
            .position(x: menuCenter.x, y: menuCenter.y)
            .fixedMovingLayer()
        }
    }

    private var menuCenter: CGPoint {
        let horizontalMargin: CGFloat = 24
        let topMargin: CGFloat = 76
        let bottomMargin: CGFloat = 116
        let proposedX = anchor.x.clamped(to: horizontalMargin + menuWidth / 2...(containerSize.width - horizontalMargin - menuWidth / 2))
        let proposedY = anchor.y + 18 + menuHeight / 2
        let minY = topMargin + menuHeight / 2
        let maxY = max(minY, containerSize.height - bottomMargin - menuHeight / 2)
        return CGPoint(
            x: proposedX,
            y: proposedY.clamped(to: minY...maxY)
        )
    }

    private var pointerOffset: CGFloat {
        (anchor.x - menuCenter.x).clamped(to: -menuWidth / 2 + 36...menuWidth / 2 - 36)
    }
}

private struct PhotoSourceMenuCard: View {
    let pointerOffset: CGFloat
    let cameraAction: () -> Void
    let galleryAction: () -> Void

    private var menuFill: Color {
        Color(red: 0.055, green: 0.055, blue: 0.060).opacity(0.98)
    }

    var body: some View {
        ZStack(alignment: .top) {
            PhotoSourceMenuPointer()
                .fill(menuFill)
                .frame(width: 28, height: 15)
                .offset(x: pointerOffset, y: -11)

            VStack(spacing: 12) {
                Text("analysis.photoSource.title")
                    .font(.headline.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .padding(.top, 17)

                VStack(spacing: 10) {
                    Button(action: cameraAction) {
                        Text("analysis.photoSource.camera")
                            .font(.headline.weight(.heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .frame(maxWidth: .infinity, minHeight: 48)
                            .background(Color.white.opacity(0.065), in: Capsule(style: .continuous))
                    }
                    .buttonStyle(.plain)

                    Button(action: galleryAction) {
                        Text("analysis.photoSource.gallery")
                            .font(.headline.weight(.heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .frame(maxWidth: .infinity, minHeight: 48)
                            .background(Color.white.opacity(0.065), in: Capsule(style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, 18)
            }
            .padding(.bottom, 16)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(menuFill)
                .shadow(color: .black.opacity(0.46), radius: 22, y: 12)
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(0.075), lineWidth: 1)
        }
    }
}

private struct PhotoSourceMenuPointer: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}

private struct AnalysisModeChooser: View {
    let modes: [AnalysisMode]
    let selectedModeID: String?
    let lockedModeIDs: Set<String>
    let selectedPhotoCount: Int
    let reduceMotion: Bool
    let selectAction: (AnalysisMode) -> Void

    private var selectedMode: AnalysisMode? {
        modes.first { $0.id == selectedModeID } ?? modes.first
    }

    private var selectedIndex: Int {
        guard let selectedMode else { return 0 }
        return modes.firstIndex { $0.id == selectedMode.id } ?? 0
    }

    private var columns: [GridItem] {
        [
            GridItem(.flexible(), spacing: 9),
            GridItem(.flexible(), spacing: 9)
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let selectedMode {
                AnalysisSelectedModeCard(
                    mode: selectedMode,
                    index: selectedIndex,
                    totalCount: modes.count,
                    isLocked: lockedModeIDs.contains(selectedMode.id),
                    selectedPhotoCount: selectedPhotoCount
                )
                .id(selectedMode.id)
                .transition(
                    reduceMotion
                    ? .opacity
                    : .asymmetric(
                        insertion: .opacity.combined(with: .offset(y: 12)).combined(with: .scale(scale: 0.985)),
                        removal: .opacity.combined(with: .offset(y: -8))
                    )
                )
            }

            HStack(alignment: .center) {
                Text("analysis.modeSection.title")
                    .font(.headline.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer(minLength: 10)

                Text("analysis.modeSection.count")
                    .font(.caption.weight(.black))
                    .foregroundStyle(FXTheme.textSecondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Color.white.opacity(0.06), in: Capsule())
            }

            LazyVGrid(columns: columns, spacing: 9) {
                ForEach(Array(modes.enumerated()), id: \.element.id) { index, mode in
                    Button {
                        selectAction(mode)
                    } label: {
                        AnalysisModeTile(
                            mode: mode,
                            index: index,
                            isLocked: lockedModeIDs.contains(mode.id),
                            isSelected: selectedModeID == mode.id
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .animation(.spring(response: reduceMotion ? 0.01 : 0.38, dampingFraction: 0.86), value: selectedModeID)
    }
}

private struct AnalysisSelectedModeCard: View {
    let mode: AnalysisMode
    let index: Int
    let totalCount: Int
    let isLocked: Bool
    let selectedPhotoCount: Int

    private var tint: Color {
        AnalysisModePresentation.tint(for: mode.id)
    }

    private var isPhotoReady: Bool {
        selectedPhotoCount >= mode.minimumPhotoCount
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(alignment: .top, spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(tint.opacity(0.16))

                    Image(systemName: mode.iconName)
                        .font(.system(size: 27, weight: .heavy))
                        .foregroundStyle(tint)
                }
                .frame(width: 58, height: 58)

                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(String(format: "%02d", index + 1))
                            .font(.caption.weight(.black).monospacedDigit())
                            .foregroundStyle(tint)

                        Text(AnalysisModePresentation.categoryKey(for: mode.id))
                            .font(.caption.weight(.black))
                            .foregroundStyle(FXTheme.textMuted)
                    }

                    Text(mode.titleKey)
                        .font(.system(size: 24, weight: .black))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(2)
                        .minimumScaleFactor(0.82)
                }

                Spacer(minLength: 8)

                if isLocked {
                    Label("analysis.trial.proFeatureBadge", systemImage: "lock.fill")
                        .font(.caption.weight(.black))
                        .foregroundStyle(FXTheme.premiumBlue)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(FXTheme.premiumBlue.opacity(0.16), in: Capsule())
                } else {
                    Text("\(index + 1)/\(totalCount)")
                        .font(.caption.weight(.black).monospacedDigit())
                        .foregroundStyle(FXTheme.textSecondary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(Color.white.opacity(0.07), in: Capsule())
                }
            }

            Text(isLocked ? "analysis.trial.modeLockedDescription" : AnalysisModePresentation.descriptionKey(for: mode.id))
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 10) {
                Label(AnalysisModePresentation.requirementKey(for: mode.minimumPhotoCount), systemImage: "photo")
                    .font(.caption.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary.opacity(0.84))
                    .padding(.horizontal, 11)
                    .padding(.vertical, 8)
                    .background(Color.white.opacity(0.07), in: Capsule())

                readinessLabel
                    .font(.caption.weight(.black))
                    .foregroundStyle(isLocked ? FXTheme.premiumBlue : (isPhotoReady ? FXTheme.green : FXTheme.textMuted))
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)

                Spacer(minLength: 0)
            }
        }
        .padding(18)
        .background(
            LinearGradient(
                colors: [
                    tint.opacity(0.18),
                    Color.white.opacity(0.075),
                    FXTheme.card.opacity(0.98)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 30, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(tint.opacity(0.30), lineWidth: 1)
        )
    }

    @ViewBuilder
    private var readinessLabel: some View {
        if isLocked {
            Text("analysis.trial.proFeatureShort")
        } else if selectedPhotoCount <= 0 {
            Text("analysis.modeDetail.needPhoto")
        } else if isPhotoReady {
            Text("analysis.modeDetail.ready")
        } else {
            Text("\(min(selectedPhotoCount, mode.minimumPhotoCount))/\(mode.minimumPhotoCount) ")
            + Text("analysis.modeDetail.photoProgressSuffix")
        }
    }
}

private struct AnalysisModeTile: View {
    let mode: AnalysisMode
    let index: Int
    let isLocked: Bool
    let isSelected: Bool

    private var tint: Color {
        AnalysisModePresentation.tint(for: mode.id)
    }

    var body: some View {
        HStack(spacing: 9) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(tint.opacity(isSelected ? 0.22 : 0.11))

                Image(systemName: mode.iconName)
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundStyle(isSelected ? tint : FXTheme.textPrimary.opacity(0.72))
            }
            .frame(width: 34, height: 34)

            VStack(alignment: .leading, spacing: 3) {
                Text(mode.titleKey)
                    .font(.caption.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.70)

                Text(AnalysisModePresentation.categoryKey(for: mode.id))
                    .font(.caption2.weight(.black))
                    .tracking(0.6)
                    .foregroundStyle(isSelected ? tint : FXTheme.textMuted)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            trailingMarker
                .frame(width: 24, alignment: .trailing)
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 17, style: .continuous)
                .fill(isSelected ? tint.opacity(0.13) : FXTheme.card)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 17, style: .continuous)
                .stroke(isSelected ? tint.opacity(0.52) : FXTheme.cardStroke, lineWidth: isSelected ? 1.4 : 1)
        )
        .contentShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
    }

    @ViewBuilder
    private var trailingMarker: some View {
        if isLocked {
            Image(systemName: "lock.fill")
                .font(.system(size: 13, weight: .black))
                .foregroundStyle(isSelected ? tint : FXTheme.textMuted)
        } else if isSelected {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(tint)
        } else {
            Text(String(format: "%02d", index + 1))
                .font(.caption2.weight(.black).monospacedDigit())
                .foregroundStyle(FXTheme.textMuted)
        }
    }
}

private struct AnalysisRunPanel: View {
    let isPrepared: Bool
    let canStartAnalysis: Bool
    let shouldOpenPaywall: Bool
    let isQuotaExhausted: Bool
    let isFreeTrialLockedMode: Bool
    let requiresProScan: Bool
    let selectedMode: AnalysisMode?
    let photoCount: Int
    let requiredPhotoCount: Int
    let captureSaveState: CaptureSaveState
    let scanBalanceText: String
    let usesFreeTrialScan: Bool
    let runAction: () -> Void

    private var tint: Color {
        selectedMode.map { AnalysisModePresentation.tint(for: $0.id) } ?? FXTheme.cyan
    }

    private var canActivateButton: Bool {
        canStartAnalysis || shouldOpenPaywall
    }

    private var buttonFill: Color {
        if canStartAnalysis {
            return FXTheme.textPrimary
        }

        if shouldOpenPaywall {
            return FXTheme.premiumBlue
        }

        return Color.white.opacity(0.07)
    }

    private var buttonForeground: Color {
        if canStartAnalysis {
            return Color.black
        }

        if shouldOpenPaywall {
            return FXTheme.textPrimary
        }

        return FXTheme.textMuted
    }

    private var buttonTitleKey: LocalizedStringKey {
        if isFreeTrialLockedMode {
            return "analysis.trial.unlockModeButton"
        }

        if shouldOpenPaywall {
            return "analysis.run.unlockButton"
        }

        if isQuotaExhausted {
            return "analysis.run.noScansButton"
        }

        return "analysis.getRating"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(alignment: .center, spacing: 12) {
                Circle()
                    .fill((isPrepared ? tint : FXTheme.textMuted).opacity(isPrepared ? 0.92 : 0.18))
                    .frame(width: 10, height: 10)

                VStack(alignment: .leading, spacing: 4) {
                    Text(isPrepared ? "analysis.run.readyTitle" : "analysis.run.waitingTitle")
                        .font(.headline.weight(.black))
                        .foregroundStyle(FXTheme.textPrimary)

                    statusLabel
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)

                if !usesFreeTrialScan {
                    Text(scanBalanceText)
                        .font(.caption.weight(.black))
                        .foregroundStyle(FXTheme.textMuted)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                }
            }

            Button(action: runAction) {
                HStack(spacing: 9) {
                    if shouldOpenPaywall {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 13, weight: .black))
                    }

                    Text(buttonTitleKey)
                        .font(.headline.weight(.black))

                    Image(systemName: canStartAnalysis ? "arrow.right" : "chevron.right")
                        .font(.system(size: 15, weight: .black))
                }
                .foregroundStyle(buttonForeground)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(buttonFill, in: Capsule())
                .overlay(
                    Capsule(style: .continuous)
                        .stroke(canActivateButton ? Color.clear : Color.white.opacity(0.08), lineWidth: 1)
                )
            }
            .buttonStyle(.plain)
            .disabled(!canActivateButton)

            if captureSaveState != .idle {
                Text(captureSaveState.titleKey)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(captureSaveState.foregroundStyle)
                    .transition(.opacity)
            }
        }
        .padding(18)
        .background(FXTheme.card, in: RoundedRectangle(cornerRadius: 30, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        )
    }

    @ViewBuilder
    private var statusLabel: some View {
        if selectedMode == nil {
            Text("analysis.run.chooseMode")
        } else if photoCount <= 0 {
            Text("analysis.run.needPhoto")
        } else if photoCount < requiredPhotoCount {
            Text("\(min(photoCount, requiredPhotoCount))/\(requiredPhotoCount) ")
            + Text("analysis.run.photoProgressSuffix")
        } else if isFreeTrialLockedMode {
            Text("analysis.trial.modeLockedRunStatus")
        } else if usesFreeTrialScan {
            Text("analysis.run.freeTrialReady")
        } else if isQuotaExhausted {
            Text("analysis.run.quotaExhausted")
        } else if shouldOpenPaywall {
            Text("analysis.run.proScanRequired")
        } else if requiresProScan {
            Text("analysis.run.readyBody")
        } else {
            Text("analysis.run.readyBody")
        }
    }
}

private struct MultiPhotoRequirementCard: View {
    let photoCount: Int
    let requiredCount: Int
    let supplementalPhotos: [UIImage]
    let canAddMore: Bool
    let addPhotoAction: () -> Void

    private var isReady: Bool {
        photoCount >= requiredCount
    }

    private var canRequestMorePhotos: Bool {
        canAddMore && !isReady
    }

    private var addPhotoTitleKey: LocalizedStringKey {
        photoCount == 0 ? "analysis.multiPhoto.addFirst" : "analysis.multiPhoto.addAnother"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: isReady ? "checkmark.circle.fill" : "photo.on.rectangle.angled")
                    .font(.title3.weight(.bold))
                    .foregroundStyle(isReady ? FXTheme.green : FXTheme.cyan)
                    .frame(width: 28)

                VStack(alignment: .leading, spacing: 5) {
                    Text(LocalizedStringKey(isReady ? "analysis.multiPhoto.readyTitle" : "analysis.multiPhoto.title"))
                        .font(.subheadline.weight(.heavy))
                        .foregroundStyle(FXTheme.textPrimary)

                    Text(LocalizedStringKey(isReady ? "analysis.multiPhoto.readyBody" : "analysis.multiPhoto.body"))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)

                Text("\(min(photoCount, requiredCount))/\(requiredCount)")
                    .font(.caption.weight(.heavy))
                    .foregroundStyle(isReady ? FXTheme.green : FXTheme.cyan)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Color.white.opacity(0.08), in: Capsule())
            }

            HStack(spacing: 10) {
                ForEach(Array(supplementalPhotos.prefix(3).enumerated()), id: \.offset) { _, image in
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(width: 44, height: 44)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .stroke(Color.white.opacity(0.16), lineWidth: 1)
                        )
                }

                Button(action: addPhotoAction) {
                    Label(addPhotoTitleKey, systemImage: "plus")
                    .font(.caption.weight(.heavy))
                    .foregroundStyle(canRequestMorePhotos ? FXTheme.textPrimary : FXTheme.textMuted)
                    .frame(maxWidth: .infinity)
                    .frame(height: 44)
                    .background(Color.white.opacity(canRequestMorePhotos ? 0.10 : 0.055), in: Capsule())
                }
                .buttonStyle(.plain)
                .disabled(!canRequestMorePhotos)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .background(FXTheme.card, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(isReady ? FXTheme.green.opacity(0.32) : FXTheme.cyan.opacity(0.24), lineWidth: 1)
        )
    }
}

private struct AnalysisPerformanceWarning: View {
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.subheadline.weight(.bold))
                .foregroundStyle(FXTheme.yellow.opacity(0.82))

            Text("analysis.performanceWarning")
                .font(.caption.weight(.semibold))
                .multilineTextAlignment(.leading)
                .foregroundStyle(FXTheme.textMuted)

            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
        .padding(.vertical, 13)
        .background {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(FXTheme.card)
        }
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        }
    }
}

private struct AnalysisLoadingOverlay: View {
    @State private var appeared = false

    var body: some View {
        ZStack {
            Color.black.opacity(0.10)
                .ignoresSafeArea()

            VStack(spacing: 2) {
                FacemaxxLottieView(animationName: "scan_loading")
                    .frame(width: 246, height: 246)
                    .accessibilityHidden(true)
                    .shadow(color: FXTheme.cyan.opacity(0.16), radius: 28, y: 10)

                Text("analysis.loading.title")
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .shadow(color: .black.opacity(0.54), radius: 10, y: 4)
                    .padding(.top, -20)

                Text("analysis.loading.subtitle")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .padding(.horizontal, 18)
                    .padding(.top, 7)
                    .shadow(color: .black.opacity(0.52), radius: 10, y: 4)
            }
            .frame(maxWidth: 310)
            .scaleEffect(appeared ? 1 : 0.985)
            .opacity(appeared ? 1 : 0)
        }
        .onAppear {
            withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
                appeared = true
            }
        }
    }
}

private struct AnalysisLoadingSection: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var activeStep = 0
    @State private var appeared = false

    private var progress: Double {
        Double(min(activeStep + 1, 4)) / 4.0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 9) {
                    Text("analysis.loading.title")
                        .font(.system(size: 23, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(2)
                        .minimumScaleFactor(0.78)

                    Text("analysis.loading.subtitle")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)

                }

                Spacer(minLength: 0)

                Text("\(Int(progress * 100))%")
                    .font(.system(size: 18, weight: .heavy, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(FXTheme.cyan)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color.white.opacity(0.060), in: Capsule())
            }

            AnalysisPipelineVisual(progress: progress, activeIndex: activeStep, isActive: !reduceMotion)
                .frame(height: 78)

            VStack(spacing: 6) {
                AnalysisLoadingStep(titleKey: "analysis.loading.step.photo", index: 0, activeIndex: activeStep)
                AnalysisLoadingStep(titleKey: "analysis.loading.step.geometry", index: 1, activeIndex: activeStep)
                AnalysisLoadingStep(titleKey: "analysis.loading.step.gemini", index: 2, activeIndex: activeStep)
                AnalysisLoadingStep(titleKey: "analysis.loading.step.report", index: 3, activeIndex: activeStep)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(20)
        .background(
            LinearGradient(
                colors: [
                    Color.white.opacity(0.052),
                    Color.white.opacity(0.026)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 30, style: .continuous)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(Color.white.opacity(0.09), lineWidth: 1)
        }
        .opacity(appeared ? 1 : 0)
        .offset(y: appeared ? 0 : 14)
        .onAppear {
            withAnimation(.spring(response: 0.48, dampingFraction: 0.84)) {
                appeared = true
            }
        }
        .task {
            if reduceMotion {
                activeStep = 3
                return
            }
            for index in 0..<4 {
                try? await Task.sleep(nanoseconds: UInt64(index == 0 ? 260_000_000 : 680_000_000))
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    withAnimation(.spring(response: 0.34, dampingFraction: 0.84)) {
                        activeStep = index
                    }
                }
            }
        }
    }
}

private struct AnalysisPipelineVisual: View {
    let progress: Double
    let activeIndex: Int
    let isActive: Bool

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = isActive ? timeline.date.timeIntervalSinceReferenceDate : 0

            GeometryReader { proxy in
                let width = proxy.size.width
                let y = proxy.size.height / 2
                let dotCount = 4
                let xPositions = (0..<dotCount).map { index in
                    CGFloat(index) * (width - 34) / CGFloat(dotCount - 1) + 17
                }

                ZStack(alignment: .leading) {
                    Capsule(style: .continuous)
                        .fill(Color.white.opacity(0.075))
                        .frame(height: 7)
                        .position(x: width / 2, y: y)

                    Capsule(style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [FXTheme.cyan, FXTheme.blue.opacity(0.72)],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: max(12, width * progress), height: 7)
                        .position(x: max(6, width * progress / 2), y: y)
                        .animation(.spring(response: 0.38, dampingFraction: 0.84), value: progress)

                    Capsule(style: .continuous)
                        .fill(Color.white.opacity(0.82))
                        .frame(width: 20, height: 3)
                        .position(
                            x: min(width - 14, max(14, width * progress + CGFloat(sin(time * 2.0)) * 4)),
                            y: y
                        )
                        .opacity(isActive ? 0.78 : 0.34)

                    ForEach(0..<dotCount, id: \.self) { index in
                        let isDone = index < activeIndex
                        let isCurrent = index == activeIndex

                        ZStack {
                            Circle()
                                .fill(isDone || isCurrent ? FXTheme.cyan : FXTheme.background)
                                .frame(width: isCurrent ? 28 : 22, height: isCurrent ? 28 : 22)

                            Circle()
                                .stroke(isDone || isCurrent ? Color.white.opacity(0.72) : Color.white.opacity(0.20), lineWidth: 1)
                                .frame(width: isCurrent ? 28 : 22, height: isCurrent ? 28 : 22)

                            if isDone {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 10, weight: .heavy))
                                    .foregroundStyle(Color.black.opacity(0.74))
                            } else {
                                Circle()
                                    .fill(isCurrent ? Color.black.opacity(0.72) : Color.white.opacity(0.20))
                                    .frame(width: 5, height: 5)
                            }
                        }
                        .position(x: xPositions[index], y: y)
                        .animation(.spring(response: 0.34, dampingFraction: 0.82), value: activeIndex)
                    }
                }
            }
        }
        .accessibilityHidden(true)
    }
}

private struct AnalysisLoadingStep: View {
    let titleKey: LocalizedStringKey
    let index: Int
    let activeIndex: Int

    private var isDone: Bool { index < activeIndex }
    private var isCurrent: Bool { index == activeIndex }

    var body: some View {
        HStack(spacing: 12) {
            Capsule(style: .continuous)
                .fill(isDone ? FXTheme.green : (isCurrent ? FXTheme.cyan : Color.white.opacity(0.18)))
                .frame(width: isCurrent ? 22 : 12, height: 6)

            Text(titleKey)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(isCurrent || isDone ? FXTheme.textPrimary : FXTheme.textMuted)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 2)
        .padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(isCurrent ? Color.white.opacity(0.040) : Color.clear)
        }
    }
}

private struct AnalysisFailureSection: View {
    let bodyKey: LocalizedStringKey

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.title.weight(.heavy))
                .foregroundStyle(FXTheme.yellow)

            Text("analysis.analysisFailed")
                .font(.title3.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)

            Text(bodyKey)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 22)
        .padding(.vertical, 26)
        .fxCard(cornerRadius: 30)
    }
}

private struct LocalizedOrRemoteText: View {
    let key: LocalizedStringKey?
    let text: String?

    var body: some View {
        if let remoteText, !remoteText.isEmpty {
            Text(remoteText)
        } else if let key {
            Text(key)
        }
    }

    private var remoteText: String? {
        guard let text else { return nil }
        let collapsed = text
            .replacingOccurrences(of: "\\s+\\.\\s+", with: " · ", options: .regularExpression)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return collapsed.isEmpty ? nil : collapsed
    }
}

private struct AnalysisMetricValueLabel: View {
    let key: LocalizedStringKey
    let text: String?
    let tint: Color
    var isVisible = true
    var frameWidth: CGFloat? = 108
    var frameAlignment: Alignment = .trailing
    var textAlignment: TextAlignment = .trailing

    var body: some View {
        LocalizedOrRemoteText(key: key, text: text)
            .font(.system(size: 14.5, weight: .bold, design: .rounded))
            .foregroundStyle(tint)
            .monospacedDigit()
            .multilineTextAlignment(textAlignment)
            .lineLimit(2)
            .minimumScaleFactor(0.86)
            .allowsTightening(true)
            .truncationMode(.tail)
            .fixedSize(horizontal: false, vertical: true)
            .frame(width: frameWidth, alignment: frameAlignment)
            .opacity(isVisible ? 1 : 0)
            .stableDuringListMotion()
    }
}

private struct AnalysisPhotoPreview: View {
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    var showsAnalysisOverlay = false

    @State private var showsOverlay = true
    @State private var photoLandmarks: [String: [[Double]]]?

    var body: some View {
        GeometryReader { proxy in
            let side = min(proxy.size.width, proxy.size.height)

            ZStack {
                if let image {
                    ZStack {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFill()
                            .frame(width: side, height: side)
                            .clipped()

                        if showsAnalysisOverlay {
                            scanOverlay(for: image, side: side)
                                .opacity(showsOverlay ? 1 : 0)
                                .scaleEffect(showsOverlay ? 1 : 0.985)
                                .allowsHitTesting(false)
                        }
                    }
                    .frame(width: side, height: side)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        guard showsAnalysisOverlay else { return }
                        withAnimation(.smooth(duration: 0.34)) {
                            showsOverlay.toggle()
                        }
                    }
                    .task(id: ObjectIdentifier(image)) {
                        showsOverlay = true
                        guard showsAnalysisOverlay, scanOverlayImage == nil else {
                            photoLandmarks = nil
                            return
                        }
                        photoLandmarks = FaceResultScanOverlay.detectLandmarks(from: image)
                    }
                } else {
                    LandmarkFacePreview()
                        .frame(width: side, height: side)
                        .clipped()
                }
            }
            .frame(width: side, height: side)
            .position(x: proxy.size.width / 2, y: proxy.size.height / 2)
            .overlay(alignment: .bottom) {
                if image != nil, showsAnalysisOverlay {
                    Text(LocalizedStringKey(showsOverlay ? "analysis.result.tapPhoto" : "analysis.result.tapPhotoRestore"))
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.72))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background {
                            Capsule(style: .continuous)
                                .fill(Color.black.opacity(0.38))
                        }
                        .padding(.bottom, 8)
                        .allowsHitTesting(false)
                }
            }
            .clipShape(.rect(cornerRadius: 31, style: .continuous))
        }
        .aspectRatio(1, contentMode: .fit)
        .clipped()
    }

    private func preferredOverlayLandmarks(for image: UIImage) -> [String: [[Double]]]? {
        if scanPayloadMatches(image: image) {
            return scanPayload?.geometry.landmarks2D ?? photoLandmarks
        }
        return photoLandmarks
    }

    @ViewBuilder
    private func scanOverlay(for image: UIImage, side: CGFloat) -> some View {
        if let scanOverlayImage {
            Image(uiImage: scanOverlayImage)
                        .resizable()
                        .scaledToFill()
                        .frame(width: side, height: side)
                        .clipped()
        } else {
            FaceResultScanOverlay(
                imageSize: image.size,
                landmarks: preferredOverlayLandmarks(for: image),
                drawsLandmarkPoints: false
            )
            .frame(width: side, height: side)
        }
    }

    private func scanPayloadMatches(image: UIImage) -> Bool {
        guard let scanPayload,
              let payloadWidth = scanPayload.imageWidth,
              let payloadHeight = scanPayload.imageHeight else {
            return true
        }
        let imageWidth = Int(image.size.width * image.scale)
        let imageHeight = Int(image.size.height * image.scale)
        return abs(payloadWidth - imageWidth) <= 2 && abs(payloadHeight - imageHeight) <= 2
    }

    private static func landmarkQuality(_ landmarks: [String: [[Double]]]) -> Double {
        let allPoints = landmarks.values.flatMap { $0 }.compactMap { raw -> CGPoint? in
            guard raw.count >= 2 else { return nil }
            return CGPoint(x: raw[0], y: raw[1])
        }
        guard let bounds = allPoints.boundingRect else { return 0 }

        let aspect = bounds.width / max(bounds.height, 0.001)
        let aspectScore = (0.34...1.42).contains(aspect) ? 2.0 : 0.0
        let sizeScore = bounds.width > 0.08 && bounds.height > 0.12 ? 1.0 : 0.0
        let contourScore = landmarks["faceContour"]?.isEmpty == false ? 1.0 : 0.0
        return aspectScore + sizeScore + contourScore + min(Double(allPoints.count) / 90.0, 1.0)
    }
}

private struct AnalysisResultPhotoFrame: View {
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    var side: CGFloat = 204
    var showsAnalysisOverlay = true

    var body: some View {
        AnalysisPhotoPreview(
            image: image,
            scanPayload: scanPayload,
            scanOverlayImage: scanOverlayImage,
            showsAnalysisOverlay: showsAnalysisOverlay
        )
            .frame(width: side, height: side)
            .padding(4)
            .background {
                RoundedRectangle(cornerRadius: 36, style: .continuous)
                    .fill(FXTheme.cardElevated.opacity(0.72))
                    .overlay {
                        RoundedRectangle(cornerRadius: 36, style: .continuous)
                            .stroke(Color.white.opacity(0.55), lineWidth: 3)
                    }
                    .shadow(color: .white.opacity(0.14), radius: 12)
                    .shadow(color: .black.opacity(0.24), radius: 16, y: 10)
            }
            .accessibilityLabel("analysis.results.analyzedImage")
            .fixedMovingLayer()
    }
}

struct FaceResultScanOverlay: View {
    let imageSize: CGSize
    let landmarks: [String: [[Double]]]?
    var drawsLandmarkPoints = true

    var body: some View {
        Canvas { context, size in
            guard let mesh = makeMesh(in: size) else { return }
            drawFaceGlow(in: mesh.faceRect, outline: mesh.outline, context: &context)
            drawDepthHints(in: mesh.faceRect, context: &context)
            drawMeshSegments(mesh.segments, context: &context)
            if drawsLandmarkPoints {
                drawLandmarkPoints(mesh.landmarkPoints, context: &context)
            }
        }
        .allowsHitTesting(false)
        .drawingGroup(opaque: false, colorMode: .linear)
    }

    private func drawFaceGlow(in rect: CGRect, outline: [CGPoint], context: inout GraphicsContext) {
        let shell = Path(ellipseIn: rect.insetBy(dx: -rect.width * 0.025, dy: -rect.height * 0.035))
        context.stroke(shell, with: .color(.white.opacity(0.12)), lineWidth: 1.4)

        guard outline.count > 2 else { return }
        var path = Path()
        path.move(to: outline[0])
        for point in outline.dropFirst() {
            path.addLine(to: point)
        }
        context.stroke(path, with: .color(.white.opacity(0.30)), lineWidth: 0.6)
    }

    private func drawMeshSegments(_ segments: [FaceResultSegment], context: inout GraphicsContext) {
        var path = Path()
        for segment in segments {
            path.move(to: segment.start)
            path.addLine(to: segment.end)
        }
        context.stroke(path, with: .color(.white.opacity(0.48)), lineWidth: 0.34)
    }

    private func drawDepthHints(in rect: CGRect, context: inout GraphicsContext) {
        var vertical = Path()
        vertical.move(to: CGPoint(x: rect.midX, y: rect.minY + rect.height * 0.10))
        vertical.addCurve(
            to: CGPoint(x: rect.midX, y: rect.maxY - rect.height * 0.08),
            control1: CGPoint(x: rect.midX + rect.width * 0.045, y: rect.midY - rect.height * 0.18),
            control2: CGPoint(x: rect.midX - rect.width * 0.035, y: rect.midY + rect.height * 0.16)
        )
        context.stroke(vertical, with: .color(FXTheme.cyan.opacity(0.32)), lineWidth: 0.8)

        var horizontal = Path()
        horizontal.move(to: CGPoint(x: rect.minX + rect.width * 0.08, y: rect.midY - rect.height * 0.02))
        horizontal.addLine(to: CGPoint(x: rect.maxX - rect.width * 0.08, y: rect.midY - rect.height * 0.02))
        context.stroke(horizontal, with: .color(FXTheme.cyan.opacity(0.26)), lineWidth: 0.8)
    }

    private func drawLandmarkPoints(_ points: [CGPoint], context: inout GraphicsContext) {
        for point in points {
            let radius: CGFloat = 1.35
            let rect = CGRect(
                x: point.x - radius,
                y: point.y - radius,
                width: radius * 2,
                height: radius * 2
            )
            context.fill(Path(ellipseIn: rect), with: .color(FXTheme.blue.opacity(0.82)))
        }
    }

    private func makeMesh(in canvasSize: CGSize) -> FaceResultMesh? {
        guard let landmarks, !landmarks.isEmpty else { return nil }
        let groups = landmarks.mapValues { values in
            values.compactMap(normalizedPoint)
        }.filter { !$0.value.isEmpty }
        let landmarkPoints = groups.values.flatMap { $0 }
        guard !landmarkPoints.isEmpty else { return nil }

        let outline = groups["faceContour"] ?? []
        let normalizedFaceRect = fittedFaceRect(outline: outline, fallbackPoints: landmarkPoints)
        let normalizedMesh = fittedMesh(
            faceRect: normalizedFaceRect,
            outline: outline,
            landmarkPoints: landmarkPoints,
            nosePoints: (groups["nose"] ?? []) + (groups["noseCrest"] ?? [])
        )
        let semanticSegments = groups.values.flatMap { segments(from: $0, closed: false) }
        let mapper = FaceResultAspectFillMapper(imageSize: imageSize, containerSize: canvasSize)

        return FaceResultMesh(
            faceRect: mapper.rect(normalizedFaceRect),
            outline: outline.map(mapper.point),
            landmarkPoints: landmarkPoints.map(mapper.point),
            segments: (normalizedMesh + semanticSegments).map {
                FaceResultSegment(start: mapper.point($0.start), end: mapper.point($0.end))
            }
        )
    }

    private func normalizedPoint(_ raw: [Double]) -> CGPoint? {
        guard raw.count >= 2 else { return nil }
        return CGPoint(x: raw[0], y: raw[1]).clampedToUnit()
    }

    private func fittedFaceRect(outline: [CGPoint], fallbackPoints: [CGPoint]) -> CGRect {
        let base = outline.boundingRect ?? fallbackPoints.boundingRect ?? CGRect(x: 0.25, y: 0.15, width: 0.5, height: 0.68)
        let sideExpansion = base.width * 0.06
        let topExpansion = base.height * 0.15
        let bottomExpansion = base.height * 0.04
        return CGRect(
            x: base.minX - sideExpansion,
            y: base.minY - topExpansion,
            width: base.width + sideExpansion * 2,
            height: base.height + topExpansion + bottomExpansion
        ).clampedToUnit()
    }

    private func fittedMesh(
        faceRect: CGRect,
        outline: [CGPoint],
        landmarkPoints: [CGPoint],
        nosePoints: [CGPoint]
    ) -> [FaceResultSegment] {
        let outlineBounds = outline.boundingRect ?? faceRect
        let centerX = nosePoints.boundingRect?.midX ?? landmarkPoints.boundingRect?.midX ?? faceRect.midX
        let rowCount = 21
        var rows: [[CGPoint]] = []

        for rowIndex in 0..<rowCount {
            let rowProgress = CGFloat(rowIndex) / CGFloat(rowCount - 1)
            let y = faceRect.minY + faceRect.height * (0.055 + rowProgress * 0.875)
            let normalizedY = (rowProgress - 0.48) / 0.57
            let widthScale = sqrt(max(0, 1 - normalizedY * normalizedY))
            let contourWidth = estimatedFaceWidth(
                rowProgress: rowProgress,
                meshWidth: faceRect.width,
                contourWidth: outlineBounds.width
            ) * widthScale
            let columns = max(7, Int(round(9 + 10 * widthScale)))
            let rowCenterX = centerX + faceRect.width * (rowProgress - 0.48) * 0.018
            var rowPoints: [CGPoint] = []

            for columnIndex in 0...columns {
                let columnProgress = CGFloat(columnIndex) / CGFloat(columns)
                let stagger = rowIndex.isMultiple(of: 2) ? 0 : (1 / CGFloat(max(columns, 1))) * 0.26
                let xProgress = min(1, max(0, columnProgress + stagger))
                let x = rowCenterX + (xProgress - 0.5) * contourWidth
                rowPoints.append(CGPoint(x: x, y: y).clampedToUnit())
            }

            rows.append(rowPoints)
        }

        var result = rows.flatMap { segments(from: $0, closed: false) }
        for rowIndex in 1..<rows.count {
            let previous = rows[rowIndex - 1]
            for point in rows[rowIndex] {
                for nearest in nearestTwoPoints(to: point, in: previous) {
                    result.append(FaceResultSegment(start: point, end: nearest))
                }
            }
        }
        return result
    }

    private func estimatedFaceWidth(rowProgress: CGFloat, meshWidth: CGFloat, contourWidth: CGFloat) -> CGFloat {
        let base = min(meshWidth * 0.94, max(contourWidth, meshWidth * 0.74))
        switch rowProgress {
        case 0.00..<0.16:
            return base * (0.42 + rowProgress * 1.82)
        case 0.16..<0.72:
            return base * 0.90
        default:
            let lowerProgress = (rowProgress - 0.72) / 0.28
            return base * (0.90 - lowerProgress * 0.34)
        }
    }

    private func segments(from points: [CGPoint], closed: Bool) -> [FaceResultSegment] {
        guard points.count > 1 else { return [] }
        var result = zip(points.dropLast(), points.dropFirst()).map {
            FaceResultSegment(start: $0.0, end: $0.1)
        }
        if closed, let first = points.first, let last = points.last {
            result.append(FaceResultSegment(start: last, end: first))
        }
        return result
    }

    private func nearestTwoPoints(to point: CGPoint, in candidates: [CGPoint]) -> [CGPoint] {
        Array(candidates.sorted { $0.distanceSquared(to: point) < $1.distanceSquared(to: point) }.prefix(2))
    }

    static func detectLandmarks(from image: UIImage, preferredRegion: CGRect? = nil) -> [String: [[Double]]]? {
        guard let cgImage = image.cgImage else { return nil }
        let request = VNDetectFaceLandmarksRequest()
        let handler = VNImageRequestHandler(
            cgImage: cgImage,
            orientation: cgImageOrientation(for: image),
            options: [:]
        )

        do {
            try handler.perform([request])
            guard let observation = bestFaceObservation(
                from: request.results ?? [],
                preferredRegion: preferredRegion
            ) else {
                return nil
            }
            let result = landmarkRegions(from: observation)
            return result.isEmpty ? nil : result
        } catch {
            return nil
        }
    }

    private static func bestFaceObservation(
        from observations: [VNFaceObservation],
        preferredRegion: CGRect?
    ) -> VNFaceObservation? {
        guard !observations.isEmpty else { return nil }
        guard let preferredRegion else {
            return observations.max {
                $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height
            }
        }

        let target = preferredRegion.expandedBy(dx: preferredRegion.width * 0.18, dy: preferredRegion.height * 0.18).clampedToUnit()
        return observations.max {
            observationScore($0, target: target) < observationScore($1, target: target)
        }
    }

    private static func observationScore(_ observation: VNFaceObservation, target: CGRect) -> CGFloat {
        let faceRect = CGRect(
            x: observation.boundingBox.minX,
            y: 1 - observation.boundingBox.maxY,
            width: observation.boundingBox.width,
            height: observation.boundingBox.height
        ).clampedToUnit()
        let intersection = faceRect.intersection(target)
        let overlapScore = intersection.isNull ? CGFloat(0) : intersection.area / max(faceRect.area, 0.0001)
        let distancePenalty = faceRect.center.distanceSquared(to: target.center)
        let areaScore = faceRect.area * 0.08
        return overlapScore * 10 + areaScore - distancePenalty
    }

    private static func landmarkRegions(from observation: VNFaceObservation) -> [String: [[Double]]] {
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

        var result: [String: [[Double]]] = [:]
        for (name, region) in regions {
            let points = landmarkPoints(from: region, in: observation.boundingBox)
            guard !points.isEmpty else { continue }
            result[name] = points.map { [Double($0.x), Double($0.y)] }
        }
        return result
    }

    private static func landmarkPoints(from region: VNFaceLandmarkRegion2D?, in boundingBox: CGRect) -> [CGPoint] {
        guard let region else { return [] }
        return region.normalizedPoints.map { point in
            CGPoint(
                x: boundingBox.minX + point.x * boundingBox.width,
                y: 1 - (boundingBox.minY + point.y * boundingBox.height)
            ).clampedToUnit()
        }
    }

    private static func cgImageOrientation(for image: UIImage) -> CGImagePropertyOrientation {
        switch image.imageOrientation {
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

private struct FaceResultMesh {
    let faceRect: CGRect
    let outline: [CGPoint]
    let landmarkPoints: [CGPoint]
    let segments: [FaceResultSegment]
}

private struct FaceResultSegment {
    let start: CGPoint
    let end: CGPoint
}

private struct FaceResultAspectFillMapper {
    let imageSize: CGSize
    let containerSize: CGSize

    private var scale: CGFloat {
        max(containerSize.width / max(imageSize.width, 1), containerSize.height / max(imageSize.height, 1))
    }

    private var drawnSize: CGSize {
        CGSize(width: imageSize.width * scale, height: imageSize.height * scale)
    }

    private var origin: CGPoint {
        CGPoint(
            x: (containerSize.width - drawnSize.width) / 2,
            y: (containerSize.height - drawnSize.height) / 2
        )
    }

    func point(_ point: CGPoint) -> CGPoint {
        CGPoint(
            x: origin.x + point.x * drawnSize.width,
            y: origin.y + point.y * drawnSize.height
        )
    }

    func rect(_ rect: CGRect) -> CGRect {
        CGRect(
            x: origin.x + rect.minX * drawnSize.width,
            y: origin.y + rect.minY * drawnSize.height,
            width: rect.width * drawnSize.width,
            height: rect.height * drawnSize.height
        )
    }
}


private extension CGPoint {
    func clampedToUnit() -> CGPoint {
        CGPoint(x: min(1, max(0, x)), y: min(1, max(0, y)))
    }

    func distanceSquared(to point: CGPoint) -> CGFloat {
        let dx = x - point.x
        let dy = y - point.y
        return dx * dx + dy * dy
    }
}

private extension Double {
    func clampedToUnit() -> Double {
        min(1, max(0, self))
    }
}

private extension CGFloat {
    func clamped(to range: ClosedRange<CGFloat>) -> CGFloat {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

private extension CGRect {
    func clampedToUnit() -> CGRect {
        let minX = min(1, max(0, minX))
        let minY = min(1, max(0, minY))
        let maxX = min(1, max(0, maxX))
        let maxY = min(1, max(0, maxY))
        return CGRect(x: minX, y: minY, width: max(0, maxX - minX), height: max(0, maxY - minY))
    }

    var area: CGFloat {
        max(0, width) * max(0, height)
    }

    var center: CGPoint {
        CGPoint(x: midX, y: midY)
    }

    var facemaxxMetadataValue: String {
        [
            minX,
            minY,
            width,
            height
        ]
        .map { String(format: "%.5f", Double($0)) }
        .joined(separator: ",")
    }

    func expandedBy(dx: CGFloat, dy: CGFloat) -> CGRect {
        insetBy(dx: -dx, dy: -dy)
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

private struct ProportionsResultSection: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    let trialAccess: TrialResultAccess
    let unlockAction: () -> Void

    @State private var expandedDetailIDs = Set<String>()
    @State private var expandedFunIDs = Set<String>()
    @State private var isActionPlanExpanded = true

    private var sectionStackAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(spacing: 28) {
            ProportionsTopCard(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                hidesRingGrid: trialAccess.isFreeTrialResult,
                unlockAction: unlockAction
            )

            ProportionsMetricSection(
                titleKey: "analysis.results.detailedMetrics",
                metrics: result.metrics.facemaxxMetrics(in: "detailed_metrics", fallback: ProportionsResultData.detailedMetrics),
                expandedIDs: $expandedDetailIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.primaryMetricLimit,
                showsUnlockCard: false,
                unlockAction: unlockAction
            )

            ProportionsMetricSection(
                titleKey: "analysis.results.funAIMetrics",
                metrics: result.metrics.facemaxxMetrics(in: "fun_metrics", fallback: ProportionsResultData.funMetrics),
                expandedIDs: $expandedFunIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.secondaryMetricLimit,
                showsUnlockCard: trialAccess.shouldShowUnlockCard,
                unlockAction: unlockAction
            )
            .fixedMovingLayer()

            if !trialAccess.isFreeTrialResult {
                GrowthOpportunitiesSection(
                    result: result,
                    isActionPlanExpanded: $isActionPlanExpanded,
                    reduceMotion: reduceMotion
                )
                .fixedMovingLayer()
            }
        }
        .animation(sectionStackAnimation, value: expandedDetailIDs)
        .animation(sectionStackAnimation, value: expandedFunIDs)
    }
}

private struct AestheticsResultSection: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    let trialAccess: TrialResultAccess
    let unlockAction: () -> Void

    @State private var expandedShapeIDs = Set<String>()
    @State private var expandedProportionIDs = Set<String>()

    private var sectionStackAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(spacing: 28) {
            AestheticsHeaderCard(
                result: result,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                expandedIDs: $expandedShapeIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.primaryMetricLimit,
                unlockAction: unlockAction
            )

            AestheticMetricSection(
                titleKey: "analysis.aestheticsResults.proportions",
                badgeKey: "analysis.badge.unlimited",
                badgeStyle: .green,
                metrics: result.metrics.facemaxxAestheticMetrics(in: "proportions", fallback: AestheticsResultData.proportions),
                expandedIDs: $expandedProportionIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.secondaryMetricLimit,
                showsUnlockCard: trialAccess.shouldShowUnlockCard,
                unlockAction: unlockAction
            )
            .fixedMovingLayer()
        }
        .animation(sectionStackAnimation, value: expandedShapeIDs)
        .animation(sectionStackAnimation, value: expandedProportionIDs)
    }
}

private struct GlowUpCoachResultSection: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    let trialAccess: TrialResultAccess
    let unlockAction: () -> Void

    @State private var expandedFacialIDs = Set<String>()
    @State private var expandedNeedsWorkIDs: Set<String> = ["expression-confidence"]
    @State private var expandedStrengthIDs = Set<String>()

    private var sectionStackAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    private var facialMetrics: [GlowUpCoachMetric] {
        result.coachItems
            .facemaxxCoachItems(in: "facial_analysis", fallback: GlowUpCoachResultData.facialAnalysis)
            .facemaxxDeduplicated()
    }

    private var needsWorkMetrics: [GlowUpCoachMetric] {
        result.coachItems
            .facemaxxCoachItems(in: "needs_work", fallback: GlowUpCoachResultData.needsWork)
            .facemaxxDeduplicated(excluding: facialMetrics)
    }

    private var strengthMetrics: [GlowUpCoachMetric] {
        result.coachItems
            .facemaxxCoachItems(in: "strengths", fallback: GlowUpCoachResultData.strengths)
            .facemaxxDeduplicated(excluding: facialMetrics + needsWorkMetrics)
    }

    var body: some View {
        VStack(spacing: 28) {
            GlowUpFacialAnalysisCard(
                metrics: facialMetrics,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage,
                expandedIDs: $expandedFacialIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.primaryMetricLimit,
                unlockAction: unlockAction
            )

            if !needsWorkMetrics.isEmpty {
                GlowUpCoachMetricSection(
                    titleKey: "analysis.glowUpCoach.needsWork",
                    metrics: needsWorkMetrics,
                    expandedIDs: $expandedNeedsWorkIDs,
                    reduceMotion: reduceMotion,
                    visibleMetricLimit: trialAccess.secondaryMetricLimit,
                    showsUnlockCard: false,
                    unlockAction: unlockAction
                )
                .fixedMovingLayer()
            }

            if !strengthMetrics.isEmpty {
                GlowUpCoachMetricSection(
                    titleKey: "analysis.glowUpCoach.yourStrengths",
                    metrics: strengthMetrics,
                    expandedIDs: $expandedStrengthIDs,
                    reduceMotion: reduceMotion,
                    visibleMetricLimit: trialAccess.secondaryMetricLimit,
                    showsUnlockCard: trialAccess.shouldShowUnlockCard,
                    unlockAction: unlockAction
                )
                .fixedMovingLayer()
            }

            if !trialAccess.isFreeTrialResult {
                AnalysisPotentialScoreCard(
                    score: result.facemaxxPotentialScore10 ?? 8.7,
                    progress: result.facemaxxPotentialProgress
                )
                .fixedMovingLayer()

                GlowUpSummary(summaryText: result.summaryText)
                    .fixedMovingLayer()
            }
        }
        .onAppear {
            let defaults = result.coachItems
                .filter { $0.section == "needs_work" && $0.isDefaultExpanded }
                .map(\.itemID)
            if !defaults.isEmpty {
                expandedNeedsWorkIDs = Set(defaults)
            }
        }
        .animation(sectionStackAnimation, value: expandedFacialIDs)
        .animation(sectionStackAnimation, value: expandedNeedsWorkIDs)
        .animation(sectionStackAnimation, value: expandedStrengthIDs)
    }
}

private struct GlowUpFacialAnalysisCard: View {
    let metrics: [GlowUpCoachMetric]
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    @Binding var expandedIDs: Set<String>
    let reduceMotion: Bool
    var visibleMetricLimit: Int? = nil
    var unlockAction: () -> Void = {}

    private var cardLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(spacing: 28) {
            AnalysisResultPhotoFrame(
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            GlowUpCoachMetricSection(
                titleKey: "analysis.glowUpCoach.facialAnalysis",
                metrics: metrics,
                expandedIDs: $expandedIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: visibleMetricLimit,
                unlockAction: unlockAction
            )
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 28)
        .fxCard(cornerRadius: 34)
        .animation(cardLayoutAnimation, value: expandedIDs)
    }
}

private struct GlowUpCoachMetricSection: View {
    let titleKey: LocalizedStringKey
    let metrics: [GlowUpCoachMetric]
    @Binding var expandedIDs: Set<String>
    let reduceMotion: Bool
    var visibleMetricLimit: Int? = nil
    var showsUnlockCard = false
    var unlockAction: () -> Void = {}

    private var listLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.66, dampingFraction: 0.90, blendDuration: 0.18)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(titleKey)
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()
                .fixedMovingLayer()

            VStack(spacing: 12) {
                ForEach(Array(metrics.enumerated()), id: \.element.id) { index, metric in
                    if isLocked(index: index) {
                        TrialLockedMetricRow(
                            titleKey: metric.titleKey,
                            iconName: metric.iconName,
                            action: unlockAction
                        )
                        .fixedMovingLayer()
                    } else {
                        GlowUpCoachMetricRow(
                            metric: metric,
                            isExpanded: expandedIDs.contains(metric.id),
                            reduceMotion: reduceMotion,
                            toggle: { toggle(metric.id) }
                        )
                        .fixedMovingLayer()
                    }
                }

                if showsUnlockCard {
                    TrialUnlockFullResultsCard(action: unlockAction)
                        .fixedMovingLayer()
                }
            }
            .animation(listLayoutAnimation, value: expandedIDs)
        }
    }

    private func isLocked(index: Int) -> Bool {
        guard let visibleMetricLimit else { return false }
        return index >= visibleMetricLimit
    }

    private func toggle(_ id: String) {
        if expandedIDs.contains(id) {
            expandedIDs.remove(id)
        } else {
            expandedIDs.insert(id)
        }
    }
}

private struct GlowUpCoachMetricRow: View {
    let metric: GlowUpCoachMetric
    let isExpanded: Bool
    let reduceMotion: Bool
    let toggle: () -> Void

    private var disclosureAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.66, dampingFraction: 0.90, blendDuration: 0.18)
    }

    private var contentFadeAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .easeInOut(duration: 0.26)
    }

    private var chevronAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.28)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: toggle) {
                HStack(spacing: 12) {
                    Image(systemName: FacemaxxSFSymbol.safeName(metric.iconName))
                        .font(.system(size: 22, weight: .heavy))
                        .foregroundStyle(FXTheme.blue)
                        .frame(width: 30)
                        .stableDuringListMotion()

                    LocalizedOrRemoteText(key: metric.titleKey, text: nil)
                        .font(.system(size: 19, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.80)
                        .layoutPriority(2)
                        .stableDuringListMotion()

                    Spacer(minLength: 8)

                    Image(systemName: "chevron.down")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                        .animation(chevronAnimation, value: isExpanded)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 17)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            CollapsibleContent(
                isExpanded: isExpanded,
                heightAnimation: disclosureAnimation,
                opacityAnimation: contentFadeAnimation
            ) {
                VStack(alignment: .leading, spacing: 18) {
                    LocalizedOrRemoteText(key: metric.assessmentKey, text: metric.assessmentText)
                        .font(.system(size: 15.8, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .stableDuringListMotion()

                    LocalizedOrRemoteText(key: metric.actionKey, text: metric.actionText)
                        .font(.system(size: 15.8, weight: .bold))
                        .foregroundStyle(FXTheme.textPrimary.opacity(0.90))
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .stableDuringListMotion()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 20)
            }
        }
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(isExpanded ? 0.16 : 0.06), lineWidth: 1)
                .animation(disclosureAnimation, value: isExpanded)
        }
    }
}

private struct GlowUpSummary: View {
    let summaryText: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("analysis.glowUpCoach.summary")
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()

            LocalizedOrRemoteText(key: "analysis.glowUpCoach.summaryBody", text: summaryText)
                .font(.body.weight(.medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct LookArchetypeResultSection: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    let trialAccess: TrialResultAccess
    let unlockAction: () -> Void

    @State private var expandedIDs: Set<String> = ["why-this-fits"]

    private var sectionStackAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        let archetype = result.lookArchetype.facemaxxValue
        VStack(spacing: 28) {
            LookArchetypeHeroCard(
                archetype: archetype,
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            AnalysisPotentialScoreCard(
                score: result.facemaxxPotentialScore10 ?? 8.7,
                progress: result.facemaxxPotentialProgress
            )
            .fixedMovingLayer()

            VStack(spacing: 12) {
                ForEach(Array(archetype.sections.enumerated()), id: \.element.id) { index, section in
                    if isLocked(index: index) {
                        TrialLockedMetricRow(
                            titleKey: section.titleKey,
                            titleText: section.titleText,
                            iconName: section.iconName,
                            action: unlockAction
                        )
                        .fixedMovingLayer()
                    } else {
                        LookArchetypeSectionRow(
                            section: section,
                            isExpanded: expandedIDs.contains(section.id),
                            reduceMotion: reduceMotion,
                            toggle: { toggle(section.id) }
                        )
                        .fixedMovingLayer()
                    }
                }

                if trialAccess.shouldShowUnlockCard {
                    TrialUnlockFullResultsCard(action: unlockAction)
                        .fixedMovingLayer()
                }
            }
            .animation(sectionStackAnimation, value: expandedIDs)
        }
        .onAppear {
            let defaults = archetype.sections
                .filter(\.isDefaultExpanded)
                .map(\.id)
            if !defaults.isEmpty {
                expandedIDs = Set(defaults)
            }
        }
        .animation(sectionStackAnimation, value: expandedIDs)
    }

    private func toggle(_ id: String) {
        if expandedIDs.contains(id) {
            expandedIDs.remove(id)
        } else {
            expandedIDs.insert(id)
        }
    }

    private func isLocked(index: Int) -> Bool {
        guard let lookSectionLimit = trialAccess.lookSectionLimit else { return false }
        return index >= lookSectionLimit
    }
}

private struct LookArchetypeHeroCard: View {
    let archetype: LookArchetypeResult
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?

    var body: some View {
        VStack(spacing: 22) {
            AnalysisResultPhotoFrame(
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            VStack(alignment: .leading, spacing: 14) {
                Text(archetype.titleKey)
                    .font(.headline.weight(.black))
                    .foregroundStyle(FXTheme.textSecondary)
                    .stableDuringListMotion()

                VStack(alignment: .leading, spacing: 10) {
                    Text(archetype.typeName)
                        .font(.system(size: 27, weight: .black))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.58)
                        .stableDuringListMotion()

                    if let secondaryTypeName = archetype.secondaryTypeName?.trimmingCharacters(in: .whitespacesAndNewlines),
                       !secondaryTypeName.isEmpty {
                        LookArchetypeSecondaryBadge(typeName: secondaryTypeName)
                            .fixedMovingLayer()
                    }
                }

                LocalizedOrRemoteText(key: nil, text: archetype.subtitleText)
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary.opacity(0.90))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .stableDuringListMotion()

                LookArchetypeTraitStrip(traits: archetype.traits)
                    .fixedMovingLayer()

                LocalizedOrRemoteText(key: nil, text: archetype.bodyText)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(4)
                    .lineLimit(5)
                    .fixedSize(horizontal: false, vertical: true)
                    .stableDuringListMotion()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 28)
        .fxCard(cornerRadius: 34)
    }
}

private struct LookArchetypeSecondaryBadge: View {
    let typeName: String

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: "plus")
                .font(.system(size: 10, weight: .black))
                .foregroundStyle(FXTheme.cyan)

            Text(typeName)
                .font(.system(size: 13.5, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary.opacity(0.88))
                .lineLimit(1)
                .minimumScaleFactor(0.76)
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 7)
        .background {
            Capsule(style: .continuous)
                .fill(FXTheme.cardElevated)
        }
        .overlay {
            Capsule(style: .continuous)
                .stroke(FXTheme.cyan.opacity(0.22), lineWidth: 1)
        }
    }
}

private struct LookArchetypeTraitStrip: View {
    let traits: [LookArchetypeTrait]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 106), spacing: 8)], spacing: 8) {
            ForEach(traits) { trait in
                LocalizedOrRemoteText(key: trait.titleKey, text: trait.titleText)
                    .font(.caption.weight(.heavy))
                    .foregroundStyle(trait.tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background {
                        Capsule(style: .continuous)
                            .fill(trait.tint.opacity(0.16))
                    }
                    .stableDuringListMotion()
            }
        }
    }
}

private struct LookArchetypeSectionRow: View {
    let section: LookArchetypeSection
    let isExpanded: Bool
    let reduceMotion: Bool
    let toggle: () -> Void

    private var disclosureAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    private var contentFadeAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .easeOut(duration: 0.18)
    }

    private var chevronAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.22)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: toggle) {
                HStack(spacing: 12) {
                    Image(systemName: FacemaxxSFSymbol.safeName(section.iconName))
                        .font(.system(size: 21, weight: .heavy))
                        .foregroundStyle(section.tint)
                        .frame(width: 30)
                        .stableDuringListMotion()

                    LocalizedOrRemoteText(key: section.titleKey, text: section.titleText)
                        .font(.system(size: 19, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.80)
                        .layoutPriority(2)
                        .stableDuringListMotion()

                    Spacer(minLength: 8)

                    Image(systemName: "chevron.down")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                        .animation(chevronAnimation, value: isExpanded)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 17)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            CollapsibleContent(
                isExpanded: isExpanded,
                heightAnimation: disclosureAnimation,
                opacityAnimation: contentFadeAnimation
            ) {
                VStack(alignment: .leading, spacing: 13) {
                    ForEach(section.items) { item in
                        LookArchetypeBulletRow(item: item, tint: section.tint)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 20)
            }
        }
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(isExpanded ? 0.16 : 0.06), lineWidth: 1)
                .animation(disclosureAnimation, value: isExpanded)
        }
    }
}

private struct LookArchetypeBulletRow: View {
    let item: LookArchetypeBullet
    let tint: Color

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: FacemaxxSFSymbol.safeName(item.iconName))
                .font(.subheadline.weight(.heavy))
                .foregroundStyle(tint)
                .frame(width: 22, height: 22)
                .stableDuringListMotion()

            LocalizedOrRemoteText(key: item.titleKey, text: item.titleText)
                .font(.system(size: 15.5, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
        }
    }
}

private struct PhotoOptimizationResultSection: View {
    let modeID: String
    let result: AnalysisResultPayload
    let image: UIImage?
    let supplementalImages: [UIImage]
    let supplementalScanOverlayImages: [UIImage?]
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    let reduceMotion: Bool
    let trialAccess: TrialResultAccess
    let unlockAction: () -> Void

    @State private var expandedPrimaryIDs = Set<String>()
    @State private var expandedSecondaryIDs = Set<String>()
    @State private var isPhotoActionPlanExpanded = true

    private var configuration: PhotoOptimizationResultConfiguration {
        PhotoOptimizationResultData.configuration(for: modeID)
    }

    private var primaryMetrics: [ProportionExpandableMetric] {
        cappedDetailedMetrics(
            result.metrics.facemaxxMetrics(in: configuration.primarySectionID, fallback: configuration.primaryMetrics)
        )
    }

    private var secondaryMetrics: [ProportionExpandableMetric] {
        cappedDetailedMetrics(
            result.metrics.facemaxxMetrics(in: configuration.secondarySectionID, fallback: configuration.secondaryMetrics)
        )
    }

    private var candidateImages: [UIImage] {
        [image].compactMap { $0 } + supplementalImages
    }

    private var candidateScanOverlayImages: [UIImage?] {
        guard image != nil else { return supplementalScanOverlayImages }
        return [scanOverlayImage] + supplementalScanOverlayImages
    }

    private var rankedCandidates: [BestPhotoCandidate] {
        BestPhotoCandidate.makeCandidates(
            from: candidateImages,
            scanOverlayImages: candidateScanOverlayImages,
            result: result
        )
        .sorted {
            if $0.rank == $1.rank {
                return $0.index < $1.index
            }
            return $0.rank < $1.rank
        }
    }

    private var shouldShowCandidateBreakdown: Bool {
        (modeID == "best-photo-selector" || modeID == "best-angle-finder")
            && rankedCandidates.contains { $0.hasDetailedBreakdown }
    }

    private var shouldCapDetailedMetrics: Bool {
        modeID == "best-photo-selector" || modeID == "best-angle-finder"
    }

    private var shouldShowSecondaryMetricSection: Bool {
        !shouldCapDetailedMetrics
    }

    private var shouldShowStandaloneSummary: Bool {
        modeID != "dating-profile-score" && modeID != "instagram-profile-score"
    }

    private func cappedDetailedMetrics(_ metrics: [ProportionExpandableMetric]) -> [ProportionExpandableMetric] {
        guard shouldCapDetailedMetrics else { return metrics }
        return Array(metrics.prefix(3))
    }

    private var photoActionPlanItems: [ActionPlanItem] {
        result.growthOpportunities.facemaxxActionPlanItems(fallback: fallbackActionPlanItems)
    }

    private var fallbackActionPlanItems: [ActionPlanItem] {
        switch modeID {
        case "best-photo-selector":
            return [
                ActionPlanItem(id: "thumbnail-read", bodyKey: "analysis.photoOptimization.action.bestPhotoThumbnail"),
                ActionPlanItem(id: "expression-retake", bodyKey: "analysis.photoOptimization.action.bestPhotoExpression"),
                ActionPlanItem(id: "background-cleanup", bodyKey: "analysis.photoOptimization.action.bestPhotoBackground"),
                ActionPlanItem(id: "final-check", bodyKey: "analysis.photoOptimization.action.bestPhotoFinalCheck")
            ]
        case "best-angle-finder":
            return [
                ActionPlanItem(id: "angle-sequence", bodyKey: "analysis.photoOptimization.action.bestAngleSequence"),
                ActionPlanItem(id: "lens-height", bodyKey: "analysis.photoOptimization.action.bestAngleLensHeight"),
                ActionPlanItem(id: "chin-shoulder", bodyKey: "analysis.photoOptimization.action.bestAngleChinShoulder"),
                ActionPlanItem(id: "side-choice", bodyKey: "analysis.photoOptimization.action.bestAngleSideChoice")
            ]
        default:
            return []
        }
    }

    private var sectionStackAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    private var potentialScore: Double {
        result.facemaxxPotentialScore10 ?? configuration.fallbackPotentialScore
    }

    private var potentialProgress: Double {
        if result.potentialScore == nil && result.potentialProgress == nil {
            return (configuration.fallbackPotentialScore / 10).clampedToUnit()
        }
        return result.facemaxxPotentialProgress
    }

    var body: some View {
        VStack(spacing: 28) {
            PhotoOptimizationHeroCard(
                configuration: configuration,
                result: result,
                image: image,
                supplementalImages: supplementalImages,
                supplementalScanOverlayImages: supplementalScanOverlayImages,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            if !trialAccess.isFreeTrialResult {
                if shouldShowCandidateBreakdown {
                    PhotoCandidateBreakdownSection(candidates: rankedCandidates)
                        .fixedMovingLayer()
                }
            }

            ProportionsMetricSection(
                titleKey: configuration.primaryTitleKey,
                metrics: primaryMetrics,
                expandedIDs: $expandedPrimaryIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: trialAccess.primaryMetricLimit,
                showsUnlockCard: trialAccess.shouldShowUnlockCard && !shouldShowSecondaryMetricSection,
                unlockAction: unlockAction
            )

            if shouldShowSecondaryMetricSection {
                ProportionsMetricSection(
                    titleKey: configuration.secondaryTitleKey,
                    metrics: secondaryMetrics,
                    expandedIDs: $expandedSecondaryIDs,
                    reduceMotion: reduceMotion,
                    visibleMetricLimit: trialAccess.secondaryMetricLimit,
                    showsUnlockCard: trialAccess.shouldShowUnlockCard,
                    unlockAction: unlockAction
                )
                .fixedMovingLayer()
            }

            if !trialAccess.isFreeTrialResult {
                if !photoActionPlanItems.isEmpty {
                    PhotoOptimizationActionPlanSection(
                        items: photoActionPlanItems,
                        isExpanded: $isPhotoActionPlanExpanded,
                        reduceMotion: reduceMotion
                    )
                    .fixedMovingLayer()
                }

                AnalysisPotentialScoreCard(
                    score: potentialScore,
                    progress: potentialProgress
                )
                .fixedMovingLayer()

                if shouldShowStandaloneSummary {
                    PhotoOptimizationSummaryCard(
                        summaryText: result.summaryText,
                        fallbackKey: configuration.summaryKey
                    )
                    .fixedMovingLayer()
                }
            }
        }
        .animation(sectionStackAnimation, value: expandedPrimaryIDs)
        .animation(sectionStackAnimation, value: expandedSecondaryIDs)
        .animation(sectionStackAnimation, value: isPhotoActionPlanExpanded)
    }
}

private struct PhotoOptimizationHeroCard: View {
    let configuration: PhotoOptimizationResultConfiguration
    let result: AnalysisResultPayload
    let image: UIImage?
    let supplementalImages: [UIImage]
    let supplementalScanOverlayImages: [UIImage?]
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?

    private var rings: [ProportionRingMetric] {
        let mapped = result.rings.sorted { $0.sortOrder < $1.sortOrder }.map(ProportionRingMetric.init)
        return mapped.isEmpty ? configuration.rings : mapped
    }

    private var overallScore: Double {
        result.facemaxxOverallScore10 ?? configuration.fallbackOverallScore
    }

    private var overallProgress: Double {
        if result.overallScore == nil && result.overallProgress == nil {
            return (configuration.fallbackOverallScore / 10).clampedToUnit()
        }
        return result.facemaxxOverallProgress
    }

    private var candidateImages: [UIImage] {
        [image].compactMap { $0 } + supplementalImages
    }

    private var candidateScanOverlayImages: [UIImage?] {
        guard image != nil else { return supplementalScanOverlayImages }
        return [scanOverlayImage] + supplementalScanOverlayImages
    }

    var body: some View {
        VStack(spacing: 24) {
            if candidateImages.count > 1 {
                UploadedAnalysisPhotoGallery(
                    modeID: configuration.modeID,
                    result: result,
                    images: candidateImages,
                    scanOverlayImages: candidateScanOverlayImages
                )
            } else {
                AnalysisResultPhotoFrame(
                    image: image,
                    scanPayload: scanPayload,
                    scanOverlayImage: scanOverlayImage
                )
            }

            HStack(spacing: 12) {
                Text(configuration.titleKey)
                    .font(.title2.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.78)
                    .stableDuringListMotion()

                Spacer(minLength: 12)
            }
            .fixedMovingLayer()

            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 18) {
                ForEach(rings) { metric in
                    ProportionScoreRing(metric: metric)
                }
            }
            .fixedMovingLayer()

            VStack(spacing: 12) {
                ProportionsScoreBar(
                    iconName: "chart.bar.fill",
                    titleKey: "analysis.photoOptimization.overallScore",
                    valueKey: "analysis.results.overallValue",
                    valueText: String(format: "%.1f/10", overallScore),
                    progress: overallProgress
                )
            }
            .fixedMovingLayer()
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 28)
        .fxCard(cornerRadius: 34)
    }
}

private struct UploadedAnalysisPhotoGallery: View {
    let modeID: String
    let result: AnalysisResultPayload
    let images: [UIImage]
    let scanOverlayImages: [UIImage?]

    private var isRankedGallery: Bool {
        modeID == "best-photo-selector" || hasCompleteStructuredRankings
    }

    private var hasCompleteStructuredRankings: Bool {
        guard images.count > 1 else { return false }
        let rankedIndexes = Set(
            result.facemaxxPhotoRankings
                .map(\.candidateIndex)
                .filter { (1...images.count).contains($0) }
        )
        return (1...images.count).allSatisfy { rankedIndexes.contains($0) }
    }

    private var candidates: [BestPhotoCandidate] {
        BestPhotoCandidate.makeCandidates(
            from: images,
            scanOverlayImages: scanOverlayImages,
            result: result
        )
    }

    private var winner: BestPhotoCandidate? {
        candidates.min {
            if $0.rank == $1.rank {
                return $0.index < $1.index
            }
            return $0.rank < $1.rank
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            let visibleCandidates = Array(candidates.prefix(3))
            let columns = Array(
                repeating: GridItem(.flexible(), spacing: 10),
                count: max(1, visibleCandidates.count)
            )

            LazyVGrid(columns: columns, spacing: 10) {
                if isRankedGallery {
                    ForEach(visibleCandidates) { candidate in
                        SquarePhotoTileContainer {
                            BestPhotoCandidateTile(candidate: candidate)
                        }
                            .fixedMovingLayer()
                    }
                } else {
                    ForEach(Array(images.prefix(3).enumerated()), id: \.offset) { offset, image in
                        SquarePhotoTileContainer {
                            UploadedPhotoTile(
                                image: image,
                                scanOverlayImage: scanOverlayImages[safe: offset] ?? nil
                            )
                        }
                            .fixedMovingLayer()
                    }
                }
            }
            .frame(maxWidth: .infinity)
            .padding(10)
            .background {
                RoundedRectangle(cornerRadius: 30, style: .continuous)
                    .fill(Color.white.opacity(0.045))
                    .overlay {
                        RoundedRectangle(cornerRadius: 30, style: .continuous)
                            .stroke(Color.white.opacity(0.09), lineWidth: 1)
                    }
            }

            if isRankedGallery, let winnerNote {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 15, weight: .heavy))
                        .foregroundStyle(Color(red: 0.97, green: 0.45, blue: 0.64))
                        .frame(width: 20)

                    Text(winnerNote)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 4)
                .stableDuringListMotion()
            }
        }
    }

    private var winnerNote: String? {
        winner?.reasonText ?? winner?.verdict
    }
}

private struct PhotoCandidateBreakdownSection: View {
    let candidates: [BestPhotoCandidate]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("analysis.photoOptimization.candidateBreakdown")
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()

            VStack(spacing: 12) {
                ForEach(Array(candidates.filter(\.hasDetailedBreakdown).prefix(3))) { candidate in
                    PhotoCandidateBreakdownCard(candidate: candidate)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct PhotoCandidateBreakdownCard: View {
    let candidate: BestPhotoCandidate

    private var accent: Color {
        candidate.isWinner ? Color(red: 0.97, green: 0.45, blue: 0.64) : FXTheme.blue.opacity(0.82)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 14) {
                ResultGalleryPhotoImage(image: candidate.image, scanOverlayImage: candidate.scanOverlayImage)
                    .frame(width: 76, height: 76)
                    .clipShape(.rect(cornerRadius: 18, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(accent.opacity(candidate.isWinner ? 0.90 : 0.36), lineWidth: candidate.isWinner ? 2 : 1)
                    }

                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        Text(String(format: String(localized: "analysis.photoOptimization.rankFormat"), candidate.rank))
                            .font(.caption.weight(.black))
                            .monospacedDigit()
                            .foregroundStyle(.white)
                            .padding(.horizontal, 9)
                            .padding(.vertical, 5)
                            .background(accent, in: Capsule(style: .continuous))

                        if let scoreText = candidate.scoreText {
                            Text("\(scoreText)/10")
                                .font(.caption.weight(.heavy))
                                .monospacedDigit()
                                .foregroundStyle(FXTheme.textSecondary)
                        }
                    }

                    if let headline = candidate.funLabelText ?? candidate.verdict {
                        Text(headline)
                            .font(.system(size: 17, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .fixedSize(horizontal: false, vertical: true)
                    } else {
                        Text("analysis.photoOptimization.candidateFallback")
                            .font(.system(size: 17, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Spacer(minLength: 0)
            }

            if let descriptionText = candidate.descriptionText ?? candidate.reasonText {
                Text(descriptionText)
                    .font(.system(size: 15.5, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .stableDuringListMotion()
            }

            if !displayChips.isEmpty {
                PhotoCandidateChipCloud(items: displayChips)
            }

            VStack(alignment: .leading, spacing: 10) {
                PhotoCandidateDetailRow(
                    titleKey: "analysis.photoOptimization.bestUse",
                    text: candidate.bestUseText,
                    iconName: "checkmark.seal.fill",
                    tint: FXTheme.green
                )

                PhotoCandidateDetailRow(
                    titleKey: "analysis.photoOptimization.watchOut",
                    text: candidate.weaknessText,
                    iconName: "exclamationmark.triangle.fill",
                    tint: FXTheme.yellow
                )

                PhotoCandidateDetailRow(
                    titleKey: "analysis.photoOptimization.quickFix",
                    text: candidate.fixText,
                    iconName: "wand.and.stars",
                    tint: FXTheme.cyan
                )

                PhotoCandidateDetailRow(
                    titleKey: "analysis.photoOptimization.captionIdea",
                    text: candidate.captionIdeaText,
                    iconName: "text.bubble.fill",
                    tint: Color(red: 0.97, green: 0.45, blue: 0.64)
                )
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
                .overlay {
                    RoundedRectangle(cornerRadius: 24, style: .continuous)
                        .stroke(Color.white.opacity(0.07), lineWidth: 1)
                }
        }
    }

    private var displayChips: [String] {
        Array(
            (candidate.strengths + candidate.vibeTags)
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
                .prefix(3)
        )
    }
}

private struct PhotoCandidateChipCloud: View {
    let items: [String]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 86), spacing: 7)], alignment: .leading, spacing: 7) {
            ForEach(Array(items.prefix(3).enumerated()), id: \.offset) { _, item in
                Text(item)
                    .font(.caption.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .multilineTextAlignment(.leading)
                    .lineLimit(2)
                    .minimumScaleFactor(0.86)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.white.opacity(0.065), in: Capsule(style: .continuous))
            }
        }
    }
}

private struct PhotoCandidateDetailRow: View {
    let titleKey: LocalizedStringKey
    let text: String?
    let iconName: String
    let tint: Color

    var body: some View {
        if let text, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: FacemaxxSFSymbol.safeName(iconName))
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(tint)
                    .frame(width: 18, height: 18)
                    .padding(.top, 2)

                VStack(alignment: .leading, spacing: 3) {
                    Text(titleKey)
                        .font(.caption.weight(.black))
                        .foregroundStyle(FXTheme.textMuted)
                        .multilineTextAlignment(.leading)

                    Text(text)
                        .font(.system(size: 14.5, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .multilineTextAlignment(.leading)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct PhotoOptimizationActionPlanSection: View {
    let items: [ActionPlanItem]
    @Binding var isExpanded: Bool
    let reduceMotion: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("analysis.results.growthOpportunities")
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()

            ActionPlanCard(
                items: items,
                isExpanded: $isExpanded,
                reduceMotion: reduceMotion
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct SquarePhotoTileContainer<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        GeometryReader { proxy in
            content
                .frame(width: proxy.size.width, height: proxy.size.width)
        }
        .aspectRatio(1, contentMode: .fit)
        .clipped()
    }
}

private struct ResultGalleryPhotoImage: View {
    let image: UIImage
    let scanOverlayImage: UIImage?

    @State private var showsScanOverlay = true

    var body: some View {
        ZStack {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipped()

            if let scanOverlayImage {
                Image(uiImage: scanOverlayImage)
                    .resizable()
                    .scaledToFill()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipped()
                    .opacity(showsScanOverlay ? 1 : 0)
                    .scaleEffect(showsScanOverlay ? 1 : 0.985)
                    .allowsHitTesting(false)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            guard scanOverlayImage != nil else { return }
            withAnimation(.smooth(duration: 0.34)) {
                showsScanOverlay.toggle()
            }
        }
        .task(id: ObjectIdentifier(image)) {
            showsScanOverlay = true
        }
    }
}

private struct UploadedPhotoTile: View {
    let image: UIImage
    let scanOverlayImage: UIImage?

    var body: some View {
        ResultGalleryPhotoImage(image: image, scanOverlayImage: scanOverlayImage)
            .clipShape(.rect(cornerRadius: 22, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(Color.white.opacity(0.30), lineWidth: 1)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct BestPhotoCandidateTile: View {
    let candidate: BestPhotoCandidate

    private var accent: Color {
        candidate.isWinner ? Color(red: 0.97, green: 0.45, blue: 0.64) : Color.white.opacity(0.44)
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            ResultGalleryPhotoImage(image: candidate.image, scanOverlayImage: candidate.scanOverlayImage)

            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 6) {
                    Image(systemName: candidate.isWinner ? "crown.fill" : "circle.fill")
                        .font(.system(size: candidate.isWinner ? 11 : 7, weight: .heavy))
                        .foregroundStyle(accent)

                    Text(String(format: String(localized: "analysis.photoOptimization.rankFormat"), candidate.rank))
                        .font(.caption2.weight(.black))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 6)
                .background(Color.black.opacity(0.42), in: Capsule(style: .continuous))

                Spacer(minLength: 0)

                if let scoreText = candidate.scoreText {
                    Text(scoreText)
                        .font(.caption2.weight(.heavy))
                        .monospacedDigit()
                        .foregroundStyle(.white.opacity(0.78))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(Color.black.opacity(0.38), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
            .padding(8)
            .allowsHitTesting(false)
        }
        .clipShape(.rect(cornerRadius: 22, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(accent.opacity(candidate.isWinner ? 0.95 : 0.34), lineWidth: candidate.isWinner ? 2.4 : 1)
        }
        .shadow(
            color: candidate.isWinner ? Color(red: 0.97, green: 0.45, blue: 0.64).opacity(0.20) : .clear,
            radius: 18,
            y: 10
        )
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct BestPhotoCandidate: Identifiable {
    let index: Int
    let image: UIImage
    let scanOverlayImage: UIImage?
    let rank: Int
    let score: Double?
    let verdict: String?
    let reasonText: String?
    let descriptionText: String?
    let bestUseText: String?
    let funLabelText: String?
    let strengths: [String]
    let weaknessText: String?
    let fixText: String?
    let captionIdeaText: String?
    let vibeTags: [String]

    var id: Int { index }
    var isWinner: Bool { rank == 1 }

    var hasDetailedBreakdown: Bool {
        [
            verdict,
            reasonText,
            descriptionText,
            bestUseText,
            funLabelText,
            weaknessText,
            fixText,
            captionIdeaText
        ]
        .contains { text in
            guard let text else { return false }
            return !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        } || !strengths.isEmpty || !vibeTags.isEmpty
    }

    var scoreText: String? {
        guard let score, score.isFinite else { return nil }
        let score10 = score <= 1 ? score * 10 : score
        return String(format: "%.1f", min(10, max(0, score10)))
    }

    static func makeCandidates(
        from images: [UIImage],
        scanOverlayImages: [UIImage?],
        result: AnalysisResultPayload
    ) -> [BestPhotoCandidate] {
        var rankingsByIndex: [Int: AnalysisPhotoRanking] = [:]
        for ranking in result.facemaxxPhotoRankings
            where (1...images.count).contains(ranking.candidateIndex) {
            if let existing = rankingsByIndex[ranking.candidateIndex], existing.rank <= ranking.rank {
                continue
            }
            rankingsByIndex[ranking.candidateIndex] = ranking
        }

        let structuredWinnerIndex = rankingsByIndex.values
            .sorted {
                if $0.rank == $1.rank {
                    return $0.candidateIndex < $1.candidateIndex
                }
                return $0.rank < $1.rank
            }
            .first?
            .candidateIndex

        let winnerIndex = structuredWinnerIndex
            ?? result.facemaxxInferredBestCandidateIndex(maxCandidateCount: images.count)
            ?? 1
        var fallbackRanks: [Int: Int] = [winnerIndex: 1]
        let remainingIndexes = Array(1...images.count).filter { $0 != winnerIndex }
        for (offset, candidateIndex) in remainingIndexes.enumerated() {
            fallbackRanks[candidateIndex] = offset + 2
        }

        return images.enumerated().map { offset, image in
            let index = offset + 1
            let ranking = rankingsByIndex[index]
            return BestPhotoCandidate(
                index: index,
                image: image,
                scanOverlayImage: scanOverlayImages[safe: offset] ?? nil,
                rank: normalizedRank(for: index, rankingsByIndex: rankingsByIndex, fallbackRanks: fallbackRanks),
                score: ranking?.score,
                verdict: ranking?.verdict,
                reasonText: ranking?.reasonText,
                descriptionText: ranking?.descriptionText,
                bestUseText: ranking?.bestUseText,
                funLabelText: ranking?.funLabelText,
                strengths: ranking?.strengths ?? [],
                weaknessText: ranking?.weaknessText,
                fixText: ranking?.fixText,
                captionIdeaText: ranking?.captionIdeaText,
                vibeTags: ranking?.vibeTags ?? []
            )
        }
    }

    private static func normalizedRank(
        for candidateIndex: Int,
        rankingsByIndex: [Int: AnalysisPhotoRanking],
        fallbackRanks: [Int: Int]
    ) -> Int {
        guard !rankingsByIndex.isEmpty else {
            return fallbackRanks[candidateIndex] ?? candidateIndex
        }

        let orderedIndexes = rankingsByIndex.values
            .sorted {
                if $0.rank == $1.rank {
                    let leftScore = $0.score ?? -1
                    let rightScore = $1.score ?? -1
                    if leftScore == rightScore {
                        return $0.candidateIndex < $1.candidateIndex
                    }
                    return leftScore > rightScore
                }
                return $0.rank < $1.rank
            }
            .map(\.candidateIndex)

        if let offset = orderedIndexes.firstIndex(of: candidateIndex) {
            return offset + 1
        }
        return fallbackRanks[candidateIndex] ?? candidateIndex
    }
}

private extension AnalysisResultPayload {
    func facemaxxInferredBestCandidateIndex(maxCandidateCount: Int) -> Int? {
        guard maxCandidateCount > 1 else { return nil }
        let fragments = [summaryText] + metrics.flatMap {
            [$0.valueText, $0.statusText, $0.detailText]
        }
        let text = fragments
            .compactMap { $0?.lowercased() }
            .joined(separator: " ")

        guard !text.isEmpty else { return nil }
        for index in 1...maxCandidateCount where winningTextPatterns(for: index).contains(where: text.contains) {
            return index
        }
        return nil
    }

    private func winningTextPatterns(for index: Int) -> [String] {
        [
            "candidate \(index) is the best",
            "candidate \(index) is best",
            "candidate \(index) is the strongest",
            "candidate \(index) is strongest",
            "candidate \(index) should lead",
            "candidate \(index) leads",
            "best candidate is \(index)",
            "best current main-pick candidate is candidate \(index)",
            "photo \(index) is the best",
            "photo \(index) is best",
            "photo \(index) should lead",
            "후보 \(index)이 가장",
            "후보 \(index)가 가장",
            "\(index)번 사진이 가장",
            "\(index)번이 가장"
        ]
    }
}

private struct PhotoOptimizationSummaryCard: View {
    let summaryText: String?
    let fallbackKey: LocalizedStringKey

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("analysis.photoOptimization.summary")
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()

            LocalizedOrRemoteText(key: fallbackKey, text: summaryText)
                .font(.body.weight(.medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct AnalysisPotentialScoreCard: View {
    let score: Double
    let progress: Double

    var body: some View {
        ProportionsScoreBar(
            iconName: "arrow.up.right.circle.fill",
            titleKey: "analysis.results.potentialScore",
            valueKey: "analysis.results.potentialScoreValue",
            valueText: String(format: "%.1f/10", score),
            progress: progress
        )
        .fixedMovingLayer()
    }
}

private struct PhotoOptimizationResultConfiguration {
    let modeID: String
    let titleKey: LocalizedStringKey
    let badgeKey: LocalizedStringKey
    let primarySectionID: String
    let primaryTitleKey: LocalizedStringKey
    let secondarySectionID: String
    let secondaryTitleKey: LocalizedStringKey
    let summaryKey: LocalizedStringKey
    let fallbackOverallScore: Double
    let fallbackPotentialScore: Double
    let rings: [ProportionRingMetric]
    let primaryMetrics: [ProportionExpandableMetric]
    let secondaryMetrics: [ProportionExpandableMetric]
}

private enum PhotoOptimizationResultData {
    static func configuration(for modeID: String) -> PhotoOptimizationResultConfiguration {
        switch modeID {
        case "best-angle-finder":
            return bestAngleFinder
        case "dating-profile-score":
            return datingProfileScore
        case "instagram-profile-score":
            return instagramProfileScore
        default:
            return bestPhotoSelector
        }
    }

    nonisolated(unsafe) private static let bestPhotoSelector = PhotoOptimizationResultConfiguration(
        modeID: "best-photo-selector",
        titleKey: "analysis.mode.bestPhotoSelector",
        badgeKey: "analysis.badge.proScan",
        primarySectionID: "photo_selection",
        primaryTitleKey: "analysis.photoOptimization.section.photoSelection",
        secondarySectionID: "improvement_plan",
        secondaryTitleKey: "analysis.photoOptimization.section.improvementPlan",
        summaryKey: "analysis.photoOptimization.summaryBody",
        fallbackOverallScore: 8.1,
        fallbackPotentialScore: 9.0,
        rings: [
            ring("clarity", "analysis.photoOptimization.ring.clarity", 0.86, "8.6"),
            ring("expression", "analysis.photoOptimization.ring.expression", 0.78, "7.8"),
            ring("lighting", "analysis.photoOptimization.ring.lighting", 0.82, "8.2"),
            ring("composition", "analysis.photoOptimization.ring.composition", 0.80, "8.0"),
            ring("background", "analysis.photoOptimization.ring.background", 0.69, "6.9", FXTheme.yellow),
            ring("presence", "analysis.photoOptimization.ring.presence", 0.83, "8.3")
        ],
        primaryMetrics: [
            metric("best-pick-readiness", "analysis.photoOptimization.metric.bestPickReadiness", "analysis.photoOptimization.metric.bestPickReadinessValue", "analysis.photoOptimization.metric.bestPickReadinessDetail", "checkmark.seal.fill"),
            metric("face-visibility", "analysis.photoOptimization.metric.faceVisibility", "analysis.photoOptimization.metric.faceVisibilityValue", "analysis.photoOptimization.metric.faceVisibilityDetail", "face.smiling"),
            metric("expression-warmth", "analysis.photoOptimization.metric.expressionWarmth", "analysis.photoOptimization.metric.expressionWarmthValue", "analysis.photoOptimization.metric.expressionWarmthDetail", "face.smiling")
        ],
        secondaryMetrics: []
    )

    nonisolated(unsafe) private static let bestAngleFinder = PhotoOptimizationResultConfiguration(
        modeID: "best-angle-finder",
        titleKey: "analysis.mode.bestAngleFinder",
        badgeKey: "analysis.badge.proScan",
        primarySectionID: "angle_breakdown",
        primaryTitleKey: "analysis.photoOptimization.section.angleBreakdown",
        secondarySectionID: "capture_plan",
        secondaryTitleKey: "analysis.photoOptimization.section.capturePlan",
        summaryKey: "analysis.photoOptimization.summaryBody",
        fallbackOverallScore: 7.9,
        fallbackPotentialScore: 8.9,
        rings: [
            ring("front", "analysis.photoOptimization.ring.front", 0.76, "7.6"),
            ring("left", "analysis.photoOptimization.ring.left", 0.84, "8.4"),
            ring("right", "analysis.photoOptimization.ring.right", 0.80, "8.0"),
            ring("high-angle", "analysis.photoOptimization.ring.highAngle", 0.72, "7.2"),
            ring("low-angle", "analysis.photoOptimization.ring.lowAngle", 0.58, "5.8", FXTheme.yellow),
            ring("presence", "analysis.photoOptimization.ring.presence", 0.82, "8.2")
        ],
        primaryMetrics: [
            metric("best-angle", "analysis.photoOptimization.metric.bestAngle", "analysis.photoOptimization.metric.bestAngleValue", "analysis.photoOptimization.metric.bestAngleDetail", "viewfinder"),
            metric("front-read", "analysis.photoOptimization.metric.frontRead", "analysis.photoOptimization.metric.frontReadValue", "analysis.photoOptimization.metric.frontReadDetail", "person.crop.square"),
            metric("camera-height", "analysis.photoOptimization.metric.cameraHeight", "analysis.photoOptimization.metric.cameraHeightValue", "analysis.photoOptimization.metric.cameraHeightDetail", "camera.viewfinder")
        ],
        secondaryMetrics: []
    )

    nonisolated(unsafe) private static let datingProfileScore = PhotoOptimizationResultConfiguration(
        modeID: "dating-profile-score",
        titleKey: "analysis.mode.datingProfileScore",
        badgeKey: "analysis.badge.proScan",
        primarySectionID: "dating_profile",
        primaryTitleKey: "analysis.photoOptimization.section.datingProfile",
        secondarySectionID: "profile_plan",
        secondaryTitleKey: "analysis.photoOptimization.section.profilePlan",
        summaryKey: "analysis.photoOptimization.summaryBody",
        fallbackOverallScore: 7.8,
        fallbackPotentialScore: 8.8,
        rings: [
            ring("first-impression", "analysis.photoOptimization.ring.firstImpression", 0.79, "7.9"),
            ring("approachability", "analysis.photoOptimization.ring.approachability", 0.73, "7.3"),
            ring("confidence", "analysis.photoOptimization.ring.confidence", 0.81, "8.1"),
            ring("trust", "analysis.photoOptimization.ring.trust", 0.84, "8.4"),
            ring("style", "analysis.photoOptimization.ring.style", 0.75, "7.5"),
            ring("conversation", "analysis.photoOptimization.ring.conversation", 0.64, "6.4", FXTheme.yellow)
        ],
        primaryMetrics: [
            metric("main-photo-suitability", "analysis.photoOptimization.metric.mainPhotoSuitability", "analysis.photoOptimization.metric.mainPhotoSuitabilityValue", "analysis.photoOptimization.metric.mainPhotoSuitabilityDetail", "heart.fill"),
            metric("first-swipe-read", "analysis.photoOptimization.metric.firstSwipeRead", "analysis.photoOptimization.metric.firstSwipeReadValue", "analysis.photoOptimization.metric.firstSwipeReadDetail", "sparkles"),
            metric("approachability", "analysis.photoOptimization.metric.approachability", "analysis.photoOptimization.metric.approachabilityValue", "analysis.photoOptimization.metric.approachabilityDetail", "bubble.left.and.bubble.right.fill"),
            metric("confidence-signal", "analysis.photoOptimization.metric.confidenceSignal", "analysis.photoOptimization.metric.confidenceSignalValue", "analysis.photoOptimization.metric.confidenceSignalDetail", "bolt.fill"),
            metric("trust-signal", "analysis.photoOptimization.metric.trustSignal", "analysis.photoOptimization.metric.trustSignalValue", "analysis.photoOptimization.metric.trustSignalDetail", "checkmark.shield.fill"),
            metric("style-signal", "analysis.photoOptimization.metric.styleSignal", "analysis.photoOptimization.metric.styleSignalValue", "analysis.photoOptimization.metric.styleSignalDetail", "person.crop.square.fill"),
            metric("conversation-hook", "analysis.photoOptimization.metric.conversationHook", "analysis.photoOptimization.metric.conversationHookValue", "analysis.photoOptimization.metric.conversationHookDetail", "quote.bubble.fill"),
            metric("photo-context", "analysis.photoOptimization.metric.photoContext", "analysis.photoOptimization.metric.photoContextValue", "analysis.photoOptimization.metric.photoContextDetail", "rectangle.stack.fill"),
            metric("red-flag-risk", "analysis.photoOptimization.metric.redFlagRisk", "analysis.photoOptimization.metric.redFlagRiskValue", "analysis.photoOptimization.metric.redFlagRiskDetail", "exclamationmark.triangle.fill")
        ],
        secondaryMetrics: [
            metric("photo-mix", "analysis.photoOptimization.metric.photoMix", "analysis.photoOptimization.metric.photoMixValue", "analysis.photoOptimization.metric.photoMixDetail", "rectangle.stack.fill"),
            metric("profile-role", "analysis.photoOptimization.metric.profileRole", "analysis.photoOptimization.metric.profileRoleValue", "analysis.photoOptimization.metric.profileRoleDetail", "person.crop.square.fill"),
            metric("message-bait", "analysis.photoOptimization.metric.messageBait", "analysis.photoOptimization.metric.messageBaitValue", "analysis.photoOptimization.metric.messageBaitDetail", "text.bubble.fill"),
            metric("missing-shot", "analysis.photoOptimization.metric.missingShot", "analysis.photoOptimization.metric.missingShotValue", "analysis.photoOptimization.metric.missingShotDetail", "camera.fill"),
            metric("opener-angle", "analysis.photoOptimization.metric.openerAngle", "analysis.photoOptimization.metric.openerAngleValue", "analysis.photoOptimization.metric.openerAngleDetail", "wand.and.stars"),
            metric("avoid-profile", "analysis.photoOptimization.metric.avoidProfile", "analysis.photoOptimization.metric.avoidProfileValue", "analysis.photoOptimization.metric.avoidProfileDetail", "exclamationmark.triangle.fill")
        ]
    )

    nonisolated(unsafe) private static let instagramProfileScore = PhotoOptimizationResultConfiguration(
        modeID: "instagram-profile-score",
        titleKey: "analysis.mode.instagramProfileScore",
        badgeKey: "analysis.badge.proScan",
        primarySectionID: "instagram_profile",
        primaryTitleKey: "analysis.photoOptimization.section.instagramProfile",
        secondarySectionID: "content_plan",
        secondaryTitleKey: "analysis.photoOptimization.section.contentPlan",
        summaryKey: "analysis.photoOptimization.summaryBody",
        fallbackOverallScore: 8.0,
        fallbackPotentialScore: 9.1,
        rings: [
            ring("visual-impact", "analysis.photoOptimization.ring.visualImpact", 0.81, "8.1"),
            ring("crop", "analysis.photoOptimization.ring.crop", 0.78, "7.8"),
            ring("lighting", "analysis.photoOptimization.ring.lighting", 0.82, "8.2"),
            ring("feed-fit", "analysis.photoOptimization.ring.feedFit", 0.76, "7.6"),
            ring("shareability", "analysis.photoOptimization.ring.shareability", 0.74, "7.4"),
            ring("vibe", "analysis.photoOptimization.ring.vibe", 0.83, "8.3")
        ],
        primaryMetrics: [
            metric("profile-crop", "analysis.photoOptimization.metric.profileCrop", "analysis.photoOptimization.metric.profileCropValue", "analysis.photoOptimization.metric.profileCropDetail", "crop"),
            metric("thumbnail-impact", "analysis.photoOptimization.metric.thumbnailImpact", "analysis.photoOptimization.metric.thumbnailImpactValue", "analysis.photoOptimization.metric.thumbnailImpactDetail", "viewfinder"),
            metric("profile-icon-energy", "analysis.photoOptimization.metric.profileIconEnergy", "analysis.photoOptimization.metric.profileIconEnergyValue", "analysis.photoOptimization.metric.profileIconEnergyDetail", "person.crop.square.fill"),
            metric("first-impression", "analysis.photoOptimization.metric.firstImpression", "analysis.photoOptimization.metric.firstImpressionValue", "analysis.photoOptimization.metric.firstImpressionDetail", "sparkles"),
            metric("feed-fit", "analysis.photoOptimization.metric.feedFit", "analysis.photoOptimization.metric.feedFitValue", "analysis.photoOptimization.metric.feedFitDetail", "square.grid.3x3.fill"),
            metric("story-thumbnail", "analysis.photoOptimization.metric.storyThumbnail", "analysis.photoOptimization.metric.storyThumbnailValue", "analysis.photoOptimization.metric.storyThumbnailDetail", "circle.grid.cross.fill"),
            metric("scroll-stop-power", "analysis.photoOptimization.metric.scrollStopPower", "analysis.photoOptimization.metric.scrollStopPowerValue", "analysis.photoOptimization.metric.scrollStopPowerDetail", "bolt.fill"),
            metric("visual-consistency", "analysis.photoOptimization.metric.visualConsistency", "analysis.photoOptimization.metric.visualConsistencyValue", "analysis.photoOptimization.metric.visualConsistencyDetail", "slider.horizontal.3"),
            metric("color-mood", "analysis.photoOptimization.metric.colorMood", "analysis.photoOptimization.metric.colorMoodValue", "analysis.photoOptimization.metric.colorMoodDetail", "slider.horizontal.3")
        ],
        secondaryMetrics: [
            metric("caption-direction", "analysis.photoOptimization.metric.captionDirection", "analysis.photoOptimization.metric.captionDirectionValue", "analysis.photoOptimization.metric.captionDirectionDetail", "text.bubble.fill"),
            metric("grid-anchor", "analysis.photoOptimization.metric.gridAnchor", "analysis.photoOptimization.metric.gridAnchorValue", "analysis.photoOptimization.metric.gridAnchorDetail", "square.grid.3x3.fill"),
            metric("story-reply-trigger", "analysis.photoOptimization.metric.storyReplyTrigger", "analysis.photoOptimization.metric.storyReplyTriggerValue", "analysis.photoOptimization.metric.storyReplyTriggerDetail", "text.bubble.fill"),
            metric("carousel-use", "analysis.photoOptimization.metric.carouselUse", "analysis.photoOptimization.metric.carouselUseValue", "analysis.photoOptimization.metric.carouselUseDetail", "rectangle.stack.fill"),
            metric("posting-rhythm", "analysis.photoOptimization.metric.postingRhythm", "analysis.photoOptimization.metric.postingRhythmValue", "analysis.photoOptimization.metric.postingRhythmDetail", "calendar"),
            metric("filter-risk", "analysis.photoOptimization.metric.filterRisk", "analysis.photoOptimization.metric.filterRiskValue", "analysis.photoOptimization.metric.filterRiskDetail", "exclamationmark.triangle.fill"),
            metric("posting-fix", "analysis.photoOptimization.metric.postingFix", "analysis.photoOptimization.metric.postingFixValue", "analysis.photoOptimization.metric.postingFixDetail", "wand.and.stars")
        ]
    )

    private static func ring(
        _ id: String,
        _ titleKey: LocalizedStringKey,
        _ value: Double,
        _ displayValue: String,
        _ tint: Color = FXTheme.green
    ) -> ProportionRingMetric {
        ProportionRingMetric(id: id, titleKey: titleKey, value: value, displayValue: displayValue, tint: tint)
    }

    private static func metric(
        _ id: String,
        _ titleKey: LocalizedStringKey,
        _ valueKey: LocalizedStringKey,
        _ detailKey: LocalizedStringKey,
        _ iconName: String
    ) -> ProportionExpandableMetric {
        ProportionExpandableMetric(
            id: id,
            titleKey: titleKey,
            valueKey: valueKey,
            detailKey: detailKey,
            iconName: iconName
        )
    }
}

private struct AestheticsHeaderCard: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    @Binding var expandedIDs: Set<String>
    let reduceMotion: Bool
    var visibleMetricLimit: Int? = nil
    var unlockAction: () -> Void = {}

    private var cardLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(spacing: 28) {
            AnalysisResultPhotoFrame(
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            AestheticMetricSection(
                titleKey: "analysis.aestheticsResults.shapes",
                badgeKey: nil,
                badgeStyle: .blue,
                metrics: result.metrics.facemaxxAestheticMetrics(in: "shapes", fallback: AestheticsResultData.shapes),
                expandedIDs: $expandedIDs,
                reduceMotion: reduceMotion,
                visibleMetricLimit: visibleMetricLimit,
                unlockAction: unlockAction
            )
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 28)
        .fxCard(cornerRadius: 34)
        .animation(cardLayoutAnimation, value: expandedIDs)
    }
}

private struct AestheticMetricSection: View {
    let titleKey: LocalizedStringKey
    let badgeKey: LocalizedStringKey?
    let badgeStyle: AestheticResultBadge.Style
    let metrics: [AestheticExpandableMetric]
    @Binding var expandedIDs: Set<String>
    let reduceMotion: Bool
    var visibleMetricLimit: Int? = nil
    var showsUnlockCard = false
    var unlockAction: () -> Void = {}

    private var listLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.66, dampingFraction: 0.90, blendDuration: 0.18)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                Text(titleKey)
                    .font(.title2.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .stableDuringListMotion()

                Spacer(minLength: 12)

                if let badgeKey {
                    AestheticResultBadge(titleKey: badgeKey, style: badgeStyle)
                        .fixedMovingLayer()
                }
            }
            .fixedMovingLayer()

            VStack(spacing: 12) {
                ForEach(Array(metrics.enumerated()), id: \.element.id) { index, metric in
                    if isLocked(index: index) {
                        TrialLockedMetricRow(
                            titleKey: metric.titleKey,
                            iconName: metric.iconName,
                            action: unlockAction
                        )
                        .fixedMovingLayer()
                    } else {
                        AestheticExpandableMetricRow(
                            metric: metric,
                            isExpanded: expandedIDs.contains(metric.id),
                            reduceMotion: reduceMotion,
                            toggle: { toggle(metric.id) }
                        )
                        .fixedMovingLayer()
                    }
                }

                if showsUnlockCard {
                    TrialUnlockFullResultsCard(action: unlockAction)
                        .fixedMovingLayer()
                }
            }
            .animation(listLayoutAnimation, value: expandedIDs)
        }
    }

    private func isLocked(index: Int) -> Bool {
        guard let visibleMetricLimit else { return false }
        return index >= visibleMetricLimit
    }

    private func toggle(_ id: String) {
        if expandedIDs.contains(id) {
            expandedIDs.remove(id)
        } else {
            expandedIDs.insert(id)
        }
    }
}

private struct AestheticResultBadge: View {
    enum Style {
        case blue
        case green
    }

    let titleKey: LocalizedStringKey
    let style: Style

    private var tint: Color {
        switch style {
        case .blue:
            FXTheme.blue
        case .green:
            FXTheme.green
        }
    }

    private var fill: Color {
        switch style {
        case .blue:
            Color.white.opacity(0.24)
        case .green:
            FXTheme.green.opacity(0.20)
        }
    }

    var body: some View {
        Text(titleKey)
            .font(.caption2.weight(.heavy))
            .tracking(0.8)
            .foregroundStyle(tint)
            .lineLimit(1)
            .padding(.horizontal, 11)
            .padding(.vertical, 7)
            .background {
                Capsule(style: .continuous)
                    .fill(fill)
            }
            .stableDuringListMotion()
    }
}

private struct AestheticExpandableMetricRow: View {
    let metric: AestheticExpandableMetric
    let isExpanded: Bool
    let reduceMotion: Bool
    let toggle: () -> Void

    @Namespace private var valueNamespace

    private var disclosureAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.66, dampingFraction: 0.90, blendDuration: 0.18)
    }

    private var contentFadeAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .easeInOut(duration: 0.26)
    }

    private var chevronAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.28)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: toggle) {
                HStack(spacing: 12) {
                    Image(systemName: FacemaxxSFSymbol.safeName(metric.iconName))
                        .font(.system(size: 21, weight: .bold))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(width: 30)
                        .stableDuringListMotion()

                    LocalizedOrRemoteText(key: metric.titleKey, text: nil)
                        .font(.system(size: 17, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.82)
                        .layoutPriority(2)
                        .stableDuringListMotion()

                    Spacer(minLength: 8)

                    if !isExpanded, metric.hasVisibleValue {
                        AnalysisMetricValueLabel(
                            key: metric.valueKey,
                            text: metric.valueText,
                            tint: metric.valueTint
                        )
                        .matchedGeometryEffect(id: "\(metric.id)-value", in: valueNamespace)
                        .animation(contentFadeAnimation, value: isExpanded)
                    }

                    Image(systemName: "chevron.down")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                        .animation(chevronAnimation, value: isExpanded)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 16)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            CollapsibleContent(
                isExpanded: isExpanded,
                heightAnimation: disclosureAnimation,
                opacityAnimation: contentFadeAnimation,
                fadesContent: false
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    if isExpanded, metric.hasVisibleValue {
                        AnalysisMetricValueLabel(
                            key: metric.valueKey,
                            text: metric.valueText,
                            tint: metric.valueTint,
                            frameWidth: nil,
                            frameAlignment: .leading,
                            textAlignment: .leading
                        )
                        .matchedGeometryEffect(id: "\(metric.id)-value", in: valueNamespace)
                    }

                    LocalizedOrRemoteText(key: metric.detailKey, text: metric.detailText)
                        .font(.system(size: 15.5, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .stableDuringListMotion()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 18)
            }
        }
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(isExpanded ? 0.16 : 0.06), lineWidth: 1)
                .animation(disclosureAnimation, value: isExpanded)
        }
    }
}

private struct ProportionsTopCard: View {
    let result: AnalysisResultPayload
    let image: UIImage?
    let scanPayload: FaceScanCapturePayload?
    let scanOverlayImage: UIImage?
    var hidesRingGrid = false
    var unlockAction: () -> Void = {}

    private var rings: [ProportionRingMetric] {
        let mapped = result.rings
            .sorted { $0.sortOrder < $1.sortOrder }
            .map(ProportionRingMetric.init)
        return mapped.isEmpty ? ProportionsResultData.rings : mapped
    }

    var body: some View {
        VStack(spacing: 28) {
            AnalysisResultPhotoFrame(
                image: image,
                scanPayload: scanPayload,
                scanOverlayImage: scanOverlayImage
            )

            if hidesRingGrid {
                TrialLockedRingGridPreview(action: unlockAction)
            } else {
                LazyVGrid(
                    columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3),
                    spacing: 18
                ) {
                    ForEach(rings) { metric in
                        ProportionScoreRing(metric: metric)
                    }
                }
            }

            ProportionsScoreBar(
                iconName: "chart.bar.fill",
                titleKey: "analysis.results.overall",
                valueKey: "analysis.results.overallValue",
                valueText: result.facemaxxOverallScore10.map { String(format: "%.1f/10", $0) },
                progress: result.facemaxxOverallProgress
            )
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 28)
        .fxCard(cornerRadius: 34)
    }
}

private struct LandmarkFacePreview: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.16, green: 0.18, blue: 0.20),
                    Color(red: 0.04, green: 0.045, blue: 0.05)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Image(systemName: "person.crop.square.fill")
                .font(.system(size: 128, weight: .light))
                .foregroundStyle(Color.white.opacity(0.22))

            Canvas { context, size in
                let face = CGRect(
                    x: size.width * 0.28,
                    y: size.height * 0.18,
                    width: size.width * 0.44,
                    height: size.height * 0.62
                )

                let rows: [CGFloat] = [0.15, 0.24, 0.33, 0.43, 0.54, 0.64, 0.74, 0.83]
                for row in rows {
                    let y = face.minY + face.height * row
                    let halfWidth = face.width * (0.16 + sin(row * .pi) * 0.38)
                    for index in 0..<9 {
                        let fraction = CGFloat(index) / 8
                        let x = face.midX - halfWidth + halfWidth * 2 * fraction
                        drawDot(at: CGPoint(x: x, y: y), context: context)
                    }
                }

                for point in [
                    CGPoint(x: face.midX - face.width * 0.15, y: face.minY + face.height * 0.38),
                    CGPoint(x: face.midX + face.width * 0.15, y: face.minY + face.height * 0.38),
                    CGPoint(x: face.midX, y: face.minY + face.height * 0.54),
                    CGPoint(x: face.midX - face.width * 0.13, y: face.minY + face.height * 0.68),
                    CGPoint(x: face.midX + face.width * 0.13, y: face.minY + face.height * 0.68)
                ] {
                    drawDot(at: point, radius: 2.6, opacity: 0.95, context: context)
                }
            }
        }
        .clipShape(.rect(cornerRadius: 31, style: .continuous))
    }

    private func drawDot(
        at point: CGPoint,
        radius: CGFloat = 1.7,
        opacity: Double = 0.82,
        context: GraphicsContext
    ) {
        let rect = CGRect(
            x: point.x - radius,
            y: point.y - radius,
            width: radius * 2,
            height: radius * 2
        )
        context.fill(Path(ellipseIn: rect), with: .color(FXTheme.blue.opacity(opacity)))
    }
}

private struct ProportionScoreRing: View {
    let metric: ProportionRingMetric

    @Environment(\.isRenderingStaticAnalysisShare) private var isRenderingStaticAnalysisShare
    @State private var visibleValue = 0.0

    private var visibleProgress: Double {
        isRenderingStaticAnalysisShare ? metric.value : (visibleValue > 0 ? visibleValue : metric.value)
    }

    private var ringProgress: Double {
        isRenderingStaticAnalysisShare ? metric.value : visibleValue
    }

    private var dynamicTint: Color {
        FacemaxxScorePalette.accent(forProgress: visibleProgress)
    }

    private var glowTint: Color {
        FacemaxxScorePalette.glow(forProgress: visibleProgress)
    }

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                dynamicTint.opacity(0.10),
                                FXTheme.card.opacity(0.18)
                            ],
                            center: .center,
                            startRadius: 4,
                            endRadius: 32
                        )
                    )

                Circle()
                    .stroke(Color.white.opacity(0.075), lineWidth: 7.5)

                Circle()
                    .trim(from: 0, to: ringProgress.clampedToUnit())
                    .stroke(dynamicTint, style: StrokeStyle(lineWidth: 7.5, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .shadow(color: glowTint.opacity(0.22), radius: 6, y: 1)

                Text(metric.displayValue)
                    .font(.subheadline.weight(.black))
                    .foregroundStyle(FXTheme.textPrimary)
                    .monospacedDigit()
            }
            .frame(width: 62, height: 62)

            Text(metric.titleKey)
                .font(.caption2.weight(.bold))
                .foregroundStyle(FXTheme.textPrimary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.78)
        }
        .frame(maxWidth: .infinity)
        .onAppear {
            if isRenderingStaticAnalysisShare {
                visibleValue = metric.value
                return
            }
            withAnimation(.smooth(duration: 0.65)) {
                visibleValue = metric.value
            }
        }
    }
}

private struct TrialLockedRingGridPreview: View {
    let action: () -> Void

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 14), count: 3)

    var body: some View {
        Button(action: action) {
            ZStack {
                LazyVGrid(columns: columns, spacing: 18) {
                    ForEach(0..<9, id: \.self) { index in
                        LockedRingPlaceholder(index: index)
                    }
                }
                .padding(.horizontal, 14)
                .blur(radius: 5.5)
                .opacity(0.42)
                .allowsHitTesting(false)

                LinearGradient(
                    colors: [
                        FXTheme.card.opacity(0.30),
                        FXTheme.card.opacity(0.88)
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .allowsHitTesting(false)

                VStack(spacing: 13) {
                    ZStack {
                        Circle()
                            .fill(FXTheme.premiumBlue.opacity(0.22))
                        Image(systemName: "lock.fill")
                            .font(.system(size: 24, weight: .black))
                            .foregroundStyle(FXTheme.premiumBlue)
                    }
                    .frame(width: 60, height: 60)

                    VStack(spacing: 6) {
                        Text("analysis.trial.metricGridLockedTitle")
                            .font(.headline.weight(.black))
                            .foregroundStyle(FXTheme.textPrimary)
                            .multilineTextAlignment(.center)

                        Text("analysis.trial.metricGridLockedBody")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(FXTheme.textSecondary)
                            .multilineTextAlignment(.center)
                            .lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    HStack(spacing: 7) {
                        Text("analysis.trial.unlockButton")
                            .font(.subheadline.weight(.black))
                        Image(systemName: "arrow.right")
                            .font(.caption.weight(.black))
                    }
                    .foregroundStyle(FXTheme.textPrimary)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 11)
                    .background(FXTheme.premiumBlue.opacity(0.88), in: Capsule(style: .continuous))
                }
                .padding(24)
            }
            .frame(maxWidth: .infinity, minHeight: 260)
            .background(
                LinearGradient(
                    colors: [
                        FXTheme.cardElevated.opacity(0.97),
                        FXTheme.card.opacity(0.98)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 28, style: .continuous)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(
                        LinearGradient(
                            colors: [
                                FXTheme.premiumBlue.opacity(0.30),
                                Color.white.opacity(0.07)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1
                    )
            }
            .contentShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct LockedRingPlaceholder: View {
    let index: Int

    private var progress: Double {
        [0.82, 0.74, 0.68, 0.78, 0.63, 0.72, 0.86, 0.69, 0.76][safe: index] ?? 0.72
    }

    var body: some View {
        VStack(spacing: 7) {
            ZStack {
                Circle()
                    .fill(FXTheme.card.opacity(0.45))

                Circle()
                    .stroke(Color.white.opacity(0.10), lineWidth: 7)

                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(FacemaxxScorePalette.accent(forProgress: progress), style: StrokeStyle(lineWidth: 7, lineCap: .round))
                    .rotationEffect(.degrees(-90))

                RoundedRectangle(cornerRadius: 2, style: .continuous)
                    .fill(Color.white.opacity(0.16))
                    .frame(width: 18, height: 4)
            }
            .frame(width: 56, height: 56)

            RoundedRectangle(cornerRadius: 2, style: .continuous)
                .fill(Color.white.opacity(0.12))
                .frame(width: 34, height: 5)
        }
        .frame(maxWidth: .infinity)
    }
}

private struct ProportionsScoreBar: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let valueKey: LocalizedStringKey
    var valueText: String? = nil
    let progress: Double
    var accentColor: Color? = nil

    @Environment(\.isRenderingStaticAnalysisShare) private var isRenderingStaticAnalysisShare
    @State private var visibleProgress = 0.0

    private var renderedProgress: Double {
        isRenderingStaticAnalysisShare ? progress.clampedToUnit() : visibleProgress
    }

    private var resolvedAccentColor: Color {
        accentColor ?? FacemaxxScorePalette.accent(forProgress: renderedProgress)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 16) {
                Image(systemName: FacemaxxSFSymbol.safeName(iconName))
                    .font(.title2.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .frame(width: 34)

                Text(titleKey)
                    .font(.title3.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer(minLength: 12)

                LocalizedOrRemoteText(key: valueKey, text: valueText)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .monospacedDigit()
            }

            PremiumScoreGauge(progress: renderedProgress, accentColor: resolvedAccentColor)
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 20)
        .background {
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .onAppear {
            if isRenderingStaticAnalysisShare {
                visibleProgress = progress.clampedToUnit()
                return
            }
            withAnimation(.smooth(duration: 0.65)) {
                visibleProgress = progress.clampedToUnit()
            }
        }
        .onChange(of: progress) { _, newValue in
            if isRenderingStaticAnalysisShare {
                visibleProgress = newValue.clampedToUnit()
                return
            }
            withAnimation(.smooth(duration: 0.45)) {
                visibleProgress = newValue.clampedToUnit()
            }
        }
    }
}

private struct PremiumScoreGauge: View {
    let progress: Double
    let accentColor: Color

    var body: some View {
        GeometryReader { proxy in
            let clampedProgress = progress.clampedToUnit()
            let fillWidth = max(10, proxy.size.width * clampedProgress)
            let glowColor = FacemaxxScorePalette.glow(forProgress: clampedProgress)
            let highlightColor = FacemaxxScorePalette.highlight(forProgress: clampedProgress)

            ZStack(alignment: .leading) {
                Capsule(style: .continuous)
                    .fill(Color.white.opacity(0.07))
                    .overlay(alignment: .top) {
                        Capsule(style: .continuous)
                            .fill(Color.white.opacity(0.055))
                            .frame(height: 3)
                            .padding(.horizontal, 2)
                    }

                Capsule(style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [
                                accentColor.opacity(0.72),
                                glowColor.opacity(0.94),
                                highlightColor
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: fillWidth)
                    .shadow(color: glowColor.opacity(0.18 + clampedProgress * 0.16), radius: 7 + clampedProgress * 5, y: 1)
                    .overlay(alignment: .trailing) {
                        Circle()
                            .fill(Color.white.opacity(0.92))
                            .frame(width: 7, height: 7)
                            .padding(.trailing, 3)
                            .opacity(clampedProgress > 0.06 ? 1 : 0)
                    }
            }
        }
        .frame(height: 11)
        .accessibilityHidden(true)
    }
}

private enum FacemaxxScorePalette {
    static func accent(forProgress progress: Double) -> Color {
        let clamped = progress.clampedToUnit()
        return Color(
            hue: 0.30 + clamped * 0.055,
            saturation: 0.18 + clamped * 0.20,
            brightness: 0.62 + clamped * 0.22
        )
    }

    static func glow(forProgress progress: Double) -> Color {
        let clamped = progress.clampedToUnit()
        return Color(
            hue: 0.31 + clamped * 0.055,
            saturation: 0.20 + clamped * 0.18,
            brightness: 0.72 + clamped * 0.18
        )
    }

    static func highlight(forProgress progress: Double) -> Color {
        let clamped = progress.clampedToUnit()
        return Color(
            hue: 0.33 + clamped * 0.040,
            saturation: 0.14 + clamped * 0.12,
            brightness: 0.78 + clamped * 0.16
        )
    }
}

private enum FacemaxxSFSymbol {
    static func safeName(_ name: String) -> String {
        aliases[name] ?? name
    }

    private static let aliases: [String: String] = [
        "angle": "arrow.up.left.and.arrow.down.right",
        "bolt.heart.fill": "bolt.fill",
        "camera.viewfinder": "viewfinder",
        "checkmark.shield.fill": "checkmark.seal.fill",
        "circle.grid.cross.fill": "circle.grid.3x3.fill",
        "eyebrow": "eye.fill",
        "mouth": "mouth.fill",
        "person.crop.square": "person.crop.square.fill",
        "quote.bubble.fill": "text.bubble.fill",
        "shield.checkmark.fill": "checkmark.seal.fill",
        "sparkle": "sparkles"
    ]
}

private struct ProportionsMetricSection: View {
    let titleKey: LocalizedStringKey
    let metrics: [ProportionExpandableMetric]
    @Binding var expandedIDs: Set<String>
    let reduceMotion: Bool
    var visibleMetricLimit: Int? = nil
    var showsUnlockCard = false
    var unlockAction: () -> Void = {}

    private var listLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(titleKey)
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()
                .fixedMovingLayer()

            VStack(spacing: 12) {
                ForEach(Array(metrics.enumerated()), id: \.element.id) { index, metric in
                    if isLocked(index: index) {
                        TrialLockedMetricRow(
                            titleKey: metric.titleKey,
                            iconName: metric.iconName,
                            action: unlockAction
                        )
                        .fixedMovingLayer()
                    } else {
                        ExpandableMetricRow(
                            metric: metric,
                            isExpanded: expandedIDs.contains(metric.id),
                            reduceMotion: reduceMotion,
                            toggle: { toggle(metric.id) }
                        )
                        .fixedMovingLayer()
                    }
                }

                if showsUnlockCard {
                    TrialUnlockFullResultsCard(action: unlockAction)
                        .fixedMovingLayer()
                }
            }
            .animation(listLayoutAnimation, value: expandedIDs)
        }
    }

    private func isLocked(index: Int) -> Bool {
        guard let visibleMetricLimit else { return false }
        return index >= visibleMetricLimit
    }

    private func toggle(_ id: String) {
        if expandedIDs.contains(id) {
            expandedIDs.remove(id)
        } else {
            expandedIDs.insert(id)
        }
    }
}

private struct ExpandableMetricRow: View {
    let metric: ProportionExpandableMetric
    let isExpanded: Bool
    let reduceMotion: Bool
    let toggle: () -> Void

    @Namespace private var valueNamespace

    private var disclosureAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    private var contentFadeAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .easeOut(duration: 0.18)
    }

    private var chevronAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.22)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: toggle) {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: FacemaxxSFSymbol.safeName(metric.iconName))
                        .font(.system(size: 21, weight: .bold))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(width: 30)
                        .padding(.top, 1)
                        .stableDuringListMotion()

                    VStack(alignment: .leading, spacing: 5) {
                        LocalizedOrRemoteText(key: metric.titleKey, text: nil)
                            .font(.system(size: 17, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .multilineTextAlignment(.leading)
                            .lineLimit(2)
                            .minimumScaleFactor(0.80)
                            .fixedSize(horizontal: false, vertical: true)
                            .stableDuringListMotion()

                        if !isExpanded, metric.hasVisibleValue {
                            AnalysisMetricValueLabel(
                                key: metric.valueKey,
                                text: metric.valueText,
                                tint: FXTheme.textSecondary,
                                frameWidth: nil,
                                frameAlignment: .leading,
                                textAlignment: .leading
                            )
                            .matchedGeometryEffect(id: "\(metric.id)-value", in: valueNamespace)
                            .animation(contentFadeAnimation, value: isExpanded)
                        }
                    }
                    .layoutPriority(2)

                    Spacer(minLength: 8)

                    Image(systemName: "chevron.down")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                        .padding(.top, 4)
                        .animation(chevronAnimation, value: isExpanded)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 16)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            CollapsibleContent(
                isExpanded: isExpanded,
                heightAnimation: disclosureAnimation,
                opacityAnimation: contentFadeAnimation,
                fadesContent: false
            ) {
                VStack(alignment: .leading, spacing: 12) {
                    if isExpanded, metric.hasVisibleValue {
                        AnalysisMetricValueLabel(
                            key: metric.valueKey,
                            text: metric.valueText,
                            tint: FXTheme.textSecondary,
                            frameWidth: nil,
                            frameAlignment: .leading,
                            textAlignment: .leading
                        )
                        .matchedGeometryEffect(id: "\(metric.id)-value", in: valueNamespace)
                    }

                    LocalizedOrRemoteText(key: metric.detailKey, text: metric.detailText)
                        .font(.system(size: 15.5, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .stableDuringListMotion()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 18)
            }
        }
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(isExpanded ? 0.16 : 0.06), lineWidth: 1)
                .animation(disclosureAnimation, value: isExpanded)
        }
    }
}

private struct GrowthOpportunitiesSection: View {
    let result: AnalysisResultPayload
    @Binding var isActionPlanExpanded: Bool
    let reduceMotion: Bool

    private var sectionLayoutAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("analysis.results.growthOpportunities")
                .font(.title2.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)

            ActionPlanCard(
                items: result.growthOpportunities.facemaxxActionPlanItems(fallback: ProportionsResultData.opportunityItems),
                isExpanded: $isActionPlanExpanded,
                reduceMotion: reduceMotion
            )
                .fixedMovingLayer()

            InsightCard(
                iconName: "person.crop.square.fill",
                titleKey: "analysis.results.lookArchetype",
                bodyKey: "analysis.results.lookArchetypeBody",
                bodyText: result.lookArchetype?.typeName,
                tint: FXTheme.textPrimary
            )
            .fixedMovingLayer()

            AnalysisPotentialScoreCard(
                score: result.facemaxxPotentialScore10 ?? 8.7,
                progress: result.facemaxxPotentialProgress
            )
            .fixedMovingLayer()

            LocalizedOrRemoteText(key: "analysis.results.summaryBody", text: result.summaryText)
                .font(.body.weight(.medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
                .fixedMovingLayer()
        }
        .animation(sectionLayoutAnimation, value: isActionPlanExpanded)
    }
}

private struct ActionPlanCard: View {
    let items: [ActionPlanItem]
    @Binding var isExpanded: Bool
    let reduceMotion: Bool

    private var disclosureAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.56, dampingFraction: 0.94, blendDuration: 0.12)
    }

    private var contentFadeAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .easeOut(duration: 0.18)
    }

    private var chevronAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.22)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Button {
                isExpanded.toggle()
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "clipboard.fill")
                        .font(.system(size: 21, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(width: 30)
                        .stableDuringListMotion()

                    Text("analysis.results.actionPlan")
                        .font(.system(size: 19, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.80)
                        .stableDuringListMotion()

                    Spacer()

                    Image(systemName: "chevron.down")
                        .font(.headline.weight(.bold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                        .animation(chevronAnimation, value: isExpanded)
                }
            }
            .buttonStyle(.plain)

            CollapsibleContent(
                isExpanded: isExpanded,
                heightAnimation: disclosureAnimation,
                opacityAnimation: contentFadeAnimation
            ) {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(items) { item in
                        ActionPlanBullet(item: item)
                    }
                }
            }
        }
        .padding(18)
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
        .clipShape(.rect(cornerRadius: 24, style: .continuous))
    }
}

private struct CollapsibleContent<Content: View>: View {
    let isExpanded: Bool
    let heightAnimation: Animation
    let opacityAnimation: Animation
    var fadesContent = true
    @ViewBuilder let content: Content

    @State private var contentHeight: CGFloat = 0

    var body: some View {
        content
            .background {
                GeometryReader { proxy in
                    Color.clear
                        .onAppear {
                            contentHeight = proxy.size.height
                        }
                        .onChange(of: proxy.size.height) { _, newHeight in
                            contentHeight = newHeight
                        }
                }
            }
            .compositingGroup()
            .frame(height: isExpanded ? contentHeight : 0, alignment: .top)
            .animation(heightAnimation, value: isExpanded)
            .opacity(fadesContent ? (isExpanded ? 1 : 0) : 1)
            .animation(opacityAnimation, value: isExpanded)
            .clipped()
    }
}

private struct ActionPlanBullet: View {
    let item: ActionPlanItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("•")
                .font(.body.weight(.bold))
                .foregroundStyle(FXTheme.textPrimary)
                .stableDuringListMotion()

            LocalizedOrRemoteText(key: item.bodyKey, text: item.bodyText)
                .font(.system(size: 15.5, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
        }
    }
}

private extension View {
    func stableDuringListMotion() -> some View {
        transaction { transaction in
            transaction.animation = nil
            transaction.disablesAnimations = true
        }
    }

    func fixedMovingLayer() -> some View {
        geometryGroup()
    }
}

private struct InsightCard: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    var bodyText: String? = nil
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                Image(systemName: FacemaxxSFSymbol.safeName(iconName))
                    .font(.system(size: 21, weight: .heavy))
                    .foregroundStyle(tint)
                    .frame(width: 30)
                    .stableDuringListMotion()

                Text(titleKey)
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.80)
                    .stableDuringListMotion()
            }

            LocalizedOrRemoteText(key: bodyKey, text: bodyText)
                .font(.system(size: 15.8, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .stableDuringListMotion()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(FXTheme.cardElevated.opacity(0.92))
        }
    }
}

private enum FacemaxxVisibleScoreFormatter {
    static func progressValue(from score: Double) -> Double {
        let normalized = score > 1 ? score / 10 : score
        return normalized.clampedToUnit()
    }

    static func ringDisplayValue(score: Double, displayValue: String) -> String {
        let trimmed = displayValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let numericValue = Double(trimmed.replacingOccurrences(of: ",", with: ".")) else {
            return displayValue
        }
        return scoreText(fromVisibleScore: numericValue <= 1 ? numericValue * 10 : numericValue)
    }

    static func metricValueText(for metric: AnalysisResultMetric) -> String? {
        guard let valueText = metric.valueText ?? metric.statusText else { return nil }
        guard shouldNormalizeScoreText(for: metric) else { return valueText }
        return normalizingLeadingScore(in: valueText)
    }

    private static func shouldNormalizeScoreText(for metric: AnalysisResultMetric) -> Bool {
        let unit = metric.unit?.lowercased()
        if unit == "score" || unit == "점수" {
            return true
        }

        let scoreSections: Set<String> = [
            "photo_selection",
            "improvement_plan",
            "angle_breakdown",
            "capture_plan",
            "dating_profile",
            "profile_plan",
            "instagram_profile",
            "content_plan"
        ]
        return scoreSections.contains(metric.section)
    }

    private static func normalizingLeadingScore(in text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        var endIndex = trimmed.startIndex
        while endIndex < trimmed.endIndex {
            let character = trimmed[endIndex]
            if character.isNumber || character == "." || character == "," {
                endIndex = trimmed.index(after: endIndex)
            } else {
                break
            }
        }

        guard endIndex > trimmed.startIndex else { return text }

        let numericPrefix = String(trimmed[..<endIndex]).replacingOccurrences(of: ",", with: ".")
        guard let number = Double(numericPrefix), number > 0, number <= 1 else {
            return text
        }

        let suffix = String(trimmed[endIndex...])
        guard suffix.isEmpty
            || suffix.first?.isWhitespace == true
            || suffix.hasPrefix("·")
            || suffix.hasPrefix("/")
            || suffix.hasPrefix("점") else {
            return text
        }
        return scoreText(fromVisibleScore: number * 10) + suffix
    }

    private static func scoreText(fromVisibleScore score: Double) -> String {
        let clamped = min(10, max(0, score))
        return String(format: "%.1f", clamped)
    }
}

private struct ProportionRingMetric: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let value: Double
    let displayValue: String
    let tint: Color

    init(id: String, titleKey: LocalizedStringKey, value: Double, displayValue: String, tint: Color) {
        self.id = id
        self.titleKey = titleKey
        self.value = value
        self.displayValue = displayValue
        self.tint = tint
    }

    init(_ ring: AnalysisScoreRing) {
        id = ring.metricID
        titleKey = LocalizedStringKey(AnalysisRingTitleKeySanitizer.titleKey(for: ring))
        value = FacemaxxVisibleScoreFormatter.progressValue(from: ring.score)
        displayValue = FacemaxxVisibleScoreFormatter.ringDisplayValue(
            score: ring.score,
            displayValue: ring.displayValue
        )
        tint = Color(facemaxxHex: ring.tint)
    }
}

private enum AnalysisRingTitleKeySanitizer {
    private static let knownByID: [String: String] = [
        "symmetry": "analysis.results.ring.symmetry",
        "skin": "analysis.results.ring.skin",
        "jawline": "analysis.results.ring.jawline",
        "eye-area": "analysis.results.ring.eyeArea",
        "cheekbones": "analysis.results.ring.cheekbones",
        "eyebrows": "analysis.results.ring.eyebrows",
        "glow": "analysis.results.ring.glow",
        "hair": "analysis.results.ring.hair",
        "harmony": "analysis.results.ring.harmony",
        "clarity": "analysis.photoOptimization.ring.clarity",
        "expression": "analysis.photoOptimization.ring.expression",
        "lighting": "analysis.photoOptimization.ring.lighting",
        "composition": "analysis.photoOptimization.ring.composition",
        "background": "analysis.photoOptimization.ring.background",
        "presence": "analysis.photoOptimization.ring.presence",
        "front": "analysis.photoOptimization.ring.front",
        "left": "analysis.photoOptimization.ring.left",
        "right": "analysis.photoOptimization.ring.right",
        "high-angle": "analysis.photoOptimization.ring.highAngle",
        "highangle": "analysis.photoOptimization.ring.highAngle",
        "low-angle": "analysis.photoOptimization.ring.lowAngle",
        "lowangle": "analysis.photoOptimization.ring.lowAngle",
        "first-impression": "analysis.photoOptimization.ring.firstImpression",
        "firstimpression": "analysis.photoOptimization.ring.firstImpression",
        "approachability": "analysis.photoOptimization.ring.approachability",
        "confidence": "analysis.photoOptimization.ring.confidence",
        "trust": "analysis.photoOptimization.ring.trust",
        "style": "analysis.photoOptimization.ring.style",
        "conversation": "analysis.photoOptimization.ring.conversation",
        "visual-impact": "analysis.photoOptimization.ring.visualImpact",
        "visualimpact": "analysis.photoOptimization.ring.visualImpact",
        "crop": "analysis.photoOptimization.ring.crop",
        "feed-fit": "analysis.photoOptimization.ring.feedFit",
        "feedfit": "analysis.photoOptimization.ring.feedFit",
        "shareability": "analysis.photoOptimization.ring.shareability",
        "vibe": "analysis.photoOptimization.ring.vibe"
    ]

    private static let knownKeys = Set(knownByID.values)
    private static let legacyKeyAliases: [String: String] = [
        "analysis.results.ring.front": "analysis.photoOptimization.ring.front",
        "analysis.results.ring.left": "analysis.photoOptimization.ring.left",
        "analysis.results.ring.right": "analysis.photoOptimization.ring.right",
        "analysis.results.ring.highAngle": "analysis.photoOptimization.ring.highAngle",
        "analysis.results.ring.lowAngle": "analysis.photoOptimization.ring.lowAngle",
        "analysis.results.ring.firstImpression": "analysis.photoOptimization.ring.firstImpression",
        "analysis.results.ring.approachability": "analysis.photoOptimization.ring.approachability",
        "analysis.results.ring.confidence": "analysis.photoOptimization.ring.confidence",
        "analysis.results.ring.trust": "analysis.photoOptimization.ring.trust",
        "analysis.results.ring.style": "analysis.photoOptimization.ring.style",
        "analysis.results.ring.conversation": "analysis.photoOptimization.ring.conversation",
        "analysis.results.ring.visualImpact": "analysis.photoOptimization.ring.visualImpact",
        "analysis.results.ring.crop": "analysis.photoOptimization.ring.crop",
        "analysis.results.ring.lighting": "analysis.photoOptimization.ring.lighting",
        "analysis.results.ring.feedFit": "analysis.photoOptimization.ring.feedFit",
        "analysis.results.ring.shareability": "analysis.photoOptimization.ring.shareability",
        "analysis.results.ring.vibe": "analysis.photoOptimization.ring.vibe"
    ]

    static func titleKey(for ring: AnalysisScoreRing) -> String {
        let normalizedID = ring.metricID
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: "_", with: "-")
            .replacingOccurrences(of: " ", with: "-")
        if let mapped = knownByID[normalizedID] {
            return mapped
        }

        let proposed = ring.titleKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if let mapped = legacyKeyAliases[proposed] {
            return mapped
        }
        if knownKeys.contains(proposed) {
            return proposed
        }
        return "analysis.results.ring.harmony"
    }
}

private struct ProportionExpandableMetric: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let valueKey: LocalizedStringKey
    var valueText: String? = nil
    var usesLocalizedFallbackValue = true
    let detailKey: LocalizedStringKey
    var detailText: String? = nil
    let iconName: String

    var hasVisibleValue: Bool {
        valueText?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false || usesLocalizedFallbackValue
    }

    init(
        id: String,
        titleKey: LocalizedStringKey,
        valueKey: LocalizedStringKey,
        valueText: String? = nil,
        usesLocalizedFallbackValue: Bool = true,
        detailKey: LocalizedStringKey,
        detailText: String? = nil,
        iconName: String
    ) {
        self.id = id
        self.titleKey = titleKey
        self.valueKey = valueKey
        self.valueText = valueText
        self.usesLocalizedFallbackValue = usesLocalizedFallbackValue
        self.detailKey = detailKey
        self.detailText = detailText
        self.iconName = iconName
    }

    init(_ metric: AnalysisResultMetric, fallback: ProportionExpandableMetric? = nil) {
        id = metric.metricID
        let sanitizedTitleKey = AnalysisMetricTitleKeySanitizer.titleKey(for: metric)
        let remoteValueText = FacemaxxVisibleScoreFormatter.metricValueText(for: metric)
        titleKey = fallback?.titleKey ?? LocalizedStringKey(sanitizedTitleKey)
        valueKey = fallback?.valueKey ?? LocalizedStringKey(sanitizedTitleKey)
        valueText = remoteValueText
        usesLocalizedFallbackValue = remoteValueText == nil ? (fallback?.usesLocalizedFallbackValue ?? false) : false
        detailKey = fallback?.detailKey ?? "analysis.results.metric.genericDetail"
        detailText = metric.detailText
        iconName = metric.iconName.isEmpty ? (fallback?.iconName ?? "face.smiling") : metric.iconName
    }
}

private struct AestheticExpandableMetric: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let valueKey: LocalizedStringKey
    var valueText: String? = nil
    var usesLocalizedFallbackValue = false
    let detailKey: LocalizedStringKey
    var detailText: String? = nil
    let iconName: String
    let valueTint: Color

    var hasVisibleValue: Bool {
        valueText?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false || usesLocalizedFallbackValue
    }

    init(
        id: String,
        titleKey: LocalizedStringKey,
        valueKey: LocalizedStringKey,
        valueText: String? = nil,
        usesLocalizedFallbackValue: Bool = true,
        detailKey: LocalizedStringKey,
        detailText: String? = nil,
        iconName: String,
        valueTint: Color
    ) {
        self.id = id
        self.titleKey = titleKey
        self.valueKey = valueKey
        self.valueText = valueText
        self.usesLocalizedFallbackValue = usesLocalizedFallbackValue
        self.detailKey = detailKey
        self.detailText = detailText
        self.iconName = iconName
        self.valueTint = valueTint
    }

    init(_ metric: AnalysisResultMetric, fallback: AestheticExpandableMetric? = nil) {
        id = metric.metricID
        let sanitizedTitleKey = AnalysisMetricTitleKeySanitizer.titleKey(for: metric)
        titleKey = fallback?.titleKey ?? LocalizedStringKey(sanitizedTitleKey)
        valueKey = fallback?.valueKey ?? LocalizedStringKey(sanitizedTitleKey)
        valueText = FacemaxxVisibleScoreFormatter.metricValueText(for: metric)
        usesLocalizedFallbackValue = fallback?.usesLocalizedFallbackValue ?? false
        detailKey = fallback?.detailKey ?? "analysis.results.metric.genericDetail"
        detailText = metric.detailText
        iconName = metric.iconName.isEmpty ? (fallback?.iconName ?? "face.smiling") : metric.iconName
        valueTint = Color(facemaxxHex: metric.valueTint)
    }
}

private enum AnalysisMetricTitleKeySanitizer {
    static func titleKey(for metric: AnalysisResultMetric) -> String {
        if let override = overrides[metric.metricID] {
            return override
        }
        if metric.titleKey.hasPrefix("analysis.") {
            return metric.titleKey
        }
        return "analysis.results.metric.symmetry"
    }

    private static let overrides: [String: String] = [
        "face-depth-width-ratio": "analysis.aestheticsResults.proportion.faceDepthWidthRatio",
        "face-contour-width-height-ratio": "analysis.aestheticsResults.proportion.faceContourWidthHeightRatio",
        "first-swipe-read": "analysis.photoOptimization.metric.firstSwipeRead",
        "style-signal": "analysis.photoOptimization.metric.styleSignal",
        "photo-context": "analysis.photoOptimization.metric.photoContext",
        "red-flag-risk": "analysis.photoOptimization.metric.redFlagRisk",
        "profile-role": "analysis.photoOptimization.metric.profileRole",
        "message-bait": "analysis.photoOptimization.metric.messageBait",
        "missing-shot": "analysis.photoOptimization.metric.missingShot",
        "opener-angle": "analysis.photoOptimization.metric.openerAngle",
        "thumbnail-impact": "analysis.photoOptimization.metric.thumbnailImpact",
        "profile-icon-energy": "analysis.photoOptimization.metric.profileIconEnergy",
        "scroll-stop-power": "analysis.photoOptimization.metric.scrollStopPower",
        "color-mood": "analysis.photoOptimization.metric.colorMood",
        "grid-anchor": "analysis.photoOptimization.metric.gridAnchor",
        "story-reply-trigger": "analysis.photoOptimization.metric.storyReplyTrigger",
        "carousel-use": "analysis.photoOptimization.metric.carouselUse",
        "posting-rhythm": "analysis.photoOptimization.metric.postingRhythm",
        "filter-risk": "analysis.photoOptimization.metric.filterRisk"
    ]
}

private struct GlowUpCoachMetric: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let assessmentKey: LocalizedStringKey
    var assessmentText: String? = nil
    let actionKey: LocalizedStringKey
    var actionText: String? = nil
    let iconName: String

    init(
        id: String,
        titleKey: LocalizedStringKey,
        assessmentKey: LocalizedStringKey,
        assessmentText: String? = nil,
        actionKey: LocalizedStringKey,
        actionText: String? = nil,
        iconName: String
    ) {
        self.id = id
        self.titleKey = titleKey
        self.assessmentKey = assessmentKey
        self.assessmentText = assessmentText
        self.actionKey = actionKey
        self.actionText = actionText
        self.iconName = iconName
    }

    init(_ item: AnalysisCoachItem, fallback: GlowUpCoachMetric? = nil) {
        id = item.itemID
        titleKey = GlowUpCoachTitleKeySanitizer.key(for: item.itemID, proposedKey: item.titleKey, fallback: fallback?.titleKey)
        assessmentKey = fallback?.assessmentKey ?? "analysis.results.coach.genericAssessment"
        assessmentText = item.assessmentText
        actionKey = fallback?.actionKey ?? "analysis.results.coach.genericAction"
        actionText = item.actionText
        iconName = item.iconName.isEmpty ? (fallback?.iconName ?? "sparkles") : item.iconName
    }
}

private enum GlowUpCoachTitleKeySanitizer {
    static func key(for itemID: String, proposedKey: String, fallback: LocalizedStringKey?) -> LocalizedStringKey {
        if let override = overrides[itemID] {
            return LocalizedStringKey(override)
        }
        if knownKeys.contains(proposedKey) {
            return LocalizedStringKey(proposedKey)
        }
        if let fallback {
            return fallback
        }
        return "analysis.glowUpCoach.item.skin"
    }

    private static let overrides: [String: String] = [
        "symmetry": "analysis.glowUpCoach.item.symmetry",
        "skin": "analysis.glowUpCoach.item.skin",
        "jawline": "analysis.glowUpCoach.item.jawline",
        "eye-area": "analysis.glowUpCoach.item.eyeArea",
        "eye_area": "analysis.glowUpCoach.item.eyeArea",
        "cheekbones": "analysis.glowUpCoach.item.cheekbones",
        "eyebrows": "analysis.glowUpCoach.item.eyebrows",
        "glow": "analysis.glowUpCoach.item.glow",
        "hair": "analysis.glowUpCoach.item.hair",
        "confidence": "analysis.glowUpCoach.item.confidence",
        "expression-confidence": "analysis.glowUpCoach.item.expressionConfidence",
        "expression_confidence": "analysis.glowUpCoach.item.expressionConfidence",
        "face-width-height-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-width-to-height-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-length-width-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-length-to-width-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face_width_height_ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "face-ratio": "analysis.glowUpCoach.item.faceWidthHeightRatio",
        "camera-angle": "analysis.glowUpCoach.item.cameraAngle",
        "camera_angle": "analysis.glowUpCoach.item.cameraAngle",
        "photo-angle": "analysis.glowUpCoach.item.cameraAngle",
        "lighting": "analysis.glowUpCoach.item.lighting",
        "grooming": "analysis.glowUpCoach.item.grooming",
        "photo-presence": "analysis.glowUpCoach.item.photoPresence",
        "photo_presence": "analysis.glowUpCoach.item.photoPresence",
        "skin-quality": "analysis.glowUpCoach.item.skinQuality",
        "skin_quality": "analysis.glowUpCoach.item.skinQuality",
        "harmony": "analysis.glowUpCoach.item.harmony",
        "harmony-strength": "analysis.glowUpCoach.item.harmony",
        "eye-area-strength": "analysis.glowUpCoach.item.eyeArea"
    ]

    private static let knownKeys = Set(overrides.values)
}

private struct LookArchetypeTrait: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    var titleText: String? = nil
    let tint: Color
}

private struct LookArchetypeSection: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    var titleText: String? = nil
    let iconName: String
    let tint: Color
    var isDefaultExpanded: Bool = false
    let items: [LookArchetypeBullet]
}

private struct LookArchetypeBullet: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    var titleText: String? = nil
    let iconName: String
}

private struct ActionPlanItem: Identifiable {
    let id: String
    let bodyKey: LocalizedStringKey
    var bodyText: String? = nil
}

private struct LookArchetypeResult {
    let titleKey: LocalizedStringKey
    let typeName: LocalizedStringKey
    let secondaryTypeName: String?
    let subtitleText: String?
    let bodyText: String?
    let shareBadgeKey: LocalizedStringKey
    let traits: [LookArchetypeTrait]
    let sections: [LookArchetypeSection]
}

private extension Array where Element == AnalysisResultMetric {
    func facemaxxMetrics(in section: String, fallback: [ProportionExpandableMetric]) -> [ProportionExpandableMetric] {
        let remoteItems = filter { $0.section == section }
            .sorted { $0.sortOrder < $1.sortOrder }
        guard !remoteItems.isEmpty else { return fallback }

        var usedRemoteIDs = Set<String>()
        let mergedFallback = fallback.map { fallbackMetric in
            guard let remoteItem = remoteItems.first(where: { $0.metricID == fallbackMetric.id }) else {
                return fallbackMetric
            }
            usedRemoteIDs.insert(remoteItem.metricID)
            return ProportionExpandableMetric(remoteItem, fallback: fallbackMetric)
        }
        let extras = remoteItems
            .filter { !usedRemoteIDs.contains($0.metricID) }
            .map { ProportionExpandableMetric($0) }
        return mergedFallback + extras
    }

    func facemaxxAestheticMetrics(in section: String, fallback: [AestheticExpandableMetric]) -> [AestheticExpandableMetric] {
        let remoteItems = filter { $0.section == section }
            .sorted { $0.sortOrder < $1.sortOrder }
        guard !remoteItems.isEmpty else { return fallback }

        var usedRemoteIDs = Set<String>()
        let mergedFallback = fallback.map { fallbackMetric in
            guard let remoteItem = remoteItems.first(where: { $0.metricID == fallbackMetric.id }) else {
                return fallbackMetric
            }
            usedRemoteIDs.insert(remoteItem.metricID)
            return AestheticExpandableMetric(remoteItem, fallback: fallbackMetric)
        }
        let extras = remoteItems
            .filter { !usedRemoteIDs.contains($0.metricID) }
            .map { AestheticExpandableMetric($0) }
        return mergedFallback + extras
    }
}

private extension Array where Element == AnalysisCoachItem {
    func facemaxxCoachItems(in section: String, fallback: [GlowUpCoachMetric]) -> [GlowUpCoachMetric] {
        let remoteItems = filter { $0.section == section }
            .sorted { $0.sortOrder < $1.sortOrder }
        guard !remoteItems.isEmpty else { return fallback }

        var usedRemoteIDs = Set<String>()
        let mergedFallback = fallback.map { fallbackMetric in
            guard let remoteItem = remoteItems.first(where: { $0.itemID == fallbackMetric.id }) else {
                return fallbackMetric
            }
            usedRemoteIDs.insert(remoteItem.itemID)
            return GlowUpCoachMetric(remoteItem, fallback: fallbackMetric)
        }
        let extras = remoteItems
            .filter { !usedRemoteIDs.contains($0.itemID) }
            .map { GlowUpCoachMetric($0) }
        return mergedFallback + extras
    }
}

private extension Array where Element == GlowUpCoachMetric {
    func facemaxxDeduplicated(excluding excluded: [GlowUpCoachMetric] = []) -> [GlowUpCoachMetric] {
        var seen = Set(excluded.map(\.facemaxxDuplicateKey))
        return filter { metric in
            seen.insert(metric.facemaxxDuplicateKey).inserted
        }
    }
}

private extension GlowUpCoachMetric {
    var facemaxxDuplicateKey: String {
        let normalized = id
            .lowercased()
            .replacingOccurrences(of: "_", with: "-")
        switch normalized {
        case "face-width-height-ratio",
             "face-width-to-height-ratio",
             "face-length-width-ratio",
             "face-length-to-width-ratio",
             "face-ratio":
            return "face-width-height-ratio"
        default:
            return normalized
        }
    }
}

private extension Array where Element == AnalysisGrowthOpportunity {
    func facemaxxActionPlanItems(fallback: [ActionPlanItem]) -> [ActionPlanItem] {
        let mapped = sorted { $0.sortOrder < $1.sortOrder }
            .map {
                ActionPlanItem(
                    id: $0.itemID,
                    bodyKey: LocalizedStringKey($0.titleKey ?? "analysis.results.action.lightingBody"),
                    bodyText: $0.bodyText
                )
            }
        return mapped.isEmpty ? fallback : mapped
    }
}

private extension Optional where Wrapped == AnalysisLookArchetype {
    @MainActor
    var facemaxxValue: LookArchetypeResult {
        guard let source = self else {
            return LookArchetypeResult(
                titleKey: "analysis.lookArchetype.title",
                typeName: "analysis.lookArchetype.typeName",
                secondaryTypeName: nil,
                subtitleText: String(localized: "analysis.lookArchetype.typeSubtitle"),
                bodyText: String(localized: "analysis.lookArchetype.typeBody"),
                shareBadgeKey: "analysis.lookArchetype.shareReady",
                traits: LookArchetypeResultData.traits,
                sections: LookArchetypeResultData.sections
            )
        }

        let traits = source.traits
            .sorted { $0.sortOrder < $1.sortOrder }
            .map {
                let titleKey = LookArchetypeI18nSanitizer.traitTitleKey(for: $0.traitID, proposedKey: $0.titleKey)
                return LookArchetypeTrait(
                    id: $0.traitID,
                    titleKey: LocalizedStringKey(titleKey),
                    titleText: LookArchetypeI18nSanitizer.shouldUseRemoteTraitText(
                        id: $0.traitID,
                        proposedKey: $0.titleKey,
                        titleKey: titleKey
                    ) ? $0.titleText : nil,
                    tint: Color(facemaxxHex: $0.tint)
                )
            }
        let sections = source.sections
            .sorted { $0.sortOrder < $1.sortOrder }
            .map { section in
                let sectionTitleKey = LookArchetypeI18nSanitizer.sectionTitleKey(for: section.sectionID, proposedKey: section.titleKey)
                return LookArchetypeSection(
                    id: section.sectionID,
                    titleKey: LocalizedStringKey(sectionTitleKey),
                    titleText: LookArchetypeI18nSanitizer.shouldUseRemoteSectionText(
                        id: section.sectionID,
                        proposedKey: section.titleKey,
                        titleKey: sectionTitleKey
                    ) ? section.titleText : nil,
                    iconName: section.iconName,
                    tint: Color(facemaxxHex: section.tint),
                    isDefaultExpanded: section.isDefaultExpanded,
                    items: section.bullets
                        .sorted { $0.sortOrder < $1.sortOrder }
                        .map {
                            let bulletTitleKey = LookArchetypeI18nSanitizer.bulletTitleKey(
                                for: $0.bulletID,
                                sectionID: section.sectionID,
                                proposedKey: $0.titleKey
                            )
                            return LookArchetypeBullet(
                                id: $0.bulletID,
                                titleKey: LocalizedStringKey(bulletTitleKey),
                                titleText: LookArchetypeI18nSanitizer.shouldUseRemoteBulletText(
                                    id: $0.bulletID,
                                    sectionID: section.sectionID,
                                    proposedKey: $0.titleKey,
                                    titleKey: bulletTitleKey
                                ) ? $0.titleText : nil,
                                iconName: $0.iconName
                            )
                        }
                )
            }

        return LookArchetypeResult(
            titleKey: LocalizedStringKey(source.titleKey),
            typeName: LookArchetypeI18nSanitizer.typeNameKey(for: source.archetypeID, sourceName: source.typeName),
            secondaryTypeName: source.secondaryTypeName,
            subtitleText: source.subtitleText,
            bodyText: source.bodyText,
            shareBadgeKey: LocalizedStringKey(source.shareBadgeKey ?? "analysis.lookArchetype.shareReady"),
            traits: traits.isEmpty ? LookArchetypeResultData.traits : traits,
            sections: sections.isEmpty ? LookArchetypeResultData.sections : sections
        )
    }
}

private enum LookArchetypeI18nSanitizer {
    private static let traitKeys: [String: String] = [
        "clean": "analysis.lookArchetype.trait.clean",
        "youthful": "analysis.lookArchetype.trait.youthful",
        "approachable": "analysis.lookArchetype.trait.approachable"
    ]

    private static let sectionKeys: [String: String] = [
        "impression-summary": "analysis.lookArchetype.impressionSummary",
        "why-this-fits": "analysis.lookArchetype.whyThisFits",
        "best-features": "analysis.lookArchetype.bestFeatures",
        "style-direction": "analysis.lookArchetype.styleDirection",
        "photo-playbook": "analysis.lookArchetype.photoPlaybook",
        "avoid": "analysis.lookArchetype.avoid"
    ]

    private static let bulletKeys: [String: String] = [
        "harmony": "analysis.lookArchetype.why.harmony",
        "skin-hair": "analysis.lookArchetype.why.skinHair",
        "soft-impression": "analysis.lookArchetype.why.softImpression",
        "skin": "analysis.lookArchetype.feature.skin",
        "hair": "analysis.lookArchetype.feature.hair",
        "symmetry": "analysis.lookArchetype.feature.symmetry",
        "natural-light": "analysis.lookArchetype.style.naturalLight",
        "neat-hair": "analysis.lookArchetype.style.neatHair",
        "clean-top": "analysis.lookArchetype.style.cleanTop",
        "natural-smile": "analysis.lookArchetype.style.naturalSmile",
        "dark-light": "analysis.lookArchetype.avoid.darkLight",
        "blank-expression": "analysis.lookArchetype.avoid.blankExpression",
        "heavy-bangs": "analysis.lookArchetype.avoid.heavyBangs"
    ]

    private static let knownKeys = Set(traitKeys.values)
        .union(sectionKeys.values)
        .union(bulletKeys.values)
        .union([
            "analysis.lookArchetype.title",
            "analysis.lookArchetype.shareReady"
        ])

    static func traitTitleKey(for id: String, proposedKey: String) -> String {
        titleKey(
            for: id,
            proposedKey: proposedKey,
            known: traitKeys,
            fallback: "analysis.lookArchetype.trait.clean"
        )
    }

    static func typeNameKey(for id: String, sourceName: String) -> LocalizedStringKey {
        let normalizedID = normalized(id)
        let normalizedName = normalized(sourceName)
        if normalizedID == "clean-cut-heartthrob" || normalizedName == "clean-cut-heartthrob" {
            return "analysis.lookArchetype.typeName"
        }
        return LocalizedStringKey(sourceName)
    }

    static func sectionTitleKey(for id: String, proposedKey: String) -> String {
        titleKey(
            for: id,
            proposedKey: proposedKey,
            known: sectionKeys,
            fallback: "analysis.lookArchetype.whyThisFits"
        )
    }

    static func bulletTitleKey(for id: String, sectionID: String, proposedKey: String) -> String {
        if let titleKey = bulletKeys[normalized(id)] {
            return titleKey
        }

        let sectionScopedID = "\(normalized(sectionID))-\(normalized(id))"
        if let titleKey = bulletKeys[sectionScopedID] {
            return titleKey
        }

        let proposed = proposedKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if knownKeys.contains(proposed) || (!proposed.hasPrefix("analysis.") && !proposed.isEmpty) {
            return proposed
        }
        return "analysis.lookArchetype.why.harmony"
    }

    static func shouldUseRemoteTraitText(id: String, proposedKey: String, titleKey: String) -> Bool {
        shouldUseRemoteText(
            hasKnownID: traitKeys[normalized(id)] != nil,
            proposedKey: proposedKey,
            titleKey: titleKey
        )
    }

    static func shouldUseRemoteSectionText(id: String, proposedKey: String, titleKey: String) -> Bool {
        shouldUseRemoteText(
            hasKnownID: sectionKeys[normalized(id)] != nil,
            proposedKey: proposedKey,
            titleKey: titleKey
        )
    }

    static func shouldUseRemoteBulletText(id: String, sectionID: String, proposedKey: String, titleKey: String) -> Bool {
        let normalizedID = normalized(id)
        let hasKnownID = bulletKeys[normalizedID] != nil || bulletKeys["\(normalized(sectionID))-\(normalizedID)"] != nil
        return shouldUseRemoteText(
            hasKnownID: hasKnownID,
            proposedKey: proposedKey,
            titleKey: titleKey
        )
    }

    private static func titleKey(for id: String, proposedKey: String, known: [String: String], fallback: String) -> String {
        if let titleKey = known[normalized(id)] {
            return titleKey
        }

        let proposed = proposedKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if knownKeys.contains(proposed) || (!proposed.hasPrefix("analysis.") && !proposed.isEmpty) {
            return proposed
        }
        return fallback
    }

    private static func shouldUseRemoteText(hasKnownID: Bool, proposedKey: String, titleKey: String) -> Bool {
        if hasKnownID {
            return false
        }

        let proposed = proposedKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if proposed.hasPrefix("analysis.") && !knownKeys.contains(proposed) {
            return true
        }
        return !knownKeys.contains(titleKey)
    }

    private static func normalized(_ value: String) -> String {
        value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: "_", with: "-")
    }
}

@MainActor private enum LookArchetypeResultData {
    static let traits = [
        LookArchetypeTrait(id: "clean", titleKey: "analysis.lookArchetype.trait.clean", tint: FXTheme.green),
        LookArchetypeTrait(id: "youthful", titleKey: "analysis.lookArchetype.trait.youthful", tint: FXTheme.blue),
        LookArchetypeTrait(id: "approachable", titleKey: "analysis.lookArchetype.trait.approachable", tint: FXTheme.cyan)
    ]

    static let sections = [
        LookArchetypeSection(
            id: "why-this-fits",
            titleKey: "analysis.lookArchetype.whyThisFits",
            iconName: "checkmark.seal.fill",
            tint: FXTheme.green,
            items: [
                LookArchetypeBullet(id: "harmony", titleKey: "analysis.lookArchetype.why.harmony", iconName: "checkmark.circle.fill"),
                LookArchetypeBullet(id: "skin-hair", titleKey: "analysis.lookArchetype.why.skinHair", iconName: "checkmark.circle.fill"),
                LookArchetypeBullet(id: "soft-impression", titleKey: "analysis.lookArchetype.why.softImpression", iconName: "checkmark.circle.fill")
            ]
        ),
        LookArchetypeSection(
            id: "best-features",
            titleKey: "analysis.lookArchetype.bestFeatures",
            iconName: "star.fill",
            tint: FXTheme.blue,
            items: [
                LookArchetypeBullet(id: "skin", titleKey: "analysis.lookArchetype.feature.skin", iconName: "sparkle"),
                LookArchetypeBullet(id: "hair", titleKey: "analysis.lookArchetype.feature.hair", iconName: "sparkle"),
                LookArchetypeBullet(id: "symmetry", titleKey: "analysis.lookArchetype.feature.symmetry", iconName: "sparkle")
            ]
        ),
        LookArchetypeSection(
            id: "style-direction",
            titleKey: "analysis.lookArchetype.styleDirection",
            iconName: "wand.and.stars",
            tint: FXTheme.cyan,
            items: [
                LookArchetypeBullet(id: "natural-light", titleKey: "analysis.lookArchetype.style.naturalLight", iconName: "sun.max.fill"),
                LookArchetypeBullet(id: "neat-hair", titleKey: "analysis.lookArchetype.style.neatHair", iconName: "comb.fill"),
                LookArchetypeBullet(id: "clean-top", titleKey: "analysis.lookArchetype.style.cleanTop", iconName: "tshirt.fill"),
                LookArchetypeBullet(id: "natural-smile", titleKey: "analysis.lookArchetype.style.naturalSmile", iconName: "face.smiling")
            ]
        ),
        LookArchetypeSection(
            id: "avoid",
            titleKey: "analysis.lookArchetype.avoid",
            iconName: "xmark.octagon.fill",
            tint: FXTheme.orange,
            items: [
                LookArchetypeBullet(id: "dark-light", titleKey: "analysis.lookArchetype.avoid.darkLight", iconName: "xmark.circle.fill"),
                LookArchetypeBullet(id: "blank-expression", titleKey: "analysis.lookArchetype.avoid.blankExpression", iconName: "xmark.circle.fill"),
                LookArchetypeBullet(id: "heavy-bangs", titleKey: "analysis.lookArchetype.avoid.heavyBangs", iconName: "xmark.circle.fill")
            ]
        )
    ]
}

@MainActor private enum GlowUpCoachResultData {
    static let facialAnalysis = [
        GlowUpCoachMetric(
            id: "symmetry",
            titleKey: "analysis.glowUpCoach.item.symmetry",
            assessmentKey: "analysis.glowUpCoach.item.symmetryAssessment",
            actionKey: "analysis.glowUpCoach.item.symmetryAction",
            iconName: "circle.lefthalf.filled"
        ),
        GlowUpCoachMetric(
            id: "skin",
            titleKey: "analysis.glowUpCoach.item.skin",
            assessmentKey: "analysis.glowUpCoach.item.skinAssessment",
            actionKey: "analysis.glowUpCoach.item.skinAction",
            iconName: "drop.fill"
        ),
        GlowUpCoachMetric(
            id: "jawline",
            titleKey: "analysis.glowUpCoach.item.jawline",
            assessmentKey: "analysis.glowUpCoach.item.jawlineAssessment",
            actionKey: "analysis.glowUpCoach.item.jawlineAction",
            iconName: "triangle.fill"
        ),
        GlowUpCoachMetric(
            id: "eye-area",
            titleKey: "analysis.glowUpCoach.item.eyeArea",
            assessmentKey: "analysis.glowUpCoach.item.eyeAreaAssessment",
            actionKey: "analysis.glowUpCoach.item.eyeAreaAction",
            iconName: "eye.fill"
        ),
        GlowUpCoachMetric(
            id: "cheekbones",
            titleKey: "analysis.glowUpCoach.item.cheekbones",
            assessmentKey: "analysis.glowUpCoach.item.cheekbonesAssessment",
            actionKey: "analysis.glowUpCoach.item.cheekbonesAction",
            iconName: "face.smiling"
        ),
        GlowUpCoachMetric(
            id: "eyebrows",
            titleKey: "analysis.glowUpCoach.item.eyebrows",
            assessmentKey: "analysis.glowUpCoach.item.eyebrowsAssessment",
            actionKey: "analysis.glowUpCoach.item.eyebrowsAction",
            iconName: "eyebrow"
        ),
        GlowUpCoachMetric(
            id: "glow",
            titleKey: "analysis.glowUpCoach.item.glow",
            assessmentKey: "analysis.glowUpCoach.item.glowAssessment",
            actionKey: "analysis.glowUpCoach.item.glowAction",
            iconName: "sparkles"
        ),
        GlowUpCoachMetric(
            id: "hair",
            titleKey: "analysis.glowUpCoach.item.hair",
            assessmentKey: "analysis.glowUpCoach.item.hairAssessment",
            actionKey: "analysis.glowUpCoach.item.hairAction",
            iconName: "comb.fill"
        ),
        GlowUpCoachMetric(
            id: "confidence",
            titleKey: "analysis.glowUpCoach.item.confidence",
            assessmentKey: "analysis.glowUpCoach.item.confidenceAssessment",
            actionKey: "analysis.glowUpCoach.item.confidenceAction",
            iconName: "heart.fill"
        )
    ]

    static let needsWork = [
        GlowUpCoachMetric(
            id: "expression-confidence",
            titleKey: "analysis.glowUpCoach.item.expressionConfidence",
            assessmentKey: "analysis.glowUpCoach.item.expressionConfidenceAssessment",
            actionKey: "analysis.glowUpCoach.item.expressionConfidenceAction",
            iconName: "exclamationmark.triangle.fill"
        ),
        GlowUpCoachMetric(
            id: "face-width-height-ratio",
            titleKey: "analysis.glowUpCoach.item.faceWidthHeightRatio",
            assessmentKey: "analysis.glowUpCoach.item.faceWidthHeightRatioAssessment",
            actionKey: "analysis.glowUpCoach.item.faceWidthHeightRatioAction",
            iconName: "rectangle.portrait"
        ),
        GlowUpCoachMetric(
            id: "camera-angle",
            titleKey: "analysis.glowUpCoach.item.cameraAngle",
            assessmentKey: "analysis.glowUpCoach.item.cameraAngleAssessment",
            actionKey: "analysis.glowUpCoach.item.cameraAngleAction",
            iconName: "camera.viewfinder"
        ),
        GlowUpCoachMetric(
            id: "lighting",
            titleKey: "analysis.glowUpCoach.item.lighting",
            assessmentKey: "analysis.glowUpCoach.item.lightingAssessment",
            actionKey: "analysis.glowUpCoach.item.lightingAction",
            iconName: "sun.max.fill"
        ),
        GlowUpCoachMetric(
            id: "photo-presence",
            titleKey: "analysis.glowUpCoach.item.photoPresence",
            assessmentKey: "analysis.glowUpCoach.item.photoPresenceAssessment",
            actionKey: "analysis.glowUpCoach.item.photoPresenceAction",
            iconName: "person.crop.square"
        )
    ]

    static let strengths = [
        GlowUpCoachMetric(
            id: "skin-quality",
            titleKey: "analysis.glowUpCoach.item.skinQuality",
            assessmentKey: "analysis.glowUpCoach.item.skinQualityAssessment",
            actionKey: "analysis.glowUpCoach.item.skinQualityAction",
            iconName: "star.fill"
        ),
        GlowUpCoachMetric(
            id: "harmony",
            titleKey: "analysis.glowUpCoach.item.harmony",
            assessmentKey: "analysis.glowUpCoach.item.harmonyAssessment",
            actionKey: "analysis.glowUpCoach.item.harmonyAction",
            iconName: "circle.hexagongrid.fill"
        ),
        GlowUpCoachMetric(
            id: "eye-area-strength",
            titleKey: "analysis.glowUpCoach.item.eyeArea",
            assessmentKey: "analysis.glowUpCoach.item.eyeAreaStrengthAssessment",
            actionKey: "analysis.glowUpCoach.item.eyeAreaStrengthAction",
            iconName: "eye.fill"
        )
    ]
}

@MainActor private enum AestheticsResultData {
    static let shapes = [
        AestheticExpandableMetric(
            id: "face-shape",
            titleKey: "analysis.aestheticsResults.shape.faceShape",
            valueKey: "analysis.aestheticsResults.shape.faceShapeValue",
            detailKey: "analysis.aestheticsResults.shape.faceShapeDetail",
            iconName: "face.smiling",
            valueTint: FXTheme.textSecondary
        ),
        AestheticExpandableMetric(
            id: "eye-shape",
            titleKey: "analysis.aestheticsResults.shape.eyeShape",
            valueKey: "analysis.aestheticsResults.shape.eyeShapeValue",
            detailKey: "analysis.aestheticsResults.shape.eyeShapeDetail",
            iconName: "eye.fill",
            valueTint: FXTheme.textSecondary
        ),
        AestheticExpandableMetric(
            id: "eyebrow-shape",
            titleKey: "analysis.aestheticsResults.shape.eyebrowShape",
            valueKey: "analysis.aestheticsResults.shape.eyebrowShapeValue",
            detailKey: "analysis.aestheticsResults.shape.eyebrowShapeDetail",
            iconName: "eyebrow",
            valueTint: FXTheme.textSecondary
        ),
        AestheticExpandableMetric(
            id: "lip-shape",
            titleKey: "analysis.aestheticsResults.shape.lipShape",
            valueKey: "analysis.aestheticsResults.shape.lipShapeValue",
            detailKey: "analysis.aestheticsResults.shape.lipShapeDetail",
            iconName: "mouth.fill",
            valueTint: FXTheme.textSecondary
        )
    ]

    static let proportions = [
        AestheticExpandableMetric(
            id: "canthal-tilt",
            titleKey: "analysis.aestheticsResults.proportion.canthalTilt",
            valueKey: "analysis.aestheticsResults.proportion.canthalTiltValue",
            detailKey: "analysis.aestheticsResults.proportion.canthalTiltDetail",
            iconName: "arrow.left.and.right.circle",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "eye-spacing-ratio",
            titleKey: "analysis.aestheticsResults.proportion.eyeSpacingRatio",
            valueKey: "analysis.aestheticsResults.proportion.eyeSpacingRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.eyeSpacingRatioDetail",
            iconName: "eye.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "face-width-height-ratio",
            titleKey: "analysis.aestheticsResults.proportion.faceWidthHeightRatio",
            valueKey: "analysis.aestheticsResults.proportion.faceWidthHeightRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.faceWidthHeightRatioDetail",
            iconName: "rectangle.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "midface-ratio",
            titleKey: "analysis.aestheticsResults.proportion.midfaceRatio",
            valueKey: "analysis.aestheticsResults.proportion.midfaceRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.midfaceRatioDetail",
            iconName: "sun.max.fill",
            valueTint: FXTheme.textSecondary
        ),
        AestheticExpandableMetric(
            id: "philtrum-chin-ratio",
            titleKey: "analysis.aestheticsResults.proportion.philtrumToChinRatio",
            valueKey: "analysis.aestheticsResults.proportion.philtrumToChinRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.philtrumToChinRatioDetail",
            iconName: "mouth.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "eye-width-face-ratio",
            titleKey: "analysis.aestheticsResults.proportion.eyeWidthFaceRatio",
            valueKey: "analysis.aestheticsResults.proportion.eyeWidthFaceRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.eyeWidthFaceRatioDetail",
            iconName: "eye.circle.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "upper-lower-lip-ratio",
            titleKey: "analysis.aestheticsResults.proportion.upperLipToLowerLip",
            valueKey: "analysis.aestheticsResults.proportion.upperLipToLowerLipValue",
            detailKey: "analysis.aestheticsResults.proportion.upperLipToLowerLipDetail",
            iconName: "mouth.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "eye-width-height-ratio",
            titleKey: "analysis.aestheticsResults.proportion.eyeWidthHeightRatio",
            valueKey: "analysis.aestheticsResults.proportion.eyeWidthHeightRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.eyeWidthHeightRatioDetail",
            iconName: "eye.fill",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "lower-full-face-ratio",
            titleKey: "analysis.aestheticsResults.proportion.lowerToFullFaceRatio",
            valueKey: "analysis.aestheticsResults.proportion.lowerToFullFaceRatioValue",
            detailKey: "analysis.aestheticsResults.proportion.lowerToFullFaceRatioDetail",
            iconName: "rectangle.portrait",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "eye-mouth-angle",
            titleKey: "analysis.aestheticsResults.proportion.eyeToMouthAngle",
            valueKey: "analysis.aestheticsResults.proportion.eyeToMouthAngleValue",
            detailKey: "analysis.aestheticsResults.proportion.eyeToMouthAngleDetail",
            iconName: "angle",
            valueTint: FXTheme.green
        ),
        AestheticExpandableMetric(
            id: "face-depth-width-ratio",
            titleKey: "analysis.aestheticsResults.proportion.faceDepthWidthRatio",
            valueKey: "analysis.aestheticsResults.proportion.faceDepthWidthRatio",
            valueText: "0.64",
            usesLocalizedFallbackValue: false,
            detailKey: "analysis.aestheticsResults.proportion.faceDepthWidthRatioDetail",
            iconName: "viewfinder",
            valueTint: FXTheme.textSecondary
        ),
        AestheticExpandableMetric(
            id: "face-contour-width-height-ratio",
            titleKey: "analysis.aestheticsResults.proportion.faceContourWidthHeightRatio",
            valueKey: "analysis.aestheticsResults.proportion.faceContourWidthHeightRatio",
            valueText: "1.58",
            usesLocalizedFallbackValue: false,
            detailKey: "analysis.aestheticsResults.proportion.faceContourWidthHeightRatioDetail",
            iconName: "rectangle.portrait",
            valueTint: FXTheme.textSecondary
        )
    ]
}

@MainActor private enum ProportionsResultData {
    static let rings = [
        ProportionRingMetric(id: "symmetry", titleKey: "analysis.results.ring.symmetry", value: 0.77, displayValue: "7.7", tint: FXTheme.green),
        ProportionRingMetric(id: "skin", titleKey: "analysis.results.ring.skin", value: 0.72, displayValue: "7.2", tint: FXTheme.green),
        ProportionRingMetric(id: "jawline", titleKey: "analysis.results.ring.jawline", value: 0.72, displayValue: "7.2", tint: FXTheme.green),
        ProportionRingMetric(id: "eye-area", titleKey: "analysis.results.ring.eyeArea", value: 0.77, displayValue: "7.7", tint: FXTheme.green),
        ProportionRingMetric(id: "cheekbones", titleKey: "analysis.results.ring.cheekbones", value: 0.72, displayValue: "7.2", tint: FXTheme.green),
        ProportionRingMetric(id: "eyebrows", titleKey: "analysis.results.ring.eyebrows", value: 0.72, displayValue: "7.2", tint: FXTheme.green),
        ProportionRingMetric(id: "glow", titleKey: "analysis.results.ring.glow", value: 0.67, displayValue: "6.7", tint: FXTheme.green),
        ProportionRingMetric(id: "hair", titleKey: "analysis.results.ring.hair", value: 0.77, displayValue: "7.7", tint: FXTheme.green),
        ProportionRingMetric(id: "harmony", titleKey: "analysis.results.ring.harmony", value: 0.77, displayValue: "7.7", tint: FXTheme.green)
    ]

    static let detailedMetrics = [
        ProportionExpandableMetric(
            id: "symmetry",
            titleKey: "analysis.results.metric.symmetry",
            valueKey: "analysis.results.metric.symmetryValue",
            detailKey: "analysis.results.metric.symmetryDetail",
            iconName: "circle.lefthalf.filled"
        ),
        ProportionExpandableMetric(
            id: "canthal-tilt",
            titleKey: "analysis.results.metric.canthalTilt",
            valueKey: "analysis.results.metric.canthalTiltValue",
            detailKey: "analysis.results.metric.canthalTiltDetail",
            iconName: "arrow.left.and.right.circle"
        ),
        ProportionExpandableMetric(
            id: "gonial-angle",
            titleKey: "analysis.results.metric.gonialAngle",
            valueKey: "analysis.results.metric.gonialAngleValue",
            detailKey: "analysis.results.metric.gonialAngleDetail",
            iconName: "angle"
        ),
        ProportionExpandableMetric(
            id: "skin-quality",
            titleKey: "analysis.results.metric.skinQuality",
            valueKey: "analysis.results.metric.skinQualityValue",
            detailKey: "analysis.results.metric.skinQualityDetail",
            iconName: "drop.fill"
        ),
        ProportionExpandableMetric(
            id: "cheekbone-projection",
            titleKey: "analysis.results.metric.cheekboneProjection",
            valueKey: "analysis.results.metric.cheekboneProjectionValue",
            detailKey: "analysis.results.metric.cheekboneProjectionDetail",
            iconName: "face.smiling"
        ),
        ProportionExpandableMetric(
            id: "jawline-definition",
            titleKey: "analysis.results.metric.jawlineDefinition",
            valueKey: "analysis.results.metric.jawlineDefinitionValue",
            detailKey: "analysis.results.metric.jawlineDefinitionDetail",
            iconName: "triangle.fill"
        )
    ]

    static let funMetrics = [
        ProportionExpandableMetric(
            id: "estimated-age",
            titleKey: "analysis.results.fun.estimatedAge",
            valueKey: "analysis.results.fun.estimatedAgeValue",
            detailKey: "analysis.results.fun.estimatedAgeDetail",
            iconName: "calendar"
        ),
        ProportionExpandableMetric(
            id: "smile-score",
            titleKey: "analysis.results.fun.smileScore",
            valueKey: "analysis.results.fun.smileScoreValue",
            detailKey: "analysis.results.fun.smileScoreDetail",
            iconName: "face.smiling"
        ),
        ProportionExpandableMetric(
            id: "mood",
            titleKey: "analysis.results.fun.mood",
            valueKey: "analysis.results.fun.moodValue",
            detailKey: "analysis.results.fun.moodDetail",
            iconName: "face.dashed"
        ),
        ProportionExpandableMetric(
            id: "glasses",
            titleKey: "analysis.results.fun.glasses",
            valueKey: "analysis.results.fun.glassesValue",
            detailKey: "analysis.results.fun.glassesDetail",
            iconName: "eyeglasses"
        ),
        ProportionExpandableMetric(
            id: "facial-hair",
            titleKey: "analysis.results.fun.facialHair",
            valueKey: "analysis.results.fun.facialHairValue",
            detailKey: "analysis.results.fun.facialHairDetail",
            iconName: "mustache.fill"
        )
    ]

    static let opportunityItems = [
        ActionPlanItem(id: "lighting", bodyKey: "analysis.results.action.lightingBody"),
        ActionPlanItem(id: "grooming", bodyKey: "analysis.results.action.groomingBody")
    ]
}

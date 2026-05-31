import AuthenticationServices
import Lottie
import SwiftUI
import UIKit

struct OnboardingView: View {
    @EnvironmentObject private var authService: FacemaxxAuthService
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    let onComplete: (FaceCameraCaptureResult?) -> Void
    var onReviewerDemoActivated: () -> Void = {}
    var onReviewerDemoPreparedForOnboarding: () -> Void = {}

    @State private var page = OnboardingPage.account
    @State private var selectedSourceID: String?
    @State private var selectedGoalIDs: Set<String> = []
    @State private var selectedGenderID: String?
    @State private var selectedAge: Int?
    @State private var errorMessage: String?
    @State private var isScanCameraPresented = false
    @State private var pendingOnboardingCrop: OnboardingPendingCrop?
    @State private var cropRequestAfterCameraDismissal: OnboardingPendingCrop?
    @State private var onboardingScanImage: UIImage?
    @State private var onboardingScanOverlayImage: UIImage?
    @State private var onboardingCaptureResult: FaceCameraCaptureResult?
    @State private var scanProcessingToken = UUID()
    @State private var didResetInitialSelections = false
    @State private var isCompleting = false
    @State private var isReviewerAccessPresented = false
    @State private var reviewerAccessMode = ReviewerAccessMode.skipToMain
    @State private var reviewerAccessCode = ""
    @State private var reviewerAccessErrorMessage: String?
    @State private var isReviewerOnboardingDemoActive = false
    @AppStorage(AIAnalysisConsentStore.grantedStorageKey) private var isAIAnalysisConsentGranted = false
    @State private var hasAcceptedAIAnalysisConsent = AIAnalysisConsentStore.isGranted

    private var onboardingPreviewImage: UIImage? {
        onboardingScanOverlayImage ?? onboardingScanImage
    }

    private var reviewerDemoScanAction: (() -> Void)? {
        guard isReviewerOnboardingDemoActive else { return nil }
        return { useReviewerDemoOnboardingScan() }
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            FXTheme.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                if page.showsPageDots {
                    OnboardingPageDots(page: page)
                        .padding(.top, 34)
                } else if page == .account {
                    Color.clear
                        .frame(height: 10)
                        .padding(.top, 4)
                }

                GeometryReader { proxy in
                    let bottomReserve: CGFloat = page.showsBottomControls ? 78 : (page == .analysisStart ? 92 : 0)
                    ScrollView(.vertical) {
                        onboardingPageContent
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: max(CGFloat.zero, proxy.size.height - bottomReserve))
                            .padding(.bottom, page.showsBottomControls ? 8 : 0)
                    }
                    .scrollIndicators(.hidden)
                }
                .animation(.smooth(duration: reduceMotion ? 0 : 0.42), value: page)

                if page.showsBottomControls {
                    OnboardingBottomControls(
                        page: page,
                        canContinue: canContinue,
                        isCompleting: isCompleting,
                        onBack: goBack,
                        onRetake: retakeOnboardingScan,
                        onContinue: advance
                    )
                    .padding(.horizontal, page == .reportReady ? 16 : 24)
                    .padding(.bottom, 14)
                }
            }

            if page == .analysisStart {
                OnboardingAnalysisStartPrimaryButton(
                    isCompleting: isCompleting,
                    onPrimary: advance
                )
                .padding(.horizontal, 24)
                .padding(.bottom, 14)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .zIndex(3)
            }
        }
        .onAppear {
            resetInitialSelectionsIfNeeded()
        }
        .preferredColorScheme(.dark)
        .fullScreenCover(
            isPresented: $isScanCameraPresented,
            onDismiss: {
                if let request = cropRequestAfterCameraDismissal {
                    cropRequestAfterCameraDismissal = nil
                    pendingOnboardingCrop = request
                }
            }
        ) {
            FaceCameraCaptureView { result in
                cropRequestAfterCameraDismissal = OnboardingPendingCrop(capture: result)
                isScanCameraPresented = false
            } onCancel: {
                isScanCameraPresented = false
            }
            .ignoresSafeArea()
        }
        .fullScreenCover(item: $pendingOnboardingCrop) { request in
            SquarePhotoCropView(
                image: request.capture.image,
                scanOverlayImage: request.capture.scanOverlayImage,
                onCancel: {
                    pendingOnboardingCrop = nil
                },
                onChoose: { result in
                    commitOnboardingCrop(result, from: request)
                }
            )
        }
        .alert("reviewer.demo.title", isPresented: $isReviewerAccessPresented) {
            TextField("reviewer.demo.codePlaceholder", text: $reviewerAccessCode)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()

            Button("reviewer.demo.cancel", role: .cancel) {
                reviewerAccessCode = ""
                reviewerAccessErrorMessage = nil
            }

            Button("reviewer.demo.continue") {
                activateReviewerDemoMode()
            }
        } message: {
            Text(reviewerAccessErrorMessage ?? String(localized: "reviewer.demo.message"))
        }
    }

    private var canContinue: Bool {
        switch page {
        case .source:
            selectedSourceID != nil
        case .faceFocus:
            !selectedGoalIDs.isEmpty
        case .aiConsent:
            hasAcceptedAIAnalysisConsent || isAIAnalysisConsentGranted
        default:
            true
        }
    }

    @ViewBuilder
    private var onboardingPageContent: some View {
        switch page {
        case .account:
            AccountOnboardingPage(
                isLoading: authService.isAuthenticating,
                errorMessage: errorMessage,
                onAppleCompletion: signInWithApple,
                onReviewerAccessRequest: presentReviewerAccess,
                onReviewerOnboardingAccessRequest: presentReviewerOnboardingAccess
            )
        case .source:
            DiscoverySourceOnboardingPage(selectedSourceID: $selectedSourceID)
        case .faceFocus:
            FaceFocusOnboardingPage(selectedGoalIDs: $selectedGoalIDs)
        case .reportPlan:
            ReportPlanOnboardingPage(selectedGoalIDs: selectedGoalIDs)
        case .scanIntro:
            FaceScanIntroOnboardingPage(
                onBack: goBack,
                onStartScan: startOnboardingScan,
                onUseDemoScan: reviewerDemoScanAction
            )
        case .scanComplete:
            ScanCompleteOnboardingPage(image: onboardingPreviewImage)
        case .scanProcessing:
            ScanProcessingOnboardingPage(image: onboardingPreviewImage, restartToken: scanProcessingToken) {
                guard page == .scanProcessing else { return }
                withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
                    page = .reportReady
                }
            }
        case .reportReady:
            ReportReadyOnboardingPage(
                selectedGoalIDs: selectedGoalIDs,
                selectedGenderID: selectedGenderID,
                selectedAge: selectedAge,
                image: onboardingScanOverlayImage ?? onboardingScanImage
            )
        case .analysisStart:
            OnboardingAnalysisStartPage(
                selectedGoalIDs: selectedGoalIDs
            )
        case .aiConsent:
            OnboardingAIConsentPage(isAccepted: $hasAcceptedAIAnalysisConsent)
        }
    }

    private func signInWithApple(_ result: Result<ASAuthorization, Error>) {
        errorMessage = nil
        Task {
            do {
                try await authService.signInWithApple(result)
                if await completeExistingAccountIfPossible() {
                    return
                }
                await MainActor.run { advance() }
            } catch {
                await MainActor.run {
                    errorMessage = String(localized: "onboarding.auth.error.retry")
                }
            }
        }
    }

    private func completeExistingAccountIfPossible() async -> Bool {
        do {
            let response = try await FacemaxxAPIClient.shared.fetchOnboardingPreferences()
            guard let preferences = response.localPreferences else {
                return false
            }
            await MainActor.run {
                OnboardingPreferencesStore.save(preferences)
                onComplete(nil)
            }
            return true
        } catch {
            print("Facemaxx onboarding preferences fetch skipped: \(error.localizedDescription)")
            return false
        }
    }

    private func signOut() {
        authService.signOut()
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            page = .account
        }
    }

    private func goBack() {
        guard let previous = OnboardingPage(rawValue: page.rawValue - 1), page != .account else {
            return
        }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            page = previous
        }
    }

    private func advance() {
        if page == .aiConsent {
            finish()
            return
        }

        guard canContinue, let next = OnboardingPage(rawValue: page.rawValue + 1) else {
            return
        }

        if next == .scanProcessing {
            scanProcessingToken = UUID()
        }
        if next == .aiConsent {
            hasAcceptedAIAnalysisConsent = isAIAnalysisConsentGranted
        }

        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            page = next
        }
    }

    private func startOnboardingScan() {
        pendingOnboardingCrop = nil
        cropRequestAfterCameraDismissal = nil
        isScanCameraPresented = true
    }

    private func retakeOnboardingScan() {
        pendingOnboardingCrop = nil
        cropRequestAfterCameraDismissal = nil
        isScanCameraPresented = true
    }

    private func commitOnboardingCrop(_ result: SquarePhotoCropResult, from request: OnboardingPendingCrop) {
        let payload = FaceScanPayloadBuilder.payload(
            for: result.image,
            source: "camera",
            isFrontCamera: true,
            basePayload: request.capture.scanPayload,
            preferredRegion: result.preferredRegion
        )
        let croppedCapture = FaceCameraCaptureResult(
            image: result.image,
            scanOverlayImage: result.scanOverlayImage,
            scanPayload: payload
        )
        pendingOnboardingCrop = nil
        onboardingCaptureResult = croppedCapture
        onboardingScanImage = result.image
        onboardingScanOverlayImage = result.scanOverlayImage
        beginOnboardingScanCompletionTransition()
    }

    private func beginOnboardingScanCompletionTransition() {
        scanProcessingToken = UUID()
        withAnimation(.spring(response: 0.44, dampingFraction: 0.86)) {
            page = .scanComplete
        }
        let transitionDelay: UInt64 = reduceMotion ? 350_000_000 : 1_050_000_000
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: transitionDelay)
            guard page == .scanComplete else { return }
            scanProcessingToken = UUID()
            withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
                page = .scanProcessing
            }
        }
    }

    private func finish() {
        guard !isCompleting else { return }
        guard hasAcceptedAIAnalysisConsent || isAIAnalysisConsentGranted else { return }
        grantAIAnalysisConsent()

        let preferences = OnboardingPreferences(
            selectedGoalIDs: Array(selectedGoalIDs).sorted(),
            genderID: selectedGenderID,
            age: selectedAge,
            discoverySourceID: selectedSourceID,
            completedAt: Date()
        )
        OnboardingPreferencesStore.save(preferences)

        isCompleting = true
        Task {
            if authService.session != nil {
                do {
                    let response = try await FacemaxxAPIClient.shared.saveOnboardingPreferences(preferences)
                    if !response.persisted {
                        print("Facemaxx onboarding preferences kept locally; remote persistence is not active.")
                    }
                } catch {
                    print("Facemaxx onboarding preferences sync failed: \(error.localizedDescription)")
                }
            }

            await MainActor.run {
                isCompleting = false
                onComplete(onboardingCaptureResult)
            }
        }
    }

    private func presentReviewerAccess() {
        reviewerAccessMode = .skipToMain
        reviewerAccessCode = ""
        reviewerAccessErrorMessage = nil
        isReviewerAccessPresented = true
    }

    private func presentReviewerOnboardingAccess() {
        reviewerAccessMode = .continueOnboarding
        reviewerAccessCode = ""
        reviewerAccessErrorMessage = nil
        isReviewerAccessPresented = true
    }

    private func activateReviewerDemoMode() {
        guard AppReviewDemoMode.matchesAccessCode(reviewerAccessCode) else {
            reviewerAccessErrorMessage = String(localized: "reviewer.demo.invalidCode")
            reviewerAccessCode = ""
            isReviewerAccessPresented = true
            return
        }

        reviewerAccessCode = ""
        reviewerAccessErrorMessage = nil
        isReviewerAccessPresented = false

        switch reviewerAccessMode {
        case .skipToMain:
            grantAIAnalysisConsent()
            OnboardingPreferencesStore.save(AppReviewDemoMode.onboardingPreferences)
            onReviewerDemoActivated()
        case .continueOnboarding:
            prepareReviewerOnboardingDemoMode()
        }
    }

    private func resetInitialSelectionsIfNeeded() {
        guard !didResetInitialSelections else { return }
        selectedSourceID = nil
        selectedGoalIDs = []
        selectedGenderID = nil
        selectedAge = nil
        didResetInitialSelections = true
    }

    private func grantAIAnalysisConsent() {
        AIAnalysisConsentStore.grant()
        isAIAnalysisConsentGranted = true
        hasAcceptedAIAnalysisConsent = true
    }

    private func prepareReviewerOnboardingDemoMode() {
        AIAnalysisConsentStore.revoke()
        isAIAnalysisConsentGranted = false
        hasAcceptedAIAnalysisConsent = false
        isReviewerOnboardingDemoActive = true
        selectedSourceID = nil
        selectedGoalIDs = []
        selectedGenderID = nil
        selectedAge = nil
        onReviewerDemoPreparedForOnboarding()

        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            page = .source
        }
    }

    private func useReviewerDemoOnboardingScan() {
        guard let image = reviewerDemoImage(named: AppReviewDemoMode.demoPhotoNames.first ?? "demo1") else {
            startOnboardingScan()
            return
        }

        onboardingCaptureResult = nil
        onboardingScanImage = image
        onboardingScanOverlayImage = nil
        beginOnboardingScanCompletionTransition()
    }

    private func reviewerDemoImage(named name: String) -> UIImage? {
        if let image = UIImage(named: name) {
            return image
        }

        guard let url = Bundle.main.url(forResource: name, withExtension: "PNG") else {
            return nil
        }
        return UIImage(contentsOfFile: url.path)
    }
}

private struct OnboardingPendingCrop: Identifiable {
    let id = UUID()
    let capture: FaceCameraCaptureResult
}

private enum ReviewerAccessMode {
    case skipToMain
    case continueOnboarding
}

private enum OnboardingPage: Int, CaseIterable, Identifiable {
    case account
    case source
    case faceFocus
    case reportPlan
    case scanIntro
    case scanComplete
    case scanProcessing
    case reportReady
    case analysisStart
    case aiConsent

    var id: Int { rawValue }

    var showsBottomControls: Bool {
        self != .account && self != .scanIntro && self != .scanComplete && self != .scanProcessing && self != .analysisStart
    }

    var showsPageDots: Bool {
        self != .account && self != .scanIntro && self != .scanComplete && self != .scanProcessing && self != .reportReady && self != .analysisStart
    }

    var continueTitleKey: LocalizedStringKey {
        switch self {
        case .reportReady:
            "onboarding.reportReady.cta"
        case .aiConsent:
            "privacy.aiConsent.acceptToContinue"
        default:
            "onboarding.continue"
        }
    }
}

private struct AccountOnboardingPage: View {
    @EnvironmentObject private var authService: FacemaxxAuthService

    let isLoading: Bool
    let errorMessage: String?
    let onAppleCompletion: (Result<ASAuthorization, Error>) -> Void
    let onReviewerAccessRequest: () -> Void
    let onReviewerOnboardingAccessRequest: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 46)

            VStack(spacing: 18) {
                FacemaxxAppIconMark()
                    .frame(width: 86, height: 86)
                    .contentShape(RoundedRectangle(cornerRadius: 23, style: .continuous))
                    .onLongPressGesture(minimumDuration: AppReviewDemoMode.longPressDuration) {
                        onReviewerAccessRequest()
                    }

                Text("onboarding.auth.title")
                    .font(.system(size: 32, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .multilineTextAlignment(.center)
                    .minimumScaleFactor(0.82)
                    .lineLimit(2)
                    .contentShape(Rectangle())
                    .onLongPressGesture(minimumDuration: AppReviewDemoMode.longPressDuration) {
                        onReviewerAccessRequest()
                    }

            }
            .padding(.horizontal, 24)

            Spacer()

            VStack(spacing: 16) {
                SignInWithAppleButton(
                    .signIn,
                    onRequest: authService.configureAppleRequest,
                    onCompletion: onAppleCompletion
                )
                .signInWithAppleButtonStyle(.white)
                .frame(height: 54)
                .clipShape(Capsule())
                .disabled(isLoading)

                if isLoading {
                    ProgressView()
                        .tint(.white)
                        .padding(.top, 4)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.red.opacity(0.9))
                        .multilineTextAlignment(.center)
                        .lineLimit(3)
                        .padding(.top, 4)
                }

                OnboardingLegalLinks()
                    .padding(.top, 12)
                    .padding(.horizontal, 10)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 16)
        }
        .contentShape(Rectangle())
        .onTapGesture(count: 3) {
            onReviewerOnboardingAccessRequest()
        }
    }
}

private struct FacemaxxAppIconMark: View {
    private var appIcon: UIImage? {
        if let image = UIImage(named: "AppIcon") {
            return image
        }

        if let icons = Bundle.main.object(forInfoDictionaryKey: "CFBundleIcons") as? [String: Any],
           let primaryIcon = icons["CFBundlePrimaryIcon"] as? [String: Any],
           let iconFiles = primaryIcon["CFBundleIconFiles"] as? [String] {
            for iconName in iconFiles.reversed() {
                if let image = UIImage(named: iconName) {
                    return image
                }
            }
        }

        return UIImage(named: "AppIcon~ios-marketing")
            ?? UIImage(named: "AppIcon@3x")
            ?? UIImage(named: "AppIcon@2x")
    }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 23, style: .continuous)
                .fill(FXTheme.cardElevated)
                .overlay {
                    RoundedRectangle(cornerRadius: 23, style: .continuous)
                        .stroke(Color.white.opacity(0.10), lineWidth: 1)
                }

            if let appIcon {
                Image(uiImage: appIcon)
                    .resizable()
                    .scaledToFill()
            } else {
                Image(systemName: "sparkles")
                    .font(.system(size: 36, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 23, style: .continuous))
        .shadow(color: Color.black.opacity(0.28), radius: 18, y: 10)
    }
}

private struct OnboardingAccountBenefit: View {
    let iconName: String
    let titleKey: LocalizedStringKey

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .frame(width: 26)

            Text(titleKey)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.78)

            Spacer(minLength: 0)
        }
    }
}

private struct WelcomeOnboardingPage: View {
    let provider: FacemaxxAuthProvider
    let displayName: String?
    let email: String?
    let onSignOut: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            AnimatedScanGlyph()
                .frame(width: 92, height: 92)
                .padding(.bottom, 26)

            Text("onboarding.welcome.title")
                .font(.system(size: 29, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.82)

            Text("onboarding.welcome.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .padding(.top, 12)

            HStack(spacing: 12) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(FXTheme.green)

                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text("onboarding.welcome.signedInAs")
                        Text(provider.titleKey)
                    }
                    .font(.system(size: 18, weight: .bold))
                    .foregroundStyle(FXTheme.textPrimary)

                    if let displayName, !displayName.isEmpty {
                        Text(displayName)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(FXTheme.textSecondary)
                    } else if let email, !email.isEmpty {
                        Text(email)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(FXTheme.textSecondary)
                    }
                }
            }
            .padding(.top, 24)

            Text("onboarding.welcome.upgradeLater")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FXTheme.textMuted)
                .padding(.top, 20)

            Button(action: onSignOut) {
                Text("onboarding.welcome.signOut")
                    .font(.system(size: 16, weight: .semibold))
                    .underline()
                    .foregroundStyle(FXTheme.textSecondary)
            }
            .buttonStyle(.plain)
            .padding(.top, 24)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct DiscoverySourceOnboardingPage: View {
    @Binding var selectedSourceID: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 36)

            Text("onboarding.source.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.82)

            Text("onboarding.source.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .padding(.top, 14)

            VStack(spacing: 12) {
                ForEach(Array(OnboardingChoices.discoverySources.enumerated()), id: \.element.id) { index, source in
                    OnboardingSelectableRow(
                        titleKey: source.titleKey,
                        isSelected: selectedSourceID == source.id
                    ) {
                        withAnimation(.spring(response: 0.28, dampingFraction: 0.82)) {
                            selectedSourceID = source.id
                        }
                    }
                    .onboardingStaggeredEntry(index: index)
                }
            }
            .padding(.top, 22)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct FaceFocusOnboardingPage: View {
    @Binding var selectedGoalIDs: Set<String>

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 36)

            Text("onboarding.faceFocus.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.82)

            Text("onboarding.faceFocus.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .padding(.top, 14)

            VStack(spacing: 12) {
                ForEach(Array(OnboardingGoal.all.enumerated()), id: \.element.id) { index, goal in
                    OnboardingSelectableRow(
                        titleKey: goal.titleKey,
                        isSelected: selectedGoalIDs.contains(goal.id)
                    ) {
                        withAnimation(.spring(response: 0.28, dampingFraction: 0.82)) {
                            if selectedGoalIDs.contains(goal.id) {
                                selectedGoalIDs.remove(goal.id)
                            } else {
                                selectedGoalIDs.insert(goal.id)
                            }
                        }
                    }
                    .onboardingStaggeredEntry(index: index)
                }
            }
            .padding(.top, 20)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct AnalysisProgressOnboardingPage: View {
    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            HStack(spacing: 14) {
                Image(systemName: "chart.bar.fill")
                    .font(.system(size: 26, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Text("onboarding.progress.eyebrow")
                    .font(.system(size: 20, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
            }

            OnboardingProgressBars()
                .frame(height: 160)
                .padding(.top, 26)

            HStack(spacing: 18) {
                StatusPill(icon: "checkmark.circle.fill", titleKey: "onboarding.progress.complete")
                StatusPill(icon: "clock.fill", titleKey: "onboarding.progress.remaining")
            }
            .padding(.top, 14)

            Text("onboarding.progress.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.top, 30)

            Text("onboarding.progress.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
                .padding(.top, 16)
                .padding(.horizontal, 16)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct AboutOnboardingPage: View {
    @Binding var selectedGenderID: String?
    @Binding var selectedAge: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 36)

            Text("onboarding.about.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.82)

            Text("onboarding.about.subtitle")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineLimit(2)
                .padding(.top, 14)

            Text("onboarding.about.gender")
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.top, 26)

            FlowLayout(spacing: 12, rowSpacing: 12) {
                ForEach(Array(OnboardingChoices.genders.enumerated()), id: \.element.id) { index, choice in
                    OnboardingChoiceChip(
                        titleKey: choice.titleKey,
                        isSelected: selectedGenderID == choice.id
                    ) {
                        withAnimation(.spring(response: 0.28, dampingFraction: 0.82)) {
                            selectedGenderID = choice.id
                        }
                    }
                    .onboardingStaggeredEntry(index: index)
                }
            }
            .padding(.top, 16)

            Text("onboarding.about.age")
                .font(.system(size: 17, weight: .bold))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.top, 28)

            OnboardingAgePickerCard(selectedAge: $selectedAge)
                .padding(.top, 14)
                .onboardingStaggeredEntry(index: OnboardingChoices.genders.count)

            Spacer()
        }
        .padding(.horizontal, 24)
        .onAppear {
            if selectedAge == nil {
                selectedAge = 24
            }
        }
    }
}

private struct OnboardingAgePickerCard: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @Binding var selectedAge: Int?

    private let ages = Array(13...70)

    private var binding: Binding<Int> {
        Binding(
            get: { selectedAge ?? 24 },
            set: { value in
                withAnimation(.spring(response: reduceMotion ? 0.01 : 0.28, dampingFraction: 0.84)) {
                    selectedAge = value
                }
            }
        )
    }

    var body: some View {
        VStack(spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("\(selectedAge ?? 24)")
                    .font(.system(size: 40, weight: .heavy, design: .rounded))
                    .foregroundStyle(FXTheme.textPrimary)
                    .contentTransition(.numericText())

                Text("onboarding.about.age.unit")
                    .font(.system(size: 15, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
            }
            .frame(maxWidth: .infinity)

            Picker("onboarding.about.age", selection: binding) {
                ForEach(ages, id: \.self) { age in
                    Text("\(age)")
                        .font(.system(size: 20, weight: .bold, design: .rounded))
                        .tag(age)
                }
            }
            .pickerStyle(.wheel)
            .frame(height: 116)
            .clipped()
            .background(Color.black.opacity(0.16), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .background(
            LinearGradient(
                colors: [
                    FXTheme.cyan.opacity(0.18),
                    FXTheme.card.opacity(0.96)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 26, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .stroke(FXTheme.cyan.opacity(0.28), lineWidth: 1)
        )
    }

}

private struct ReportPlanOnboardingPage: View {
    let selectedGoalIDs: Set<String>

    private var leadTitleKey: LocalizedStringKey {
        OnboardingReportCopy.reportPlanTitleKey(for: selectedGoalIDs)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 30)

            Text("onboarding.reportPlan.eyebrow")
                .font(.system(size: 15, weight: .heavy))
                .foregroundStyle(FXTheme.cyan)

            Text(leadTitleKey)
                .font(.system(size: 29, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineSpacing(2)
                .lineLimit(3)
                .minimumScaleFactor(0.78)
                .padding(.top, 12)

            Text("onboarding.reportPlan.subtitle")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 14)

            VStack(spacing: 12) {
                ForEach(Array(OnboardingReportPillar.all.enumerated()), id: \.element.id) { index, pillar in
                    OnboardingReportPillarRow(pillar: pillar)
                        .onboardingStaggeredEntry(index: index)
                }
            }
            .padding(.top, 24)

            Text("onboarding.reportPlan.includes")
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.top, 26)

            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                ForEach(Array(OnboardingReportModule.all.enumerated()), id: \.element.id) { index, module in
                    OnboardingReportModuleChip(module: module)
                        .onboardingStaggeredEntry(index: index + OnboardingReportPillar.all.count)
                }
            }
            .padding(.top, 14)

            Spacer(minLength: 20)
        }
        .padding(.horizontal, 24)
    }
}

private struct ReportReadyOnboardingPage: View {
    let selectedGoalIDs: Set<String>
    let selectedGenderID: String?
    let selectedAge: Int?
    let image: UIImage?

    @State private var animate = false

    private var headlineKey: LocalizedStringKey {
        OnboardingReportCopy.readyTitleKey(for: selectedGoalIDs)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 20)

            Text(headlineKey)
                .font(.system(size: 31, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.76)

            Text("onboarding.reportReady.subtitle")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .padding(.top, 10)

            OnboardingPremiumReportPreview(
                image: image,
                selectedGoalIDs: selectedGoalIDs,
                selectedGenderID: selectedGenderID,
                selectedAge: selectedAge,
                animate: animate
            )
                .frame(maxWidth: .infinity)
                .padding(.top, 22)

            OnboardingLockedInsightCard(
                iconName: "sparkles",
                titleKey: "onboarding.reportReady.lockedInsight.title",
                bodyKey: "onboarding.reportReady.lockedInsight.body",
                tint: FXTheme.cyan
            )
            .padding(.top, 14)

            Spacer(minLength: 16)
        }
        .padding(.horizontal, 16)
        .onAppear {
            animate = true
        }
    }
}

private struct OnboardingAnalysisStartPage: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    let selectedGoalIDs: Set<String>

    @State private var selectedModeIndex = 0
    @State private var didSetInitialMode = false
    @State private var isVisible = false

    private var titleKey: LocalizedStringKey {
        OnboardingReportCopy.analysisStartTitleKey(for: selectedGoalIDs)
    }

    private var recommendation: OnboardingAnalysisStartRecommendation {
        OnboardingAnalysisStartRecommendation.bestMatch(for: selectedGoalIDs)
    }

    private var modules: [OnboardingReportModule] {
        OnboardingReportModule.all
    }

    private var entranceAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .smooth(duration: 0.54)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 44)

            Text("onboarding.analysisStart.eyebrow")
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(FXTheme.textMuted)

            Text(titleKey)
                .font(.system(size: 34, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineSpacing(2)
                .lineLimit(2)
                .minimumScaleFactor(0.76)
                .padding(.top, 12)

            Text("onboarding.analysisStart.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 14)

            OnboardingAnalysisStartModeShowcase(
                modules: modules,
                selectedIndex: $selectedModeIndex,
                recommendedID: recommendation.module.id
            )
                .padding(.top, 34)

            Spacer(minLength: 108)
        }
        .padding(.horizontal, 24)
        .opacity(isVisible ? 1 : 0)
        .offset(y: isVisible ? 0 : 18)
        .scaleEffect(isVisible ? 1 : 0.985, anchor: .bottom)
        .blur(radius: reduceMotion || isVisible ? 0 : 6)
        .onAppear {
            if !didSetInitialMode {
                didSetInitialMode = true
                selectedModeIndex = recommendation.index
            }

            isVisible = false
            withAnimation(entranceAnimation.delay(reduceMotion ? 0 : 0.04)) {
                isVisible = true
            }
        }
        .onDisappear {
            isVisible = false
        }
    }
}

private struct OnboardingAIConsentPage: View {
    @Binding var isAccepted: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 36)

            VStack(alignment: .leading, spacing: 12) {
                Text("privacy.aiConsent.pageTitle")
                    .font(.system(size: 32, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.76)

                Text("privacy.aiConsent.pageSubtitle")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }

            consentPreviewCard
                .padding(.top, 24)

            consentCheckbox
                .padding(.top, 18)

            Spacer(minLength: 96)
        }
        .padding(.horizontal, 24)
        .onAppear {
            isAccepted = isAccepted || AIAnalysisConsentStore.isGranted
        }
    }

    private var consentPreviewCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("privacy.aiConsent.previewTitle")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
                    .textCase(.uppercase)

                Text("privacy.aiConsent.previewIntro")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(alignment: .leading, spacing: 9) {
                AIConsentPreviewRow(iconName: "photo.fill", titleKey: "privacy.aiConsent.preview.photo")
                AIConsentPreviewRow(iconName: "faceid", titleKey: "privacy.aiConsent.preview.geometry")
                AIConsentPreviewRow(iconName: "server.rack", titleKey: "privacy.aiConsent.preview.provider")
            }

            Text("privacy.aiConsent.previewUsage")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(FXTheme.textMuted)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FXTheme.cardElevated, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(Color.white.opacity(0.075), lineWidth: 1.2)
        }
    }

    private var consentCheckbox: some View {
        Button {
            withAnimation(.spring(response: 0.28, dampingFraction: 0.78)) {
                isAccepted.toggle()
            }
        } label: {
            HStack(alignment: .top, spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(isAccepted ? Color.white : Color.clear)
                        .overlay {
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .stroke(Color.white, lineWidth: 1.8)
                        }

                    if isAccepted {
                        Image(systemName: "checkmark")
                            .font(.system(size: 16, weight: .black))
                            .foregroundStyle(Color.black)
                    }
                }
                .frame(width: 26, height: 26)
                .padding(.top, 2)

                Text("privacy.aiConsent.checkbox")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text("privacy.aiConsent.checkbox"))
        .accessibilityValue(isAccepted ? Text("profile.aiConsent.allowed") : Text("profile.aiConsent.notAllowed"))
    }
}

private struct AIConsentPreviewRow: View {
    let iconName: String
    let titleKey: LocalizedStringKey

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: iconName)
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(FXTheme.cyan)
                .frame(width: 19)
                .padding(.top, 2)

            Text(titleKey)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct OnboardingAnalysisStartPrimaryButton: View {
    let isCompleting: Bool
    let onPrimary: () -> Void

    var body: some View {
        Button(action: onPrimary) {
            HStack(spacing: 9) {
                if isCompleting {
                    ProgressView()
                        .tint(Color.black)
                        .controlSize(.small)
                } else {
                    Image(systemName: "arrow.right")
                        .font(.system(size: 17, weight: .heavy))
                }

                Text("onboarding.analysisStart.primary")
                    .font(.system(size: 17, weight: .heavy))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
            }
            .foregroundStyle(Color.black)
            .frame(maxWidth: .infinity)
            .frame(height: 56)
            .background(Color.white, in: Capsule())
            .shadow(color: Color.black.opacity(0.34), radius: 20, x: 0, y: 10)
        }
        .buttonStyle(.plain)
        .disabled(isCompleting)
        .opacity(isCompleting ? 0.82 : 1)
    }
}

private struct OnboardingAnalysisStartRecommendation {
    let module: OnboardingReportModule
    let bodyKey: LocalizedStringKey
    let index: Int

    @MainActor
    static func bestMatch(for goals: Set<String>) -> OnboardingAnalysisStartRecommendation {
        let moduleID: String
        if goals.contains("profile") {
            moduleID = "dating-profile-score"
        } else if goals.contains("photos") {
            moduleID = "best-photo-selector"
        } else if goals.contains("jawline") {
            moduleID = "best-angle-finder"
        } else if goals.contains("skin") || goals.contains("progress") {
            moduleID = "glow-up-coach"
        } else if goals.contains("symmetry") || goals.contains("proportions") {
            moduleID = "proportions"
        } else {
            moduleID = "aesthetics"
        }

        let modules = OnboardingReportModule.all
        let index = modules.firstIndex { $0.id == moduleID } ?? 1
        let module = modules[index]
        return OnboardingAnalysisStartRecommendation(module: module, bodyKey: bodyKey(for: moduleID), index: index)
    }

    private static func bodyKey(for moduleID: String) -> LocalizedStringKey {
        switch moduleID {
        case "dating-profile-score":
            return "onboarding.analysisStart.recommendation.dating"
        case "best-photo-selector":
            return "onboarding.analysisStart.recommendation.photo"
        case "best-angle-finder":
            return "onboarding.analysisStart.recommendation.angle"
        case "glow-up-coach":
            return "onboarding.analysisStart.recommendation.glow"
        case "proportions":
            return "onboarding.analysisStart.recommendation.proportions"
        default:
            return "onboarding.analysisStart.recommendation.aesthetics"
        }
    }
}

private enum OnboardingAnalysisStartModeCopy {
    static func bodyKey(for moduleID: String) -> LocalizedStringKey {
        switch moduleID {
        case "proportions":
            return "onboarding.analysisStart.mode.proportions"
        case "aesthetics":
            return "onboarding.analysisStart.mode.aesthetics"
        case "glow-up-coach":
            return "onboarding.analysisStart.mode.glow"
        case "look-archetype":
            return "onboarding.analysisStart.mode.archetype"
        case "best-photo-selector":
            return "onboarding.analysisStart.mode.photo"
        case "best-angle-finder":
            return "onboarding.analysisStart.mode.angle"
        case "dating-profile-score":
            return "onboarding.analysisStart.mode.dating"
        case "instagram-profile-score":
            return "onboarding.analysisStart.mode.instagram"
        default:
            return "onboarding.analysisStart.mode.aesthetics"
        }
    }
}

private struct OnboardingAnalysisStartModeShowcase: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    let modules: [OnboardingReportModule]
    @Binding var selectedIndex: Int
    let recommendedID: String

    private var currentIndex: Int {
        min(max(selectedIndex, 0), max(modules.count - 1, 0))
    }

    private var selectedModule: OnboardingReportModule {
        modules[currentIndex]
    }

    private var animation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.46, dampingFraction: 0.86, blendDuration: 0.08)
    }

    var body: some View {
        VStack(spacing: 14) {
            ZStack {
                OnboardingAnalysisStartModeCard(
                    module: selectedModule,
                    bodyKey: OnboardingAnalysisStartModeCopy.bodyKey(for: selectedModule.id),
                    index: currentIndex,
                    total: modules.count,
                    isRecommended: selectedModule.id == recommendedID
                )
                .id(selectedModule.id)
                .transition(
                    .asymmetric(
                        insertion: .opacity
                            .combined(with: .scale(scale: 0.985, anchor: .center))
                            .combined(with: .offset(x: 18)),
                        removal: .opacity
                            .combined(with: .scale(scale: 0.995, anchor: .center))
                            .combined(with: .offset(x: -18))
                    )
                )
            }
            .animation(animation, value: currentIndex)
            .gesture(
                DragGesture(minimumDistance: 18)
                    .onEnded { value in
                        if value.translation.width < -36 {
                            showNext()
                        } else if value.translation.width > 36 {
                            showPrevious()
                        }
                    }
            )

            HStack(spacing: 12) {
                OnboardingAnalysisStartModeControlButton(systemName: "chevron.left", action: showPrevious)

                OnboardingAnalysisStartModeDots(
                    modules: modules,
                    selectedIndex: currentIndex,
                    onSelect: selectMode
                )

                OnboardingAnalysisStartModeControlButton(systemName: "chevron.right", action: showNext)
            }
        }
    }

    private func showPrevious() {
        guard !modules.isEmpty else { return }
        withAnimation(animation) {
            selectedIndex = selectedIndex == 0 ? modules.count - 1 : selectedIndex - 1
        }
    }

    private func showNext() {
        guard !modules.isEmpty else { return }
        withAnimation(animation) {
            selectedIndex = (selectedIndex + 1) % modules.count
        }
    }

    private func selectMode(_ index: Int) {
        withAnimation(animation) {
            selectedIndex = min(max(index, 0), max(modules.count - 1, 0))
        }
    }
}

private struct OnboardingAnalysisStartModeCard: View {
    let module: OnboardingReportModule
    let bodyKey: LocalizedStringKey
    let index: Int
    let total: Int
    let isRecommended: Bool

    private var countText: String {
        "\(String(format: "%02d", index + 1)) / \(String(format: "%02d", total))"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                ZStack {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(module.tint.opacity(0.14))

                    Image(systemName: module.iconName)
                        .font(.system(size: 26, weight: .heavy))
                        .foregroundStyle(module.tint)
                }
                .frame(width: 60, height: 60)

                Spacer(minLength: 12)

                VStack(alignment: .trailing, spacing: 8) {
                    Text(countText)
                        .font(.system(size: 12, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)

                    if isRecommended {
                        Text("onboarding.analysisStart.recommended")
                            .font(.system(size: 10, weight: .heavy))
                            .foregroundStyle(Color.black.opacity(0.82))
                            .padding(.horizontal, 9)
                            .frame(height: 23)
                            .background(module.tint, in: Capsule())
                    }
                }
            }

            VStack(alignment: .leading, spacing: 9) {
                Text(module.titleKey)
                    .font(.system(size: 26, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.74)

                Text(bodyKey)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack(spacing: 8) {
                Circle()
                    .fill(module.tint)
                    .frame(width: 7, height: 7)

                Text("onboarding.analysisStart.readyStatus")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.76)
            }
            .padding(.top, 2)
        }
        .padding(20)
        .frame(maxWidth: .infinity, minHeight: 246, alignment: .topLeading)
        .background(
            LinearGradient(
                colors: [
                    module.tint.opacity(0.13),
                    FXTheme.card.opacity(0.96),
                    FXTheme.card.opacity(0.92)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 28, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(
                    LinearGradient(
                        colors: [module.tint.opacity(0.24), Color.white.opacity(0.08)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
        .shadow(color: module.tint.opacity(0.09), radius: 18, x: 0, y: 14)
    }
}

private struct OnboardingAnalysisStartModeDots: View {
    let modules: [OnboardingReportModule]
    let selectedIndex: Int
    let onSelect: (Int) -> Void

    var body: some View {
        HStack(spacing: 7) {
            ForEach(Array(modules.enumerated()), id: \.element.id) { index, module in
                Button {
                    onSelect(index)
                } label: {
                    Capsule()
                        .fill(index == selectedIndex ? module.tint : Color.white.opacity(0.16))
                        .frame(width: index == selectedIndex ? 24 : 7, height: 7)
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 6)
        .frame(height: 34)
        .background(Color.white.opacity(0.035), in: Capsule())
    }
}

private struct OnboardingAnalysisStartModeControlButton: View {
    let systemName: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 12, weight: .black))
                .foregroundStyle(FXTheme.textPrimary)
                .frame(width: 34, height: 34)
                .background(Color.white.opacity(0.055), in: Circle())
                .overlay(
                    Circle()
                        .stroke(Color.white.opacity(0.07), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}

private struct OnboardingAnalysisStartHeroCard: View {
    let recommendation: OnboardingAnalysisStartRecommendation

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 16) {
                ZStack {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(recommendation.module.tint.opacity(0.13))

                    Image(systemName: recommendation.module.iconName)
                        .font(.system(size: 24, weight: .heavy))
                        .foregroundStyle(recommendation.module.tint)
                }
                .frame(width: 58, height: 58)

                VStack(alignment: .leading, spacing: 6) {
                    Text("onboarding.analysisStart.recommended")
                        .font(.system(size: 11, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)

                    Text(recommendation.module.titleKey)
                        .font(.system(size: 21, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(2)
                        .minimumScaleFactor(0.78)

                    Text(recommendation.bodyKey)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            Divider()
                .overlay(Color.white.opacity(0.08))

            Text("onboarding.analysisStart.readyStatus")
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(FXTheme.textSecondary)
                .lineLimit(2)
                .minimumScaleFactor(0.78)
        }
        .padding(18)
        .background(
            FXTheme.card.opacity(0.96),
            in: RoundedRectangle(cornerRadius: 24, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct OnboardingAnalysisStartModeStrip: View {
    let recommendedID: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("onboarding.analysisStart.modulesTitle")
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)

                Spacer()

                Text(String(format: String(localized: "onboarding.analysisStart.modulesCountFormat"), OnboardingReportModule.all.count))
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
            }

            HStack(spacing: 8) {
                ForEach(OnboardingReportModule.all) { module in
                    Image(systemName: module.iconName)
                        .font(.system(size: 13, weight: .heavy))
                        .foregroundStyle(module.id == recommendedID ? Color.black : module.tint)
                        .frame(maxWidth: .infinity)
                        .frame(height: 34)
                        .background(
                            module.id == recommendedID ? module.tint : Color.white.opacity(0.045),
                            in: RoundedRectangle(cornerRadius: 10, style: .continuous)
                        )
                }
            }
        }
        .padding(14)
        .background(FXTheme.glassFill, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.07), lineWidth: 1)
        )
    }
}

private struct OnboardingAnalysisStartStep: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color

    @MainActor
    static let all: [OnboardingAnalysisStartStep] = [
        OnboardingAnalysisStartStep(
            id: "photo",
            iconName: "photo.on.rectangle.angled",
            titleKey: "onboarding.analysisStart.step.photo.title",
            bodyKey: "onboarding.analysisStart.step.photo.body",
            tint: Color(red: 0.97, green: 0.45, blue: 0.64)
        ),
        OnboardingAnalysisStartStep(
            id: "mode",
            iconName: "square.grid.2x2.fill",
            titleKey: "onboarding.analysisStart.step.mode.title",
            bodyKey: "onboarding.analysisStart.step.mode.body",
            tint: FXTheme.cyan
        ),
        OnboardingAnalysisStartStep(
            id: "track",
            iconName: "chart.xyaxis.line",
            titleKey: "onboarding.analysisStart.step.track.title",
            bodyKey: "onboarding.analysisStart.step.track.body",
            tint: FXTheme.green
        )
    ]
}

private struct OnboardingAnalysisStartStepRow: View {
    let step: OnboardingAnalysisStartStep
    let index: Int

    var body: some View {
        HStack(alignment: .top, spacing: 13) {
            ZStack {
                Circle()
                    .fill(step.tint.opacity(0.15))

                Image(systemName: step.iconName)
                    .font(.system(size: 15, weight: .heavy))
                    .foregroundStyle(step.tint)
            }
            .frame(width: 36, height: 36)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(String(format: String(localized: "onboarding.analysisStart.stepNumberFormat"), index + 1))
                        .font(.system(size: 11, weight: .black))
                        .foregroundStyle(step.tint)

                    Text(step.titleKey)
                        .font(.system(size: 15, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)
                }

                Text(step.bodyKey)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(14)
        .background(FXTheme.glassFill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Color.white.opacity(0.07), lineWidth: 1)
        )
    }
}

private struct OnboardingAnalysisStartModuleTile: View {
    let module: OnboardingReportModule
    let isRecommended: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: module.iconName)
                    .font(.system(size: 15, weight: .heavy))
                    .foregroundStyle(module.tint)
                    .frame(width: 30, height: 30)
                    .background(module.tint.opacity(0.15), in: Circle())

                Spacer(minLength: 6)

                if isRecommended {
                    Image(systemName: "star.fill")
                        .font(.system(size: 10, weight: .heavy))
                        .foregroundStyle(module.tint)
                }
            }

            Text(module.titleKey)
                .font(.system(size: 12, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.76)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 86, alignment: .topLeading)
        .background((isRecommended ? module.tint.opacity(0.12) : Color.white.opacity(0.035)), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(isRecommended ? module.tint.opacity(0.32) : Color.white.opacity(0.065), lineWidth: 1)
        )
    }
}

private struct ReadyOnboardingPage: View {
    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 48)

            Text("onboarding.ready.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.82)

            VStack(spacing: 20) {
                OnboardingFeatureRow(
                    iconName: "chart.xyaxis.line",
                    titleKey: "onboarding.ready.track.title",
                    bodyKey: "onboarding.ready.track.body"
                )

                OnboardingFeatureRow(
                    iconName: "brain.head.profile",
                    titleKey: "onboarding.ready.ai.title",
                    bodyKey: "onboarding.ready.ai.body"
                )

                OnboardingFeatureRow(
                    iconName: "list.clipboard",
                    titleKey: "onboarding.ready.plan.title",
                    bodyKey: "onboarding.ready.plan.body"
                )
            }
            .padding(.top, 28)

            Text("onboarding.ready.freeMode")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textMuted)
                .padding(.top, 22)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct FaceScanIntroOnboardingPage: View {
    @State private var isPressingCTA = false

    let onBack: () -> Void
    let onStartScan: () -> Void
    let onUseDemoScan: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 16) {
                Button(action: onBack) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 24, weight: .heavy))
                        .foregroundStyle(FXTheme.textSecondary)
                        .frame(width: 40, height: 40)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)

                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        Capsule()
                            .fill(Color.white.opacity(0.11))

                        Capsule()
                            .fill(
                                LinearGradient(
                                    colors: [FXTheme.cyan, FXTheme.blue.opacity(0.72)],
                                    startPoint: .leading,
                                    endPoint: .trailing
                                )
                            )
                            .frame(width: proxy.size.width * 0.66)
                    }
                }
                .frame(height: 6)
            }
            .padding(.top, 14)

            Text("onboarding.scanIntro.title")
                .font(.system(size: 32, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.78)
                .padding(.top, 26)

            Text("onboarding.scanIntro.subtitle")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .lineSpacing(5)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 14)

            Spacer(minLength: 18)

            FacemaxxLottieView(animationName: "facescan")
                .frame(maxWidth: .infinity)
                .frame(height: 312)

            Spacer(minLength: 18)

            HStack(spacing: 0) {
                OnboardingPrivacyItem(
                    iconName: "lock.shield.fill",
                    titleKey: "onboarding.scanIntro.secure.title",
                    bodyKey: "onboarding.scanIntro.secure.body"
                )

                Divider()
                    .overlay(Color.white.opacity(0.12))
                    .frame(height: 84)

                OnboardingPrivacyItem(
                    iconName: "hand.raised.slash.fill",
                    titleKey: "onboarding.scanIntro.private.title",
                    bodyKey: "onboarding.scanIntro.private.body"
                )

                Divider()
                    .overlay(Color.white.opacity(0.12))
                    .frame(height: 84)

                OnboardingPrivacyItem(
                    iconName: "trash.fill",
                    titleKey: "onboarding.scanIntro.data.title",
                    bodyKey: "onboarding.scanIntro.data.body"
                )
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 16)
            .background(Color.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 26, style: .continuous)
                    .stroke(Color.white.opacity(0.12), lineWidth: 1)
            )

            Button(action: onStartScan) {
                Text("onboarding.scanIntro.cta")
                    .font(.system(size: 17, weight: .heavy))
                    .foregroundStyle(Color.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 58)
                    .background(
                        LinearGradient(
                            colors: [FXTheme.cyan, FXTheme.blue.opacity(0.72)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        in: Capsule()
                    )
                    .overlay {
                        Capsule()
                            .stroke(Color.white.opacity(0.20), lineWidth: 1)
                    }
                    .scaleEffect(isPressingCTA ? 0.985 : 1)
                    .shadow(color: FXTheme.cyan.opacity(0.18), radius: 22, y: 10)
            }
            .buttonStyle(.plain)
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in isPressingCTA = true }
                    .onEnded { _ in isPressingCTA = false }
            )
            .padding(.top, 14)

            if let onUseDemoScan {
                Button(action: onUseDemoScan) {
                    HStack(spacing: 8) {
                        Image(systemName: "person.crop.square.fill")
                            .font(.system(size: 15, weight: .heavy))

                        Text("onboarding.scanIntro.demoCta")
                            .font(.system(size: 15, weight: .heavy))
                            .lineLimit(1)
                            .minimumScaleFactor(0.78)
                    }
                    .foregroundStyle(FXTheme.textPrimary)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(FXTheme.pill, in: Capsule())
                    .overlay {
                        Capsule()
                            .stroke(Color.white.opacity(0.10), lineWidth: 1)
                    }
                }
                .buttonStyle(.plain)
                .padding(.top, 10)
            }
        }
        .padding(.horizontal, 24)
        .padding(.bottom, 16)
    }
}

private struct OnboardingLottieAnimationView: UIViewRepresentable {
    let animationName: String
    var loopMode: LottieLoopMode = .loop

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> UIView {
        let containerView = UIView()
        containerView.backgroundColor = .clear

        let animationView = context.coordinator.animationView
        animationView.translatesAutoresizingMaskIntoConstraints = false
        animationView.backgroundColor = .clear
        animationView.contentMode = .scaleAspectFit
        animationView.loopMode = loopMode
        animationView.backgroundBehavior = .pauseAndRestore
        animationView.animation = loadAnimation()

        containerView.addSubview(animationView)
        NSLayoutConstraint.activate([
            animationView.leadingAnchor.constraint(equalTo: containerView.leadingAnchor),
            animationView.trailingAnchor.constraint(equalTo: containerView.trailingAnchor),
            animationView.topAnchor.constraint(equalTo: containerView.topAnchor),
            animationView.bottomAnchor.constraint(equalTo: containerView.bottomAnchor)
        ])

        context.coordinator.animationName = animationName
        animationView.play()
        return containerView
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        let animationView = context.coordinator.animationView
        animationView.loopMode = loopMode

        if context.coordinator.animationName != animationName {
            animationView.animation = loadAnimation()
            context.coordinator.animationName = animationName
            animationView.play()
        } else if !animationView.isAnimationPlaying {
            animationView.play()
        }
    }

    private func loadAnimation() -> LottieAnimation? {
        if let animation = LottieAnimation.named(animationName, bundle: .main) {
            return animation
        }

        if let path = Bundle.main.path(forResource: animationName, ofType: "json") {
            return LottieAnimation.filepath(path)
        }

        if let path = Bundle.main.path(forResource: animationName, ofType: "json", inDirectory: "Assets") {
            return LottieAnimation.filepath(path)
        }

        return nil
    }

    @MainActor
    final class Coordinator {
        let animationView = LottieAnimationView()
        var animationName: String?
    }
}

private struct ScanCompleteOnboardingPage: View {
    let image: UIImage?

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 104, height: 104)
                    .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 28, style: .continuous)
                            .stroke(Color.white.opacity(0.34), lineWidth: 2)
                    )
                    .shadow(color: FXTheme.cyan.opacity(0.22), radius: 24, y: 8)
                    .padding(.bottom, 28)
            }

            ZStack {
                Circle()
                    .fill(FXTheme.cyan)
                    .frame(width: 70, height: 70)

                Image(systemName: "checkmark")
                    .font(.system(size: 38, weight: .heavy))
                    .foregroundStyle(Color.black)
            }

            Text("onboarding.scanComplete.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.top, 30)

            Text("onboarding.scanComplete.subtitle")
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.top, 18)

            Spacer()
        }
        .padding(.horizontal, 24)
    }
}

private struct ScanProcessingOnboardingPage: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let image: UIImage?
    let restartToken: UUID
    let onComplete: @MainActor () -> Void

    @State private var phase = 0
    @State private var appeared = false

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.025, green: 0.030, blue: 0.036),
                    FXTheme.background
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer(minLength: 36)

                OnboardingScanPhotoLottiePreview(image: image)
                    .frame(maxWidth: .infinity)
                    .frame(height: 250)
                .scaleEffect(appeared ? 1 : 0.92)
                .opacity(appeared ? 1 : 0)

                VStack(spacing: 10) {
                    Text("onboarding.scanProcessing.title")
                        .font(.system(size: 15, weight: .heavy))
                        .foregroundStyle(FXTheme.cyan)
                        .textCase(.uppercase)
                        .tracking(1.4)

                    Text("onboarding.scanProcessing.subtitle")
                        .font(.system(size: 28, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .minimumScaleFactor(0.78)
                }
                .padding(.top, 30)
                .opacity(appeared ? 1 : 0)
                .offset(y: appeared ? 0 : 10)

                VStack(spacing: 10) {
                    OnboardingProcessingStep(
                        titleKey: "analysis.loading.step.photo",
                        index: 0,
                        activeIndex: phase
                    )
                    OnboardingProcessingStep(
                        titleKey: "analysis.loading.step.geometry",
                        index: 1,
                        activeIndex: phase
                    )
                    OnboardingProcessingStep(
                        titleKey: "analysis.loading.step.gemini",
                        index: 2,
                        activeIndex: phase
                    )
                    OnboardingProcessingStep(
                        titleKey: "analysis.loading.step.report",
                        index: 3,
                        activeIndex: phase
                    )
                }
                .padding(12)
                .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 26, style: .continuous)
                        .stroke(Color.white.opacity(0.08), lineWidth: 1)
                }
                .padding(.top, 26)
                .opacity(appeared ? 1 : 0)
                .offset(y: appeared ? 0 : 14)

                Spacer(minLength: 40)
            }
            .padding(.horizontal, 24)
        }
        .onAppear {
            withAnimation(.spring(response: 0.58, dampingFraction: 0.86)) {
                appeared = true
            }
        }
        .task(id: restartToken) {
            phase = 0
            guard !reduceMotion else {
                await MainActor.run {
                    phase = 4
                    onComplete()
                }
                return
            }
            for step in 0...4 {
                try? await Task.sleep(nanoseconds: UInt64(1_540_000_000))
                await MainActor.run {
                    withAnimation(.spring(response: 0.36, dampingFraction: 0.82)) {
                        phase = min(step, 4)
                    }
                }
            }
            try? await Task.sleep(nanoseconds: UInt64(300_000_000))
            await MainActor.run {
                onComplete()
            }
        }
    }
}

private struct OnboardingScanPhotoLottiePreview: View {
    let image: UIImage?

    var body: some View {
        ZStack {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(width: 238, height: 238)
                    .clipped()
            } else {
                Color.white.opacity(0.055)
                    .overlay {
                        Image(systemName: "face.smiling")
                            .font(.system(size: 54, weight: .heavy))
                            .foregroundStyle(FXTheme.cyan.opacity(0.70))
                    }
            }

            FacemaxxLottieView(animationName: "scan_onboarding", contentMode: .scaleToFill)
                .frame(width: 326, height: 286)
                .offset(y: -22)
                .allowsHitTesting(false)
                .blendMode(.screen)
        }
        .frame(width: 238, height: 238)
        .clipShape(RoundedRectangle(cornerRadius: 32, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 32, style: .continuous)
                .stroke(Color.white.opacity(0.24), lineWidth: 1.2)
        }
        .shadow(color: FXTheme.cyan.opacity(0.18), radius: 26, y: 12)
        .accessibilityHidden(true)
    }
}

private struct OnboardingReportBuildVisual: View {
    let phase: Int
    let isActive: Bool

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = isActive ? timeline.date.timeIntervalSinceReferenceDate : 0

            ZStack {
                RoundedRectangle(cornerRadius: 36, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0.050),
                                Color.white.opacity(0.022)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .overlay {
                        RoundedRectangle(cornerRadius: 36, style: .continuous)
                            .stroke(Color.white.opacity(0.09), lineWidth: 1)
                    }

                ForEach(0..<3, id: \.self) { index in
                    let isReady = phase >= index
                    let lift = CGFloat(index) * -18
                    let xOffset = CGFloat(index - 1) * 22
                    let pulse = CGFloat(sin(time * 1.2 + Double(index))) * 2.0

                    OnboardingReportSheet(
                        index: index,
                        isReady: isReady,
                        pulse: isActive ? pulse : 0
                    )
                    .frame(width: 176, height: 208)
                    .offset(x: xOffset, y: lift + CGFloat(index) * 12)
                    .scaleEffect(isReady ? 1 : 0.94)
                    .opacity(isReady ? 1 : 0.38)
                    .animation(.spring(response: 0.46, dampingFraction: 0.84), value: phase)
                }

                HStack(spacing: 7) {
                    ForEach(0..<4, id: \.self) { index in
                        Capsule(style: .continuous)
                            .fill(index <= min(phase, 3) ? FXTheme.cyan : Color.white.opacity(0.16))
                            .frame(width: index == min(phase, 3) ? 28 : 10, height: 5)
                            .animation(.spring(response: 0.34, dampingFraction: 0.82), value: phase)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color.black.opacity(0.24), in: Capsule())
                .offset(y: 106)
            }
        }
        .accessibilityHidden(true)
    }
}

private struct OnboardingReportSheet: View {
    let index: Int
    let isReady: Bool
    let pulse: CGFloat

    private var tint: Color {
        switch index {
        case 0: return FXTheme.cyan
        case 1: return FXTheme.blue
        default: return Color(red: 0.72, green: 0.88, blue: 1.00)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(tint.opacity(isReady ? 0.90 : 0.22))
                    .frame(width: 34, height: 7)

                Spacer()

                Circle()
                    .fill(isReady ? tint : Color.white.opacity(0.12))
                    .frame(width: 8, height: 8)
            }

            VStack(alignment: .leading, spacing: 8) {
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .fill(Color.white.opacity(isReady ? 0.30 : 0.12))
                    .frame(width: 112, height: 8)

                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .fill(Color.white.opacity(isReady ? 0.18 : 0.09))
                    .frame(width: 136, height: 6)
            }

            Spacer()

            VStack(spacing: 8) {
                ForEach(0..<4, id: \.self) { row in
                    HStack(spacing: 7) {
                        RoundedRectangle(cornerRadius: 3, style: .continuous)
                            .fill(row <= index ? tint.opacity(0.55) : Color.white.opacity(0.10))
                            .frame(width: 18 + CGFloat(row * 6), height: 6)

                        RoundedRectangle(cornerRadius: 3, style: .continuous)
                            .fill(Color.white.opacity(row <= index ? 0.18 : 0.08))
                            .frame(height: 6)
                    }
                }
            }
        }
        .padding(18)
        .background(
            LinearGradient(
                colors: [
                    Color.white.opacity(isReady ? 0.105 : 0.045),
                    Color.white.opacity(isReady ? 0.040 : 0.025)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 28, style: .continuous)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(tint.opacity(isReady ? 0.28 : 0.08), lineWidth: 1)
        }
        .shadow(color: tint.opacity(isReady ? 0.08 : 0), radius: 18, y: 8)
        .offset(y: pulse)
    }
}

private struct OnboardingProcessingStep: View {
    let titleKey: LocalizedStringKey
    let index: Int
    let activeIndex: Int

    private var isDone: Bool { index < activeIndex }
    private var isCurrent: Bool { index == activeIndex }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(isDone ? FXTheme.green : (isCurrent ? FXTheme.cyan : Color.white.opacity(0.13)))

                if isDone {
                    Image(systemName: "checkmark")
                        .font(.system(size: 10, weight: .heavy))
                        .foregroundStyle(Color.black.opacity(0.72))
                } else if isCurrent {
                    Circle()
                        .fill(Color.white.opacity(0.70))
                        .frame(width: 5, height: 5)
                }
            }
            .frame(width: 18, height: 18)

            Text(titleKey)
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(isCurrent || isDone ? FXTheme.textPrimary : FXTheme.textMuted)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(isCurrent ? FXTheme.cyan.opacity(0.09) : Color.clear)
        )
        .animation(.spring(response: 0.34, dampingFraction: 0.82), value: activeIndex)
    }
}

private struct OnboardingPrivacyItem: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey

    var body: some View {
        VStack(spacing: 9) {
            ZStack {
                RoundedRectangle(cornerRadius: 15, style: .continuous)
                    .fill(FXTheme.cyan.opacity(0.13))

                Image(systemName: iconName)
                    .font(.system(size: 20, weight: .heavy))
                    .foregroundStyle(FXTheme.cyan)
            }
            .frame(width: 42, height: 42)

            Text(titleKey)
                .font(.system(size: 14, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.8)

            Text(bodyKey)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(FXTheme.textMuted)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.78)
        }
        .frame(maxWidth: .infinity)
    }
}

private struct SupportOnboardingPage: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var animate = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            ZStack {
                Circle()
                    .fill(FXTheme.pill)
                    .frame(width: 104, height: 104)

                Circle()
                    .fill(Color.white)
                    .frame(width: 68, height: 68)

                Image(systemName: "checkmark")
                    .font(.system(size: 38, weight: .heavy))
                    .foregroundStyle(FXTheme.pill)
            }
            .scaleEffect(animate ? 1 : 0.84)

            HStack(spacing: 14) {
                ForEach(0..<5, id: \.self) { index in
                    Image(systemName: "star.fill")
                        .font(.system(size: 30, weight: .heavy))
                        .foregroundStyle(FXTheme.yellow)
                        .scaleEffect(animate ? 1 : 0.55)
                        .opacity(animate ? 1 : 0)
                        .animation(
                            .spring(response: 0.42, dampingFraction: 0.68)
                                .delay(reduceMotion ? 0 : Double(index) * 0.07),
                            value: animate
                        )
                }
            }
            .padding(.top, 32)

            Text("onboarding.support.title")
                .font(.system(size: 28, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.top, 28)

            Text("onboarding.support.subtitle")
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(4)
                .padding(.top, 18)
                .padding(.horizontal, 8)

            Text("onboarding.support.prompt")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(FXTheme.textSecondary)
                .padding(.top, 30)

            Spacer()
        }
        .padding(.horizontal, 24)
        .onAppear {
            guard !reduceMotion else {
                animate = true
                return
            }
            withAnimation(.spring(response: 0.48, dampingFraction: 0.74)) {
                animate = true
            }
        }
    }
}

private struct OnboardingBottomControls: View {
    let page: OnboardingPage
    let canContinue: Bool
    let isCompleting: Bool
    let onBack: () -> Void
    let onRetake: () -> Void
    let onContinue: () -> Void

    var body: some View {
        HStack(spacing: 18) {
            backButton
            continueButton
        }
    }

    private var secondaryTitleKey: LocalizedStringKey {
        page == .reportReady ? "onboarding.retakePhoto" : "onboarding.back"
    }

    private var backButton: some View {
        Button(action: page == .reportReady ? onRetake : onBack) {
            HStack(spacing: 8) {
                if page == .reportReady {
                    Image(systemName: "camera.fill")
                        .font(.system(size: 15, weight: .bold))
                }

                Text(secondaryTitleKey)
                    .font(.system(size: 17, weight: .bold))
            }
            .foregroundStyle(FXTheme.textPrimary)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(FXTheme.pill, in: Capsule())
        }
        .buttonStyle(.plain)
    }

    private var continueButton: some View {
        Button(action: onContinue) {
            HStack(spacing: 8) {
                if isCompleting && page == .aiConsent {
                    ProgressView()
                        .tint(Color.black)
                        .controlSize(.small)
                }

                Text(isCompleting && page == .aiConsent ? "onboarding.settingUpAccount" : page.continueTitleKey)
                    .font(.system(size: 17, weight: .bold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.70)
            }
            .foregroundStyle(canContinue ? Color.black : FXTheme.textMuted)
            .frame(maxWidth: .infinity)
            .frame(height: 54)
            .background(canContinue ? Color.white : FXTheme.pill.opacity(0.7), in: Capsule())
        }
        .buttonStyle(.plain)
        .disabled(!canContinue || isCompleting)
    }
}

private struct OnboardingPageDots: View {
    let page: OnboardingPage

    var body: some View {
        HStack(spacing: 13) {
            ForEach(OnboardingPage.allCases.filter(\.showsPageDots)) { dotPage in
                Circle()
                    .fill(dotPage == page ? Color.white : Color.white.opacity(0.18))
                    .frame(width: dotPage == page ? 11 : 10, height: dotPage == page ? 11 : 10)
                    .animation(.smooth(duration: 0.22), value: page)
            }
        }
        .frame(height: 18)
    }
}

private struct OnboardingReportPillar: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color

    @MainActor
    static let all: [OnboardingReportPillar] = [
        OnboardingReportPillar(
            id: "face-structure",
            iconName: "face.smiling",
            titleKey: "onboarding.reportPillar.face.title",
            bodyKey: "onboarding.reportPillar.face.body",
            tint: FXTheme.cyan
        ),
        OnboardingReportPillar(
            id: "glow-up",
            iconName: "sparkles",
            titleKey: "onboarding.reportPillar.glow.title",
            bodyKey: "onboarding.reportPillar.glow.body",
            tint: FXTheme.green
        ),
        OnboardingReportPillar(
            id: "profile",
            iconName: "person.crop.square.fill",
            titleKey: "onboarding.reportPillar.profile.title",
            bodyKey: "onboarding.reportPillar.profile.body",
            tint: Color(red: 0.77, green: 0.67, blue: 1.00)
        )
    ]
}

private struct OnboardingReportModule: Identifiable {
    let id: String
    let titleKey: LocalizedStringKey
    let iconName: String
    let tint: Color

    @MainActor
    static let all: [OnboardingReportModule] = [
        OnboardingReportModule(id: "proportions", titleKey: "analysis.mode.proportions", iconName: "chart.bar.fill", tint: Color(red: 1.00, green: 0.50, blue: 0.50)),
        OnboardingReportModule(id: "aesthetics", titleKey: "analysis.mode.aesthetics", iconName: "brain.head.profile", tint: FXTheme.cyan),
        OnboardingReportModule(id: "glow-up-coach", titleKey: "analysis.mode.glowUpCoach", iconName: "sparkles", tint: FXTheme.green),
        OnboardingReportModule(id: "look-archetype", titleKey: "analysis.mode.lookArchetype", iconName: "theatermasks.fill", tint: Color(red: 0.86, green: 0.56, blue: 1.00)),
        OnboardingReportModule(id: "best-photo-selector", titleKey: "analysis.mode.bestPhotoSelector", iconName: "checkmark.seal.fill", tint: Color(red: 0.97, green: 0.45, blue: 0.64)),
        OnboardingReportModule(id: "best-angle-finder", titleKey: "analysis.mode.bestAngleFinder", iconName: "viewfinder", tint: Color(red: 1.00, green: 0.75, blue: 0.36)),
        OnboardingReportModule(id: "dating-profile-score", titleKey: "analysis.mode.datingProfileScore", iconName: "heart.fill", tint: Color(red: 1.00, green: 0.36, blue: 0.54)),
        OnboardingReportModule(id: "instagram-profile-score", titleKey: "analysis.mode.instagramProfileScore", iconName: "square.grid.3x3.fill", tint: Color(red: 0.58, green: 0.72, blue: 1.00))
    ]
}

private struct OnboardingReportPreviewPage: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let categoryKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color
    let yoursWidth: CGFloat
    let idealWidth: CGFloat
    let hiddenMetricCount: Int
    let classificationKey: LocalizedStringKey
    let scoreMetrics: [OnboardingReportScoreMetricTemplate]
    let lockedMetrics: [OnboardingReportPreviewMetric]
}

private struct OnboardingReportPreviewMetric: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color
    let valueWidth: CGFloat
}

private struct OnboardingReportScoreMetricTemplate: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let tint: Color
    let delta: Int
}

private struct OnboardingReportScoreMetric: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color
    let signalKey: LocalizedStringKey
}

private struct OnboardingReportPreviewInsight {
    let pageID: String
    let classificationKey: LocalizedStringKey
    let rows: [OnboardingReportScoreMetric]
}

private enum OnboardingReportPreviewContent {
    @MainActor
    static let pages: [OnboardingReportPreviewPage] = [
        OnboardingReportPreviewPage(
            id: "proportions",
            iconName: "chart.bar.fill",
            titleKey: "analysis.mode.proportions",
            categoryKey: "onboarding.reportReady.category.structure",
            bodyKey: "onboarding.reportPage.proportions.body",
            tint: Color(red: 1.00, green: 0.50, blue: 0.50),
            yoursWidth: 46,
            idealWidth: 38,
            hiddenMetricCount: 6,
            classificationKey: "onboarding.reportScore.classification.proportions",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "facial-index", iconName: "ruler", titleKey: "onboarding.reportScore.proportions.rowOne", tint: Color(red: 1.00, green: 0.50, blue: 0.50), delta: 2),
                OnboardingReportScoreMetricTemplate(id: "thirds", iconName: "rectangle.split.3x1", titleKey: "onboarding.reportScore.proportions.rowTwo", tint: Color(red: 0.94, green: 0.52, blue: 0.50), delta: -3),
                OnboardingReportScoreMetricTemplate(id: "symmetry-axis", iconName: "arrow.left.and.right", titleKey: "onboarding.reportScore.proportions.rowThree", tint: Color(red: 0.62, green: 0.80, blue: 0.78), delta: 5),
                OnboardingReportScoreMetricTemplate(id: "jaw-relation", iconName: "triangle", titleKey: "onboarding.reportScore.proportions.rowFour", tint: Color(red: 0.78, green: 0.68, blue: 1.00), delta: -1)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "facial-index", iconName: "ruler", titleKey: "onboarding.reportPage.proportions.metricOne", bodyKey: "onboarding.reportPage.proportions.metricOneBody", tint: Color(red: 1.00, green: 0.50, blue: 0.50), valueWidth: 50),
                OnboardingReportPreviewMetric(id: "lower-face", iconName: "rectangle.split.3x1", titleKey: "onboarding.reportPage.proportions.metricTwo", bodyKey: "onboarding.reportPage.proportions.metricTwoBody", tint: Color(red: 0.94, green: 0.52, blue: 0.50), valueWidth: 42)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "aesthetics",
            iconName: "brain.head.profile",
            titleKey: "analysis.mode.aesthetics",
            categoryKey: "onboarding.reportReady.category.face",
            bodyKey: "onboarding.reportPage.aesthetics.body",
            tint: FXTheme.cyan,
            yoursWidth: 44,
            idealWidth: 38,
            hiddenMetricCount: 8,
            classificationKey: "onboarding.reportScore.classification.aesthetics",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "harmony", iconName: "face.smiling", titleKey: "onboarding.reportScore.aesthetics.rowOne", tint: FXTheme.cyan, delta: 1),
                OnboardingReportScoreMetricTemplate(id: "presence", iconName: "sparkles", titleKey: "onboarding.reportScore.aesthetics.rowTwo", tint: FXTheme.green, delta: 4),
                OnboardingReportScoreMetricTemplate(id: "feature-balance", iconName: "circle.hexagongrid.fill", titleKey: "onboarding.reportScore.aesthetics.rowThree", tint: Color(red: 0.62, green: 0.80, blue: 0.78), delta: -2),
                OnboardingReportScoreMetricTemplate(id: "definition", iconName: "camera.macro", titleKey: "onboarding.reportScore.aesthetics.rowFour", tint: Color(red: 0.58, green: 0.72, blue: 1.00), delta: 3)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "harmony-index", iconName: "face.smiling", titleKey: "onboarding.reportPage.aesthetics.metricOne", bodyKey: "onboarding.reportPage.aesthetics.metricOneBody", tint: FXTheme.cyan, valueWidth: 52),
                OnboardingReportPreviewMetric(id: "feature-balance", iconName: "circle.hexagongrid.fill", titleKey: "onboarding.reportPage.aesthetics.metricTwo", bodyKey: "onboarding.reportPage.aesthetics.metricTwoBody", tint: Color(red: 0.62, green: 0.80, blue: 0.78), valueWidth: 46)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "glow-up-coach",
            iconName: "sparkles",
            titleKey: "analysis.mode.glowUpCoach",
            categoryKey: "onboarding.reportReady.category.coach",
            bodyKey: "onboarding.reportPage.glow.body",
            tint: FXTheme.green,
            yoursWidth: 54,
            idealWidth: 40,
            hiddenMetricCount: 9,
            classificationKey: "onboarding.reportScore.classification.glow",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "priority", iconName: "sparkle.magnifyingglass", titleKey: "onboarding.reportScore.glow.rowOne", tint: FXTheme.green, delta: 5),
                OnboardingReportScoreMetricTemplate(id: "skin-light", iconName: "sun.max.fill", titleKey: "onboarding.reportScore.glow.rowTwo", tint: Color(red: 1.00, green: 0.80, blue: 0.32), delta: -1),
                OnboardingReportScoreMetricTemplate(id: "hair-frame", iconName: "person.crop.circle", titleKey: "onboarding.reportScore.glow.rowThree", tint: Color(red: 0.60, green: 0.86, blue: 0.36), delta: 2),
                OnboardingReportScoreMetricTemplate(id: "photo-lift", iconName: "camera.fill", titleKey: "onboarding.reportScore.glow.rowFour", tint: Color(red: 0.97, green: 0.45, blue: 0.64), delta: 3)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "priority-upgrades", iconName: "sparkle.magnifyingglass", titleKey: "onboarding.reportPage.glow.metricOne", bodyKey: "onboarding.reportPage.glow.metricOneBody", tint: FXTheme.green, valueWidth: 54),
                OnboardingReportPreviewMetric(id: "routine-impact", iconName: "checklist.checked", titleKey: "onboarding.reportPage.glow.metricTwo", bodyKey: "onboarding.reportPage.glow.metricTwoBody", tint: Color(red: 0.60, green: 0.86, blue: 0.36), valueWidth: 44)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "look-archetype",
            iconName: "theatermasks.fill",
            titleKey: "analysis.mode.lookArchetype",
            categoryKey: "onboarding.reportReady.category.style",
            bodyKey: "onboarding.reportPage.archetype.body",
            tint: Color(red: 0.78, green: 0.62, blue: 0.98),
            yoursWidth: 48,
            idealWidth: 36,
            hiddenMetricCount: 5,
            classificationKey: "onboarding.reportScore.classification.archetype",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "match", iconName: "theatermasks.fill", titleKey: "onboarding.reportScore.archetype.rowOne", tint: Color(red: 0.78, green: 0.62, blue: 0.98), delta: 2),
                OnboardingReportScoreMetricTemplate(id: "style", iconName: "wand.and.stars", titleKey: "onboarding.reportScore.archetype.rowTwo", tint: Color(red: 0.92, green: 0.58, blue: 0.92), delta: 4),
                OnboardingReportScoreMetricTemplate(id: "mood", iconName: "person.crop.rectangle.stack.fill", titleKey: "onboarding.reportScore.archetype.rowThree", tint: Color(red: 0.58, green: 0.72, blue: 1.00), delta: -1),
                OnboardingReportScoreMetricTemplate(id: "signature", iconName: "star.square.fill", titleKey: "onboarding.reportScore.archetype.rowFour", tint: Color(red: 1.00, green: 0.75, blue: 0.36), delta: 1)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "archetype-match", iconName: "person.crop.rectangle.stack.fill", titleKey: "onboarding.reportPage.archetype.metricOne", bodyKey: "onboarding.reportPage.archetype.metricOneBody", tint: Color(red: 0.78, green: 0.62, blue: 0.98), valueWidth: 48),
                OnboardingReportPreviewMetric(id: "style-direction", iconName: "wand.and.stars", titleKey: "onboarding.reportPage.archetype.metricTwo", bodyKey: "onboarding.reportPage.archetype.metricTwoBody", tint: Color(red: 0.92, green: 0.58, blue: 0.92), valueWidth: 42)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "best-photo-selector",
            iconName: "checkmark.seal.fill",
            titleKey: "analysis.mode.bestPhotoSelector",
            categoryKey: "onboarding.reportReady.category.photo",
            bodyKey: "onboarding.reportPage.photo.body",
            tint: Color(red: 0.97, green: 0.45, blue: 0.64),
            yoursWidth: 42,
            idealWidth: 39,
            hiddenMetricCount: 7,
            classificationKey: "onboarding.reportScore.classification.photo",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "best-pick", iconName: "checkmark.seal.fill", titleKey: "onboarding.reportScore.photo.rowOne", tint: Color(red: 0.97, green: 0.45, blue: 0.64), delta: 3),
                OnboardingReportScoreMetricTemplate(id: "expression", iconName: "face.smiling", titleKey: "onboarding.reportScore.photo.rowTwo", tint: FXTheme.cyan, delta: 1),
                OnboardingReportScoreMetricTemplate(id: "lighting", iconName: "sun.max.fill", titleKey: "onboarding.reportScore.photo.rowThree", tint: Color(red: 1.00, green: 0.75, blue: 0.36), delta: -2),
                OnboardingReportScoreMetricTemplate(id: "crop", iconName: "crop", titleKey: "onboarding.reportScore.photo.rowFour", tint: Color(red: 0.95, green: 0.62, blue: 0.74), delta: 2)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "best-pick", iconName: "camera.fill", titleKey: "onboarding.reportPage.photo.metricOne", bodyKey: "onboarding.reportPage.photo.metricOneBody", tint: Color(red: 0.97, green: 0.45, blue: 0.64), valueWidth: 46),
                OnboardingReportPreviewMetric(id: "crop-lighting", iconName: "crop", titleKey: "onboarding.reportPage.photo.metricTwo", bodyKey: "onboarding.reportPage.photo.metricTwoBody", tint: Color(red: 0.95, green: 0.62, blue: 0.74), valueWidth: 40)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "best-angle-finder",
            iconName: "viewfinder",
            titleKey: "analysis.mode.bestAngleFinder",
            categoryKey: "onboarding.reportReady.category.angle",
            bodyKey: "onboarding.reportPage.angle.body",
            tint: Color(red: 1.00, green: 0.75, blue: 0.36),
            yoursWidth: 52,
            idealWidth: 38,
            hiddenMetricCount: 6,
            classificationKey: "onboarding.reportScore.classification.angle",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "angle", iconName: "viewfinder", titleKey: "onboarding.reportScore.angle.rowOne", tint: Color(red: 1.00, green: 0.75, blue: 0.36), delta: 4),
                OnboardingReportScoreMetricTemplate(id: "camera-height", iconName: "camera.metering.center.weighted", titleKey: "onboarding.reportScore.angle.rowTwo", tint: Color(red: 0.94, green: 0.64, blue: 0.26), delta: 1),
                OnboardingReportScoreMetricTemplate(id: "face-turn", iconName: "rotate.3d", titleKey: "onboarding.reportScore.angle.rowThree", tint: FXTheme.cyan, delta: -1),
                OnboardingReportScoreMetricTemplate(id: "jawline", iconName: "triangle", titleKey: "onboarding.reportScore.angle.rowFour", tint: Color(red: 0.78, green: 0.68, blue: 1.00), delta: 2)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "angle-confidence", iconName: "viewfinder", titleKey: "onboarding.reportPage.angle.metricOne", bodyKey: "onboarding.reportPage.angle.metricOneBody", tint: Color(red: 1.00, green: 0.75, blue: 0.36), valueWidth: 52),
                OnboardingReportPreviewMetric(id: "camera-height", iconName: "camera.metering.center.weighted", titleKey: "onboarding.reportPage.angle.metricTwo", bodyKey: "onboarding.reportPage.angle.metricTwoBody", tint: Color(red: 0.94, green: 0.64, blue: 0.26), valueWidth: 44)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "dating-profile-score",
            iconName: "heart.fill",
            titleKey: "analysis.mode.datingProfileScore",
            categoryKey: "onboarding.reportReady.category.profile",
            bodyKey: "onboarding.reportPage.dating.body",
            tint: Color(red: 1.00, green: 0.36, blue: 0.54),
            yoursWidth: 47,
            idealWidth: 37,
            hiddenMetricCount: 8,
            classificationKey: "onboarding.reportScore.classification.dating",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "first-impression", iconName: "heart.text.square.fill", titleKey: "onboarding.reportScore.dating.rowOne", tint: Color(red: 1.00, green: 0.36, blue: 0.54), delta: 3),
                OnboardingReportScoreMetricTemplate(id: "trust", iconName: "checkmark.shield.fill", titleKey: "onboarding.reportScore.dating.rowTwo", tint: Color(red: 0.62, green: 0.80, blue: 0.78), delta: 1),
                OnboardingReportScoreMetricTemplate(id: "approachability", iconName: "person.2.fill", titleKey: "onboarding.reportScore.dating.rowThree", tint: Color(red: 0.96, green: 0.54, blue: 0.62), delta: 4),
                OnboardingReportScoreMetricTemplate(id: "clarity", iconName: "camera.fill", titleKey: "onboarding.reportScore.dating.rowFour", tint: FXTheme.cyan, delta: -2)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "first-impression", iconName: "heart.text.square.fill", titleKey: "onboarding.reportPage.dating.metricOne", bodyKey: "onboarding.reportPage.dating.metricOneBody", tint: Color(red: 1.00, green: 0.36, blue: 0.54), valueWidth: 48),
                OnboardingReportPreviewMetric(id: "approachability", iconName: "person.2.fill", titleKey: "onboarding.reportPage.dating.metricTwo", bodyKey: "onboarding.reportPage.dating.metricTwoBody", tint: Color(red: 0.96, green: 0.54, blue: 0.62), valueWidth: 42)
            ]
        ),
        OnboardingReportPreviewPage(
            id: "instagram-profile-score",
            iconName: "square.grid.3x3.fill",
            titleKey: "analysis.mode.instagramProfileScore",
            categoryKey: "onboarding.reportReady.category.social",
            bodyKey: "onboarding.reportPage.instagram.body",
            tint: Color(red: 0.58, green: 0.72, blue: 1.00),
            yoursWidth: 50,
            idealWidth: 39,
            hiddenMetricCount: 7,
            classificationKey: "onboarding.reportScore.classification.instagram",
            scoreMetrics: [
                OnboardingReportScoreMetricTemplate(id: "thumbnail", iconName: "person.crop.square.fill", titleKey: "onboarding.reportScore.instagram.rowOne", tint: Color(red: 0.58, green: 0.72, blue: 1.00), delta: 3),
                OnboardingReportScoreMetricTemplate(id: "feed-fit", iconName: "square.grid.3x3.fill", titleKey: "onboarding.reportScore.instagram.rowTwo", tint: Color(red: 0.54, green: 0.82, blue: 0.96), delta: 2),
                OnboardingReportScoreMetricTemplate(id: "contrast", iconName: "circle.lefthalf.filled", titleKey: "onboarding.reportScore.instagram.rowThree", tint: Color(red: 1.00, green: 0.75, blue: 0.36), delta: -1),
                OnboardingReportScoreMetricTemplate(id: "presence", iconName: "sparkles", titleKey: "onboarding.reportScore.instagram.rowFour", tint: FXTheme.green, delta: 4)
            ],
            lockedMetrics: [
                OnboardingReportPreviewMetric(id: "feed-fit", iconName: "square.grid.3x3.fill", titleKey: "onboarding.reportPage.instagram.metricOne", bodyKey: "onboarding.reportPage.instagram.metricOneBody", tint: Color(red: 0.58, green: 0.72, blue: 1.00), valueWidth: 50),
                OnboardingReportPreviewMetric(id: "profile-crop", iconName: "person.crop.square.fill", titleKey: "onboarding.reportPage.instagram.metricTwo", bodyKey: "onboarding.reportPage.instagram.metricTwoBody", tint: Color(red: 0.54, green: 0.82, blue: 0.96), valueWidth: 44)
            ]
        )
    ]
}

private enum OnboardingReportPreviewSignalEngine {
    static func insight(
        for page: OnboardingReportPreviewPage,
        selectedGoalIDs: Set<String>,
        selectedGenderID: String?,
        selectedAge: Int?,
        image: UIImage?
    ) -> OnboardingReportPreviewInsight {
        let base = baseScore(for: page.id)
        let goal = goalBoost(for: page.id, goals: selectedGoalIDs)
        let image = imageSignal(for: image)
        let age = ageSignal(for: page.id, age: selectedAge)
        let noise = stableNoise("\(page.id)|\(selectedGoalIDs.sorted().joined(separator: ","))|\(selectedGenderID ?? "unknown")|\(selectedAge.map(String.init) ?? "unknown")")
        let score = clamp(base + goal + image + age + noise, min: 58, max: 94)

        let rows = page.scoreMetrics.map { metric in
            let rowNoise = stableNoise("\(page.id)|\(metric.id)|\(score)|\(selectedGoalIDs.count)")
            let value = clamp(score + metric.delta + rowNoise, min: 48, max: 97)
            return (
                value,
                OnboardingReportScoreMetric(
                    id: metric.id,
                    iconName: metric.iconName,
                    titleKey: metric.titleKey,
                    bodyKey: bodyKey(for: metric.id),
                    tint: metric.tint,
                    signalKey: signalKey(for: value)
                )
            )
        }
        .sorted { lhs, rhs in lhs.0 > rhs.0 }
        .map { $0.1 }

        return OnboardingReportPreviewInsight(
            pageID: page.id,
            classificationKey: page.classificationKey,
            rows: Array(rows.prefix(3))
        )
    }

    private static func baseScore(for pageID: String) -> Int {
        switch pageID {
        case "proportions": 67
        case "aesthetics": 69
        case "glow-up-coach": 72
        case "look-archetype": 70
        case "best-photo-selector": 66
        case "best-angle-finder": 68
        case "dating-profile-score": 65
        case "instagram-profile-score": 66
        default: 66
        }
    }

    private static func goalBoost(for pageID: String, goals: Set<String>) -> Int {
        let weights: [String: [String: Int]] = [
            "symmetry": ["proportions": 5, "aesthetics": 4, "best-angle-finder": 2],
            "jawline": ["aesthetics": 3, "glow-up-coach": 4, "best-angle-finder": 5],
            "skin": ["glow-up-coach": 5, "aesthetics": 2, "best-photo-selector": 3],
            "proportions": ["proportions": 6, "aesthetics": 3, "look-archetype": 1],
            "progress": ["glow-up-coach": 6, "aesthetics": 2, "instagram-profile-score": 1],
            "photos": ["best-photo-selector": 6, "best-angle-finder": 4, "instagram-profile-score": 3, "dating-profile-score": 2],
            "profile": ["dating-profile-score": 6, "instagram-profile-score": 5, "best-photo-selector": 3, "look-archetype": 2]
        ]

        let raw = goals.reduce(0) { partial, goal in
            partial + (weights[goal]?[pageID] ?? 0)
        }
        return min(raw, 12)
    }

    private static func imageSignal(for image: UIImage?) -> Int {
        guard let image else { return -6 }
        let pixelWidth = max(1, Int(image.size.width * image.scale))
        let pixelHeight = max(1, Int(image.size.height * image.scale))
        let shortEdge = min(pixelWidth, pixelHeight)
        let detailScore = min(5, max(1, shortEdge / 240))
        let aspect = image.size.width / max(image.size.height, 1)
        let portraitFit = 1 - min(abs(aspect - 0.75), 0.55) / 0.55
        return 4 + detailScore + Int((portraitFit * 4).rounded())
    }

    private static func ageSignal(for pageID: String, age: Int?) -> Int {
        guard let age else { return 0 }
        let ageRangeID = ageRangeID(for: age)
        switch (pageID, ageRangeID) {
        case ("dating-profile-score", "18-24"), ("instagram-profile-score", "18-24"):
            return 2
        case ("best-photo-selector", "25-34"), ("best-angle-finder", "25-34"):
            return 2
        case ("glow-up-coach", "35-44"), ("aesthetics", "35-44"):
            return 2
        case ("glow-up-coach", "45+"):
            return 3
        default:
            return 1
        }
    }

    private static func ageRangeID(for age: Int) -> String {
        switch age {
        case ..<25:
            "18-24"
        case 25..<35:
            "25-34"
        case 35..<45:
            "35-44"
        default:
            "45+"
        }
    }

    private static func stableNoise(_ value: String) -> Int {
        var hash: UInt32 = 2_166_136_261
        for byte in value.utf8 {
            hash ^= UInt32(byte)
            hash = hash &* 16_777_619
        }
        return Int(hash % 9) - 4
    }

    private static func clamp(_ value: Int, min minimum: Int, max maximum: Int) -> Int {
        Swift.max(minimum, Swift.min(maximum, value))
    }

    private static func signalKey(for value: Int) -> LocalizedStringKey {
        switch value {
        case 82...:
            return "onboarding.reportSignal.high"
        case 70..<82:
            return "onboarding.reportSignal.medium"
        default:
            return "onboarding.reportSignal.review"
        }
    }

    private static func bodyKey(for metricID: String) -> LocalizedStringKey {
        switch metricID {
        case "facial-index":
            return "onboarding.reportInsight.facial-index.body"
        case "thirds":
            return "onboarding.reportInsight.thirds.body"
        case "symmetry-axis":
            return "onboarding.reportInsight.symmetry-axis.body"
        case "jaw-relation":
            return "onboarding.reportInsight.jaw-relation.body"
        case "harmony":
            return "onboarding.reportInsight.harmony.body"
        case "presence":
            return "onboarding.reportInsight.presence.body"
        case "feature-balance":
            return "onboarding.reportInsight.feature-balance.body"
        case "definition":
            return "onboarding.reportInsight.definition.body"
        case "priority":
            return "onboarding.reportInsight.priority.body"
        case "skin-light":
            return "onboarding.reportInsight.skin-light.body"
        case "hair-frame":
            return "onboarding.reportInsight.hair-frame.body"
        case "photo-lift":
            return "onboarding.reportInsight.photo-lift.body"
        case "match":
            return "onboarding.reportInsight.match.body"
        case "style":
            return "onboarding.reportInsight.style.body"
        case "mood":
            return "onboarding.reportInsight.mood.body"
        case "signature":
            return "onboarding.reportInsight.signature.body"
        case "best-pick":
            return "onboarding.reportInsight.best-pick.body"
        case "expression":
            return "onboarding.reportInsight.expression.body"
        case "lighting":
            return "onboarding.reportInsight.lighting.body"
        case "crop":
            return "onboarding.reportInsight.crop.body"
        case "angle":
            return "onboarding.reportInsight.angle.body"
        case "camera-height":
            return "onboarding.reportInsight.camera-height.body"
        case "face-turn":
            return "onboarding.reportInsight.face-turn.body"
        case "jawline":
            return "onboarding.reportInsight.jawline.body"
        case "first-impression":
            return "onboarding.reportInsight.first-impression.body"
        case "trust":
            return "onboarding.reportInsight.trust.body"
        case "approachability":
            return "onboarding.reportInsight.approachability.body"
        case "clarity":
            return "onboarding.reportInsight.clarity.body"
        case "thumbnail":
            return "onboarding.reportInsight.thumbnail.body"
        case "feed-fit":
            return "onboarding.reportInsight.feed-fit.body"
        case "contrast":
            return "onboarding.reportInsight.contrast.body"
        default:
            return "onboarding.reportInsight.default.body"
        }
    }
}

private enum OnboardingReportCopy {
    static func readyTitleKey(for goals: Set<String>) -> LocalizedStringKey {
        if goals.contains("photos") || goals.contains("profile") {
            return "onboarding.reportReady.title.profile"
        }
        if goals.contains("skin") || goals.contains("jawline") || goals.contains("symmetry") || goals.contains("proportions") {
            return "onboarding.reportReady.title.face"
        }
        return "onboarding.reportReady.title.default"
    }

    static func reportPlanTitleKey(for goals: Set<String>) -> LocalizedStringKey {
        if goals.contains("photos") || goals.contains("profile") {
            return "onboarding.reportPlan.title.profile"
        }
        if goals.contains("skin") || goals.contains("jawline") || goals.contains("symmetry") || goals.contains("proportions") {
            return "onboarding.reportPlan.title.face"
        }
        return "onboarding.reportPlan.title.default"
    }

    static func paywallTitleKey(for goals: Set<String>) -> LocalizedStringKey {
        if goals.contains("photos") || goals.contains("profile") {
            return "onboarding.paywall.title.profile"
        }
        if goals.contains("skin") || goals.contains("jawline") || goals.contains("symmetry") || goals.contains("proportions") {
            return "onboarding.paywall.title.face"
        }
        return "onboarding.paywall.title.default"
    }

    static func analysisStartTitleKey(for goals: Set<String>) -> LocalizedStringKey {
        if goals.contains("photos") || goals.contains("profile") {
            return "onboarding.analysisStart.title.profile"
        }
        if goals.contains("skin") || goals.contains("jawline") || goals.contains("symmetry") || goals.contains("proportions") {
            return "onboarding.analysisStart.title.face"
        }
        return "onboarding.analysisStart.title.default"
    }
}

private struct OnboardingReportPillarRow: View {
    let pillar: OnboardingReportPillar

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            ZStack {
                Circle()
                    .fill(pillar.tint.opacity(0.18))
                    .frame(width: 44, height: 44)

                Image(systemName: pillar.iconName)
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(pillar.tint)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(pillar.titleKey)
                    .font(.system(size: 17, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Text(pillar.bodyKey)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(14)
        .background(FXTheme.card.opacity(0.94), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct OnboardingReportModuleChip: View {
    let module: OnboardingReportModule

    var body: some View {
        HStack(spacing: 9) {
            Image(systemName: module.iconName)
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(module.tint)
                .frame(width: 18)

            Text(module.titleKey)
                .font(.system(size: 12, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(2)
                .minimumScaleFactor(0.78)

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 11)
        .frame(height: 46)
        .background(FXTheme.glassFill, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(module.tint.opacity(0.22), lineWidth: 1)
        )
    }
}

private struct OnboardingPremiumReportPreview: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    let image: UIImage?
    let selectedGoalIDs: Set<String>
    let selectedGenderID: String?
    let selectedAge: Int?
    let animate: Bool

    @State private var selectedPreviewIndex = 0

    private var pages: [OnboardingReportPreviewPage] {
        OnboardingReportPreviewContent.pages
    }

    private var selectedPage: OnboardingReportPreviewPage {
        pages[min(selectedPreviewIndex, max(pages.count - 1, 0))]
    }

    private var previewInsight: OnboardingReportPreviewInsight {
        OnboardingReportPreviewSignalEngine.insight(
            for: selectedPage,
            selectedGoalIDs: selectedGoalIDs,
            selectedGenderID: selectedGenderID,
            selectedAge: selectedAge,
            image: image
        )
    }

    private var lowerDeckAnimation: Animation {
        reduceMotion ? .linear(duration: 0.01) : .spring(response: 0.52, dampingFraction: 0.90, blendDuration: 0.10)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("onboarding.reportReady.previewEyebrow")
                        .font(.system(size: 11, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)
                        .tracking(0.8)

                    Text("onboarding.reportReady.previewTitle")
                        .font(.system(size: 17, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                }

                Spacer(minLength: 12)

                HStack(spacing: 6) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 10, weight: .heavy))
                    Text("onboarding.paywall.preview.locked")
                        .font(.system(size: 11, weight: .heavy))
                }
                .foregroundStyle(Color.black.opacity(0.86))
                .padding(.horizontal, 10)
                .frame(height: 27)
                .background(FXTheme.cyan, in: Capsule())
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)

            OnboardingReportScanStage(image: image, animate: animate)
                .padding(.top, 14)

            OnboardingReportMeasurementPanel(
                pages: pages,
                selectedIndex: $selectedPreviewIndex
            )
                .padding(.horizontal, 12)
                .padding(.top, 12)

            ZStack {
                OnboardingReportInsightDeck(insight: previewInsight)
                    .id(previewInsight.pageID)
                    .transition(
                        .asymmetric(
                            insertion: .opacity
                                .combined(with: .scale(scale: 0.985, anchor: .top))
                                .combined(with: .offset(y: 10)),
                            removal: .opacity
                                .combined(with: .scale(scale: 0.995, anchor: .top))
                                .combined(with: .offset(y: -8))
                        )
                    )
            }
            .animation(lowerDeckAnimation, value: previewInsight.pageID)
            .padding(.horizontal, 12)
            .padding(.top, 12)
            .padding(.bottom, 12)
        }
        .background(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.070, green: 0.073, blue: 0.079),
                            Color(red: 0.044, green: 0.046, blue: 0.052)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(
                    LinearGradient(
                        colors: [Color.white.opacity(0.18), Color.white.opacity(0.04)],
                        startPoint: .top,
                        endPoint: .bottom
                    ),
                    lineWidth: 1
                )
        )
        .shadow(color: Color.black.opacity(0.38), radius: 28, y: 18)
    }
}

private struct OnboardingReportScanStage: View {
    let image: UIImage?
    let animate: Bool

    var body: some View {
        VStack(spacing: 12) {
            GeometryReader { proxy in
                ZStack {
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .fill(Color.white.opacity(0.025))

                    VStack(spacing: 12) {
                        ZStack {
                            if let image {
                                Image(uiImage: image)
                                    .resizable()
                                    .scaledToFill()
                                    .frame(width: 148, height: 176)
                                    .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
                                    .saturation(0.72)
                                    .contrast(1.08)
                                    .overlay(Color.black.opacity(0.26))
                            } else {
                                OnboardingFaceMeshPreview()
                                    .frame(width: 148, height: 176)
                                    .scaleEffect(animate ? 1.02 : 0.98)
                            }
                        }
                        .frame(width: proxy.size.width, height: 180)

                        HStack(spacing: 8) {
                            Image(systemName: "hand.draw.fill")
                                .font(.system(size: 12, weight: .heavy))
                            Text("onboarding.reportReady.scanHint")
                                .font(.system(size: 12, weight: .heavy))
                        }
                        .foregroundStyle(FXTheme.textMuted)
                    }
                }
            }
            .frame(height: 232)

            OnboardingReportProgressStrip(animate: animate)
                .padding(.horizontal, 16)
        }
    }
}

private struct OnboardingReportProgressStrip: View {
    let animate: Bool

    var body: some View {
        VStack(spacing: 10) {
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.10))

                    Capsule()
                        .fill(FXTheme.cyan)
                        .frame(width: proxy.size.width * (animate ? 0.82 : 0.34))
                }
            }
            .frame(height: 6)

            HStack {
                Text("onboarding.reportReady.yourScore")
                    .font(.system(size: 11, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)

                Spacer()

                Text("82")
                    .font(.system(size: 11, weight: .heavy))
                    .foregroundStyle(FXTheme.textSecondary)
            }
        }
    }
}

private struct OnboardingReportMeasurementPanel: View {
    let pages: [OnboardingReportPreviewPage]
    @Binding var selectedIndex: Int

    var body: some View {
        VStack(spacing: 0) {
            OnboardingReportResultDots(pages: pages, selectedIndex: $selectedIndex)
                .frame(height: 30)

            HStack(spacing: 5) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 9, weight: .black))
                Text("onboarding.reportReady.swipeHint")
                    .font(.system(size: 11, weight: .heavy))
                Image(systemName: "chevron.right")
                    .font(.system(size: 9, weight: .black))
            }
            .foregroundStyle(FXTheme.textMuted)
            .frame(height: 22)
            .padding(.bottom, 2)

            TabView(selection: $selectedIndex) {
                ForEach(Array(pages.enumerated()), id: \.element.id) { index, page in
                    OnboardingReportMeasurementPage(page: page)
                        .tag(index)
                        .padding(.horizontal, 1)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .frame(height: 260)
        }
        .padding(10)
        .background(Color.white.opacity(0.045), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(Color.white.opacity(0.075), lineWidth: 1)
        )
    }
}

private struct OnboardingReportResultDots: View {
    let pages: [OnboardingReportPreviewPage]
    @Binding var selectedIndex: Int

    var body: some View {
        HStack(spacing: 9) {
            ForEach(Array(pages.enumerated()), id: \.element.id) { index, page in
                Button {
                    withAnimation(.smooth(duration: 0.18)) {
                        selectedIndex = index
                    }
                } label: {
                    Circle()
                        .fill(index == selectedIndex ? page.tint : Color.white.opacity(0.34))
                        .frame(width: index == selectedIndex ? 13 : 8, height: index == selectedIndex ? 13 : 8)
                        .overlay(
                            Circle()
                                .stroke(Color.white.opacity(index == selectedIndex ? 0.18 : 0.10), lineWidth: 1)
                        )
                        .contentShape(Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text(String(format: String(localized: "onboarding.reportReady.pageIndicatorAccessibilityFormat"), index + 1, pages.count)))
            }
        }
    }
}

private struct OnboardingReportMeasurementPage: View {
    let page: OnboardingReportPreviewPage

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 13) {
                Image(systemName: page.iconName)
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(page.tint)
                    .frame(width: 32, height: 32)
                    .background(page.tint.opacity(0.15), in: Circle())

                VStack(alignment: .leading, spacing: 5) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(page.categoryKey)
                            .font(.system(size: 10, weight: .heavy))
                            .foregroundStyle(page.tint)
                            .lineLimit(1)
                            .minimumScaleFactor(0.70)

                        Text(page.titleKey)
                            .font(.system(size: 17, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.62)
                    }

                    Text(page.bodyKey)
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineLimit(2)
                        .minimumScaleFactor(0.74)
                }

                Spacer(minLength: 8)

                OnboardingPremiumLockBadge(tint: page.tint)
            }
            .padding(.horizontal, 14)
            .frame(height: 88)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(page.tint.opacity(0.105))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(Color.white.opacity(0.055), lineWidth: 1)
            )

            ForEach(Array(page.lockedMetrics.enumerated()), id: \.element.id) { _, metric in
                Divider()
                    .overlay(Color.white.opacity(0.08))
                    .padding(.leading, 14)

                OnboardingLockedMetricRow(
                    iconName: metric.iconName,
                    titleKey: metric.titleKey,
                    bodyKey: metric.bodyKey,
                    tint: metric.tint
                )
            }

            HStack(spacing: 8) {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(page.tint)

                Text("+\(page.hiddenMetricCount)")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Text("onboarding.reportReady.moreMetrics")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .frame(height: 36)
            .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .padding(.top, 10)
        }
    }
}

private struct OnboardingPremiumLockBadge: View {
    let tint: Color

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "lock.fill")
                .font(.system(size: 10, weight: .heavy))

            Text("onboarding.paywall.preview.locked")
                .font(.system(size: 10, weight: .heavy))
                .lineLimit(1)
        }
        .foregroundStyle(FXTheme.textPrimary.opacity(0.88))
        .padding(.horizontal, 10)
        .frame(height: 30)
        .background(
            LinearGradient(
                colors: [
                    tint.opacity(0.18),
                    Color.white.opacity(0.055),
                    Color.black.opacity(0.10)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 11, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 11, style: .continuous)
                .stroke(
                    LinearGradient(
                        colors: [Color.white.opacity(0.18), tint.opacity(0.22), Color.white.opacity(0.055)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1
                )
        )
        .shadow(color: tint.opacity(0.12), radius: 12, x: 0, y: 8)
    }
}

private struct OnboardingLockedMetricRow: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color

    var body: some View {
        HStack(spacing: 13) {
            Image(systemName: iconName)
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(tint)
                .frame(width: 30, height: 30)
                .background(tint.opacity(0.14), in: Circle())

            VStack(alignment: .leading, spacing: 3) {
                Text(titleKey)
                    .font(.system(size: 14, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary.opacity(0.82))
                    .lineLimit(1)
                    .minimumScaleFactor(0.74)

                Text(bodyKey)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }

            Spacer(minLength: 8)

            OnboardingPremiumLockBadge(tint: tint)
        }
        .frame(height: 58)
        .padding(.horizontal, 10)
    }
}

private struct OnboardingReportInsightDeck: View {
    let insight: OnboardingReportPreviewInsight

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 7) {
                    Image(systemName: "doc.text.magnifyingglass")
                        .font(.system(size: 12, weight: .heavy))
                        .foregroundStyle(FXTheme.cyan)

                    Text("onboarding.reportReady.readingLabel")
                        .font(.system(size: 11, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)
                }

                Text(insight.classificationKey)
                    .font(.system(size: 19, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.76)
            }

            VStack(spacing: 9) {
                ForEach(insight.rows) { row in
                    OnboardingReportInsightRow(row: row)
                }
            }

            HStack(spacing: 8) {
                Image(systemName: "lock.fill")
                    .font(.system(size: 10, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)

                Text("onboarding.reportReady.fullExplanationLocked")
                    .font(.system(size: 11, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.76)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .frame(height: 34)
            .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .padding(15)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(Color.white.opacity(0.045))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.white.opacity(0.075), lineWidth: 1)
        )
    }
}

private struct OnboardingReportInsightRow: View {
    let row: OnboardingReportScoreMetric

    var body: some View {
        HStack(alignment: .top, spacing: 11) {
            Image(systemName: row.iconName)
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(row.tint)
                .frame(width: 30, height: 30)
                .background(row.tint.opacity(0.13), in: RoundedRectangle(cornerRadius: 9, style: .continuous))

            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(row.titleKey)
                        .font(.system(size: 13, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary.opacity(0.88))
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)

                    Spacer(minLength: 4)

                    Text(row.signalKey)
                        .font(.system(size: 9, weight: .heavy))
                        .foregroundStyle(row.tint)
                        .lineLimit(1)
                        .padding(.horizontal, 7)
                        .frame(height: 18)
                        .background(row.tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                }

                Text(row.bodyKey)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(2)
                    .minimumScaleFactor(0.74)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 2)
    }
}

private struct OnboardingReportHeroCard: View {
    let image: UIImage?
    let animate: Bool

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .fill(FXTheme.card.opacity(0.96))
                .overlay(
                    RoundedRectangle(cornerRadius: 26, style: .continuous)
                        .stroke(Color.white.opacity(0.08), lineWidth: 1)
                )

            HStack(spacing: 18) {
                ZStack {
                    Circle()
                        .fill(
                            RadialGradient(
                                colors: [FXTheme.cyan.opacity(0.28), Color.clear],
                                center: .center,
                                startRadius: 12,
                                endRadius: 78
                            )
                        )
                        .frame(width: 116, height: 116)

                    if let image {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFill()
                            .frame(width: 92, height: 116)
                            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                    } else {
                        OnboardingFaceMeshPreview()
                            .frame(width: 104, height: 118)
                    }
                }

                VStack(alignment: .leading, spacing: 12) {
                    OnboardingMiniMetric(titleKey: "onboarding.reportReady.metric.structure", value: "82", tint: FXTheme.cyan, progress: animate ? 0.82 : 0.24)
                    OnboardingMiniMetric(titleKey: "onboarding.reportReady.metric.photo", value: "74", tint: Color(red: 0.97, green: 0.45, blue: 0.64), progress: animate ? 0.74 : 0.22)
                    OnboardingMiniMetric(titleKey: "onboarding.reportReady.metric.plan", value: "91", tint: FXTheme.green, progress: animate ? 0.91 : 0.24)
                }
            }
            .padding(18)
        }
        .frame(height: 162)
    }
}

private struct OnboardingFaceMeshPreview: View {
    var body: some View {
        ZStack {
            FaceOutlineShape()
                .fill(Color.white.opacity(0.16))
                .frame(width: 90, height: 116)

            FaceOutlineShape()
                .stroke(Color.white.opacity(0.34), lineWidth: 1)
                .frame(width: 90, height: 116)

            VStack(spacing: 11) {
                HStack(spacing: 22) {
                    Capsule().fill(Color.black).frame(width: 22, height: 6)
                    Capsule().fill(Color.black).frame(width: 22, height: 6)
                }
                Capsule().fill(Color.black.opacity(0.55)).frame(width: 18, height: 5)
                Capsule().fill(Color.black.opacity(0.55)).frame(width: 34, height: 4)
            }
            .offset(y: 4)
        }
    }
}

private struct FaceOutlineShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY + 8))
        path.addCurve(
            to: CGPoint(x: rect.minX + 12, y: rect.midY + 22),
            control1: CGPoint(x: rect.minX + 32, y: rect.minY + 18),
            control2: CGPoint(x: rect.minX + 4, y: rect.midY - 48)
        )
        path.addCurve(
            to: CGPoint(x: rect.midX, y: rect.maxY - 8),
            control1: CGPoint(x: rect.minX + 20, y: rect.maxY - 42),
            control2: CGPoint(x: rect.midX - 48, y: rect.maxY)
        )
        path.addCurve(
            to: CGPoint(x: rect.maxX - 12, y: rect.midY + 22),
            control1: CGPoint(x: rect.midX + 48, y: rect.maxY),
            control2: CGPoint(x: rect.maxX - 20, y: rect.maxY - 42)
        )
        path.addCurve(
            to: CGPoint(x: rect.midX, y: rect.minY + 8),
            control1: CGPoint(x: rect.maxX - 4, y: rect.midY - 48),
            control2: CGPoint(x: rect.maxX - 32, y: rect.minY + 18)
        )
        return path
    }
}

private struct OnboardingMiniMetric: View {
    let titleKey: LocalizedStringKey
    let value: String
    let tint: Color
    let progress: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text(titleKey)
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Spacer(minLength: 6)

                Text(value)
                    .font(.system(size: 15, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
            }

            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.12))
                    Capsule()
                        .fill(tint)
                        .frame(width: proxy.size.width * progress.clampedToUnit())
                }
            }
            .frame(height: 7)
        }
    }
}

private struct OnboardingReportScorePreview: View {
    private let rows: [(icon: String, title: LocalizedStringKey, value: String, progress: Double, tint: Color)] = [
        ("eye.fill", "onboarding.reportReady.score.structure", "82", 0.82, FXTheme.cyan),
        ("sparkles", "onboarding.reportReady.score.glow", "91", 0.91, FXTheme.green),
        ("camera.fill", "onboarding.reportReady.score.profile", "74", 0.74, Color(red: 0.97, green: 0.45, blue: 0.64))
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("onboarding.reportReady.previewTitle")
                        .font(.system(size: 14, weight: .heavy))
                        .foregroundStyle(FXTheme.textSecondary)

                    Text("onboarding.reportReady.classification")
                        .font(.system(size: 24, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                }

                Spacer(minLength: 10)

                VStack(alignment: .trailing, spacing: 2) {
                    Text("onboarding.reportReady.scoreLabel")
                        .font(.system(size: 12, weight: .heavy))
                        .foregroundStyle(FXTheme.textSecondary)

                    Text("82")
                        .font(.system(size: 42, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                }
            }

            VStack(spacing: 10) {
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    HStack(spacing: 12) {
                        Image(systemName: row.icon)
                            .font(.system(size: 16, weight: .heavy))
                            .foregroundStyle(row.tint)
                            .frame(width: 24)

                        Text(row.title)
                            .font(.system(size: 14, weight: .heavy))
                            .foregroundStyle(FXTheme.textSecondary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.76)

                        GeometryReader { proxy in
                            ZStack(alignment: .leading) {
                                Capsule().fill(Color.white.opacity(0.11))
                                Capsule()
                                    .fill(row.tint)
                                    .frame(width: proxy.size.width * row.progress.clampedToUnit())
                            }
                        }
                        .frame(height: 7)

                        Text(row.value)
                            .font(.system(size: 14, weight: .heavy))
                            .foregroundStyle(FXTheme.textPrimary)
                            .frame(width: 28, alignment: .trailing)
                    }
                }
            }
        }
        .padding(16)
        .background(FXTheme.card.opacity(0.96), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct OnboardingLockedInsightCard: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: iconName)
                .font(.system(size: 20, weight: .heavy))
                .foregroundStyle(tint)
                .frame(width: 42, height: 42)
                .background(tint.opacity(0.16), in: Circle())

            VStack(alignment: .leading, spacing: 5) {
                Text(titleKey)
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.74)

                Text(bodyKey)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.76)
            }

            Spacer(minLength: 0)

            Image(systemName: "lock.fill")
                .font(.system(size: 15, weight: .heavy))
                .foregroundStyle(FXTheme.textMuted)
        }
        .padding(15)
        .background(FXTheme.glassFill, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct OnboardingPaywallBenefit: Identifiable {
    let id: String
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey
    let tint: Color

    @MainActor
    static let all: [OnboardingPaywallBenefit] = [
        OnboardingPaywallBenefit(
            id: "full-report",
            iconName: "chart.bar.doc.horizontal.fill",
            titleKey: "onboarding.paywall.benefit.report.title",
            bodyKey: "onboarding.paywall.benefit.report.body",
            tint: FXTheme.cyan
        ),
        OnboardingPaywallBenefit(
            id: "coach",
            iconName: "sparkles",
            titleKey: "onboarding.paywall.benefit.coach.title",
            bodyKey: "onboarding.paywall.benefit.coach.body",
            tint: FXTheme.green
        ),
        OnboardingPaywallBenefit(
            id: "profile",
            iconName: "camera.filters",
            titleKey: "onboarding.paywall.benefit.profile.title",
            bodyKey: "onboarding.paywall.benefit.profile.body",
            tint: Color(red: 0.97, green: 0.45, blue: 0.64)
        )
    ]
}

private struct OnboardingPaywallBenefitRow: View {
    let benefit: OnboardingPaywallBenefit

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: benefit.iconName)
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(benefit.tint)
                .frame(width: 38, height: 38)
                .background(benefit.tint.opacity(0.16), in: Circle())

            VStack(alignment: .leading, spacing: 4) {
                Text(benefit.titleKey)
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)

                Text(benefit.bodyKey)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.76)
            }

            Spacer(minLength: 0)
        }
    }
}

private struct OnboardingPaywallPreviewCard: View {
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text("onboarding.paywall.preview.title")
                    .font(.system(size: 17, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer()

                Text("onboarding.paywall.preview.locked")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(Color.black)
                    .padding(.horizontal, 10)
                    .frame(height: 25)
                    .background(FXTheme.cyan, in: Capsule())
            }

            ForEach(Array(OnboardingReportModule.all.prefix(4).enumerated()), id: \.element.id) { index, module in
                HStack(spacing: 12) {
                    Image(systemName: module.iconName)
                        .font(.system(size: 15, weight: .heavy))
                        .foregroundStyle(module.tint)
                        .frame(width: 28)

                    Text(module.titleKey)
                        .font(.system(size: 14, weight: .heavy))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.76)

                    Spacer(minLength: 10)

                    Capsule()
                        .fill(Color.white.opacity(0.14))
                        .frame(width: 88, height: 8)
                        .overlay(alignment: .leading) {
                            Capsule()
                                .fill(module.tint.opacity(0.9))
                                .frame(width: [64, 72, 80, 58][index], height: 8)
                                .blur(radius: 2.5)
                        }

                    Image(systemName: "lock.fill")
                        .font(.system(size: 12, weight: .heavy))
                        .foregroundStyle(FXTheme.textMuted)
                }
            }
        }
        .padding(16)
        .background(FXTheme.card.opacity(0.96), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct OnboardingPaywallPlanCard: View {
    var body: some View {
        VStack(spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("onboarding.paywall.plan.title")
                        .font(.system(size: 17, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)

                    Text("onboarding.paywall.plan.body")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                }

                Spacer(minLength: 12)

                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 24, weight: .heavy))
                    .foregroundStyle(FXTheme.cyan)
            }

            OnboardingLegalLinks()
        }
        .padding(16)
        .background(FXTheme.glassFill, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(FXTheme.cyan.opacity(0.24), lineWidth: 1.2)
        )
    }
}

private struct OnboardingLegalLinks: View {
    private let termsURL = URL(string: "https://skinny-look-a0c.notion.site/Terms-of-Use-367da865dff180bebffad4a6d5322a84?source=copy_link")!
    private let privacyURL = URL(string: "https://skinny-look-a0c.notion.site/Privacy-Policy-Facemaxx-367da865dff180b8a6cdecca53bcda69?source=copy_link")!

    var body: some View {
        VStack(spacing: 7) {
            Text("onboarding.auth.legal.prefix")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(FXTheme.textMuted)
                .multilineTextAlignment(.center)
                .lineSpacing(2)

            ViewThatFits(in: .horizontal) {
                legalLinkRow

                VStack(spacing: 5) {
                    Link("onboarding.auth.legal.terms", destination: termsURL)
                    Text("onboarding.auth.legal.and")
                        .foregroundStyle(FXTheme.textMuted)
                    Link("onboarding.auth.legal.privacy", destination: privacyURL)
                }
            }
            .font(.system(size: 12, weight: .heavy))
            .foregroundStyle(FXTheme.blue)
            .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .fixedSize(horizontal: false, vertical: true)
    }

    private var legalLinkRow: some View {
        HStack(spacing: 10) {
            Link("onboarding.auth.legal.terms", destination: termsURL)
            Text("onboarding.auth.legal.and")
                .foregroundStyle(FXTheme.textMuted)
            Link("onboarding.auth.legal.privacy", destination: privacyURL)
        }
        .lineLimit(1)
        .minimumScaleFactor(0.72)
    }
}

private struct OnboardingSelectableRow: View {
    let titleKey: LocalizedStringKey
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Text(titleKey)
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)

                Spacer(minLength: 12)

                Image(systemName: "checkmark")
                    .font(.system(size: 22, weight: .heavy))
                    .foregroundStyle(Color.white)
                    .opacity(isSelected ? 1 : 0)
                    .scaleEffect(isSelected ? 1 : 0.72)
            }
            .padding(.horizontal, 16)
            .frame(height: 54)
            .background(isSelected ? FXTheme.cardElevated : FXTheme.card.opacity(0.9), in: Capsule())
        }
        .buttonStyle(.plain)
    }
}

private struct OnboardingChoiceChip: View {
    let titleKey: LocalizedStringKey
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(titleKey)
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
                .padding(.horizontal, 20)
                .frame(height: 46)
                .background(isSelected ? FXTheme.glassFillElevated : FXTheme.card.opacity(0.9), in: Capsule())
                .overlay(
                    Capsule()
                        .stroke(isSelected ? FXTheme.selectedStroke : Color.clear, lineWidth: 1.4)
                )
        }
        .buttonStyle(.plain)
    }
}

private struct OnboardingStaggeredEntryModifier: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isVisible = false

    let index: Int

    func body(content: Content) -> some View {
        content
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 14)
            .scaleEffect(isVisible ? 1 : 0.97)
            .task(id: index) {
                if reduceMotion {
                    isVisible = true
                    return
                }

                isVisible = false
                try? await Task.sleep(nanoseconds: UInt64(index) * 70_000_000)
                guard !Task.isCancelled else { return }

                withAnimation(.smooth(duration: 0.42)) {
                    isVisible = true
                }
            }
            .onDisappear {
                isVisible = false
            }
    }
}

private extension View {
    func onboardingStaggeredEntry(index: Int) -> some View {
        modifier(OnboardingStaggeredEntryModifier(index: index))
    }
}

private extension Double {
    func clampedToUnit() -> Double {
        min(1, max(0, self))
    }
}

private struct StatusPill: View {
    let icon: String
    let titleKey: LocalizedStringKey

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(Color.white)

            Text(titleKey)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(FXTheme.textPrimary)
        }
        .padding(.horizontal, 14)
        .frame(height: 38)
        .background(FXTheme.pill, in: Capsule())
    }
}

private struct OnboardingFeatureRow: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    let bodyKey: LocalizedStringKey

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: iconName)
                .font(.system(size: 26, weight: .bold))
                .foregroundStyle(FXTheme.textPrimary)
                .frame(width: 42)

            VStack(alignment: .leading, spacing: 6) {
                Text(titleKey)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundStyle(FXTheme.textPrimary)

                Text(bodyKey)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
    }
}

private struct AnimatedScanGlyph: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var rotation = 0.0

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.white.opacity(0.18), lineWidth: 13)

            Circle()
                .trim(from: 0.08, to: 0.74)
                .stroke(Color.white, style: StrokeStyle(lineWidth: 13, lineCap: .round))
                .rotationEffect(.degrees(rotation))

            HStack(spacing: 26) {
                Circle()
                    .fill(Color.white)
                    .frame(width: 14, height: 14)
                Circle()
                    .fill(Color.white)
                    .frame(width: 14, height: 14)
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.linear(duration: 2.4).repeatForever(autoreverses: false)) {
                rotation = 360
            }
        }
    }
}

private struct OnboardingProgressBars: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var animate = false

    private let bars: [(key: LocalizedStringKey, height: CGFloat)] = [
        ("onboarding.progress.metric.symmetry", 122),
        ("onboarding.progress.metric.proportions", 122),
        ("onboarding.progress.metric.features", 62),
        ("onboarding.progress.metric.shape", 62),
        ("onboarding.progress.metric.quality", 62)
    ]

    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            ForEach(Array(bars.enumerated()), id: \.offset) { index, item in
                VStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [Color.white, Color.white.opacity(0.75)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        .frame(width: 48, height: animate ? item.height : 20)
                        .shadow(color: .white.opacity(0.24), radius: 14, y: 4)
                        .animation(
                            .spring(response: 0.56, dampingFraction: 0.72)
                                .delay(reduceMotion ? 0 : Double(index) * 0.08),
                            value: animate
                        )

                    Text(item.key)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                        .frame(width: 56)
                }
            }
        }
        .onAppear {
            animate = true
        }
    }
}

private struct FlowLayout: Layout {
    var spacing: CGFloat = 12
    var rowSpacing: CGFloat = 12

    func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) -> CGSize {
        let width = proposal.width ?? 0
        let rows = rows(in: width, subviews: subviews)
        let height = rows.reduce(CGFloat.zero) { partial, row in
            partial + row.height
        } + CGFloat(max(rows.count - 1, 0)) * rowSpacing
        return CGSize(width: width, height: height)
    }

    func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) {
        let rows = rows(in: bounds.width, subviews: subviews)
        var y = bounds.minY

        for row in rows {
            var x = bounds.minX
            for item in row.items {
                subviews[item.index].place(
                    at: CGPoint(x: x, y: y),
                    proposal: ProposedViewSize(item.size)
                )
                x += item.size.width + spacing
            }
            y += row.height + rowSpacing
        }
    }

    private func rows(in width: CGFloat, subviews: Subviews) -> [FlowRow] {
        var rows = [FlowRow]()
        var currentItems = [FlowItem]()
        var currentWidth: CGFloat = 0
        var currentHeight: CGFloat = 0

        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            let nextWidth = currentItems.isEmpty ? size.width : currentWidth + spacing + size.width

            if nextWidth > width, !currentItems.isEmpty {
                rows.append(FlowRow(items: currentItems, height: currentHeight))
                currentItems = [FlowItem(index: index, size: size)]
                currentWidth = size.width
                currentHeight = size.height
            } else {
                currentItems.append(FlowItem(index: index, size: size))
                currentWidth = nextWidth
                currentHeight = max(currentHeight, size.height)
            }
        }

        if !currentItems.isEmpty {
            rows.append(FlowRow(items: currentItems, height: currentHeight))
        }

        return rows
    }

    private struct FlowItem {
        let index: Int
        let size: CGSize
    }

    private struct FlowRow {
        let items: [FlowItem]
        let height: CGFloat
    }
}

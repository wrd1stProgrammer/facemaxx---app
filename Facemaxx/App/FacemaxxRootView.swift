import SwiftUI
import UserNotifications

struct FacemaxxRootView: View {
    @State private var selectedTab = FacemaxxTab.home
    @StateObject private var authService = FacemaxxAuthService.shared
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage(AppLanguage.storageKey) private var selectedLanguageID = AppLanguage.system.rawValue
    @AppStorage(OnboardingState.completedStorageKey) private var hasCompletedOnboarding = false
    @State private var pendingOnboardingCapture: FaceCameraCaptureResult?
    @State private var isAppReviewDemoMode = AppReviewDemoMode.isEnabled

    private var selectedLanguage: AppLanguage {
        AppLanguage.storedValue(for: selectedLanguageID)
    }

    var body: some View {
        Group {
            if hasCompletedOnboarding {
                appContent
            } else {
                OnboardingView { capture in
                    withAnimation(.easeInOut(duration: 0.24)) {
                        pendingOnboardingCapture = capture
                        selectedTab = capture == nil && !isAppReviewDemoMode ? .home : .analyze
                        hasCompletedOnboarding = true
                    }
                } onReviewerDemoActivated: {
                    activateAppReviewDemoMode()
                } onReviewerDemoPreparedForOnboarding: {
                    prepareAppReviewOnboardingDemoMode()
                }
            }
        }
        .preferredColorScheme(.dark)
        .environment(\.locale, selectedLanguage.locale)
        .environment(\.layoutDirection, selectedLanguage.layoutDirection)
        .environmentObject(authService)
        .onChange(of: authService.session) { _, _ in
            Task {
                await purchaseService.configure(appUserID: FacemaxxPurchaseService.currentAppUserID())
            }
        }
        .task(id: hasCompletedOnboarding) {
            guard hasCompletedOnboarding else { return }
            await FacemaxxNotificationService.shared.requestInitialAuthorizationIfNeeded()
            await purchaseService.refreshEntitlementsAndServerStatus()
        }
        .onChange(of: scenePhase) { _, newPhase in
            guard newPhase == .active, hasCompletedOnboarding else { return }
            Task {
                await purchaseService.refreshEntitlementsAndServerStatus()
            }
        }
    }

    @ViewBuilder
    private var appContent: some View {
        if #available(iOS 18.0, *) {
            nativeTabView
        } else {
            legacyCustomTabView
        }
    }

    @available(iOS 18.0, *)
    private var nativeTabView: some View {
        TabView(selection: $selectedTab) {
            Tab(FacemaxxTab.home.titleKey, systemImage: FacemaxxTab.home.symbolName, value: .home) {
                HomeView(
                    onStartScan: { selectedTab = .analyze }
                )
            }

            Tab(FacemaxxTab.analyze.titleKey, systemImage: FacemaxxTab.analyze.symbolName, value: .analyze) {
                AnalyzeView(initialCapture: pendingOnboardingCapture, preloadDemoPhotos: isAppReviewDemoMode) {
                    pendingOnboardingCapture = nil
                }
            }

            Tab(FacemaxxTab.progress.titleKey, systemImage: FacemaxxTab.progress.symbolName, value: .progress) {
                GlowProgressView()
            }

            Tab(FacemaxxTab.profile.titleKey, systemImage: FacemaxxTab.profile.symbolName, value: .profile) {
                ProfileView(onReturnToOnboarding: resetToOnboarding)
            }
        }
        .background(FXTheme.background)
        .toolbarBackground(FXTheme.card, for: .tabBar)
        .toolbarBackground(.visible, for: .tabBar)
        .toolbarColorScheme(.dark, for: .tabBar)
        .fxNativeTabBarBehavior()
    }

    private var legacyCustomTabView: some View {
        ZStack(alignment: .bottom) {
            FXTheme.background
                .ignoresSafeArea()

            Group {
                switch selectedTab {
                case .home:
                    HomeView(
                        onStartScan: { selectedTab = .analyze }
                    )
                case .analyze:
                    AnalyzeView(initialCapture: pendingOnboardingCapture, preloadDemoPhotos: isAppReviewDemoMode) {
                        pendingOnboardingCapture = nil
                    }
                case .progress:
                    GlowProgressView()
                case .profile:
                    ProfileView(onReturnToOnboarding: resetToOnboarding)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            FacemaxxTabBar(selectedTab: $selectedTab)
                .padding(.horizontal, 14)
                .padding(.bottom, 8)
        }
    }

    private func resetToOnboarding() {
        purchaseService.deactivateAppReviewDemoMode()
        isAppReviewDemoMode = false
        pendingOnboardingCapture = nil
        selectedTab = .home
        withAnimation(.easeInOut(duration: 0.24)) {
            hasCompletedOnboarding = false
        }
    }

    private func activateAppReviewDemoMode() {
        purchaseService.activateAppReviewDemoMode()
        isAppReviewDemoMode = true
        pendingOnboardingCapture = nil
        selectedTab = .analyze
        withAnimation(.easeInOut(duration: 0.24)) {
            hasCompletedOnboarding = true
        }
    }

    private func prepareAppReviewOnboardingDemoMode() {
        purchaseService.activateAppReviewDemoMode()
        isAppReviewDemoMode = true
        pendingOnboardingCapture = nil
        selectedTab = .analyze
    }
}

private extension View {
    @ViewBuilder
    func fxNativeTabBarBehavior() -> some View {
        if #available(iOS 26.0, *) {
            tabBarMinimizeBehavior(.never)
        } else {
            self
        }
    }
}

enum AppLanguage: String, CaseIterable, Identifiable {
    static let storageKey = "facemaxx.appLanguage"

    case system
    case english = "en"
    case korean = "ko"
    case japanese = "ja"
    case german = "de"
    case spanishLatinAmerica = "es-419"
    case traditionalChinese = "zh-Hant"
    case portugueseBrazil = "pt-BR"
    case french = "fr"
    case italian = "it"
    case indonesian = "id"
    case turkish = "tr"
    case arabic = "ar"

    var id: String { rawValue }

    var titleKey: LocalizedStringKey {
        switch self {
        case .system:
            "profile.language.system"
        case .english:
            "profile.language.english"
        case .korean:
            "profile.language.korean"
        case .japanese:
            "profile.language.japanese"
        case .german:
            "profile.language.german"
        case .spanishLatinAmerica:
            "profile.language.spanishLatinAmerica"
        case .traditionalChinese:
            "profile.language.traditionalChinese"
        case .portugueseBrazil:
            "profile.language.portugueseBrazil"
        case .french:
            "profile.language.french"
        case .italian:
            "profile.language.italian"
        case .indonesian:
            "profile.language.indonesian"
        case .turkish:
            "profile.language.turkish"
        case .arabic:
            "profile.language.arabic"
        }
    }

    var locale: Locale {
        switch self {
        case .system:
            .autoupdatingCurrent
        default:
            Locale(identifier: rawValue)
        }
    }

    var analysisLocale: String {
        switch self {
        case .system:
            let identifier = Locale.autoupdatingCurrent.identifier
            return Self.supportedLocaleIdentifier(for: identifier)
        default:
            return rawValue
        }
    }

    var layoutDirection: LayoutDirection {
        analysisLocale == "ar" ? .rightToLeft : .leftToRight
    }

    private static func supportedLocaleIdentifier(for identifier: String) -> String {
        let normalized = identifier.replacingOccurrences(of: "_", with: "-")
        let lowercased = normalized.lowercased()

        if lowercased.hasPrefix("pt-br") { return "pt-BR" }
        if lowercased.hasPrefix("zh-hant") || lowercased.hasPrefix("zh-tw") || lowercased.hasPrefix("zh-hk") {
            return "zh-Hant"
        }
        if lowercased.hasPrefix("es") { return "es-419" }

        let languageCode = Locale(identifier: identifier).language.languageCode?.identifier ?? "en"
        switch languageCode {
        case "ko", "ja", "de", "fr", "it", "id", "tr", "ar":
            return languageCode
        case "pt":
            return "pt-BR"
        case "zh":
            return "zh-Hant"
        default:
            return "en"
        }
    }

    static func storedValue(for rawValue: String) -> AppLanguage {
        AppLanguage(rawValue: rawValue) ?? .system
    }
}

@MainActor
final class FacemaxxNotificationService: ObservableObject {
    static let shared = FacemaxxNotificationService()

    @Published private(set) var authorizationStatus: UNAuthorizationStatus = .notDetermined
    private let defaults = UserDefaults.standard
    private let enabledKey = "facemaxx.notifications.enabled"
    private let didAskOnMainKey = "facemaxx.notifications.didAskOnMain"

    private init() {}

    private var notificationsEnabled: Bool {
        get { defaults.bool(forKey: enabledKey) }
        set { defaults.set(newValue, forKey: enabledKey) }
    }

    private var didAskOnMain: Bool {
        get { defaults.bool(forKey: didAskOnMainKey) }
        set { defaults.set(newValue, forKey: didAskOnMainKey) }
    }

    var statusTitleKey: LocalizedStringKey {
        switch authorizationStatus {
        case .authorized, .provisional, .ephemeral:
            "profile.notificationsValue.on"
        case .denied:
            "profile.notificationsValue.denied"
        case .notDetermined:
            "profile.notificationsValue.notSet"
        @unknown default:
            "profile.notificationsValue.off"
        }
    }

    func refreshAuthorizationStatus() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        authorizationStatus = settings.authorizationStatus
        if authorizationStatus == .denied {
            notificationsEnabled = false
        }
    }

    func requestInitialAuthorizationIfNeeded() async {
        await refreshAuthorizationStatus()
        guard !didAskOnMain, authorizationStatus == .notDetermined else { return }
        didAskOnMain = true
        await requestAuthorization()
    }

    func prepareSettingsFromProfile() async {
        await refreshAuthorizationStatus()
        if authorizationStatus == .notDetermined {
            await requestAuthorization()
        }
    }

    private func requestAuthorization() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound])
            notificationsEnabled = granted
            await refreshAuthorizationStatus()
        } catch {
            notificationsEnabled = false
            await refreshAuthorizationStatus()
        }
    }
}

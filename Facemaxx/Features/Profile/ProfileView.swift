import SwiftUI
import UIKit

struct ProfileView: View {
    @Environment(\.openURL) private var openURL
    @EnvironmentObject private var authService: FacemaxxAuthService
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService
    @StateObject private var notificationService = FacemaxxNotificationService.shared
    @AppStorage(AppLanguage.storageKey) private var selectedLanguageID = AppLanguage.system.rawValue
    @State private var showsSignOutConfirmation = false
    @State private var showsDeleteConfirmation = false
    @State private var showsAIConsentRevokeConfirmation = false
    @State private var showsSupportEmail = false
    @State private var isProPaywallPresented = false
    @State private var isDeletingAccount = false
    @State private var accountMessageKey: LocalizedStringKey?
    @State private var accountErrorMessage: String?
    @AppStorage(AIAnalysisConsentStore.grantedStorageKey) private var isAIAnalysisConsentGranted = false
    @AppStorage(AIAnalysisConsentStore.promptSeenStorageKey) private var hasSeenAIAnalysisConsentPrompt = false
    @State private var isAIAnalysisConsentPresented = false
    var onReturnToOnboarding: () -> Void = {}

    private var selectedLanguage: AppLanguage {
        AppLanguage.storedValue(for: selectedLanguageID)
    }

    private var displayName: String {
        authService.session?.displayName?.nilIfBlank
            ?? authService.session?.email?.nilIfBlank
            ?? String(localized: "profile.guestName", locale: selectedLanguage.locale)
    }

    private var accountDetailKey: LocalizedStringKey {
        authService.session == nil ? "profile.account.guestDetail" : "profile.account.signedInDetail"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                accountCard
                planCard
                preferencesSection
                supportSection
                accountSection

                if let accountMessageKey {
                    StatusBanner(iconName: "checkmark.circle.fill", titleKey: accountMessageKey, tint: FXTheme.green)
                }

                if let accountErrorMessage {
                    StatusBanner(iconName: "exclamationmark.triangle.fill", title: accountErrorMessage, tint: FXTheme.orange)
                }

                Text("profile.footer")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(FXTheme.textMuted)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 4)
            }
            .padding(.horizontal, 16)
            .padding(.top, 76)
            .safeAreaPadding(.bottom, 118)
        }
        .scrollIndicators(.hidden)
        .background(FXTheme.background)
        .confirmationDialog("profile.signOut.title", isPresented: $showsSignOutConfirmation, titleVisibility: .visible) {
            Button("profile.signOut.confirm", role: .destructive, action: signOut)
            Button("common.cancel", role: .cancel) { }
        } message: {
            Text("profile.signOut.message")
        }
        .confirmationDialog("profile.delete.title", isPresented: $showsDeleteConfirmation, titleVisibility: .visible) {
            Button("profile.delete.confirm", role: .destructive) {
                Task { await deleteAccount() }
            }
            Button("common.cancel", role: .cancel) { }
        } message: {
            Text("profile.delete.message")
        }
        .confirmationDialog("profile.aiConsent.revokeTitle", isPresented: $showsAIConsentRevokeConfirmation, titleVisibility: .visible) {
            Button("profile.aiConsent.revoke", role: .destructive) {
                revokeAIAnalysisConsent()
            }
            Button("common.cancel", role: .cancel) { }
        } message: {
            Text("profile.aiConsent.revokeMessage")
        }
        .alert("profile.contactSupport", isPresented: $showsSupportEmail) {
            Button("common.done", role: .cancel) { }
        } message: {
            Text("profile.contactSupportEmail")
        }
        .fullScreenCover(isPresented: $isProPaywallPresented) {
            ProScanPaywallView()
                .environmentObject(purchaseService)
        }
        .sheet(isPresented: $isAIAnalysisConsentPresented) {
            AIAnalysisConsentSheet(
                primaryButtonKey: "privacy.aiConsent.agreeContinue",
                onAgree: grantAIAnalysisConsent,
                onNotNow: deferAIAnalysisConsent
            )
            .presentationDetents([.large])
            .presentationDragIndicator(.visible)
        }
        .task {
            await notificationService.refreshAuthorizationStatus()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("profile.title")
                    .font(.largeTitle.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                Spacer()

                Text("profile.version")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textSecondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .fxCapsuleSurface(fill: FXTheme.pill, stroke: Color.white.opacity(0.035))
            }

            Text("profile.subtitle")
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(FXTheme.textSecondary)
        }
    }

    private var accountCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 16) {
                ZStack {
                    Circle()
                        .fill(FXTheme.cardElevated)

                    Image(systemName: "person.crop.circle.fill")
                        .font(.system(size: 38, weight: .semibold))
                        .foregroundStyle(FXTheme.textPrimary, FXTheme.cardElevated)
                }
                .frame(width: 56, height: 56)

                VStack(alignment: .leading, spacing: 6) {
                    Text(displayName)
                        .font(.system(size: 19, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)

                    Text(accountDetailKey)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineLimit(2)
                }

                Spacer()
            }

            HStack(spacing: 10) {
                AccountChip(iconName: "person.badge.key.fill", titleKey: authService.session?.provider.titleKey ?? "onboarding.auth.provider.guest")
                AccountChip(iconName: "shield.checkered", titleKey: "profile.account.private")
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 18)
        .fxCard(cornerRadius: 30)
    }

    private var planCard: some View {
        ProfileSectionCard(titleKey: "profile.planSection") {
            VStack(spacing: 12) {
                ProfileActionRow(
                    iconName: "sparkles",
                    titleKey: "profile.currentPlan",
                    value: purchaseService.planSummaryText(locale: selectedLanguage.locale),
                    tint: FXTheme.cyan
                )

                ProfileActionRow(
                    iconName: "crown.fill",
                    titleKey: "profile.openPaywall",
                    valueKey: "profile.openPaywallValue",
                    tint: FXTheme.premiumBlue,
                    showsChevron: true
                ) {
                    isProPaywallPresented = true
                }

                ProfileActionRow(
                    iconName: "arrow.clockwise.circle.fill",
                    titleKey: "profile.restorePurchases",
                    valueKey: "profile.restorePurchasesValue",
                    tint: FXTheme.green,
                    showsChevron: true
                ) {
                    Task {
                        await purchaseService.restorePurchases()
                        if let errorMessage = purchaseService.errorMessage {
                            accountMessageKey = nil
                            accountErrorMessage = errorMessage
                        } else {
                            accountMessageKey = "profile.restorePurchases.done"
                            accountErrorMessage = nil
                        }
                    }
                }

            }
        }
    }

    private var preferencesSection: some View {
        ProfileSectionCard(titleKey: "profile.preferences") {
            VStack(spacing: 12) {
                languagePicker
                ProfileActionRow(
                    iconName: "bell.fill",
                    titleKey: "profile.notifications",
                    valueKey: notificationService.statusTitleKey,
                    showsChevron: true
                ) {
                    Task { await handleNotificationTap() }
                }
                ProfileActionRow(iconName: "lock.shield.fill", titleKey: "profile.privacy", valueKey: "profile.privacyValue")
                ProfileActionRow(
                    iconName: "sparkles.rectangle.stack.fill",
                    titleKey: "profile.aiConsent",
                    valueKey: isAIAnalysisConsentGranted ? "profile.aiConsent.allowed" : "profile.aiConsent.notAllowed",
                    tint: isAIAnalysisConsentGranted ? FXTheme.green : FXTheme.orange,
                    showsChevron: true
                ) {
                    if isAIAnalysisConsentGranted {
                        showsAIConsentRevokeConfirmation = true
                    } else {
                        isAIAnalysisConsentPresented = true
                    }
                }
            }
        }
    }

    private var supportSection: some View {
        ProfileSectionCard(titleKey: "profile.support") {
            VStack(spacing: 12) {
                ProfileActionRow(iconName: "doc.text.fill", titleKey: "profile.terms", valueKey: "profile.open", showsChevron: true) {
                    openURL(URL(string: "https://skinny-look-a0c.notion.site/Terms-of-Use-367da865dff180bebffad4a6d5322a84?source=copy_link")!)
                }
                ProfileActionRow(iconName: "hand.raised.fill", titleKey: "profile.privacyPolicy", valueKey: "profile.open", showsChevron: true) {
                    openURL(URL(string: "https://skinny-look-a0c.notion.site/Privacy-Policy-Facemaxx-367da865dff180b8a6cdecca53bcda69?source=copy_link")!)
                }
                ProfileActionRow(iconName: "envelope.fill", titleKey: "profile.contactSupport", valueKey: "profile.contactSupportValue", showsChevron: true) {
                    showsSupportEmail = true
                }
                ProfileActionRow(iconName: "info.circle.fill", titleKey: "profile.appVersion", value: Bundle.main.facemaxxVersionText)
            }
        }
    }

    private var accountSection: some View {
        ProfileSectionCard(titleKey: "profile.account") {
            VStack(spacing: 12) {
                ProfileActionRow(
                    iconName: "rectangle.portrait.and.arrow.right.fill",
                    titleKey: "profile.signOut.row",
                    valueKey: "profile.signOut.value",
                    showsChevron: true
                ) {
                    showsSignOutConfirmation = true
                }

                ProfileActionRow(
                    iconName: "trash.fill",
                    titleKey: "profile.delete.row",
                    valueKey: isDeletingAccount ? "profile.delete.inProgress" : "profile.delete.value",
                    showsChevron: !isDeletingAccount
                ) {
                    guard !isDeletingAccount else { return }
                    showsDeleteConfirmation = true
                }
                .opacity(isDeletingAccount ? 0.62 : 1)
            }
        }
    }

    private var languagePicker: some View {
        Menu {
            Picker("profile.languagePickerTitle", selection: $selectedLanguageID) {
                ForEach(AppLanguage.allCases) { language in
                    Text(language.titleKey)
                        .tag(language.rawValue)
                }
            }
        } label: {
            ProfileActionRow(
                iconName: "globe",
                titleKey: "profile.language",
                valueKey: selectedLanguage.titleKey,
                showsChevron: true
            )
        }
        .buttonStyle(.plain)
    }

    private func handleNotificationTap() async {
        await notificationService.prepareSettingsFromProfile()
        if let settingsURL = URL(string: UIApplication.openSettingsURLString) {
            await MainActor.run {
                openURL(settingsURL)
            }
        }
    }

    private func signOut() {
        purchaseService.deactivateAppReviewDemoMode()
        PhotoImageCache.shared.clear()
        AnalysisJSONCache.shared.clear()
        OnboardingPreferencesStore.clear()
        authService.signOut()
        onReturnToOnboarding()
    }

    private func deleteAccount() async {
        guard !isDeletingAccount else { return }
        isDeletingAccount = true
        accountMessageKey = nil
        accountErrorMessage = nil
        defer { isDeletingAccount = false }

        do {
            try await FacemaxxAPIClient.shared.deleteAccount()
            purchaseService.deactivateAppReviewDemoMode()
            PhotoImageCache.shared.clear()
            AnalysisJSONCache.shared.clear()
            OnboardingPreferencesStore.clear()
            authService.signOut()
            onReturnToOnboarding()
        } catch {
            accountErrorMessage = error.localizedDescription
        }
    }

    private func grantAIAnalysisConsent() {
        AIAnalysisConsentStore.grant()
        isAIAnalysisConsentGranted = true
        hasSeenAIAnalysisConsentPrompt = true
        isAIAnalysisConsentPresented = false
        accountMessageKey = "profile.aiConsent.grantedDone"
        accountErrorMessage = nil
    }

    private func deferAIAnalysisConsent() {
        AIAnalysisConsentStore.markPromptSeen()
        hasSeenAIAnalysisConsentPrompt = true
        isAIAnalysisConsentPresented = false
    }

    private func revokeAIAnalysisConsent() {
        AIAnalysisConsentStore.revoke()
        isAIAnalysisConsentGranted = false
        hasSeenAIAnalysisConsentPrompt = true
        accountMessageKey = "profile.aiConsent.revokeDone"
        accountErrorMessage = nil
    }
}

private struct SectionHeader: View {
    let titleKey: LocalizedStringKey

    var body: some View {
        Text(titleKey)
            .font(.system(size: 22, weight: .heavy))
            .foregroundStyle(FXTheme.textPrimary)
            .padding(.top, 8)
    }
}

private struct ProfileSectionCard<Content: View>: View {
    let titleKey: LocalizedStringKey
    private let content: Content

    init(titleKey: LocalizedStringKey, @ViewBuilder content: () -> Content) {
        self.titleKey = titleKey
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(titleKey: titleKey)
            content
        }
    }
}

private struct AccountChip: View {
    let iconName: String
    let titleKey: LocalizedStringKey

    var body: some View {
        Label(titleKey, systemImage: iconName)
            .font(.system(size: 11, weight: .heavy))
            .foregroundStyle(FXTheme.textSecondary)
            .padding(.horizontal, 11)
            .padding(.vertical, 7)
            .fxCapsuleSurface(fill: FXTheme.cardElevated, stroke: Color.white.opacity(0.035))
    }
}

private struct ProfileActionRow: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    var valueKey: LocalizedStringKey?
    var value: String?
    var tint: Color = FXTheme.textPrimary
    var showsChevron = false
    var action: (() -> Void)?

    var body: some View {
        if let action {
            Button(action: action) {
                content
            }
            .buttonStyle(.plain)
        } else {
            content
        }
    }

    private var content: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .font(.system(size: 21, weight: .heavy))
                .foregroundStyle(tint)
                .frame(width: 44, alignment: .center)

            Text(titleKey)
                .font(.system(size: 17, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.72)

            Spacer(minLength: 12)

            if let valueKey {
                Text(valueKey)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.68)
            } else if let value {
                Text(value)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.68)
            }

            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(FXTheme.textMuted)
            }
        }
        .padding(.horizontal, 17)
        .frame(height: 70)
        .background {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(FXTheme.cardElevated)
        }
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(Color.white.opacity(0.035), lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct StatusBanner: View {
    let iconName: String
    var titleKey: LocalizedStringKey?
    var title: String?
    let tint: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: iconName)
                .font(.headline.weight(.heavy))
                .foregroundStyle(tint)

            if let titleKey {
                Text(titleKey)
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(FXTheme.textPrimary)
            } else if let title {
                Text(title)
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(FXTheme.textPrimary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .fxCard(cornerRadius: 20, fill: tint.opacity(0.12), stroke: tint.opacity(0.20))
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

private extension Bundle {
    var facemaxxVersionText: String {
        let version = object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        let build = object(forInfoDictionaryKey: "CFBundleVersion") as? String
        return [version, build.map { "(\($0))" }]
            .compactMap { $0 }
            .joined(separator: " ")
            .nilIfBlank ?? "1.0"
    }
}

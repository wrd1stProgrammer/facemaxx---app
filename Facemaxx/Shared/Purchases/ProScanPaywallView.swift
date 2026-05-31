import RevenueCat
import SwiftUI

struct ProScanPaywallView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService

    @State private var selectedPackageID: String?
    @State private var isReviewerAccessPresented = false
    @State private var reviewerAccessCode = ""
    @State private var reviewerAccessErrorMessage: String?

    private var displayPackages: [Package] {
        purchaseService.subscriptionPackages + purchaseService.scanPackPackages
    }

    private var selectedPackage: Package? {
        displayPackages.first { $0.identifier == selectedPackageID }
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            FXTheme.background
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    topBar
                    hero
                    benefitsCard
                    subscriptionProducts
                    scanPackProducts
                    footer
                    statusSection
                }
                .padding(.horizontal, 20)
                .padding(.top, 14)
                .padding(.bottom, 126)
            }
            .scrollIndicators(.hidden)

            stickyContinueButton
        }
        .preferredColorScheme(.dark)
        .task {
            await purchaseService.refresh()
            syncDefaultSelection()
        }
        .onChange(of: purchaseService.packages.map(\.identifier)) { _, _ in
            syncDefaultSelection()
        }
        .sheet(isPresented: $isReviewerAccessPresented) {
            ReviewerAccessSheet(
                code: $reviewerAccessCode,
                errorMessage: reviewerAccessErrorMessage,
                isRedeeming: purchaseService.isLoading,
                onCancel: {
                    isReviewerAccessPresented = false
                },
                onRedeem: redeemReviewerAccessCode
            )
            .presentationDetents([.height(340)])
            .presentationDragIndicator(.visible)
            .preferredColorScheme(.dark)
        }
    }

    private var topBar: some View {
        HStack {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 21, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .frame(width: 46, height: 46)
            }
            .buttonStyle(.plain)

            Spacer()

            Button {
                Task {
                    await purchaseService.restorePurchases()
                }
            } label: {
                Text("purchases.paywall.restore")
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .frame(height: 46)
            }
            .buttonStyle(.plain)
            .disabled(purchaseService.isLoading || purchaseService.isPurchasing)
            .opacity(purchaseService.isLoading || purchaseService.isPurchasing ? 0.55 : 1)
        }
    }

    private var hero: some View {
        VStack(spacing: 12) {
            Label(purchaseService.scanBalanceText(locale: locale), systemImage: "bolt.fill")
                .font(.caption.weight(.black))
                .foregroundStyle(FXTheme.textPrimary)
                .padding(.horizontal, 12)
                .padding(.vertical, 7)
                .background(FXTheme.card, in: Capsule(style: .continuous))
                .overlay {
                    Capsule(style: .continuous)
                        .stroke(FXTheme.cardStroke, lineWidth: 1)
                }

            Text("purchases.paywall.title")
                .font(.system(size: 31, weight: .black))
                .foregroundStyle(FXTheme.textPrimary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.72)

            Text("purchases.paywall.subtitle")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .padding(.horizontal, 8)
        }
        .padding(.top, 10)
    }

    private var benefitsCard: some View {
        VStack(alignment: .leading, spacing: 15) {
            PaywallBenefit(iconName: "viewfinder", titleKey: "purchases.benefit.detailedReports")
            PaywallBenefit(iconName: "waveform.path.ecg", titleKey: "purchases.benefit.trackInsights")
            PaywallBenefit(iconName: "sparkles", titleKey: "purchases.benefit.powerfulAI")
            PaywallBenefit(iconName: "chart.line.uptrend.xyaxis", titleKey: "purchases.benefit.trackScores")
            PaywallBenefit(iconName: "face.smiling", titleKey: "purchases.benefit.learnFace")
            PaywallBenefit(iconName: "star", titleKey: "purchases.benefit.glowPlan")
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(FXTheme.card, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        }
    }

    @ViewBuilder
    private var subscriptionProducts: some View {
        let packages = purchaseService.subscriptionPackages
        if packages.isEmpty {
            EmptyProductState()
        } else {
            VStack(alignment: .leading, spacing: 10) {
                PaywallSectionLabel(titleKey: "purchases.section.subscription")
                ForEach(packages, id: \.identifier) { package in
                    PaywallProductCard(
                        package: package,
                        isSelected: selectedPackageID == package.identifier,
                        badgeKey: badgeKey(for: package),
                        onSelect: { selectedPackageID = package.identifier }
                    )
                }
            }
        }
    }

    @ViewBuilder
    private var scanPackProducts: some View {
        let packages = purchaseService.scanPackPackages
        if !packages.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                PaywallSectionLabel(titleKey: "purchases.section.scanPacks")
                ForEach(packages, id: \.identifier) { package in
                    PaywallProductCard(
                        package: package,
                        isSelected: selectedPackageID == package.identifier,
                        badgeKey: badgeKey(for: package),
                        onSelect: { selectedPackageID = package.identifier }
                    )
                }
            }
            .padding(.top, 12)
        }
    }

    private var stickyContinueButton: some View {
        VStack(spacing: 10) {
            Divider()
                .overlay(Color.white.opacity(0.08))

            continueButton
                .padding(.horizontal, 20)
                .padding(.bottom, 14)
        }
        .padding(.top, 14)
        .background {
            LinearGradient(
                colors: [
                    FXTheme.background.opacity(0.12),
                    FXTheme.background.opacity(0.82),
                    FXTheme.background
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea(edges: .bottom)
        }
    }

    private var continueButton: some View {
        HStack(spacing: 10) {
            if purchaseService.isPurchasing {
                ProgressView()
                    .tint(.white)
            }

            Text(continueTitle)
                .font(.system(size: 20, weight: .heavy))
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity)
        .frame(height: 58)
        .background(FXTheme.premiumBlue, in: Capsule(style: .continuous))
        .contentShape(Capsule(style: .continuous))
        .gesture(
            ExclusiveGesture(LongPressGesture(minimumDuration: 5), TapGesture())
                .onEnded { gestureValue in
                    switch gestureValue {
                    case .first(true):
                        presentReviewerAccessCodeSheet()
                    case .first(false):
                        break
                    case .second:
                        purchaseSelectedPackage()
                    }
                }
        )
        .opacity(selectedPackage == nil || purchaseService.isPurchasing || purchaseService.isLoading ? 0.56 : 1)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
    }

    private var continueTitle: String {
        guard let selectedPackage else {
            return String(localized: "purchases.paywall.continue", locale: locale)
        }

        return String(
            format: String(localized: "purchases.paywall.continueWithFormat", locale: locale),
            purchaseService.title(for: selectedPackage, locale: locale)
        )
    }

    private var footer: some View {
        VStack(spacing: 22) {
            Text("purchases.paywall.cancelAnytime")
                .font(.system(size: 13, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)

            HStack(spacing: 36) {
                Link("purchases.paywall.terms", destination: URL(string: "https://skinny-look-a0c.notion.site/Terms-of-Use-367da865dff180bebffad4a6d5322a84?source=copy_link")!)
                Link("purchases.paywall.privacy", destination: URL(string: "https://skinny-look-a0c.notion.site/Privacy-Policy-Facemaxx-367da865dff180b8a6cdecca53bcda69?source=copy_link")!)
            }
            .font(.system(size: 14, weight: .heavy))
            .foregroundStyle(FXTheme.blue)
        }
        .padding(.top, 4)
    }

    @ViewBuilder
    private var statusSection: some View {
        VStack(spacing: 10) {
            if purchaseService.isLoading {
                PaywallStatusBanner(iconName: "arrow.triangle.2.circlepath", titleKey: "purchases.status.loading", tint: FXTheme.cyan)
            }

            if let statusMessage = purchaseService.statusMessage {
                PaywallStatusBanner(iconName: "checkmark.circle.fill", title: statusMessage, tint: FXTheme.green)
            }

            if let errorMessage = purchaseService.errorMessage {
                PaywallStatusBanner(iconName: "exclamationmark.triangle.fill", title: errorMessage, tint: FXTheme.orange)
            }
        }
    }

    private func syncDefaultSelection() {
        let identifiers = Set(displayPackages.map(\.identifier))
        if let selectedPackageID, identifiers.contains(selectedPackageID) {
            return
        }

        selectedPackageID =
            purchaseService.subscriptionPackages.first { $0.storeProduct.productIdentifier == FacemaxxPurchaseService.monthlyProductID }?.identifier
            ?? purchaseService.subscriptionPackages.first?.identifier
            ?? purchaseService.scanPackPackages.first?.identifier
    }

    private func presentReviewerAccessCodeSheet() {
        guard !purchaseService.isPurchasing, !purchaseService.isLoading else { return }
        reviewerAccessCode = ""
        reviewerAccessErrorMessage = nil
        isReviewerAccessPresented = true
    }

    private func purchaseSelectedPackage() {
        guard !purchaseService.isPurchasing, !purchaseService.isLoading else { return }
        guard !isReviewerAccessPresented else { return }
        guard let selectedPackage else { return }

        Task {
            let didPurchase = await purchaseService.purchase(selectedPackage)
            if didPurchase {
                dismiss()
            }
        }
    }

    private func redeemReviewerAccessCode() {
        let code = reviewerAccessCode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !code.isEmpty else {
            reviewerAccessErrorMessage = String(localized: "purchases.reviewerAccess.invalidCode", locale: locale)
            return
        }

        reviewerAccessErrorMessage = nil
        Task {
            let didRedeem = await purchaseService.redeemReviewerAccessCode(code)
            if didRedeem {
                reviewerAccessCode = ""
                isReviewerAccessPresented = false
            } else {
                reviewerAccessErrorMessage = purchaseService.errorMessage
                    ?? String(localized: "purchases.reviewerAccess.invalidCode", locale: locale)
            }
        }
    }

    private func badgeKey(for package: Package) -> LocalizedStringKey? {
        switch package.storeProduct.productIdentifier {
        case FacemaxxPurchaseService.monthlyProductID:
            return "purchases.badge.bestValue"
        case FacemaxxPurchaseService.twentyScanProductID:
            return "purchases.badge.mostPopular"
        default:
            return nil
        }
    }
}

private struct PaywallBenefit: View {
    let iconName: String
    let titleKey: LocalizedStringKey

    var body: some View {
        HStack(spacing: 18) {
            Image(systemName: iconName)
                .font(.system(size: 15, weight: .black))
                .foregroundStyle(Color.black)
                .frame(width: 24, height: 24)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 6, style: .continuous))

            Text(titleKey)
                .font(.system(size: 15.5, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
    }
}

private struct ReviewerAccessSheet: View {
    @FocusState private var isCodeFocused: Bool

    @Binding var code: String
    let errorMessage: String?
    let isRedeeming: Bool
    let onCancel: () -> Void
    let onRedeem: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 7) {
                Text("purchases.reviewerAccess.title")
                    .font(.system(size: 24, weight: .black))
                    .foregroundStyle(FXTheme.textPrimary)

                Text("purchases.reviewerAccess.body")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            SecureField("purchases.reviewerAccess.codePlaceholder", text: $code)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .font(.system(size: 18, weight: .heavy, design: .monospaced))
                .foregroundStyle(FXTheme.textPrimary)
                .focused($isCodeFocused)
                .submitLabel(.done)
                .onSubmit(onRedeem)
                .padding(.horizontal, 16)
                .frame(height: 56)
                .background(FXTheme.cardElevated, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(errorMessage == nil ? FXTheme.cardStroke : FXTheme.orange.opacity(0.7), lineWidth: 1.2)
                }

            if let errorMessage {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .font(.caption.weight(.heavy))
                    .foregroundStyle(FXTheme.orange)
            }

            HStack(spacing: 12) {
                Button(action: onCancel) {
                    Text("purchases.reviewerAccess.cancel")
                        .font(.system(size: 16, weight: .heavy))
                        .foregroundStyle(FXTheme.textPrimary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(FXTheme.card, in: Capsule(style: .continuous))
                }
                .buttonStyle(.plain)

                Button(action: onRedeem) {
                    HStack(spacing: 8) {
                        if isRedeeming {
                            ProgressView()
                                .tint(.white)
                        }

                        Text("purchases.reviewerAccess.redeem")
                            .font(.system(size: 16, weight: .heavy))
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(FXTheme.premiumBlue, in: Capsule(style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(isRedeeming || code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .opacity(isRedeeming || code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.58 : 1)
            }
        }
        .padding(.horizontal, 22)
        .padding(.top, 26)
        .padding(.bottom, 18)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(FXTheme.background.ignoresSafeArea())
        .task {
            isCodeFocused = true
        }
    }
}

private struct PaywallSectionLabel: View {
    let titleKey: LocalizedStringKey

    var body: some View {
        Text(titleKey)
            .font(.system(size: 15, weight: .black))
            .foregroundStyle(FXTheme.textPrimary)
            .padding(.horizontal, 4)
    }
}

private struct PaywallProductCard: View {
    @Environment(\.locale) private var locale
    @EnvironmentObject private var purchaseService: FacemaxxPurchaseService

    let package: Package
    let isSelected: Bool
    let badgeKey: LocalizedStringKey?
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 14) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(purchaseService.title(for: package, locale: locale))
                            .font(.system(size: 19, weight: .black))
                            .foregroundStyle(FXTheme.textPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.62)

                        Text(purchaseService.subtitle(for: package, locale: locale))
                            .font(.system(size: 13.5, weight: .semibold))
                            .foregroundStyle(FXTheme.textSecondary)
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 12)

                    VStack(alignment: .trailing, spacing: 5) {
                        Text(package.localizedPriceString)
                            .font(.system(size: 19, weight: .black))
                            .foregroundStyle(FXTheme.textPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)

                        if let perScanPrice = purchaseService.perScanPriceText(for: package, locale: locale) {
                            Text(perScanPrice)
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundStyle(isSelected ? FXTheme.cyan : FXTheme.textSecondary)
                                .lineLimit(1)
                                .minimumScaleFactor(0.7)
                        }
                    }
                }

                HStack(spacing: 8) {
                    if let quotaText = purchaseService.quotaText(for: package, locale: locale) {
                        PaywallProductPill(
                            iconName: "bolt.fill",
                            text: quotaText,
                            tint: isSelected ? FXTheme.cyan : FXTheme.textMuted
                        )
                    }

                    if let badgeKey {
                        PaywallProductPill(
                            iconName: "sparkles",
                            textKey: badgeKey,
                            tint: FXTheme.green
                        )
                    }

                    Spacer(minLength: 8)

                    Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                        .font(.system(size: 26, weight: .bold))
                        .foregroundStyle(isSelected ? FXTheme.textPrimary : FXTheme.textMuted)
                        .frame(width: 30)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 17)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(isSelected ? FXTheme.cardElevated : FXTheme.card)
                    .overlay {
                        if isSelected {
                            LinearGradient(
                                colors: [FXTheme.cyan.opacity(0.18), Color.clear],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                        }
                    }
            }
            .overlay {
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(isSelected ? FXTheme.cyan.opacity(0.78) : FXTheme.cardStroke, lineWidth: isSelected ? 1.6 : 1)
            }
            .shadow(color: isSelected ? FXTheme.cyan.opacity(0.15) : .clear, radius: 18, x: 0, y: 8)
            .animation(.smooth(duration: 0.18), value: isSelected)
        }
        .buttonStyle(.plain)
    }
}

private struct PaywallProductPill: View {
    let iconName: String
    var text: String?
    var textKey: LocalizedStringKey?
    let tint: Color

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: iconName)
                .font(.system(size: 10, weight: .black))

            if let text {
                Text(text)
            } else if let textKey {
                Text(textKey)
            }
        }
        .font(.system(size: 11.5, weight: .black))
        .foregroundStyle(tint)
        .lineLimit(1)
        .minimumScaleFactor(0.74)
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background {
            Capsule(style: .continuous)
                .fill(tint.opacity(0.14))
                .overlay {
                    Capsule(style: .continuous)
                        .stroke(tint.opacity(0.22), lineWidth: 1)
                }
            }
    }
}

private struct EmptyProductState: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("purchases.emptyProducts.title")
                .font(.subheadline.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)

            Text("purchases.emptyProducts.body")
                .font(.caption.weight(.semibold))
                .foregroundStyle(FXTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(FXTheme.card, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        }
    }
}

private struct PaywallStatusBanner: View {
    let iconName: String
    var titleKey: LocalizedStringKey?
    var title: String?
    let tint: Color

    var body: some View {
        HStack(spacing: 11) {
            Image(systemName: iconName)
                .font(.subheadline.weight(.heavy))
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
        .padding(14)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(tint.opacity(0.22), lineWidth: 1)
        }
    }
}

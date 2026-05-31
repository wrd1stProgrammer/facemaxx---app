import Foundation
import RevenueCat

struct ProScanStatusResponse: Decodable {
    let appUserID: String
    let hasActiveProSubscription: Bool
    let freeTrialScanAvailable: Bool
    let proScansRemaining: Int
    let subscriptionProductID: String?
    let subscriptionScanLimit: Int?
    let subscriptionScansRemaining: Int?
    let subscriptionQuotaResetAt: String?
    let consumableProScansRemaining: Int?
    let canUseProScan: Bool

    enum CodingKeys: String, CodingKey {
        case appUserID = "app_user_id"
        case hasActiveProSubscription = "has_active_pro_subscription"
        case freeTrialScanAvailable = "free_trial_scan_available"
        case proScansRemaining = "pro_scans_remaining"
        case subscriptionProductID = "subscription_product_id"
        case subscriptionScanLimit = "subscription_scan_limit"
        case subscriptionScansRemaining = "subscription_scans_remaining"
        case subscriptionQuotaResetAt = "subscription_quota_reset_at"
        case consumableProScansRemaining = "consumable_pro_scans_remaining"
        case canUseProScan = "can_use_pro_scan"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        appUserID = try container.decode(String.self, forKey: .appUserID)
        hasActiveProSubscription = try container.decode(Bool.self, forKey: .hasActiveProSubscription)
        freeTrialScanAvailable = try container.decodeIfPresent(Bool.self, forKey: .freeTrialScanAvailable) ?? false
        proScansRemaining = try container.decode(Int.self, forKey: .proScansRemaining)
        subscriptionProductID = try container.decodeIfPresent(String.self, forKey: .subscriptionProductID)
        subscriptionScanLimit = try container.decodeIfPresent(Int.self, forKey: .subscriptionScanLimit)
        subscriptionScansRemaining = try container.decodeIfPresent(Int.self, forKey: .subscriptionScansRemaining)
        subscriptionQuotaResetAt = try container.decodeIfPresent(String.self, forKey: .subscriptionQuotaResetAt)
        consumableProScansRemaining = try container.decodeIfPresent(Int.self, forKey: .consumableProScansRemaining)
        canUseProScan = try container.decode(Bool.self, forKey: .canUseProScan)
    }
}

struct ReviewerProScanGrantRequest: Encodable {
    let code: String
}

struct ReviewerProScanGrantResponse: Decodable {
    let ok: Bool
    let creditsGranted: Int
    let status: ProScanStatusResponse

    enum CodingKeys: String, CodingKey {
        case ok
        case creditsGranted = "credits_granted"
        case status
    }
}

@MainActor
final class FacemaxxPurchaseService: ObservableObject {
    static let shared = FacemaxxPurchaseService()

    static let entitlementID = "pro"
    static let offeringID = "default"

    static let weeklyProductID = "facemaxx1wk"
    static let monthlyProductID = "facemaxx1mo"
    static let tenScanProductID = "facemaxx10scan"
    static let twentyScanProductID = "facemaxx20scan"
    static let fiftyScanProductID = "facemaxx50scan"

    @Published private(set) var isConfigured = false
    @Published private(set) var isLoading = false
    @Published private(set) var isPurchasing = false
    @Published private(set) var customerInfo: CustomerInfo?
    @Published private(set) var packages: [Package] = []
    @Published private(set) var proScanCredits: Int
    @Published private(set) var serverAllowsProScan = false
    @Published private(set) var serverHasActiveProSubscription = false
    @Published private(set) var serverFreeTrialScanAvailable = false
    @Published var statusMessage: String?
    @Published var errorMessage: String?

    private let creditStore = ProScanCreditStore()
    private var configuredAppUserID: String?
    private var lastRevenueCatServerSyncAt: Date?
    private let revenueCatServerSyncCooldown: TimeInterval = 5 * 60

    private init() {
        proScanCredits = creditStore.currentCredits
    }

    private var hasRevenueCatActiveEntitlement: Bool {
        customerInfo?.entitlements[Self.entitlementID]?.isActive == true
    }

    var hasActiveProSubscription: Bool {
        hasRevenueCatActiveEntitlement || serverHasActiveProSubscription
    }

    var canUseProScan: Bool {
        if AppReviewDemoMode.isEnabled {
            return true
        }

        return hasFreeTrialScanAvailable || proScanCredits > 0 || serverAllowsProScan
    }

    var hasFreeTrialScanAvailable: Bool {
        serverFreeTrialScanAvailable && proScanCredits <= 0 && !hasActiveProSubscription
    }

    var subscriptionPackages: [Package] {
        packages.filter { Self.subscriptionProductIDs.contains($0.storeProduct.productIdentifier) }
    }

    var scanPackPackages: [Package] {
        packages.filter { Self.scanPackCreditsByProductID[$0.storeProduct.productIdentifier] != nil }
    }

    var planSummaryText: String {
        planSummaryText(locale: .autoupdatingCurrent)
    }

    func planSummaryText(locale: Locale) -> String {
        if AppReviewDemoMode.isEnabled {
            return String(localized: "purchases.plan.reviewerDemo", locale: locale)
        }

        if hasActiveProSubscription || proScanCredits > 0 {
            return String(
                format: String(localized: "purchases.plan.scanCountFormat", locale: locale),
                proScanCredits
            )
        }

        return String(localized: "purchases.plan.free", locale: locale)
    }

    var scanBalanceText: String {
        scanBalanceText(locale: .autoupdatingCurrent)
    }

    func scanBalanceText(locale: Locale) -> String {
        if AppReviewDemoMode.isEnabled {
            return String(localized: "purchases.scanBalance.reviewerDemo", locale: locale)
        }

        if hasFreeTrialScanAvailable {
            return ""
        }

        guard proScanCredits > 0 || serverAllowsProScan else {
            return String(localized: "purchases.scanBalance.none", locale: locale)
        }

        return String(
            format: String(localized: "purchases.scanBalance.countFormat", locale: locale),
            proScanCredits
        )
    }

    func configure() async {
        await configure(appUserID: Self.currentAppUserID())
    }

    func configure(appUserID: String) async {
        guard let apiKey = Self.apiKey else {
            isConfigured = false
            errorMessage = String(localized: "purchases.error.missingAPIKey")
            return
        }

        do {
            if Purchases.isConfigured {
                if Purchases.shared.appUserID != appUserID {
                    let result = try await Purchases.shared.logIn(appUserID)
                    customerInfo = result.customerInfo
                }
            } else {
                #if DEBUG
                Purchases.logLevel = .debug
                #else
                Purchases.logLevel = .warn
                #endif
                Purchases.configure(withAPIKey: apiKey, appUserID: appUserID)
            }

            configuredAppUserID = appUserID
            isConfigured = true
            await refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refresh() async {
        guard Purchases.isConfigured else {
            await configure()
            return
        }

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            async let info = Purchases.shared.customerInfo()
            async let offerings = Purchases.shared.offerings()

            customerInfo = try await info
            let resolvedOfferings = try await offerings
            let offering = resolvedOfferings.offering(identifier: Self.offeringID) ?? resolvedOfferings.current
            packages = offering?.availablePackages.sorted(by: Self.packageSortPriority) ?? []
            await refreshServerStatus(syncIfRevenueCatActive: true)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refreshEntitlementsAndServerStatus() async {
        guard Purchases.isConfigured else {
            await configure()
            return
        }

        do {
            customerInfo = try await Purchases.shared.customerInfo()
        } catch {
            print("Facemaxx RevenueCat customer info refresh failed: \(error.localizedDescription)")
        }

        await refreshServerStatus(syncIfRevenueCatActive: true)
    }

    @discardableResult
    func purchase(_ package: Package) async -> Bool {
        if !Purchases.isConfigured {
            await configure()
            guard Purchases.isConfigured else { return false }
        }

        isPurchasing = true
        errorMessage = nil
        statusMessage = nil
        defer { isPurchasing = false }

        do {
            let result = try await Purchases.shared.purchase(package: package)
            customerInfo = result.customerInfo
            guard !result.userCancelled else { return false }

            let productID = package.storeProduct.productIdentifier
            if let credits = Self.scanPackCreditsByProductID[productID] {
                creditStore.add(credits)
                proScanCredits = creditStore.currentCredits
                statusMessage = String(
                    format: String(localized: "purchases.status.addedCreditsFormat"),
                    credits
                )
            } else {
                statusMessage = String(localized: "purchases.status.subscriptionActive")
            }

            await syncServerStatus()
            await refresh()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func restorePurchases() async {
        guard Purchases.isConfigured else {
            await configure()
            return
        }

        isLoading = true
        errorMessage = nil
        statusMessage = nil
        defer { isLoading = false }

        do {
            customerInfo = try await Purchases.shared.restorePurchases()
            statusMessage = String(localized: "purchases.status.restoreDone")
            await syncServerStatus()
            await refresh()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @discardableResult
    func redeemReviewerAccessCode(_ code: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        statusMessage = nil
        defer { isLoading = false }

        do {
            let response = try await FacemaxxAPIClient.shared.redeemReviewerProScanCode(code)
            updateServerStatus(response.status)
            statusMessage = response.creditsGranted > 0
                ? String(localized: "purchases.reviewerAccess.granted")
                : String(localized: "purchases.reviewerAccess.alreadyRedeemed")
            return true
        } catch let error as FacemaxxAPIError {
            if case let .server(statusCode, _) = error, statusCode == 403 {
                errorMessage = String(localized: "purchases.reviewerAccess.invalidCode")
            } else {
                errorMessage = error.localizedDescription
            }
            return false
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func consumeProScanIfNeeded() {
        guard !AppReviewDemoMode.isEnabled else { return }

        if hasFreeTrialScanAvailable {
            serverFreeTrialScanAvailable = false
            serverAllowsProScan = proScanCredits > 0
            return
        }

        guard proScanCredits > 0 else { return }
        creditStore.consumeOne()
        proScanCredits = creditStore.currentCredits
        serverAllowsProScan = proScanCredits > 0
    }

    func activateAppReviewDemoMode() {
        AppReviewDemoMode.activate()
        serverFreeTrialScanAvailable = false
        serverHasActiveProSubscription = false
        serverAllowsProScan = true
        creditStore.set(AppReviewDemoMode.unlimitedScanDisplayCount)
        proScanCredits = creditStore.currentCredits
        statusMessage = String(localized: "purchases.status.reviewerDemoActive")
        errorMessage = nil
    }

    func deactivateAppReviewDemoMode() {
        guard AppReviewDemoMode.isEnabled else { return }
        AppReviewDemoMode.deactivate()
        serverFreeTrialScanAvailable = false
        serverHasActiveProSubscription = false
        serverAllowsProScan = false
        creditStore.set(0)
        proScanCredits = creditStore.currentCredits
        statusMessage = nil
        errorMessage = nil
    }

    func refreshServerStatus(syncIfRevenueCatActive: Bool = false) async {
        if syncIfRevenueCatActive, hasRevenueCatActiveEntitlement, shouldSyncRevenueCatServerStatus() {
            await syncServerStatus()
            return
        }

        do {
            updateServerStatus(try await FacemaxxAPIClient.shared.fetchProScanStatus())
        } catch {
            print("Facemaxx pro scan status refresh failed: \(error.localizedDescription)")
        }
    }

    func syncServerStatus() async {
        lastRevenueCatServerSyncAt = Date()
        do {
            updateServerStatus(try await FacemaxxAPIClient.shared.syncProScanStatus())
        } catch {
            print("Facemaxx pro scan server sync failed: \(error.localizedDescription)")
        }
    }

    private func shouldSyncRevenueCatServerStatus(now: Date = Date()) -> Bool {
        guard let lastRevenueCatServerSyncAt else { return true }
        return now.timeIntervalSince(lastRevenueCatServerSyncAt) >= revenueCatServerSyncCooldown
    }

    private func updateServerStatus(_ status: ProScanStatusResponse) {
        serverHasActiveProSubscription = status.hasActiveProSubscription
        serverFreeTrialScanAvailable = status.freeTrialScanAvailable
        serverAllowsProScan = status.canUseProScan
        creditStore.set(status.proScansRemaining)
        proScanCredits = creditStore.currentCredits
    }

    func title(for package: Package) -> String {
        title(for: package, locale: .autoupdatingCurrent)
    }

    func title(for package: Package, locale: Locale) -> String {
        switch package.storeProduct.productIdentifier {
        case Self.weeklyProductID:
            return String(localized: "purchases.package.weekly", locale: locale)
        case Self.monthlyProductID:
            return String(localized: "purchases.package.monthly", locale: locale)
        case Self.tenScanProductID:
            return String(localized: "purchases.package.tenScans", locale: locale)
        case Self.twentyScanProductID:
            return String(localized: "purchases.package.twentyScans", locale: locale)
        case Self.fiftyScanProductID:
            return String(localized: "purchases.package.fiftyScans", locale: locale)
        default:
            return String(localized: "purchases.package.defaultTitle", locale: locale)
        }
    }

    func subtitle(for package: Package) -> String {
        subtitle(for: package, locale: .autoupdatingCurrent)
    }

    func subtitle(for package: Package, locale: Locale) -> String {
        switch package.storeProduct.productIdentifier {
        case Self.weeklyProductID:
            return String(localized: "purchases.package.weeklySubtitle", locale: locale)
        case Self.monthlyProductID:
            return String(localized: "purchases.package.monthlySubtitle", locale: locale)
        case Self.tenScanProductID, Self.twentyScanProductID, Self.fiftyScanProductID:
            return String(localized: "purchases.package.scanPackSubtitle", locale: locale)
        default:
            return String(localized: "purchases.package.defaultSubtitle", locale: locale)
        }
    }

    func scanQuota(for package: Package) -> Int? {
        switch package.storeProduct.productIdentifier {
        case Self.weeklyProductID:
            return 12
        case Self.monthlyProductID:
            return 50
        default:
            return Self.scanPackCreditsByProductID[package.storeProduct.productIdentifier]
        }
    }

    func quotaText(for package: Package) -> String? {
        quotaText(for: package, locale: .autoupdatingCurrent)
    }

    func quotaText(for package: Package, locale: Locale) -> String? {
        guard let scanQuota = scanQuota(for: package) else { return nil }
        return String(
            format: String(localized: "purchases.package.scanQuotaFormat", locale: locale),
            scanQuota
        )
    }

    func perScanPriceText(for package: Package) -> String? {
        perScanPriceText(for: package, locale: .autoupdatingCurrent)
    }

    func perScanPriceText(for package: Package, locale: Locale) -> String? {
        guard
            let scanQuota = scanQuota(for: package),
            scanQuota > 0,
            let priceFormatter = package.storeProduct.priceFormatter
        else {
            return nil
        }

        let unitPrice = NSDecimalNumber(decimal: package.storeProduct.price)
            .dividing(by: NSDecimalNumber(value: scanQuota))
        let formatter = priceFormatter.copy() as? NumberFormatter ?? priceFormatter
        let fractionDigits = max(0, formatter.maximumFractionDigits)
        formatter.minimumFractionDigits = min(formatter.minimumFractionDigits, fractionDigits)
        formatter.maximumFractionDigits = fractionDigits

        let roundedUnitPrice = unitPrice.rounding(accordingToBehavior: NSDecimalNumberHandler(
            roundingMode: .plain,
            scale: Int16(fractionDigits),
            raiseOnExactness: false,
            raiseOnOverflow: false,
            raiseOnUnderflow: false,
            raiseOnDivideByZero: false
        ))
        let localizedPrice = formatter.string(from: roundedUnitPrice) ?? package.storeProduct.localizedPriceString
        let reconstructedPrice = roundedUnitPrice.multiplying(by: NSDecimalNumber(value: scanQuota))
        if reconstructedPrice.compare(NSDecimalNumber(decimal: package.storeProduct.price)) == .orderedSame {
            return String(
                format: String(localized: "purchases.package.perScanFormat", locale: locale),
                localizedPrice
            )
        }

        return String(
            format: String(localized: "purchases.package.perScanApproxFormat", locale: locale),
            localizedPrice
        )
    }

    private static var apiKey: String? {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "FacemaxxRevenueCatAPIKey") as? String else {
            return nil
        }

        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !trimmed.contains("$(") else { return nil }
        return trimmed
    }

    static func currentAppUserID() -> String {
        if let userID = FacemaxxAuthSessionStore.load()?.userID?.trimmingCharacters(in: .whitespacesAndNewlines),
           !userID.isEmpty {
            return userID
        }

        return FacemaxxInstallIdentity.currentID.uuidString
    }

    private static let subscriptionProductIDs: Set<String> = [
        weeklyProductID,
        monthlyProductID
    ]

    private static let scanPackCreditsByProductID: [String: Int] = [
        tenScanProductID: 10,
        twentyScanProductID: 20,
        fiftyScanProductID: 50
    ]

    private static func packageSortPriority(_ left: Package, _ right: Package) -> Bool {
        priority(for: left.storeProduct.productIdentifier) < priority(for: right.storeProduct.productIdentifier)
    }

    private static func priority(for productID: String) -> Int {
        switch productID {
        case weeklyProductID: 10
        case monthlyProductID: 20
        case tenScanProductID: 30
        case twentyScanProductID: 40
        case fiftyScanProductID: 50
        default: 999
        }
    }
}

private final class ProScanCreditStore {
    private let creditsKey = "facemaxx.purchase.proScanCredits"
    private let initializedKey = "facemaxx.purchase.proScanCredits.initialized"
    private let zeroDefaultMigrationKey = "facemaxx.purchase.proScanCredits.zeroDefaultMigration"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if !defaults.bool(forKey: initializedKey) {
            defaults.set(0, forKey: creditsKey)
            defaults.set(true, forKey: initializedKey)
        }

        if !defaults.bool(forKey: zeroDefaultMigrationKey) {
            if defaults.integer(forKey: creditsKey) == 1 {
                defaults.set(0, forKey: creditsKey)
            }
            defaults.set(true, forKey: zeroDefaultMigrationKey)
        }
    }

    var currentCredits: Int {
        max(0, defaults.integer(forKey: creditsKey))
    }

    func add(_ count: Int) {
        defaults.set(currentCredits + max(0, count), forKey: creditsKey)
    }

    func set(_ count: Int) {
        defaults.set(max(0, count), forKey: creditsKey)
    }

    func consumeOne() {
        defaults.set(max(0, currentCredits - 1), forKey: creditsKey)
    }
}

import SwiftUI

@main
struct FacemaxxApp: App {
    @StateObject private var purchaseService = FacemaxxPurchaseService.shared

    var body: some Scene {
        WindowGroup {
            FacemaxxRootView()
                .environmentObject(purchaseService)
                .task {
                    await purchaseService.configure()
                }
        }
    }
}

import SwiftUI

enum FacemaxxTab: CaseIterable, Identifiable {
    case home
    case analyze
    case progress
    case profile

    var id: Self { self }

    var titleKey: LocalizedStringKey {
        switch self {
        case .home:
            "tab.home"
        case .analyze:
            "tab.analyze"
        case .progress:
            "tab.progress"
        case .profile:
            "tab.profile"
        }
    }

    var symbolName: String {
        switch self {
        case .home:
            "house.fill"
        case .analyze:
            "camera.fill"
        case .progress:
            "chart.line.uptrend.xyaxis"
        case .profile:
            "person.fill"
        }
    }
}

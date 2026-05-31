import SwiftUI

struct FacemaxxTabBar: View {
    @Binding var selectedTab: FacemaxxTab

    var body: some View {
        HStack(spacing: 5) {
            ForEach(FacemaxxTab.allCases) { tab in
                Button {
                    withAnimation(.smooth(duration: 0.22)) {
                        selectedTab = tab
                    }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.symbolName)
                            .font(.title3.weight(.heavy))
                            .frame(height: 24)

                        Text(tab.titleKey)
                            .font(.caption2.weight(.bold))
                    }
                    .foregroundStyle(selectedTab == tab ? FXTheme.textPrimary : FXTheme.textPrimary.opacity(0.92))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background {
                        if selectedTab == tab {
                            Capsule(style: .continuous)
                                .fill(FXTheme.cardElevated)
                        }
                    }
                    .contentShape(.capsule)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(tab.titleKey)
                .accessibilityAddTraits(selectedTab == tab ? .isSelected : [])
            }
        }
        .padding(6)
        .background {
            Capsule(style: .continuous)
                .fill(FXTheme.card.opacity(0.98))
        }
        .overlay {
            Capsule(style: .continuous)
                .stroke(FXTheme.cardStroke, lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.38), radius: 24, y: 10)
    }
}

import SwiftUI

struct UploadPhotoButton: View {
    let hasSelectedPhoto: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            label
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var label: some View {
        if #available(iOS 26.0, *) {
            baseLabel
                .foregroundStyle(FXTheme.textPrimary)
                .fxCapsuleSurface(
                    fill: Color.white.opacity(0.15),
                    stroke: Color.white.opacity(0.24),
                    usesLiquidGlass: true,
                    tint: FXTheme.cyan.opacity(0.18),
                    isInteractive: true,
                    shadowColor: FXTheme.cyan.opacity(0.10),
                    shadowRadius: 18,
                    shadowY: 7
                )
        } else {
            baseLabel
                .foregroundStyle(.black)
                .background {
                    Capsule(style: .continuous)
                        .fill(FXTheme.textPrimary)
                }
        }
    }

    private var baseLabel: some View {
        Label {
            Text(LocalizedStringKey(hasSelectedPhoto ? "analysis.uploadNewPhoto" : "analysis.uploadPhoto"))
        } icon: {
            Image(systemName: "camera.fill")
        }
        .font(.title3.weight(.bold))
        .frame(maxWidth: .infinity)
        .padding(.vertical, 22)
    }
}

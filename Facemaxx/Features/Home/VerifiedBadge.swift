import SwiftUI

struct VerifiedBadge: View {
    let scanCount: Int

    private var detailText: String {
        guard scanCount > 0 else {
            return String(localized: "home.badge.ready")
        }
        return String(format: String(localized: "home.badge.activeFormat"), scanCount)
    }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.seal.fill")
                .foregroundStyle(FXTheme.cyan)

            Text(detailText)
                .font(.caption.weight(.black))
        }
        .lineLimit(1)
        .minimumScaleFactor(0.76)
        .foregroundStyle(FXTheme.textPrimary)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background {
            Capsule(style: .continuous)
                .fill(FXTheme.pill.opacity(0.92))
        }
        .overlay {
            Capsule(style: .continuous)
                .stroke(Color.white.opacity(0.12), lineWidth: 1)
        }
    }
}

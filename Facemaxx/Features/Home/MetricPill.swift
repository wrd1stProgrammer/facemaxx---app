import SwiftUI

struct MetricPill: View {
    let iconName: String
    let value: String
    let titleKey: LocalizedStringKey
    let sourceKey: LocalizedStringKey?

    init(
        iconName: String,
        value: String,
        titleKey: LocalizedStringKey,
        sourceKey: LocalizedStringKey? = nil
    ) {
        self.iconName = iconName
        self.value = value
        self.titleKey = titleKey
        self.sourceKey = sourceKey
    }

    var body: some View {
        VStack(spacing: 7) {
            HStack(spacing: 6) {
                Image(systemName: iconName)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(FXTheme.textSecondary)

                Text(value)
                    .font(.subheadline.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
            }
            .frame(minWidth: 72)
            .padding(.vertical, 7)
            .background {
                Capsule(style: .continuous)
                    .fill(FXTheme.pill.opacity(0.88))
            }
            .overlay {
                Capsule(style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            }

            VStack(spacing: 2) {
                Text(titleKey)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(FXTheme.textMuted)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)

                if let sourceKey {
                    Text(sourceKey)
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(FXTheme.textSecondary.opacity(0.72))
                        .lineLimit(1)
                        .minimumScaleFactor(0.58)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

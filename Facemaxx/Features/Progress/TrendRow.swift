import SwiftUI

struct TrendRow: View {
    let iconName: String
    let titleKey: LocalizedStringKey
    var subtitleKey: LocalizedStringKey?
    var subtitleText: String?
    var valueText: String?
    var valueKey: LocalizedStringKey?
    let tint: Color

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Image(systemName: iconName)
                    .font(.system(size: 15.5, weight: .heavy))
                    .foregroundStyle(tint)

                subtitleView
            }

            Text(titleKey)
                .font(.system(size: 15.5, weight: .bold))
                .foregroundStyle(FXTheme.textSecondary)
                .lineLimit(1)
                .minimumScaleFactor(0.78)

            Spacer(minLength: 12)

            valueView
        }
        .padding(.horizontal, 13)
        .frame(height: 54)
        .background {
            Capsule(style: .continuous)
                .fill(FXTheme.cardElevated)
        }
        .overlay {
            Capsule(style: .continuous)
                .stroke(Color.white.opacity(0.035), lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private var subtitleView: some View {
        if let subtitleText {
            Text(subtitleText)
                .font(.system(size: 10.5, weight: .heavy))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.70)
        } else if let subtitleKey {
            Text(subtitleKey)
                .font(.system(size: 10.5, weight: .heavy))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.70)
        }
    }

    @ViewBuilder
    private var valueView: some View {
        if let valueText {
            Text(valueText)
                .font(.system(size: 15.5, weight: .heavy, design: .rounded))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.70)
        } else if let valueKey {
            Text(valueKey)
                .font(.system(size: 15.5, weight: .heavy, design: .rounded))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.70)
        }
    }
}

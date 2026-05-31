import SwiftUI

struct AnalysisOptionRow: View {
    let mode: AnalysisMode
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: mode.iconName)
                .font(.system(size: 25, weight: .heavy))
                .foregroundStyle(isSelected ? FXTheme.textPrimary : FXTheme.textPrimary.opacity(0.76))
                .frame(width: 34)

            Text(mode.titleKey)
                .font(.system(size: 21, weight: .heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.82)
                .layoutPriority(1)

            Spacer(minLength: 10)

            Text(mode.badgeKey)
                .font(.caption2.weight(.black))
                .tracking(1.1)
                .foregroundStyle(mode.badgeColor)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background {
                    Capsule(style: .continuous)
                        .fill(mode.badgeColor.opacity(mode.id == "proportions" ? 0.20 : 0.16))
                }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 20)
        .fxCapsuleSurface(
            fill: isSelected ? FXTheme.cardElevated : FXTheme.card,
            stroke: isSelected ? FXTheme.selectedStroke : Color.clear,
            strokeWidth: isSelected ? 2 : 0,
            usesLiquidGlass: true,
            tint: isSelected ? FXTheme.cyan.opacity(0.18) : FXTheme.glassTint,
            isInteractive: true,
            shadowColor: isSelected ? FXTheme.cyan.opacity(0.08) : .clear,
            shadowRadius: isSelected ? 18 : 0,
            shadowY: isSelected ? 6 : 0
        )
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

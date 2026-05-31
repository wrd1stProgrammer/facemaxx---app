import SwiftUI

struct StatValueColumn: View {
    let iconName: String
    let iconColor: Color
    let value: String
    let titleKey: LocalizedStringKey

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: iconName)
                .font(.body.weight(.bold))
                .foregroundStyle(iconColor)

            Text(value)
                .font(.headline.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
                .fixedSize(horizontal: true, vertical: false)

            Text(titleKey)
                .font(.caption2.weight(.bold))
                .foregroundStyle(FXTheme.textMuted)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
        }
        .frame(maxWidth: .infinity)
        .overlay(alignment: .trailing) {
            Rectangle()
                .fill(Color.white.opacity(0.08))
                .frame(width: 1, height: 42)
                .padding(.trailing, -0.5)
        }
    }
}

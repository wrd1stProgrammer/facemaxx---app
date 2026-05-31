import SwiftUI

struct ProgressMetricCard: View {
    let titleKey: LocalizedStringKey
    let valueText: String
    var suffixKey: LocalizedStringKey?
    let iconName: String
    let iconColor: Color

    var body: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 8) {
                Text(titleKey)
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(FXTheme.textSecondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)

                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(valueText)
                    if let suffixKey {
                        Text(suffixKey)
                    }
                }
                .font(.headline.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.74)
            }

            Spacer(minLength: 8)

            Image(systemName: iconName)
                .font(.title3.weight(.bold))
                .foregroundStyle(iconColor)
        }
        .padding(18)
        .frame(maxWidth: .infinity, minHeight: 94)
        .fxCard(cornerRadius: 28)
    }
}

import SwiftUI

struct NoScanTodayCard: View {
    let hasScanToday: Bool
    let startScanAction: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .center, spacing: 14) {
                Image(systemName: hasScanToday ? "checkmark.seal.fill" : "faceid")
                    .font(.system(size: 28, weight: .heavy))
                    .foregroundStyle(hasScanToday ? FXTheme.green : FXTheme.textPrimary)
                    .frame(width: 54, height: 54)
                    .background {
                        Circle()
                            .fill(FXTheme.cardElevated)
                    }

                VStack(alignment: .leading, spacing: 6) {
                    Text(LocalizedStringKey(hasScanToday ? "home.scanToday" : "home.noScanToday"))
                        .font(.headline.weight(.heavy))
                        .foregroundStyle(FXTheme.textPrimary)

                    Text(LocalizedStringKey(hasScanToday ? "home.scanTodaySubtitle" : "home.noScanSubtitle"))
                        .font(.callout.weight(.semibold))
                        .foregroundStyle(FXTheme.textSecondary)
                        .lineSpacing(2)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("home.nextStep.title")
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(FXTheme.textPrimary)

                HStack(spacing: 9) {
                    HomeActionChip(iconName: "camera.metering.center.weighted", titleKey: "home.nextStep.lighting")
                    HomeActionChip(iconName: "face.smiling", titleKey: "home.nextStep.expression")
                    HomeActionChip(iconName: "arrow.triangle.2.circlepath", titleKey: "home.nextStep.compare")
                }
            }

            Button(action: startScanAction) {
                Label {
                    Text(LocalizedStringKey(hasScanToday ? "home.scanAgain" : "home.startScan"))
                } icon: {
                    Image(systemName: "camera.fill")
                }
                .font(.subheadline.weight(.heavy))
                .foregroundStyle(.black)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background {
                    Capsule(style: .continuous)
                        .fill(FXTheme.cyan)
                }
            }
            .buttonStyle(.plain)
        }
        .padding(20)
        .fxCard(cornerRadius: 34)
    }
}

private struct HomeActionChip: View {
    let iconName: String
    let titleKey: LocalizedStringKey

    var body: some View {
        Label(titleKey, systemImage: iconName)
            .font(.system(size: 11, weight: .heavy))
            .foregroundStyle(FXTheme.textSecondary)
            .lineLimit(1)
            .minimumScaleFactor(0.74)
            .padding(.horizontal, 9)
            .padding(.vertical, 7)
            .frame(maxWidth: .infinity)
            .background {
                Capsule(style: .continuous)
                    .fill(FXTheme.cardElevated)
            }
    }
}

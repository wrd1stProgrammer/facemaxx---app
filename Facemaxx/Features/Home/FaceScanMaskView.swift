import SwiftUI

struct FaceScanMaskView: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            FXTheme.cardElevated.opacity(0.92),
                            FXTheme.card.opacity(0.78)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

            ScanGridBackground()
                .opacity(0.42)
                .padding(12)

            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .strokeBorder(
                    LinearGradient(
                        colors: [
                            FXTheme.premiumBlue.opacity(0.55),
                            FXTheme.green.opacity(0.35),
                            Color.white.opacity(0.10)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 1.4
                )
                .padding(10)

            VStack(spacing: 10) {
                ZStack {
                    Circle()
                        .fill(FXTheme.premiumBlue.opacity(0.18))
                    Circle()
                        .strokeBorder(FXTheme.premiumBlue.opacity(0.42), lineWidth: 1)

                    Image(systemName: "camera.viewfinder")
                        .font(.system(size: 25, weight: .black))
                        .foregroundStyle(FXTheme.textPrimary)
                }
                .frame(width: 54, height: 54)

                HStack(spacing: 5) {
                    ForEach(0..<3, id: \.self) { index in
                        Capsule(style: .continuous)
                            .fill(index == 0 ? FXTheme.green : Color.white.opacity(0.20))
                            .frame(width: index == 0 ? 18 : 10, height: 5)
                    }
                }
            }
        }
        .frame(width: 112, height: 112)
        .fxCard(cornerRadius: 26, fill: FXTheme.cardElevated.opacity(0.62), stroke: Color.white.opacity(0.08))
        .accessibilityLabel("home.faceMaskAccessibility")
    }
}

private struct ScanGridBackground: View {
    var body: some View {
        Canvas { context, size in
            let step = size.width / 4
            for index in 1..<4 {
                let offset = CGFloat(index) * step

                var vertical = Path()
                vertical.move(to: CGPoint(x: offset, y: 0))
                vertical.addLine(to: CGPoint(x: offset, y: size.height))
                context.stroke(vertical, with: .color(Color.white.opacity(0.18)), lineWidth: 0.7)

                var horizontal = Path()
                horizontal.move(to: CGPoint(x: 0, y: offset))
                horizontal.addLine(to: CGPoint(x: size.width, y: offset))
                context.stroke(horizontal, with: .color(Color.white.opacity(0.18)), lineWidth: 0.7)
            }

            var scanLine = Path()
            scanLine.move(to: CGPoint(x: 0, y: size.height * 0.62))
            scanLine.addLine(to: CGPoint(x: size.width, y: size.height * 0.62))
            context.stroke(scanLine, with: .color(FXTheme.cyan.opacity(0.44)), lineWidth: 1.2)
        }
    }
}

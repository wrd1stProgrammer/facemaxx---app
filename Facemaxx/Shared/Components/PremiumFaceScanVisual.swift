import SwiftUI

struct PremiumFaceScanVisual: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var progress: Double
    var isActive: Bool
    var accentColor: Color = FXTheme.cyan
    var showsOuterPanel = true

    var body: some View {
        TimelineView(.animation) { timeline in
            let time = isActive && !reduceMotion ? timeline.date.timeIntervalSinceReferenceDate : 0

            GeometryReader { proxy in
                let side = min(proxy.size.width, proxy.size.height)
                let clampedProgress = progress.clamped(to: 0...1)

                ZStack {
                    if showsOuterPanel {
                        RoundedRectangle(cornerRadius: side * 0.18, style: .continuous)
                            .fill(
                                LinearGradient(
                                    colors: [
                                        Color(red: 0.06, green: 0.09, blue: 0.11),
                                        Color(red: 0.025, green: 0.030, blue: 0.036)
                                    ],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .overlay {
                                RoundedRectangle(cornerRadius: side * 0.18, style: .continuous)
                                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
                            }
                    }

                    Circle()
                        .fill(
                            RadialGradient(
                                colors: [
                                    accentColor.opacity(0.18),
                                    accentColor.opacity(0.05),
                                    .clear
                                ],
                                center: .center,
                                startRadius: side * 0.10,
                                endRadius: side * 0.54
                            )
                        )
                        .frame(width: side * 0.88, height: side * 0.88)
                        .opacity(0.86)

                    PremiumScanRing(
                        progress: clampedProgress,
                        time: time,
                        accentColor: accentColor
                    )
                    .frame(width: side * 0.76, height: side * 0.76)

                    PremiumDepthLens(
                        progress: clampedProgress,
                        time: time,
                        accentColor: accentColor
                    )
                    .frame(width: side * 0.58, height: side * 0.58)

                    PremiumScanCorners(time: time, accentColor: accentColor)
                        .frame(width: side * 0.58, height: side * 0.58)
                }
                .frame(width: proxy.size.width, height: proxy.size.height)
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

private struct PremiumScanRing: View {
    let progress: Double
    let time: TimeInterval
    let accentColor: Color

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.white.opacity(0.055), lineWidth: 18)

            Circle()
                .trim(from: 0, to: progress)
                .stroke(
                    AngularGradient(
                        colors: [
                            accentColor.opacity(0.32),
                            accentColor,
                            Color.white.opacity(0.82),
                            accentColor.opacity(0.48)
                        ],
                        center: .center
                    ),
                    style: StrokeStyle(lineWidth: 18, lineCap: .round)
                )
                .rotationEffect(.degrees(-92))

            Circle()
                .trim(from: 0.06, to: 0.24)
                .stroke(accentColor.opacity(0.78), style: StrokeStyle(lineWidth: 5, lineCap: .round))
                .rotationEffect(.degrees(time * 42))

            Circle()
                .trim(from: 0.56, to: 0.72)
                .stroke(Color.white.opacity(0.30), style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(-time * 28))
        }
    }
}

private struct PremiumDepthLens: View {
    let progress: Double
    let time: TimeInterval
    let accentColor: Color

    var body: some View {
        GeometryReader { proxy in
            let size = proxy.size
            let sweep = CGFloat((sin(time * 1.34) + 1) / 2)
            let scanX = size.width * (0.14 + sweep * 0.72)
            let center = CGPoint(x: size.width / 2, y: size.height / 2)

            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [
                                Color.white.opacity(0.10),
                                accentColor.opacity(0.07),
                                Color.black.opacity(0.18)
                            ],
                            center: .center,
                            startRadius: 0,
                            endRadius: size.width * 0.48
                        )
                    )

                contourRings(in: size, time: time)

                depthDots(in: size, time: time)

                scanRibbon(in: size, scanX: scanX)

                PremiumLensNeedle(progress: progress, time: time, accentColor: accentColor)
                    .frame(width: size.width * 0.72, height: size.height * 0.72)
                    .position(center)
            }
            .clipShape(Circle())
            .overlay {
                Circle()
                    .stroke(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(0.22),
                                accentColor.opacity(0.52),
                                Color.white.opacity(0.07)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1.2
                    )
            }
            .overlay {
                Circle()
                    .stroke(Color.black.opacity(0.38), lineWidth: 10)
                    .blur(radius: 11)
                    .offset(y: size.height * 0.05)
                    .mask(Circle().stroke(lineWidth: 16))
            }
        }
    }

    private func contourRings(in size: CGSize, time: TimeInterval) -> some View {
        ZStack {
            ForEach(0..<5, id: \.self) { index in
                let scale = 0.36 + CGFloat(index) * 0.14
                let alpha = 0.24 - Double(index) * 0.028
                let drift = CGFloat(sin(time * 0.65 + Double(index) * 0.9)) * 0.012

                Circle()
                    .stroke(Color.white.opacity(alpha), lineWidth: 1)
                    .frame(width: size.width * (scale + drift), height: size.height * (scale + drift))
            }
        }
    }

    private func depthDots(in size: CGSize, time: TimeInterval) -> some View {
        ZStack {
            ForEach(0..<9, id: \.self) { row in
                ForEach(0..<9, id: \.self) { column in
                    let xRatio = 0.14 + CGFloat(column) * 0.09
                    let yRatio = 0.14 + CGFloat(row) * 0.09
                    let xDistance = abs(xRatio - 0.50)
                    let yDistance = abs(yRatio - 0.50)
                    let distance = sqrt(xDistance * xDistance + yDistance * yDistance)
                    let isInsideLens = distance < 0.42
                    let phase = time * 2.1 + Double(row * 4 + column) * 0.33
                    let alpha = 0.16 + 0.34 * (sin(phase) + 1) / 2
                    let dotSize = 3.2 + CGFloat(sin(phase * 0.72) + 1) * 1.0

                    if isInsideLens {
                        RoundedRectangle(cornerRadius: dotSize / 2, style: .continuous)
                            .fill(accentColor.opacity(alpha))
                            .frame(width: dotSize, height: dotSize)
                            .position(x: size.width * xRatio, y: size.height * yRatio)
                    }
                }
            }
        }
    }

    private func scanRibbon(in size: CGSize, scanX: CGFloat) -> some View {
        ZStack {
            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [
                            .clear,
                            accentColor.opacity(0.06),
                            accentColor.opacity(0.38),
                            accentColor.opacity(0.06),
                            .clear
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .frame(width: size.width * 0.18, height: size.height * 1.12)
                .rotationEffect(.degrees(-12))
                .position(x: scanX, y: size.height / 2)

            Capsule(style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [.clear, Color.white.opacity(0.78), .clear],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .frame(width: 1.4, height: size.height * 0.76)
                .rotationEffect(.degrees(-12))
                .position(x: scanX + size.width * 0.03, y: size.height / 2)
        }
    }
}

private struct PremiumLensNeedle: View {
    let progress: Double
    let time: TimeInterval
    let accentColor: Color

    var body: some View {
        ZStack {
            ForEach(0..<4, id: \.self) { index in
                let rotation = Double(index) * 90 + time * 18
                Capsule(style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [
                                .clear,
                                accentColor.opacity(index == 0 ? 0.58 : 0.20)
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: 44, height: index == 0 ? 2.4 : 1.2)
                    .offset(x: 22)
                    .rotationEffect(.degrees(rotation))
            }

            Circle()
                .fill(Color.white.opacity(0.92))
                .frame(width: 5.5, height: 5.5)
                .shadow(color: accentColor.opacity(0.42), radius: 7)
                .offset(x: 44)
                .rotationEffect(.degrees(-90 + progress * 360 + sin(time * 0.8) * 5))
        }
    }
}

private struct PremiumScanCorners: View {
    let time: TimeInterval
    let accentColor: Color

    var body: some View {
        GeometryReader { proxy in
            let size = proxy.size
            let inset = size.width * 0.08
            let length = size.width * 0.14
            let alpha = 0.55 + 0.25 * (sin(time * 2.4) + 1) / 2

            Path { path in
                path.move(to: CGPoint(x: inset + length, y: inset))
                path.addLine(to: CGPoint(x: inset, y: inset))
                path.addLine(to: CGPoint(x: inset, y: inset + length))

                path.move(to: CGPoint(x: size.width - inset - length, y: inset))
                path.addLine(to: CGPoint(x: size.width - inset, y: inset))
                path.addLine(to: CGPoint(x: size.width - inset, y: inset + length))

                path.move(to: CGPoint(x: inset, y: size.height - inset - length))
                path.addLine(to: CGPoint(x: inset, y: size.height - inset))
                path.addLine(to: CGPoint(x: inset + length, y: size.height - inset))

                path.move(to: CGPoint(x: size.width - inset - length, y: size.height - inset))
                path.addLine(to: CGPoint(x: size.width - inset, y: size.height - inset))
                path.addLine(to: CGPoint(x: size.width - inset, y: size.height - inset - length))
            }
            .stroke(accentColor.opacity(alpha), style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
        }
    }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}

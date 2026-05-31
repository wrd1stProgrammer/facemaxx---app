import SwiftUI

struct FXCardStyle: ViewModifier {
    let cornerRadius: CGFloat
    let fill: Color
    let stroke: Color
    let strokeWidth: CGFloat
    let usesLiquidGlass: Bool

    func body(content: Content) -> some View {
        content.modifier(
            FXRoundedSurfaceStyle(
                cornerRadius: cornerRadius,
                fill: fill,
                stroke: stroke,
                strokeWidth: strokeWidth,
                usesLiquidGlass: usesLiquidGlass,
                tint: FXTheme.glassTint,
                isInteractive: false,
                shadowColor: .black.opacity(0.16),
                shadowRadius: 18,
                shadowY: 8
            )
        )
    }
}

private struct FXRoundedSurfaceStyle: ViewModifier {
    let cornerRadius: CGFloat
    let fill: Color
    let stroke: Color
    let strokeWidth: CGFloat
    let usesLiquidGlass: Bool
    let tint: Color
    let isInteractive: Bool
    let shadowColor: Color
    let shadowRadius: CGFloat
    let shadowY: CGFloat

    @ViewBuilder
    func body(content: Content) -> some View {
        if usesLiquidGlass, #available(iOS 26.0, *) {
            content
                .background {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .fill(fill.opacity(0.72))
                }
                .glassEffect(
                    .regular.tint(tint).interactive(isInteractive),
                    in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .stroke(stroke.opacity(1.45), lineWidth: strokeWidth)
                }
                .shadow(color: shadowColor, radius: shadowRadius, y: shadowY)
        } else {
            legacy(content)
        }
    }

    private func legacy(_ content: Content) -> some View {
        content
            .background {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(fill)
            }
            .overlay {
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(stroke, lineWidth: strokeWidth)
            }
    }
}

private struct FXCapsuleSurfaceStyle: ViewModifier {
    let fill: Color
    let stroke: Color
    let strokeWidth: CGFloat
    let usesLiquidGlass: Bool
    let tint: Color
    let isInteractive: Bool
    let shadowColor: Color
    let shadowRadius: CGFloat
    let shadowY: CGFloat

    @ViewBuilder
    func body(content: Content) -> some View {
        if usesLiquidGlass, #available(iOS 26.0, *) {
            content
                .background {
                    Capsule(style: .continuous)
                        .fill(fill.opacity(0.76))
                }
                .glassEffect(
                    .regular.tint(tint).interactive(isInteractive),
                    in: Capsule(style: .continuous)
                )
                .overlay {
                    Capsule(style: .continuous)
                        .stroke(stroke.opacity(1.3), lineWidth: strokeWidth)
                }
                .shadow(color: shadowColor, radius: shadowRadius, y: shadowY)
        } else {
            legacy(content)
        }
    }

    private func legacy(_ content: Content) -> some View {
        content
            .background {
                Capsule(style: .continuous)
                    .fill(fill)
            }
            .overlay {
                Capsule(style: .continuous)
                    .stroke(stroke, lineWidth: strokeWidth)
            }
    }
}

extension View {
    func fxCard(
        cornerRadius: CGFloat = 34,
        fill: Color = FXTheme.card,
        stroke: Color = FXTheme.cardStroke,
        strokeWidth: CGFloat = 1,
        usesLiquidGlass: Bool = false
    ) -> some View {
        modifier(
            FXCardStyle(
                cornerRadius: cornerRadius,
                fill: fill,
                stroke: stroke,
                strokeWidth: strokeWidth,
                usesLiquidGlass: usesLiquidGlass
            )
        )
    }

    func fxCapsuleSurface(
        fill: Color,
        stroke: Color = FXTheme.cardStroke,
        strokeWidth: CGFloat = 1,
        usesLiquidGlass: Bool = false,
        tint: Color = FXTheme.glassTint,
        isInteractive: Bool = false,
        shadowColor: Color = .clear,
        shadowRadius: CGFloat = 0,
        shadowY: CGFloat = 0
    ) -> some View {
        modifier(
            FXCapsuleSurfaceStyle(
                fill: fill,
                stroke: stroke,
                strokeWidth: strokeWidth,
                usesLiquidGlass: usesLiquidGlass,
                tint: tint,
                isInteractive: isInteractive,
                shadowColor: shadowColor,
                shadowRadius: shadowRadius,
                shadowY: shadowY
            )
        )
    }
}

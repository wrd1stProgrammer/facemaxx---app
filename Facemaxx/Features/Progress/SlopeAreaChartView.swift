import SwiftUI

struct SlopeAreaChartView: View {
    let points: [HomeProgressChartPoint]

    @State private var selectedPointID: UUID?
    @State private var dismissSelectionTask: Task<Void, Never>?

    var body: some View {
        GeometryReader { proxy in
            let geometry = ProgressChartGeometry(points: points, size: proxy.size)
            let selectedPoint = geometry.renderPoints.first { $0.source.id == selectedPointID }

            ZStack(alignment: .topLeading) {
                Canvas { context, size in
                    drawChart(in: &context, size: size, geometry: geometry, selectedPoint: selectedPoint)
                }

                if points.isEmpty {
                    ProgressChartEmptyState()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .allowsHitTesting(false)
                }

                if let selectedPoint {
                    ChartTooltip(point: selectedPoint.source)
                        .position(tooltipPosition(for: selectedPoint.location, in: proxy.size))
                        .transition(.opacity.combined(with: .scale(scale: 0.94)))
                }
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        dismissSelectionTask?.cancel()
                        selectedPointID = geometry.nearestPoint(to: value.location)?.source.id
                    }
                    .onEnded { _ in
                        dismissSelectionTask?.cancel()
                        dismissSelectionTask = Task {
                            try? await Task.sleep(nanoseconds: 1_200_000_000)
                            await MainActor.run {
                                selectedPointID = nil
                            }
                        }
                    }
            )
            .animation(.smooth(duration: 0.18), value: selectedPointID)
        }
        .accessibilityLabel("progress.chartAccessibility")
    }

    private func drawChart(
        in context: inout GraphicsContext,
        size: CGSize,
        geometry: ProgressChartGeometry,
        selectedPoint: ProgressChartRenderPoint?
    ) {
        let chartRect = geometry.chartRect

        for index in 0...5 {
            let y = chartRect.minY + chartRect.height * CGFloat(index) / 5
            var grid = Path()
            grid.move(to: CGPoint(x: chartRect.minX, y: y))
            grid.addLine(to: CGPoint(x: chartRect.maxX, y: y))
            context.stroke(grid, with: .color(Color.white.opacity(0.07)), lineWidth: 1)

            let score = 100 - index * 20
            context.draw(
                Text("\(score)")
                    .font(.caption2.weight(.semibold))
                    .foregroundColor(FXTheme.textMuted.opacity(0.7)),
                at: CGPoint(x: chartRect.minX - 18, y: y),
                anchor: .trailing
            )
        }

        for index in 0...3 {
            let x = chartRect.minX + chartRect.width * CGFloat(index) / 3
            var grid = Path()
            grid.move(to: CGPoint(x: x, y: chartRect.minY))
            grid.addLine(to: CGPoint(x: x, y: chartRect.maxY))
            context.stroke(grid, with: .color(Color.white.opacity(0.035)), lineWidth: 1)
        }

        guard geometry.renderPoints.count >= 2 else {
            if let point = geometry.renderPoints.first {
                drawPoint(point.location, in: &context, highlighted: true)
                drawDateLabels(in: &context, geometry: geometry)
            }
            return
        }

        let points = geometry.renderPoints.map(\.location)
        let line = smoothedPath(points: points)
        var area = Path()
        area.move(to: CGPoint(x: points[0].x, y: chartRect.maxY))
        appendSmoothedSegments(to: &area, points: points)
        area.addLine(to: CGPoint(x: points.last?.x ?? chartRect.maxX, y: chartRect.maxY))
        area.closeSubpath()

        context.fill(area, with: .linearGradient(
            Gradient(colors: [
                FXTheme.blue.opacity(0.42),
                FXTheme.cyan.opacity(0.16),
                FXTheme.cyan.opacity(0.03)
            ]),
            startPoint: CGPoint(x: chartRect.minX, y: chartRect.minY),
            endPoint: CGPoint(x: chartRect.minX, y: chartRect.maxY)
        ))

        context.stroke(line, with: .color(FXTheme.cyan.opacity(0.16)), lineWidth: 9)
        context.stroke(line, with: .linearGradient(
            Gradient(colors: [FXTheme.cyan, FXTheme.blue]),
            startPoint: CGPoint(x: chartRect.minX, y: chartRect.minY),
            endPoint: CGPoint(x: chartRect.maxX, y: chartRect.minY)
        ), lineWidth: 3)

        if let selectedPoint {
            var verticalRule = Path()
            verticalRule.move(to: CGPoint(x: selectedPoint.location.x, y: chartRect.minY))
            verticalRule.addLine(to: CGPoint(x: selectedPoint.location.x, y: chartRect.maxY))
            context.stroke(verticalRule, with: .color(Color.white.opacity(0.18)), style: StrokeStyle(lineWidth: 1, dash: [4, 5]))
        }

        for point in geometry.renderPoints {
            drawPoint(point.location, in: &context, highlighted: point.source.id == selectedPoint?.source.id)
        }

        drawDateLabels(in: &context, geometry: geometry)
    }

    private func drawPoint(_ point: CGPoint, in context: inout GraphicsContext, highlighted: Bool) {
        let outerRadius: CGFloat = highlighted ? 8 : 5.5
        let innerRadius: CGFloat = highlighted ? 4 : 2.7
        context.fill(
            Path(ellipseIn: CGRect(
                x: point.x - outerRadius,
                y: point.y - outerRadius,
                width: outerRadius * 2,
                height: outerRadius * 2
            )),
            with: .color(FXTheme.blue.opacity(highlighted ? 0.34 : 0.20))
        )
        context.fill(
            Path(ellipseIn: CGRect(
                x: point.x - innerRadius,
                y: point.y - innerRadius,
                width: innerRadius * 2,
                height: innerRadius * 2
            )),
            with: .color(.white.opacity(0.96))
        )
    }

    private func drawDateLabels(in context: inout GraphicsContext, geometry: ProgressChartGeometry) {
        guard let first = geometry.renderPoints.first, let last = geometry.renderPoints.last else { return }
        let formatter = ProgressChartDateFormatter.short
        context.draw(
            Text(formatter.string(from: first.source.createdAt))
                .font(.caption2.weight(.bold))
                .foregroundColor(FXTheme.textMuted.opacity(0.7)),
            at: CGPoint(x: geometry.chartRect.minX, y: geometry.chartRect.maxY + 22),
            anchor: .leading
        )
        context.draw(
            Text(formatter.string(from: last.source.createdAt))
                .font(.caption2.weight(.bold))
                .foregroundColor(FXTheme.textMuted.opacity(0.7)),
            at: CGPoint(x: geometry.chartRect.maxX, y: geometry.chartRect.maxY + 22),
            anchor: .trailing
        )
    }

    private func tooltipPosition(for point: CGPoint, in size: CGSize) -> CGPoint {
        let tooltipWidth: CGFloat = 122
        let x = point.x.clamped(to: (tooltipWidth / 2 + 8)...(size.width - tooltipWidth / 2 - 8))
        let y = max(24, point.y - 42)
        return CGPoint(x: x, y: y)
    }

    private func smoothedPath(points: [CGPoint]) -> Path {
        var path = Path()
        appendSmoothedSegments(to: &path, points: points)
        return path
    }

    private func appendSmoothedSegments(to path: inout Path, points: [CGPoint]) {
        guard let first = points.first else { return }
        path.move(to: first)
        guard points.count > 2 else {
            points.dropFirst().forEach { path.addLine(to: $0) }
            return
        }

        for index in 1..<points.count {
            let previous = points[index - 1]
            let current = points[index]
            let midpoint = CGPoint(x: (previous.x + current.x) / 2, y: (previous.y + current.y) / 2)
            path.addQuadCurve(to: midpoint, control: previous)
            if index == points.count - 1 {
                path.addQuadCurve(to: current, control: current)
            }
        }
    }
}

private struct ProgressChartEmptyState: View {
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(FXTheme.textMuted.opacity(0.72))

            VStack(spacing: 7) {
                Text("progress.chart.emptyTitle")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(FXTheme.textSecondary)

                Text("progress.chart.emptyBody")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(FXTheme.textMuted)
                    .multilineTextAlignment(.center)
                    .lineSpacing(2)
            }
        }
        .padding(.horizontal, 24)
    }
}

private struct ChartTooltip: View {
    let point: HomeProgressChartPoint

    var body: some View {
        VStack(spacing: 2) {
            Text(ProgressChartDateFormatter.tooltip.string(from: point.createdAt))
                .font(.caption2.weight(.semibold))
                .foregroundStyle(FXTheme.textSecondary)
            Text(String(format: "%.1f", Double(point.score100) / 10))
                .font(.caption.weight(.heavy))
                .foregroundStyle(FXTheme.textPrimary)
        }
        .frame(width: 122)
        .padding(.vertical, 8)
        .background {
            Capsule(style: .continuous)
                .fill(Color.black.opacity(0.74))
                .stroke(Color.white.opacity(0.16), lineWidth: 1)
        }
    }
}

private struct ProgressChartGeometry {
    let points: [HomeProgressChartPoint]
    let size: CGSize

    var chartRect: CGRect {
        CGRect(
            x: 48,
            y: 28,
            width: max(0, size.width - 58),
            height: max(0, size.height - 64)
        )
    }

    var renderPoints: [ProgressChartRenderPoint] {
        let source = points.sorted { $0.createdAt < $1.createdAt }
        guard !source.isEmpty else { return [] }
        let usableRect = chartRect.insetBy(dx: 4, dy: 14)

        return source.enumerated().map { index, point in
            let xProgress = source.count == 1
                ? 0.5
                : CGFloat(index) / CGFloat(source.count - 1)
            let yProgress = CGFloat(point.score100.clamped(to: 0...100)) / 100
            let location = CGPoint(
                x: usableRect.minX + usableRect.width * xProgress,
                y: usableRect.maxY - usableRect.height * yProgress
            )
            return ProgressChartRenderPoint(source: point, location: location)
        }
    }

    func nearestPoint(to location: CGPoint) -> ProgressChartRenderPoint? {
        renderPoints.min { lhs, rhs in
            lhs.location.distance(to: location) < rhs.location.distance(to: location)
        }
    }
}

private struct ProgressChartRenderPoint {
    let source: HomeProgressChartPoint
    let location: CGPoint
}

private enum ProgressChartDateFormatter {
    static let short: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = .autoupdatingCurrent
        formatter.setLocalizedDateFormatFromTemplate("Md")
        return formatter
    }()

    static let tooltip: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = .autoupdatingCurrent
        formatter.setLocalizedDateFormatFromTemplate("MMMd")
        return formatter
    }()
}

private extension CGPoint {
    func distance(to point: CGPoint) -> CGFloat {
        hypot(x - point.x, y - point.y)
    }
}

private extension Int {
    func clamped(to range: ClosedRange<Int>) -> Int {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

private extension CGFloat {
    func clamped(to range: ClosedRange<CGFloat>) -> CGFloat {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

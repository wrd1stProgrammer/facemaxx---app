import SwiftUI
import UIKit

struct SquarePhotoCropResult {
    let image: UIImage
    let scanOverlayImage: UIImage?
    let originalImage: UIImage
    let originalScanOverlayImage: UIImage?
    let preferredRegion: CGRect?
}

struct SquarePhotoCropView: View {
    let image: UIImage
    let scanOverlayImage: UIImage?
    let onCancel: () -> Void
    let onChoose: (SquarePhotoCropResult) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var committedScale: CGFloat = 1
    @GestureState private var gestureScale: CGFloat = 1
    @State private var committedOffset: CGSize = .zero
    @GestureState private var gestureOffset: CGSize = .zero

    private var displayImage: UIImage {
        image.facemaxxNormalizedUp()
    }

    private var displayOverlayImage: UIImage? {
        scanOverlayImage?.facemaxxNormalizedUp()
    }

    private var currentScale: CGFloat {
        (committedScale * gestureScale).clamped(to: 1...4)
    }

    private var currentOffset: CGSize {
        CGSize(
            width: committedOffset.width + gestureOffset.width,
            height: committedOffset.height + gestureOffset.height
        )
    }

    var body: some View {
        GeometryReader { proxy in
            let layout = SquarePhotoCropLayout(
                containerSize: proxy.size,
                imageSize: displayImage.size,
                scale: currentScale,
                offset: currentOffset
            )

            ZStack {
                Color.black.ignoresSafeArea()

                ZStack {
                    Image(uiImage: displayImage)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: layout.imageFrame.width, height: layout.imageFrame.height)
                        .position(x: layout.imageFrame.midX, y: layout.imageFrame.midY)
                        .animation(.smooth(duration: reduceMotion ? 0.01 : 0.18), value: committedScale)
                        .animation(.smooth(duration: reduceMotion ? 0.01 : 0.18), value: committedOffset)

                    cropChrome(cropRect: layout.cropRect, containerSize: proxy.size)
                }
                .contentShape(Rectangle())
                .gesture(cropGesture(layout: layout))
            }
            .overlay(alignment: .bottom) {
                bottomActionBar(layout: layout, bottomInset: proxy.safeAreaInsets.bottom)
            }
        }
    }

    private func bottomActionBar(layout: SquarePhotoCropLayout, bottomInset: CGFloat) -> some View {
        LinearGradient(
            colors: [
                Color.black.opacity(0),
                Color.black.opacity(0.76),
                Color.black.opacity(0.96)
            ],
            startPoint: .top,
            endPoint: .bottom
        )
        .frame(height: 142 + bottomInset)
        .overlay(alignment: .bottom) {
            HStack {
                Button(action: onCancel) {
                    Text("common.cancel")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 22)
                        .padding(.vertical, 14)
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    onChoose(layout.selectionResult(
                        image: displayImage,
                        overlayImage: displayOverlayImage
                    ))
                } label: {
                    Text("common.choose")
                        .font(.body.weight(.medium))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 22)
                        .padding(.vertical, 14)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 12)
            .padding(.bottom, max(bottomInset, 8) + 6)
        }
        .ignoresSafeArea(edges: .bottom)
    }

    @ViewBuilder
    private func cropChrome(cropRect: CGRect, containerSize: CGSize) -> some View {
        Path { path in
            path.addRect(CGRect(origin: .zero, size: containerSize).insetBy(dx: -200, dy: -200))
            path.addRect(cropRect)
        }
        .fill(Color.black.opacity(0.58), style: FillStyle(eoFill: true))
        .allowsHitTesting(false)

        Rectangle()
            .stroke(Color.white.opacity(0.78), lineWidth: 1.2)
            .frame(width: cropRect.width, height: cropRect.height)
            .position(x: cropRect.midX, y: cropRect.midY)
            .allowsHitTesting(false)

        Path { path in
            for index in 1...2 {
                let x = cropRect.minX + cropRect.width * CGFloat(index) / 3
                path.move(to: CGPoint(x: x, y: cropRect.minY))
                path.addLine(to: CGPoint(x: x, y: cropRect.maxY))

                let y = cropRect.minY + cropRect.height * CGFloat(index) / 3
                path.move(to: CGPoint(x: cropRect.minX, y: y))
                path.addLine(to: CGPoint(x: cropRect.maxX, y: y))
            }
        }
        .stroke(Color.white.opacity(0.18), lineWidth: 1)
        .allowsHitTesting(false)
    }

    private func cropGesture(layout: SquarePhotoCropLayout) -> some Gesture {
        SimultaneousGesture(
            DragGesture(minimumDistance: 3)
                .updating($gestureOffset) { value, state, _ in
                    state = value.translation
                }
                .onEnded { value in
                    let nextOffset = CGSize(
                        width: committedOffset.width + value.translation.width,
                        height: committedOffset.height + value.translation.height
                    )
                    committedOffset = layout.clampedOffset(nextOffset)
                },
            MagnificationGesture()
                .updating($gestureScale) { value, state, _ in
                    state = value
                }
                .onEnded { value in
                    committedScale = (committedScale * value).clamped(to: 1...4)
                    let refreshedLayout = SquarePhotoCropLayout(
                        containerSize: layout.containerSize,
                        imageSize: layout.imageSize,
                        scale: committedScale,
                        offset: committedOffset
                    )
                    committedOffset = refreshedLayout.clampedOffset(committedOffset)
                }
        )
    }
}

private struct SquarePhotoCropLayout {
    let containerSize: CGSize
    let imageSize: CGSize
    let scale: CGFloat
    let offset: CGSize

    var cropSide: CGFloat {
        let horizontalInset: CGFloat = 0
        let controlReserve: CGFloat = 206
        let availableWidth = max(220, containerSize.width - horizontalInset)
        let availableHeight = max(220, containerSize.height - controlReserve)
        return min(availableWidth, availableHeight)
    }

    var cropRect: CGRect {
        let topReserve: CGFloat = 88
        let bottomReserve: CGFloat = 118
        let availableHeight = max(cropSide, containerSize.height - topReserve - bottomReserve)
        let y = topReserve + max(0, availableHeight - cropSide) / 2
        return CGRect(
            x: (containerSize.width - cropSide) / 2,
            y: y,
            width: cropSide,
            height: cropSide
        )
    }

    private var baseScale: CGFloat {
        max(cropSide / max(imageSize.width, 1), cropSide / max(imageSize.height, 1))
    }

    var imageFrame: CGRect {
        let size = CGSize(
            width: imageSize.width * baseScale * scale,
            height: imageSize.height * baseScale * scale
        )
        let center = CGPoint(
            x: cropRect.midX + offset.width,
            y: cropRect.midY + offset.height
        )
        return CGRect(
            x: center.x - size.width / 2,
            y: center.y - size.height / 2,
            width: size.width,
            height: size.height
        )
    }

    func clampedOffset(_ proposed: CGSize) -> CGSize {
        let proposedLayout = SquarePhotoCropLayout(
            containerSize: containerSize,
            imageSize: imageSize,
            scale: scale,
            offset: proposed
        )
        let frame = proposedLayout.imageFrame
        var next = proposed

        if frame.width > cropRect.width {
            let allowance = (frame.width - cropRect.width) / 2
            next.width = proposed.width.clamped(to: -allowance...allowance)
        } else {
            next.width = 0
        }

        if frame.height > cropRect.height {
            let allowance = (frame.height - cropRect.height) / 2
            next.height = proposed.height.clamped(to: -allowance...allowance)
        } else {
            next.height = 0
        }

        return next
    }

    func selectionResult(image: UIImage, overlayImage: UIImage?) -> SquarePhotoCropResult {
        guard let cropRegion = normalizedSelectionRect() else {
            return SquarePhotoCropResult(
                image: image.facemaxxSquareCropped(),
                scanOverlayImage: overlayImage?.facemaxxSquareCropped(),
                originalImage: image,
                originalScanOverlayImage: overlayImage,
                preferredRegion: nil
            )
        }

        return SquarePhotoCropResult(
            image: image.facemaxxCropped(toNormalizedRect: cropRegion),
            scanOverlayImage: overlayImage?.facemaxxCropped(toNormalizedRect: cropRegion),
            originalImage: image,
            originalScanOverlayImage: overlayImage,
            preferredRegion: cropRegion
        )
    }

    private func normalizedSelectionRect() -> CGRect? {
        let rect = CGRect(
            x: (cropRect.minX - imageFrame.minX) / imageFrame.width,
            y: (cropRect.minY - imageFrame.minY) / imageFrame.height,
            width: cropRect.width / imageFrame.width,
            height: cropRect.height / imageFrame.height
        ).clampedToUnit()
        guard rect.width > 0.02, rect.height > 0.02 else { return nil }
        return rect
    }
}

private extension UIImage {
    func facemaxxNormalizedUp() -> UIImage {
        guard imageOrientation != .up || scale != 1 else { return self }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        return UIGraphicsImageRenderer(size: size, format: format).image { _ in
            draw(in: CGRect(origin: .zero, size: size))
        }
    }

    func facemaxxCropped(toPixelRect rect: CGRect) -> UIImage {
        let normalized = facemaxxNormalizedUp()
        guard let cgImage = normalized.cgImage else { return normalized.facemaxxSquareCropped() }
        let bounds = CGRect(x: 0, y: 0, width: cgImage.width, height: cgImage.height)
        let cropRect = rect.integral.intersection(bounds)
        guard cropRect.width > 1, cropRect.height > 1, let croppedCGImage = cgImage.cropping(to: cropRect) else {
            return normalized.facemaxxSquareCropped()
        }
        return UIImage(cgImage: croppedCGImage, scale: 1, orientation: .up)
    }

    func facemaxxCropped(toNormalizedRect rect: CGRect) -> UIImage {
        let normalized = facemaxxNormalizedUp()
        guard let cgImage = normalized.cgImage else { return normalized.facemaxxSquareCropped() }
        let pixelRect = CGRect(
            x: rect.minX * CGFloat(cgImage.width),
            y: rect.minY * CGFloat(cgImage.height),
            width: rect.width * CGFloat(cgImage.width),
            height: rect.height * CGFloat(cgImage.height)
        )
        return normalized.facemaxxCropped(toPixelRect: pixelRect)
    }

    func facemaxxSquareCropped() -> UIImage {
        let normalized = facemaxxNormalizedUp()
        guard let cgImage = normalized.cgImage else { return normalized }
        let side = min(cgImage.width, cgImage.height)
        let rect = CGRect(
            x: (cgImage.width - side) / 2,
            y: (cgImage.height - side) / 2,
            width: side,
            height: side
        )
        guard let croppedCGImage = cgImage.cropping(to: rect) else { return normalized }
        return UIImage(cgImage: croppedCGImage, scale: 1, orientation: .up)
    }
}

private extension CGFloat {
    func clamped(to range: ClosedRange<CGFloat>) -> CGFloat {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

private extension CGRect {
    func clampedToUnit() -> CGRect {
        let minX = Swift.min(1, Swift.max(0, minX))
        let minY = Swift.min(1, Swift.max(0, minY))
        let maxX = Swift.min(1, Swift.max(0, maxX))
        let maxY = Swift.min(1, Swift.max(0, maxY))
        return CGRect(x: minX, y: minY, width: Swift.max(0, maxX - minX), height: Swift.max(0, maxY - minY))
    }
}

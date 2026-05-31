import SwiftUI
import UIKit

struct SelectedAnalysisPhotoView: View {
    let image: UIImage
    let supplementalPhotos: [UIImage]
    let requiredPhotoCount: Int
    let canAddSupplementalPhoto: Bool
    let reduceMotion: Bool
    let addSupplementalPhotoAction: (CGPoint) -> Void
    let removeSupplementalPhotoAction: (Int) -> Void
    let removeAction: () -> Void

    private var displaySlotCount: Int {
        max(1, requiredPhotoCount)
    }

    private var photoSize: CGFloat {
        switch displaySlotCount {
        case 1:
            162
        case 2:
            148
        default:
            104
        }
    }

    private var cornerRadius: CGFloat {
        switch displaySlotCount {
        case 1:
            28
        case 2:
            26
        default:
            22
        }
    }

    var body: some View {
        HStack(alignment: .center, spacing: displaySlotCount == 1 ? 0 : 10) {
            photoCard(image: image, borderColor: Color.white.opacity(0.88), removeAction: removeAction)

            if displaySlotCount > 1 {
                ForEach(0..<(displaySlotCount - 1), id: \.self) { index in
                    supplementalSlot(index: index)
                        .id("supplemental-\(index)-\(supplementalPhotos.indices.contains(index))")
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 0)
        .animation(.spring(response: reduceMotion ? 0.01 : 0.38, dampingFraction: 0.86), value: supplementalPhotos.count)
        .animation(.spring(response: reduceMotion ? 0.01 : 0.34, dampingFraction: 0.9), value: requiredPhotoCount)
    }

    @ViewBuilder
    private func supplementalSlot(index: Int) -> some View {
        if supplementalPhotos.indices.contains(index) {
            photoCard(
                image: supplementalPhotos[index],
                borderColor: FXTheme.green.opacity(0.55),
                removeAction: { removeSupplementalPhotoAction(index) }
            )
            .transition(
                reduceMotion
                ? .opacity
                : .asymmetric(
                    insertion: .move(edge: .leading).combined(with: .opacity).combined(with: .scale(scale: 0.96)),
                    removal: .opacity.combined(with: .scale(scale: 0.96))
                )
            )
        } else if canAddSupplementalPhoto && index == supplementalPhotos.count {
            emptySlot(index: index)
                .contentShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
                .gesture(
                    SpatialTapGesture(coordinateSpace: .named(AnalysisPhotoSourceMenuCoordinateSpace.name))
                        .onEnded { value in
                            addSupplementalPhotoAction(value.location)
                        }
                )
                .accessibilityAddTraits(.isButton)
            .transition(reduceMotion ? .opacity : .move(edge: .leading).combined(with: .opacity))
        } else {
            lockedSlot(index: index)
        }
    }

    private func photoCard(
        image: UIImage,
        borderColor: Color,
        removeAction: @escaping () -> Void
    ) -> some View {
        ZStack(alignment: .topTrailing) {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
                .frame(width: photoSize, height: photoSize)
                .clipped()
                .clipShape(.rect(cornerRadius: cornerRadius, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .stroke(borderColor, lineWidth: 1.8)
                }
                .shadow(color: .black.opacity(0.30), radius: 16, y: 9)
                .accessibilityLabel("analysis.selectedPhoto")

            Button(action: removeAction) {
                Image(systemName: "xmark")
                    .font(.system(size: displaySlotCount >= 3 ? 12 : 15, weight: .black))
                    .foregroundStyle(.black)
                    .frame(width: displaySlotCount >= 3 ? 25 : 32, height: displaySlotCount >= 3 ? 25 : 32)
                    .background {
                        Circle()
                            .fill(Color.white)
                            .shadow(color: .black.opacity(0.20), radius: 7, y: 3)
                    }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("analysis.removeSelectedPhoto")
            .offset(x: displaySlotCount >= 3 ? 7 : 9, y: displaySlotCount >= 3 ? -7 : -9)
        }
    }

    private func emptySlot(index: Int) -> some View {
        VStack(spacing: 7) {
            Image(systemName: "plus")
                .font(.system(size: 18, weight: .black))

            Text("\(index + 2)")
                .font(.caption.weight(.black).monospacedDigit())
        }
        .foregroundStyle(FXTheme.cyan)
        .frame(width: photoSize, height: photoSize)
        .background(FXTheme.cyan.opacity(0.10), in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .stroke(FXTheme.cyan.opacity(0.30), style: StrokeStyle(lineWidth: 1.2, dash: [5, 5]))
        )
        .accessibilityLabel("analysis.multiPhoto.addAnother")
    }

    private func lockedSlot(index: Int) -> some View {
        Text("\(index + 2)")
            .font(.caption.weight(.black).monospacedDigit())
            .foregroundStyle(FXTheme.textMuted)
            .frame(width: photoSize, height: photoSize)
            .background(Color.white.opacity(0.035), in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(Color.white.opacity(0.08), lineWidth: 1)
            )
    }
}

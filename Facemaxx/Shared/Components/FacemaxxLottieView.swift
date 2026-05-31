import Lottie
import SwiftUI
import UIKit

struct FacemaxxLottieView: UIViewRepresentable {
    let animationName: String
    var loopMode: LottieLoopMode = .loop
    var contentMode: UIView.ContentMode = .scaleAspectFit

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> UIView {
        let containerView = UIView()
        containerView.backgroundColor = .clear

        let animationView = context.coordinator.animationView
        animationView.translatesAutoresizingMaskIntoConstraints = false
        animationView.backgroundColor = .clear
        animationView.contentMode = contentMode
        animationView.loopMode = loopMode
        animationView.backgroundBehavior = .pauseAndRestore
        animationView.animation = loadAnimation()

        containerView.addSubview(animationView)
        NSLayoutConstraint.activate([
            animationView.leadingAnchor.constraint(equalTo: containerView.leadingAnchor),
            animationView.trailingAnchor.constraint(equalTo: containerView.trailingAnchor),
            animationView.topAnchor.constraint(equalTo: containerView.topAnchor),
            animationView.bottomAnchor.constraint(equalTo: containerView.bottomAnchor)
        ])

        context.coordinator.animationName = animationName
        animationView.play()
        return containerView
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        let animationView = context.coordinator.animationView
        animationView.contentMode = contentMode
        animationView.loopMode = loopMode

        if context.coordinator.animationName != animationName {
            animationView.animation = loadAnimation()
            context.coordinator.animationName = animationName
            animationView.play()
        } else if !animationView.isAnimationPlaying {
            animationView.play()
        }
    }

    private func loadAnimation() -> LottieAnimation? {
        if let animation = LottieAnimation.named(animationName, bundle: .main) {
            return animation
        }

        if let path = Bundle.main.path(forResource: animationName, ofType: "json") {
            return LottieAnimation.filepath(path)
        }

        if let path = Bundle.main.path(forResource: animationName, ofType: "json", inDirectory: "Assets") {
            return LottieAnimation.filepath(path)
        }

        return nil
    }

    @MainActor
    final class Coordinator {
        let animationView = LottieAnimationView()
        var animationName: String?
    }
}

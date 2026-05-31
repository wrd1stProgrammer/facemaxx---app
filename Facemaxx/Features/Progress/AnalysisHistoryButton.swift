import SwiftUI

struct AnalysisHistoryButton: View {
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.title3.weight(.bold))

                Text("progress.analysisHistory")
                    .font(.title3.weight(.heavy))

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.headline.weight(.bold))
                    .foregroundStyle(FXTheme.textSecondary)
            }
            .foregroundStyle(FXTheme.textPrimary)
            .padding(.horizontal, 18)
            .frame(height: 58)
            .fxCard(cornerRadius: 26)
        }
        .buttonStyle(.plain)
    }
}

import SwiftUI

struct AestheticsProgressCard: View {
    let points: [HomeProgressChartPoint]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 10) {
                Text("progress.aestheticsTitle")
                    .font(.title2.weight(.heavy))
                    .foregroundStyle(FXTheme.textPrimary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.82)

                Text("progress.aestheticsSubtitle")
                    .font(.headline.weight(.medium))
                    .foregroundStyle(FXTheme.textSecondary)
            }

            SlopeAreaChartView(points: points)
                .frame(height: 248)
        }
        .padding(.horizontal, 16)
        .padding(.top, 24)
        .padding(.bottom, 20)
        .fxCard(cornerRadius: 34)
    }
}

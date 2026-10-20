import Testing

@testable import CaptureCore

private let rate = 16_000.0

private func seconds(_ s: Double, of value: Float) -> [Float] {
    [Float](repeating: value, count: Int(s * rate))
}

@Test func emptyDetectorIsNotAllZero() {
    let detector = SilenceDetector()
    #expect(!detector.hasSamples)
    #expect(!detector.isAllZero)
}

@Test func onlyExactZerosCountAsSilent() {
    var detector = SilenceDetector()
    detector.add([Float](repeating: 0, count: 1000))
    #expect(detector.isAllZero)
    #expect(detector.trailingZeroCount == 1000)

    // A faint noise floor (like Zoom's) is not a permission problem.
    detector.add([0.00001])
    #expect(!detector.isAllZero)
    #expect(detector.sampleCount == 1001)
    #expect(detector.nonZeroCount == 1)
    #expect(detector.trailingZeroCount == 0)
}

@Test func warnsOnlyAfterTheDelay() {
    var zeros = SilenceDetector()
    zeros.add(seconds(9.9, of: 0))
    #expect(!shouldWarnAboutSystemAudio(elapsed: 9.9, detector: zeros, sampleRate: rate))
    zeros.add(seconds(0.1, of: 0))
    #expect(shouldWarnAboutSystemAudio(elapsed: 10, detector: zeros, sampleRate: rate))
}

@Test func warnsWhenNoAudioArrivesAtAll() {
    #expect(shouldWarnAboutSystemAudio(elapsed: 10, detector: SilenceDetector(), sampleRate: rate))
}

@Test func doesNotWarnAboutRealAudio() {
    var audio = SilenceDetector()
    audio.add(seconds(60, of: 0.01))
    #expect(!shouldWarnAboutSystemAudio(elapsed: 60, detector: audio, sampleRate: rate))
}

@Test func warnsWhenAudioTurnsToZerosPartWayThrough() {
    // What a pending permission prompt looked like: ~2 s of real audio, then only zeros.
    var detector = SilenceDetector()
    detector.add(seconds(2, of: 0.2))
    detector.add(seconds(9, of: 0))
    #expect(!shouldWarnAboutSystemAudio(elapsed: 11, detector: detector, sampleRate: rate))
    detector.add(seconds(1, of: 0))
    #expect(shouldWarnAboutSystemAudio(elapsed: 12, detector: detector, sampleRate: rate))
}

@Test func stopsWarningWhenAudioReturns() {
    var detector = SilenceDetector()
    detector.add(seconds(12, of: 0))
    #expect(shouldWarnAboutSystemAudio(elapsed: 12, detector: detector, sampleRate: rate))
    detector.add([0.1])
    #expect(!shouldWarnAboutSystemAudio(elapsed: 12, detector: detector, sampleRate: rate))
}

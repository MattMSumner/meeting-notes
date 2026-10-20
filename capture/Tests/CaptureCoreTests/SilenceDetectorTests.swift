import Testing

@testable import CaptureCore

@Test func emptyDetectorIsNotAllZero() {
    let detector = SilenceDetector()
    #expect(!detector.hasSamples)
    #expect(!detector.isAllZero)
}

@Test func onlyExactZerosCountAsSilent() {
    var detector = SilenceDetector()
    detector.add([Float](repeating: 0, count: 1000))
    #expect(detector.isAllZero)

    // A faint noise floor (like Zoom's) is not a permission problem.
    detector.add([0.00001])
    #expect(!detector.isAllZero)
    #expect(detector.sampleCount == 1001)
    #expect(detector.nonZeroCount == 1)
}

@Test func warnsOnlyAfterTheDelay() {
    var zeros = SilenceDetector()
    zeros.add([0, 0, 0])
    #expect(!shouldWarnAboutSystemAudio(elapsed: 9.9, detector: zeros))
    #expect(shouldWarnAboutSystemAudio(elapsed: 10, detector: zeros))
}

@Test func warnsWhenNoAudioArrivesAtAll() {
    #expect(shouldWarnAboutSystemAudio(elapsed: 10, detector: SilenceDetector()))
}

@Test func doesNotWarnAboutRealAudio() {
    var audio = SilenceDetector()
    audio.add([0, 0.2, -0.1])
    #expect(!shouldWarnAboutSystemAudio(elapsed: 60, detector: audio))
}

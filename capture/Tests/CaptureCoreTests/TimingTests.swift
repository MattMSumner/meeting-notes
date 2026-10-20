import Foundation
import Testing

@testable import CaptureCore

// Apple Silicon's timebase: 125/3 ns per tick (24 MHz).
private let appleSilicon = HostClock(numerator: 125, denominator: 3)

@Test func convertsTicksToSeconds() {
    #expect(appleSilicon.seconds(from: 0, to: 24_000_000) == 1.0)
    #expect(abs(appleSilicon.seconds(from: 1_000, to: 1_000 + 533_000) - 0.0222083) < 1e-6)
}

@Test func negativeWhenEndIsEarlier() {
    #expect(appleSilicon.seconds(from: 24_000_000, to: 0) == -1.0)
}

@Test func manifestRecordsEachChannelsOffsetFromRecordingStart() throws {
    var audio = SilenceDetector()
    audio.add([0.1])
    let start: UInt64 = 1_000_000
    let me = ChannelStats(firstHostTime: start + 24_000, silence: audio, framesWritten: 32_000)
    let them = ChannelStats(firstHostTime: start + 600_000, silence: audio, framesWritten: 16_000)

    let manifest = CaptureManifest(
        startedAt: Date(timeIntervalSince1970: 1_792_000_000),
        sampleRate: 16_000,
        channels: [
            "me": .init(file: "me.wav", stats: me, recordingStart: start, clock: appleSilicon),
            "them": .init(file: "them.wav", stats: them, recordingStart: start, clock: appleSilicon),
        ]
    )

    #expect(manifest.channels["me"]?.offsetSeconds == 0.001)
    #expect(manifest.channels["them"]?.offsetSeconds == 0.025)
    #expect(manifest.channels["me"]?.durationSeconds == 2.0)
    #expect(try CaptureManifest.decode(manifest.encoded()) == manifest)
}

@Test func manifestUsesSnakeCaseKeysForPython() throws {
    let manifest = CaptureManifest(
        startedAt: Date(timeIntervalSince1970: 0), sampleRate: 16_000,
        channels: ["them": .init(
            file: "them.wav", stats: ChannelStats(firstHostTime: nil, silence: SilenceDetector(), framesWritten: 0),
            recordingStart: 0, clock: appleSilicon)]
    )
    let json = String(decoding: try manifest.encoded(), as: UTF8.self)

    #expect(json.contains("\"sample_rate\" : 16000"))
    #expect(json.contains("\"started_at\" : \"1970-01-01T00:00:00Z\""))
    #expect(json.contains("\"all_zero\" : false"))
    // A channel that never received audio has no offset.
    #expect(!json.contains("offset_seconds"))
}

import AVFoundation
import CaptureCore
import Foundation

/// Records the mic to me.wav and system audio to them.wav in `directory`, until SIGINT,
/// SIGTERM or SIGHUP, then writes capture.json.
func record(to directory: URL) throws -> Int32 {
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    guard Microphone.requestAccess() else {
        warn("microphone access denied. Allow NotesCapture in System Settings > Privacy & Security > Microphone.")
        return 1
    }

    let tap = try SystemAudioTap()
    let mic = Microphone()
    let them = try ChannelWriter(url: directory.appendingPathComponent("them.wav"), inputFormat: tap.format)
    let me = try ChannelWriter(url: directory.appendingPathComponent("me.wav"), inputFormat: mic.format)

    let startedAt = Date()
    let start = mach_absolute_time()
    // System audio first: in the spike it was the one that could start late.
    try tap.start { buffer, hostTime in them.append(buffer, hostTime: hostTime) }
    try mic.start { buffer, hostTime in me.append(buffer, hostTime: hostTime) }
    warn("recording to \(directory.path) (mic: \(describe(mic.format)), system: \(describe(tap.format)))")

    var stopRequested = false
    let stopSources = [SIGINT, SIGTERM, SIGHUP].map { sig in
        signal(sig, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        source.setEventHandler { stopRequested = true }
        source.resume()
        return source
    }
    defer { stopSources.forEach { $0.cancel() } }

    var warned = false
    while !stopRequested {
        RunLoop.main.run(until: Date().addingTimeInterval(0.25))
        let elapsed = Date().timeIntervalSince(startedAt)
        if !warned && shouldWarnAboutSystemAudio(elapsed: elapsed, detector: them.silenceSoFar) {
            warned = true
            warn("""
                WARNING: no system audio after \(Int(elapsed))s (all zeros). If a call is playing, \
                macOS is blocking system audio capture. Stop, run `notes-capture check`, and try again.
                """)
        }
    }

    tap.stop()
    mic.stop()
    let clock = HostClock.system
    let manifest = CaptureManifest(
        startedAt: startedAt,
        sampleRate: Int(outputSampleRate),
        channels: [
            "me": .init(file: "me.wav", stats: me.finish(), recordingStart: start, clock: clock),
            "them": .init(file: "them.wav", stats: them.finish(), recordingStart: start, clock: clock),
        ]
    )
    try manifest.encoded().write(to: directory.appendingPathComponent("capture.json"))
    for (name, channel) in manifest.channels.sorted(by: { $0.key < $1.key }) {
        let offset = channel.offsetSeconds.map { String(format: "starts at %.3fs", $0) } ?? "no audio"
        let silent = channel.allZero ? ", ALL ZEROS" : ""
        warn(String(format: "%@: %.1fs, %@%@", name, channel.durationSeconds, offset, silent))
    }
    return 0
}

private func describe(_ format: AVAudioFormat) -> String {
    "\(Int(format.sampleRate / 1000)) kHz \(format.channelCount == 1 ? "mono" : "\(format.channelCount) ch")"
}

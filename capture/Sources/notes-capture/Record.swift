import AVFoundation
import CaptureCore
import Foundation

/// Records the mic to me.wav and system audio to them.wav in `directory`, until SIGINT,
/// SIGTERM or SIGHUP, then writes capture.json.
func record(to directory: URL) throws -> Int32 {
    // Handle stop signals before anything else, so a Ctrl-C during a permission prompt or
    // setup still ends cleanly (it's acted on once recording starts, which finishes at once).
    var stopRequested = false
    let stopSources = [SIGINT, SIGTERM, SIGHUP].map { sig in
        signal(sig, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        source.setEventHandler { stopRequested = true }
        source.resume()
        return source
    }
    defer { stopSources.forEach { $0.cancel() } }

    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    guard Microphone.requestAccess() else {
        warn("microphone access denied. Allow NotesCapture in System Settings > Privacy & Security > Microphone.")
        return 1
    }

    let startedAt = Date()
    let start = mach_absolute_time()

    // Output device changes (like an idle AirPods mic switching them into call mode)
    // break the tap, so it's rebuilt once they settle. See TapRebuildScheduler.
    var rebuilds = TapRebuildScheduler()
    let monitor = DeviceMonitor { change in
        // Device-list changes are mostly our own rebuilds: not worth logging.
        guard change.affectsOutput else { return }
        let elapsed = Date().timeIntervalSince(startedAt)
        warn(String(format: "[%.2fs] %@", elapsed, change.description))
        DispatchQueue.main.async { rebuilds.deviceChanged(at: elapsed) }
    }
    defer { withExtendedLifetime(monitor) {} }

    // Mic first, so a Bluetooth headset switches into call mode as early as possible.
    // Channel offsets in capture.json absorb the difference in start times.
    let mic = Microphone()
    let me = try ChannelWriter(url: directory.appendingPathComponent("me.wav"), inputFormat: mic.format)
    // Restart the mic if its input changes or it stops delivering, at most every few seconds.
    var lastMicRestart = Date()
    func restartMic(_ why: String) {
        guard Date().timeIntervalSince(lastMicRestart) >= micRestartInterval else { return }
        lastMicRestart = Date()
        do {
            try mic.restart()
            warn(String(format: "[%.2fs] %@; restarted the mic (now %@)",
                         Date().timeIntervalSince(startedAt), why, describe(mic.format)))
        } catch {
            warn("ERROR: \(why) and the mic couldn't be restarted: \(error)")
        }
    }
    lastMicRestart = .distantPast
    try mic.start(
        onBuffer: { buffer, hostTime in me.append(buffer, hostTime: hostTime) },
        onConfigurationChange: { restartMic("mic input changed") }
    )
    lastMicRestart = Date()

    var tap = try SystemAudioTap()
    let them = try ChannelWriter(url: directory.appendingPathComponent("them.wav"), inputFormat: tap.format)
    let feedThem: (AVAudioPCMBuffer, UInt64) -> Void = { buffer, hostTime in them.append(buffer, hostTime: hostTime) }
    try tap.start(onBuffer: feedThem)
    warn("recording to \(directory.path) (mic: \(describe(mic.format)), system: \(describe(tap.format)))")

    // Warn once each time system audio goes quiet (exact zeros) for long enough, and say
    // so when it comes back.
    var warning = false
    while !stopRequested {
        RunLoop.main.run(until: Date().addingTimeInterval(0.25))
        let elapsed = Date().timeIntervalSince(startedAt)
        if mic.secondsSinceLastBuffer >= micStallSeconds {
            restartMic(String(format: "no mic audio for %.0fs", mic.secondsSinceLastBuffer))
        }
        let silence = them.silenceSoFar
        let zeroSeconds = Double(silence.trailingZeroCount) / outputSampleRate
        if let reason = rebuilds.rebuildReason(at: elapsed, trailingZeroSeconds: zeroSeconds) {
            tap.stop()
            do {
                tap = try SystemAudioTap()
                try tap.start(onBuffer: feedThem)
                if reason == .deviceChange {
                    warn(String(format: "[%.2fs] rebuilt system audio capture after device changes", elapsed))
                }
            } catch {
                warn("ERROR: couldn't rebuild system audio capture: \(error)")
            }
        }
        let blocked = shouldWarnAboutSystemAudio(
            elapsed: elapsed, detector: silence, sampleRate: outputSampleRate)
        if blocked && !warning {
            warn("""
                WARNING: system audio has been digital silence for \(Int(systemAudioWarningDelay))s \
                (at \(Int(elapsed))s). Fine if nothing is playing, but if a call is, macOS is \
                blocking capture: check for a NotesCapture permission prompt.
                """)
        } else if !blocked && warning {
            warn("system audio is back (at \(Int(elapsed))s)")
        }
        warning = blocked
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

/// How long without mic buffers counts as stalled, and the least time between restarts.
private let micStallSeconds: TimeInterval = 3
private let micRestartInterval: TimeInterval = 3

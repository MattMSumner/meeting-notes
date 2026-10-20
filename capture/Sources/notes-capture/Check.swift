import AVFoundation
import CaptureCore
import Foundation

/// Confirms the mic and system audio can be captured, so permission problems show up
/// before a meeting rather than in one.
///
/// Plays a short sound from a separate process (the tap excludes this one) and checks the
/// tap heard it. Retries once: the first run after a rebuild records zeros.
func checkCapture() throws -> Int32 {
    guard Microphone.requestAccess() else {
        warn("FAIL microphone: access denied. Allow NotesCapture in System Settings > Privacy & Security > Microphone.")
        return 1
    }
    warn("ok   microphone: access granted")

    for attempt in 1...2 {
        if try tapHearsTestSound() {
            warn("ok   system audio: captured a test sound")
            return 0
        }
        if attempt == 1 {
            warn("     system audio: only zeros, retrying (expected on the first run after a rebuild)")
        }
    }
    warn("""
        FAIL system audio: only zeros. Check System Settings > Privacy & Security > \
        Screen & System Audio Recording > System Audio Recording Only: NotesCapture should be listed and on. \
        If it is, try: tccutil reset AudioCapture com.mattmsumner.notes-capture
        """)
    return 1
}

private func tapHearsTestSound() throws -> Bool {
    let tap = try SystemAudioTap()
    let lock = NSLock()
    var detector = SilenceDetector()
    try tap.start { buffer, _ in
        guard let data = buffer.floatChannelData else { return }
        // Interleaved: all channels are in the first buffer.
        let count = Int(buffer.frameLength) * (buffer.format.isInterleaved ? Int(buffer.format.channelCount) : 1)
        lock.withLock { detector.add(UnsafeBufferPointer(start: data[0], count: count)) }
    }
    defer { tap.stop() }

    let player = Process()
    player.executableURL = URL(fileURLWithPath: "/usr/bin/afplay")
    player.arguments = ["-v", "0.15", "/System/Library/Sounds/Tink.aiff"]
    try player.run()
    player.waitUntilExit()
    RunLoop.main.run(until: Date().addingTimeInterval(0.3))

    return lock.withLock { detector.hasSamples && !detector.isAllZero }
}

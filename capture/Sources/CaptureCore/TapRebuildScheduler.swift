/// Decides when to rebuild the system audio tap.
///
/// Opening an idle Bluetooth headset's mic switches it into call mode. The switch takes a
/// few seconds (playback sounds garbled meanwhile), and a tap created before it finishes
/// stops receiving audio, delivering exact zeros while playback carries on. Not every step
/// of the switch is visible as a device change, so there are two triggers:
///
/// - Output device changes: rebuild once changes stop for `settleSeconds`.
/// - Exact zeros for `silentSeconds`: rebuild. A tap created after the switch works. If
///   nothing is playing (a paused video, an in-person meeting), the rebuild is harmless,
///   but repeating it every few seconds for an hour is churn, so the wait between silence
///   rebuilds doubles from `minimumInterval` up to `maximumInterval`. It resets when audio
///   flows again or a device changes.
public struct TapRebuildScheduler: Sendable {
    public static let settleSeconds: Double = 1.5
    public static let silentSeconds: Double = 1
    public static let minimumInterval: Double = 3
    public static let maximumInterval: Double = 60

    public enum Reason: Equatable, Sendable {
        case deviceChange
        case silence
    }

    private var lastChange: Double?
    private var lastRebuild: Double
    private var silenceInterval = minimumInterval

    /// `startedAt` is when the current tap was created, in seconds into the recording.
    public init(startedAt: Double = 0) {
        lastRebuild = startedAt
    }

    /// Records an output device change, `time` seconds into the recording.
    public mutating func deviceChanged(at time: Double) {
        lastChange = time
    }

    /// Whether to rebuild now, given how long the tap has delivered only exact zeros.
    /// Assumes the caller rebuilds when told to.
    public mutating func rebuildReason(at time: Double, trailingZeroSeconds: Double) -> Reason? {
        if let lastChange, time - lastChange >= Self.settleSeconds {
            self.lastChange = nil
            lastRebuild = time
            silenceInterval = Self.minimumInterval
            return .deviceChange
        }
        guard trailingZeroSeconds >= Self.silentSeconds else {
            silenceInterval = Self.minimumInterval  // audio is flowing
            return nil
        }
        guard time - lastRebuild >= silenceInterval else { return nil }
        lastRebuild = time
        silenceInterval = min(silenceInterval * 2, Self.maximumInterval)
        return .silence
    }
}

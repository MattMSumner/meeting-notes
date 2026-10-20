/// Counts samples, how many are non-zero, and how long the current run of zeros is.
///
/// When macOS blocks system audio (permission missing, or a permission prompt not yet
/// answered), the tap still delivers buffers but every sample is exactly zero, with no
/// error. This can start a second or two into a recording. Real audio, even "silence"
/// from a call, is almost never exactly zero (Zoom sends a faint noise floor), though a
/// paused video is.
public struct SilenceDetector: Sendable {
    public private(set) var sampleCount = 0
    public private(set) var nonZeroCount = 0
    /// Consecutive zero samples at the end of what's been seen so far.
    public private(set) var trailingZeroCount = 0

    public init() {}

    public mutating func add<C: Collection>(_ samples: C) where C.Element == Float {
        sampleCount += samples.count
        for sample in samples {
            if sample == 0 {
                trailingZeroCount += 1
            } else {
                nonZeroCount += 1
                trailingZeroCount = 0
            }
        }
    }

    public var hasSamples: Bool { sampleCount > 0 }

    /// True once samples have arrived and every one of them was zero.
    public var isAllZero: Bool { hasSamples && nonZeroCount == 0 }
}

/// How long the tap may deliver nothing, or only zeros, before warning.
public let systemAudioWarningDelay: Double = 10

/// Whether to warn that system audio looks blocked, `elapsed` seconds into a recording.
/// `sampleRate` is the rate of the samples the detector has seen.
public func shouldWarnAboutSystemAudio(elapsed: Double, detector: SilenceDetector, sampleRate: Double) -> Bool {
    guard elapsed >= systemAudioWarningDelay else { return false }
    let zeroSeconds = Double(detector.trailingZeroCount) / sampleRate
    return !detector.hasSamples || zeroSeconds >= systemAudioWarningDelay
}

/// Counts samples and how many are non-zero.
///
/// When macOS denies system audio access, the tap still delivers buffers but every sample
/// is exactly zero, with no error. Real audio, even "silence" from a call, is almost never
/// exactly zero (Zoom sends a faint noise floor).
public struct SilenceDetector: Sendable {
    public private(set) var sampleCount = 0
    public private(set) var nonZeroCount = 0

    public init() {}

    public mutating func add<C: Collection>(_ samples: C) where C.Element == Float {
        sampleCount += samples.count
        nonZeroCount += samples.lazy.filter { $0 != 0 }.count
    }

    public var hasSamples: Bool { sampleCount > 0 }

    /// True once samples have arrived and every one of them was zero.
    public var isAllZero: Bool { hasSamples && nonZeroCount == 0 }
}

/// How long the tap may stay all-zero (or deliver nothing) before warning.
public let systemAudioWarningDelay: Double = 10

/// Whether to warn that system audio looks blocked, `elapsed` seconds into a recording.
public func shouldWarnAboutSystemAudio(elapsed: Double, detector: SilenceDetector) -> Bool {
    elapsed >= systemAudioWarningDelay && (detector.isAllZero || !detector.hasSamples)
}

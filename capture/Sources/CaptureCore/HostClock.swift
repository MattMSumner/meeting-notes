import Darwin

/// Converts between mach host time ticks (what Core Audio timestamps use) and seconds.
public struct HostClock: Sendable {
    public let numerator: UInt32
    public let denominator: UInt32

    public init(numerator: UInt32, denominator: UInt32) {
        self.numerator = numerator
        self.denominator = denominator
    }

    public static let system: HostClock = {
        var info = mach_timebase_info_data_t()
        mach_timebase_info(&info)
        return HostClock(numerator: info.numer, denominator: info.denom)
    }()

    /// Seconds from `start` to `end`; negative if `end` is earlier.
    public func seconds(from start: UInt64, to end: UInt64) -> Double {
        let ticks = end >= start ? Double(end - start) : -Double(start - end)
        return ticks * Double(numerator) / Double(denominator) / 1_000_000_000
    }
}

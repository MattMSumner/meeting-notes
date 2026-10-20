/// An audio device as far as choosing the system-audio tap's clock is concerned.
public struct AudioDeviceInfo: Equatable, Sendable {
    public let id: UInt32
    public let uid: String
    public let isBuiltIn: Bool
    public let hasOutput: Bool

    public init(id: UInt32, uid: String, isBuiltIn: Bool, hasOutput: Bool) {
        self.id = id
        self.uid = uid
        self.isBuiltIn = isBuiltIn
        self.hasOutput = hasOutput
    }
}

/// The device whose clock drives the tap's aggregate device.
///
/// Prefers the built-in output over the default device: Bluetooth headphones whose mic is
/// in use switch to call mode (24 kHz) while the tap still reports 48 kHz, which made the
/// recording play back at double speed in the spike.
public func chooseClockDevice(from devices: [AudioDeviceInfo], defaultOutput: UInt32) -> AudioDeviceInfo? {
    let outputs = devices.filter(\.hasOutput)
    return outputs.first(where: \.isBuiltIn)
        ?? outputs.first(where: { $0.id == defaultOutput })
        ?? outputs.first
}

import CaptureCore
import CoreAudio
import Foundation

struct CoreAudioError: Error, CustomStringConvertible {
    let operation: String
    let status: OSStatus
    var description: String { "\(operation) failed (OSStatus \(status))" }
}

func check(_ status: OSStatus, _ operation: String) throws {
    guard status == noErr else { throw CoreAudioError(operation: operation, status: status) }
}

private func address(
    _ selector: AudioObjectPropertySelector, scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal
) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
}

func getProperty<T: BitwiseCopyable>(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T) throws -> T {
    var property = address(selector)
    var value = initial
    var size = UInt32(MemoryLayout<T>.size)
    try check(AudioObjectGetPropertyData(object, &property, 0, nil, &size, &value), "read property \(selector)")
    return value
}

func deviceUID(_ device: AudioObjectID) throws -> String {
    var property = address(kAudioDevicePropertyDeviceUID)
    var uid: Unmanaged<CFString>?
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    try check(AudioObjectGetPropertyData(device, &property, 0, nil, &size, &uid), "read device UID")
    guard let uid else { throw CoreAudioError(operation: "read device UID", status: kAudioHardwareUnspecifiedError) }
    return uid.takeRetainedValue() as String
}

func defaultOutputDevice() throws -> AudioObjectID {
    try getProperty(AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDefaultOutputDevice, AudioObjectID(0))
}

func allDevices() throws -> [AudioDeviceInfo] {
    let system = AudioObjectID(kAudioObjectSystemObject)
    var property = address(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    try check(AudioObjectGetPropertyDataSize(system, &property, 0, nil, &size), "count devices")
    var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    try check(AudioObjectGetPropertyData(system, &property, 0, nil, &size, &ids), "list devices")

    return ids.compactMap { id in
        var streams = address(kAudioDevicePropertyStreams, scope: kAudioObjectPropertyScopeOutput)
        var streamsSize: UInt32 = 0
        AudioObjectGetPropertyDataSize(id, &streams, 0, nil, &streamsSize)
        guard let uid = try? deviceUID(id),
              let transport = try? getProperty(id, kAudioDevicePropertyTransportType, UInt32(0))
        else { return nil }
        return AudioDeviceInfo(
            id: id, uid: uid, isBuiltIn: transport == kAudioDeviceTransportTypeBuiltIn, hasOutput: streamsSize > 0)
    }
}

/// This process's Core Audio process object, so the tap can exclude our own sounds.
func ownProcessObject() -> AudioObjectID? {
    var property = address(kAudioHardwarePropertyTranslatePIDToProcessObject)
    var pid = getpid()
    var object = AudioObjectID(kAudioObjectUnknown)
    var size = UInt32(MemoryLayout<AudioObjectID>.size)
    let status = AudioObjectGetPropertyData(
        AudioObjectID(kAudioObjectSystemObject), &property, UInt32(MemoryLayout<pid_t>.size), &pid, &size, &object)
    return status == noErr && object != kAudioObjectUnknown ? object : nil
}

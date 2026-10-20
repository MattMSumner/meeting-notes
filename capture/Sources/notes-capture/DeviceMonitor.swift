import CoreAudio
import Foundation

/// Reports audio hardware changes during a recording: devices appearing or disappearing,
/// default devices changing, and output devices changing sample rate or streams (which
/// Bluetooth headsets do when their mic opens).
///
/// `affectsOutput` is false for device-list changes: creating and destroying the tap's own
/// private aggregate device triggers those, and rebuilding the tap on them would loop.
final class DeviceMonitor {
    struct Change {
        let description: String
        let affectsOutput: Bool
    }

    private let queue = DispatchQueue(label: "DeviceMonitor")
    private let onChange: (Change) -> Void
    private var listeners: [(AudioObjectID, AudioObjectPropertyAddress, AudioObjectPropertyListenerBlock)] = []

    init(onChange: @escaping (Change) -> Void) {
        self.onChange = onChange
        let system = AudioObjectID(kAudioObjectSystemObject)
        listen(system, kAudioHardwarePropertyDevices, "device list changed", affectsOutput: false)
        listen(system, kAudioHardwarePropertyDefaultOutputDevice, "default output changed")
        listen(system, kAudioHardwarePropertyDefaultInputDevice, "default input changed", affectsOutput: false)
        for device in (try? allDevices()) ?? [] where device.hasOutput {
            let name = device.uid
            listen(device.id, kAudioDevicePropertyNominalSampleRate, "\(name): sample rate changed") {
                (try? getProperty(device.id, kAudioDevicePropertyNominalSampleRate, Float64(0))).map { "\(Int($0)) Hz" }
            }
            listen(device.id, kAudioDevicePropertyStreams, "\(name): streams changed", scope: kAudioObjectPropertyScopeOutput)
            listen(device.id, kAudioDevicePropertyDeviceIsAlive, "\(name): alive changed")
        }
    }

    private func listen(
        _ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ message: String,
        scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal,
        affectsOutput: Bool = true,
        detail: @escaping () -> String? = { nil }
    ) {
        var address = AudioObjectPropertyAddress(
            mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
        let block: AudioObjectPropertyListenerBlock = { [onChange] _, _ in
            onChange(Change(description: detail().map { "\(message) (\($0))" } ?? message, affectsOutput: affectsOutput))
        }
        if AudioObjectAddPropertyListenerBlock(object, &address, queue, block) == noErr {
            listeners.append((object, address, block))
        }
    }

    deinit {
        for (object, address, block) in listeners {
            var address = address
            AudioObjectRemovePropertyListenerBlock(object, &address, queue, block)
        }
    }
}

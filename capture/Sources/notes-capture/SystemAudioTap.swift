import AVFoundation
import CaptureCore
import CoreAudio

/// Captures everything the Mac plays (except this process) through a Core Audio process
/// tap wrapped in a private aggregate device.
final class SystemAudioTap {
    let format: AVAudioFormat
    private var tapID = AudioObjectID(kAudioObjectUnknown)
    private var aggregateID = AudioObjectID(kAudioObjectUnknown)
    private var ioProcID: AudioDeviceIOProcID?

    init() throws {
        let description = CATapDescription(stereoGlobalTapButExcludeProcesses: ownProcessObject().map { [$0] } ?? [])
        description.uuid = UUID()
        description.muteBehavior = .unmuted
        description.isPrivate = true
        try check(AudioHardwareCreateProcessTap(description, &tapID), "create process tap")

        var streamDescription = try getProperty(tapID, kAudioTapPropertyFormat, AudioStreamBasicDescription())
        guard let format = AVAudioFormat(streamDescription: &streamDescription) else {
            throw CoreAudioError(operation: "read tap format", status: kAudioHardwareUnspecifiedError)
        }
        self.format = format

        guard let clock = chooseClockDevice(from: try allDevices(), defaultOutput: try defaultOutputDevice()) else {
            throw CoreAudioError(operation: "find an output device", status: kAudioHardwareBadDeviceError)
        }
        let aggregate: [String: Any] = [
            kAudioAggregateDeviceNameKey: "notes-capture",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceMainSubDeviceKey: clock.uid,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: clock.uid]],
            kAudioAggregateDeviceTapListKey: [[
                kAudioSubTapDriftCompensationKey: true,
                kAudioSubTapUIDKey: description.uuid.uuidString,
            ]],
        ]
        try check(AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &aggregateID), "create aggregate device")
    }

    /// Starts delivering buffers. Buffers are only valid during the callback.
    /// The "System Audio Recording" permission prompt, if any, appears here.
    func start(onBuffer: @escaping (AVAudioPCMBuffer, UInt64) -> Void) throws {
        let format = self.format
        try check(AudioDeviceCreateIOProcIDWithBlock(&ioProcID, aggregateID, DispatchQueue(label: "tap.io")) {
            _, input, inputTime, _, _ in
            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, bufferListNoCopy: input, deallocator: nil)
            else { return }
            onBuffer(buffer, inputTime.pointee.mHostTime)
        }, "create IO proc")
        try check(AudioDeviceStart(aggregateID, ioProcID), "start system audio capture")
    }

    func stop() {
        if let ioProcID {
            AudioDeviceStop(aggregateID, ioProcID)
            AudioDeviceDestroyIOProcID(aggregateID, ioProcID)
            self.ioProcID = nil
        }
        if aggregateID != kAudioObjectUnknown {
            AudioHardwareDestroyAggregateDevice(aggregateID)
            aggregateID = AudioObjectID(kAudioObjectUnknown)
        }
        if tapID != kAudioObjectUnknown {
            AudioHardwareDestroyProcessTap(tapID)
            tapID = AudioObjectID(kAudioObjectUnknown)
        }
    }

    deinit { stop() }
}

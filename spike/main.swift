// Throwaway spike: can a CLI launched from Ghostty record the mic AND all system
// output (via a Core Audio process tap) on macOS Tahoe, without silent zeros?
//
// Usage: ./tapspike [seconds] [output-dir]
// Writes me.wav (mic) and them.wav (system output) and prints per-second levels.

import AVFoundation
import CoreAudio
import Foundation

// MARK: - Level meter shared between audio threads and the main loop

final class Meter {
    private let lock = NSLock()
    private var sumSquares: Double = 0
    private var count: Int = 0
    private var totalNonZero: Int = 0
    private var totalFrames: Int = 0

    func add(_ buffer: AVAudioPCMBuffer) {
        guard let data = buffer.floatChannelData else { return }
        let frames = Int(buffer.frameLength)
        let channels = Int(buffer.format.channelCount)
        let stride = buffer.stride
        var sum: Double = 0
        var nonZero = 0
        for c in 0..<channels {
            let ch = data[c]
            for i in 0..<frames {
                let s = Double(ch[i * stride])
                sum += s * s
                if s != 0 { nonZero += 1 }
            }
        }
        markData()
        lock.lock()
        sumSquares += sum
        count += frames * channels
        totalNonZero += nonZero
        totalFrames += frames * channels
        lock.unlock()
    }

    /// dBFS since the last call, then reset.
    func takeLevel() -> String {
        lock.lock()
        defer { sumSquares = 0; count = 0; lock.unlock() }
        guard count > 0 else { return "  no data" }
        let rms = (sumSquares / Double(count)).squareRoot()
        if rms == 0 { return "  SILENT " }
        return String(format: "%6.1f dB", 20 * log10(rms))
    }

    private var firstData: Date?

    func markData() {
        lock.lock(); if firstData == nil { firstData = Date() }; lock.unlock()
    }

    /// Frames actually delivered per wall-clock second since the first buffer.
    func framesPerSecond(channels: Int) -> Double {
        lock.lock(); defer { lock.unlock() }
        guard let firstData, channels > 0 else { return 0 }
        return Double(totalFrames / channels) / Date().timeIntervalSince(firstData)
    }

    var summary: String {
        lock.lock(); defer { lock.unlock() }
        let pct = totalFrames == 0 ? 0 : 100 * Double(totalNonZero) / Double(totalFrames)
        return String(format: "%d samples, %.1f%% non-zero", totalFrames, pct)
    }
}

// MARK: - Core Audio helpers

func check(_ status: OSStatus, _ what: String) {
    guard status == noErr else {
        FileHandle.standardError.write("error: \(what) failed (OSStatus \(status))\n".data(using: .utf8)!)
        exit(1)
    }
}

func getProperty<T>(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T) -> T {
    var address = AudioObjectPropertyAddress(
        mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var value = initial
    var size = UInt32(MemoryLayout<T>.size)
    check(AudioObjectGetPropertyData(object, &address, 0, nil, &size, &value), "get property \(selector)")
    return value
}

func ownProcessObjectID() -> AudioObjectID? {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyTranslatePIDToProcessObject,
        mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var pid = getpid()
    var objectID = AudioObjectID(kAudioObjectUnknown)
    var size = UInt32(MemoryLayout<AudioObjectID>.size)
    let status = AudioObjectGetPropertyData(
        AudioObjectID(kAudioObjectSystemObject), &address,
        UInt32(MemoryLayout<pid_t>.size), &pid, &size, &objectID)
    return status == noErr && objectID != kAudioObjectUnknown ? objectID : nil
}

// MARK: - Arguments and output files

let args = CommandLine.arguments
let seconds = args.count > 1 ? Int(args[1]) ?? 30 : 30
let outDir = URL(fileURLWithPath: args.count > 2 ? args[2] : "out", isDirectory: true)
try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

let meMeter = Meter()
let themMeter = Meter()

// MARK: - Mic (started first: it can force a Bluetooth profile switch)

let granted: Bool = {
    let sema = DispatchSemaphore(value: 0)
    var ok = false
    AVCaptureDevice.requestAccess(for: .audio) { ok = $0; sema.signal() }
    sema.wait()
    return ok
}()
print("microphone permission: \(granted ? "granted" : "DENIED")")

let engine = AVAudioEngine()
let micFormat = engine.inputNode.outputFormat(forBus: 0)
let meFile = try AVAudioFile(forWriting: outDir.appendingPathComponent("me.wav"), settings: micFormat.settings)
engine.inputNode.installTap(onBus: 0, bufferSize: 4096, format: micFormat) { buffer, _ in
    try? meFile.write(from: buffer)
    meMeter.add(buffer)
}
try engine.start()
print("mic: \(micFormat)")

// MARK: - System output tap -> private aggregate device -> IOProc

let exclude = ownProcessObjectID().map { [$0] } ?? []
let tapDescription = CATapDescription(stereoGlobalTapButExcludeProcesses: exclude)
tapDescription.uuid = UUID()
tapDescription.muteBehavior = .unmuted
tapDescription.isPrivate = true

var tapID = AudioObjectID(kAudioObjectUnknown)
check(AudioHardwareCreateProcessTap(tapDescription, &tapID), "AudioHardwareCreateProcessTap")

var tapASBD = getProperty(tapID, kAudioTapPropertyFormat, AudioStreamBasicDescription())
guard let tapFormat = AVAudioFormat(streamDescription: &tapASBD) else {
    print("error: could not read tap format"); exit(1)
}
print("tap: \(tapFormat)")

// Clock the aggregate from the built-in output, not the default device: Bluetooth
// headphones in call (HFP) mode run at 24 kHz while the tap still reports 48 kHz.
func builtInOutputDevice() -> AudioDeviceID? {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDevices,
        mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    check(AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size), "device list size")
    var devices = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    check(AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &devices), "device list")
    return devices.first { device in
        var streams = AudioObjectPropertyAddress(
            mSelector: kAudioDevicePropertyStreams,
            mScope: kAudioObjectPropertyScopeOutput, mElement: kAudioObjectPropertyElementMain)
        var streamsSize: UInt32 = 0
        AudioObjectGetPropertyDataSize(device, &streams, 0, nil, &streamsSize)
        return streamsSize > 0
            && getProperty(device, kAudioDevicePropertyTransportType, UInt32(0)) == kAudioDeviceTransportTypeBuiltIn
    }
}

let defaultOutput = getProperty(
    AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDefaultOutputDevice, AudioDeviceID(0))
let clockDevice = builtInOutputDevice() ?? defaultOutput
let outputUID = getProperty(clockDevice, kAudioDevicePropertyDeviceUID, "" as CFString) as String
print("default output: \(getProperty(defaultOutput, kAudioDevicePropertyDeviceUID, "" as CFString) as String)")
print("clock device: \(outputUID)")

let aggregateDescription: [String: Any] = [
    kAudioAggregateDeviceNameKey: "tapspike",
    kAudioAggregateDeviceUIDKey: UUID().uuidString,
    kAudioAggregateDeviceMainSubDeviceKey: outputUID,
    kAudioAggregateDeviceIsPrivateKey: true,
    kAudioAggregateDeviceIsStackedKey: false,
    kAudioAggregateDeviceTapAutoStartKey: true,
    kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: outputUID]],
    kAudioAggregateDeviceTapListKey: [[
        kAudioSubTapDriftCompensationKey: true,
        kAudioSubTapUIDKey: tapDescription.uuid.uuidString,
    ]],
]
var aggregateID = AudioObjectID(kAudioObjectUnknown)
check(AudioHardwareCreateAggregateDevice(aggregateDescription as CFDictionary, &aggregateID),
      "AudioHardwareCreateAggregateDevice")
print("aggregate sample rate: \(getProperty(aggregateID, kAudioDevicePropertyNominalSampleRate, Float64(0))) Hz")

let themFile = try AVAudioFile(
    forWriting: outDir.appendingPathComponent("them.wav"), settings: tapFormat.settings,
    commonFormat: .pcmFormatFloat32, interleaved: tapFormat.isInterleaved)
var ioProcID: AudioDeviceIOProcID?
check(AudioDeviceCreateIOProcIDWithBlock(&ioProcID, aggregateID, DispatchQueue(label: "tap.io")) {
    _, inInputData, _, _, _ in
    guard let buffer = AVAudioPCMBuffer(pcmFormat: tapFormat, bufferListNoCopy: inInputData, deallocator: nil)
    else { return }
    try? themFile.write(from: buffer)
    themMeter.add(buffer)
}, "AudioDeviceCreateIOProcIDWithBlock")

// The "System Audio Recording" permission prompt is triggered here, not at tap creation.
check(AudioDeviceStart(aggregateID, ioProcID), "AudioDeviceStart")

// MARK: - Run, printing levels once a second; Ctrl-C stops early

var stopRequested = false
signal(SIGINT, SIG_IGN)
let sigint = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
sigint.setEventHandler { stopRequested = true }
sigint.resume()

print("recording \(seconds)s to \(outDir.path) (Ctrl-C to stop)")
print("  t     me (mic)    them (system)")
for t in 1...seconds {
    RunLoop.main.run(until: Date().addingTimeInterval(1))
    print(String(format: "%3ds  %@   %@", t, meMeter.takeLevel(), themMeter.takeLevel()))
    if stopRequested { break }
}

// MARK: - Teardown (closes the WAVs so their headers are finalized)

AudioDeviceStop(aggregateID, ioProcID)
if let ioProcID { AudioDeviceDestroyIOProcID(aggregateID, ioProcID) }
AudioHardwareDestroyAggregateDevice(aggregateID)
AudioHardwareDestroyProcessTap(tapID)
engine.inputNode.removeTap(onBus: 0)
engine.stop()
meFile.close()
themFile.close()

print("me:   \(meMeter.summary)")
print("them: \(themMeter.summary)")
print(String(format: "them frames/sec: %.0f (tap format says %.0f)",
             themMeter.framesPerSecond(channels: Int(tapFormat.channelCount)), tapFormat.sampleRate))

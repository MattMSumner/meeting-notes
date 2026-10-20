import AVFoundation

/// The default input device, via AVAudioEngine.
final class Microphone {
    private let engine = AVAudioEngine()

    var format: AVAudioFormat { engine.inputNode.outputFormat(forBus: 0) }

    /// Asks for microphone access if it hasn't been decided yet.
    static func requestAccess() -> Bool {
        let done = DispatchSemaphore(value: 0)
        var granted = false
        AVCaptureDevice.requestAccess(for: .audio) { granted = $0; done.signal() }
        done.wait()
        return granted
    }

    func start(onBuffer: @escaping (AVAudioPCMBuffer, UInt64) -> Void) throws {
        engine.inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, time in
            onBuffer(buffer, time.hostTime)
        }
        try engine.start()
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
    }
}

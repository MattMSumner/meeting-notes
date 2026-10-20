import AVFoundation

/// The default input device, via AVAudioEngine.
///
/// AVAudioEngine stops itself when its input changes (AirPods connecting or disconnecting
/// mid-meeting, a new default input). `restart()` picks up the new device and format;
/// ChannelWriter handles the format change and fills the gap with silence.
///
/// Restarting creates a new engine: after a device change, the old engine's input node can
/// still report the previous format, and installing a tap with it raises an Objective-C
/// exception that Swift can't catch, killing the recording.
final class Microphone {
    private var engine = AVAudioEngine()
    private var onBuffer: ((AVAudioPCMBuffer, UInt64) -> Void)?
    private var configurationObserver: NSObjectProtocol?
    private let lock = NSLock()
    private var lastBuffer = Date()

    var format: AVAudioFormat { engine.inputNode.outputFormat(forBus: 0) }

    /// Asks for microphone access if it hasn't been decided yet.
    static func requestAccess() -> Bool {
        let done = DispatchSemaphore(value: 0)
        var granted = false
        AVCaptureDevice.requestAccess(for: .audio) { granted = $0; done.signal() }
        done.wait()
        return granted
    }

    /// Starts delivering buffers. `onConfigurationChange` is called on the main queue when
    /// the engine stops because its input changed; call `restart()` from there.
    func start(
        onBuffer: @escaping (AVAudioPCMBuffer, UInt64) -> Void,
        onConfigurationChange: @escaping () -> Void
    ) throws {
        self.onBuffer = onBuffer
        self.onConfigurationChange = onConfigurationChange
        try startEngine()
    }

    /// Restarts on the current default input, in whatever format it now has.
    func restart() throws {
        stopEngine()
        engine = AVAudioEngine()
        try startEngine()
    }

    /// Seconds since the last buffer arrived (or since the engine last started).
    var secondsSinceLastBuffer: TimeInterval {
        lock.withLock { Date().timeIntervalSince(lastBuffer) }
    }

    func stop() {
        stopEngine()
    }

    private var onConfigurationChange: (() -> Void)?

    private func stopEngine() {
        if let configurationObserver { NotificationCenter.default.removeObserver(configurationObserver) }
        configurationObserver = nil
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
    }

    private func startEngine() throws {
        guard let onBuffer else { return }
        let onConfigurationChange = self.onConfigurationChange
        configurationObserver = NotificationCenter.default.addObserver(
            forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main
        ) { _ in onConfigurationChange?() }
        lock.withLock { lastBuffer = Date() }
        engine.inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, time in
            self?.lock.withLock { self?.lastBuffer = Date() }
            onBuffer(buffer, time.hostTime)
        }
        engine.prepare()
        try engine.start()
    }
}

import AVFoundation

/// The format every channel is stored in: what the transcription model wants.
public let outputSampleRate: Double = 16_000

/// What a channel recorded, for capture.json.
public struct ChannelStats: Sendable {
    /// Host time of the first sample, or nil if no audio arrived.
    public let firstHostTime: UInt64?
    public let silence: SilenceDetector
    public let framesWritten: Int
}

public enum ChannelWriterError: Error {
    case unsupportedFormat(AVAudioFormat)
}

/// Writes one channel to a 16 kHz mono 16-bit WAV, converting from whatever format the
/// device delivers (24 kHz mono from a Bluetooth mic, 48 kHz stereo from the tap).
///
/// `append` is called from audio threads: it only copies the buffer and hands it to a
/// serial queue, which does the conversion and file I/O.
public final class ChannelWriter: @unchecked Sendable {
    private let queue: DispatchQueue
    private let file: AVAudioFile
    private let converter: AVAudioConverter
    private let outputFormat: AVAudioFormat
    private var firstHostTime: UInt64?
    private var silence = SilenceDetector()
    private var framesWritten = 0
    private var finished = false

    public init(url: URL, inputFormat: AVAudioFormat) throws {
        guard let output = AVAudioFormat(
            commonFormat: .pcmFormatFloat32, sampleRate: outputSampleRate, channels: 1, interleaved: false),
            let converter = AVAudioConverter(from: inputFormat, to: output)
        else { throw ChannelWriterError.unsupportedFormat(inputFormat) }
        converter.downmix = true  // without this, stereo -> mono keeps only the left channel

        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: outputSampleRate,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]
        self.file = try AVAudioFile(
            forWriting: url, settings: settings, commonFormat: .pcmFormatFloat32, interleaved: false)
        self.converter = converter
        self.outputFormat = output
        self.queue = DispatchQueue(label: "ChannelWriter.\(url.lastPathComponent)")
    }

    public func append(_ buffer: AVAudioPCMBuffer, hostTime: UInt64) {
        guard let copy = buffer.deepCopy() else { return }
        queue.async { [self] in
            guard !finished else { return }
            if firstHostTime == nil { firstHostTime = hostTime }
            convertAndWrite(copy)
        }
    }

    /// Silence statistics so far, for live warnings while recording.
    public var silenceSoFar: SilenceDetector { queue.sync { silence } }

    /// Drains the converter, closes the file, and returns what was recorded.
    public func finish() -> ChannelStats {
        queue.sync {
            if !finished {
                convertAndWrite(nil)
                file.close()
                finished = true
            }
            return ChannelStats(firstHostTime: firstHostTime, silence: silence, framesWritten: framesWritten)
        }
    }

    /// Converts one input buffer, or drains the converter when `input` is nil.
    private func convertAndWrite(_ input: AVAudioPCMBuffer?) {
        let ratio = outputSampleRate / converter.inputFormat.sampleRate
        let inputFrames = Double(input?.frameLength ?? 0)
        let capacity = AVAudioFrameCount((inputFrames * ratio).rounded(.up)) + 1024
        var supplied = false

        while true {
            guard let out = AVAudioPCMBuffer(pcmFormat: outputFormat, frameCapacity: capacity) else { return }
            var error: NSError?
            let status = converter.convert(to: out, error: &error) { _, inputStatus in
                if supplied || input == nil {
                    inputStatus.pointee = input == nil ? .endOfStream : .noDataNow
                    return nil
                }
                supplied = true
                inputStatus.pointee = .haveData
                return input
            }
            if out.frameLength > 0, let samples = out.floatChannelData?[0] {
                silence.add(UnsafeBufferPointer(start: samples, count: Int(out.frameLength)))
                framesWritten += Int(out.frameLength)
                try? file.write(from: out)
            }
            // Keep pulling only while the converter fills whole buffers.
            if status != .haveData || out.frameLength < out.frameCapacity { return }
        }
    }
}

extension AVAudioPCMBuffer {
    /// A copy that owns its memory. Buffers from Core Audio callbacks are only valid
    /// during the callback.
    func deepCopy() -> AVAudioPCMBuffer? {
        guard let copy = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameLength) else { return nil }
        copy.frameLength = frameLength
        let source = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: audioBufferList))
        let destination = UnsafeMutableAudioBufferListPointer(copy.mutableAudioBufferList)
        for (src, dst) in zip(source, destination) {
            guard let from = src.mData, let to = dst.mData else { continue }
            memcpy(to, from, Int(min(src.mDataByteSize, dst.mDataByteSize)))
        }
        return copy
    }
}

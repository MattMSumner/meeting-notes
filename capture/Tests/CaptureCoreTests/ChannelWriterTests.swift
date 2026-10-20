import AVFoundation
import Foundation
import Testing

@testable import CaptureCore

/// Feeds `seconds` of a sine wave through a ChannelWriter in device-sized chunks, the way
/// the mic and tap deliver audio, and reads the resulting file back.
private func writeTone(
    frequency: Double, seconds: Double, format: AVAudioFormat, amplitude: Float = 0.5
) throws -> (samples: [Float], file: AVAudioFile, stats: ChannelStats) {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).wav")
    defer { try? FileManager.default.removeItem(at: url) }
    let writer = try ChannelWriter(url: url, inputFormat: format)

    let total = Int(seconds * format.sampleRate)
    let chunk = 512
    for start in stride(from: 0, to: total, by: chunk) {
        let frames = min(chunk, total - start)
        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(frames))!
        buffer.frameLength = AVAudioFrameCount(frames)
        let channels = Int(format.channelCount)
        for i in 0..<frames {
            let t = Double(start + i) / format.sampleRate
            let value = amplitude * Float(sin(2 * .pi * frequency * t))
            for c in 0..<channels {
                if format.isInterleaved {
                    buffer.floatChannelData![0][i * channels + c] = value
                } else {
                    buffer.floatChannelData![c][i] = value
                }
            }
        }
        writer.append(buffer, hostTime: UInt64(1_000 + start))
    }
    let stats = writer.finish()

    let file = try AVAudioFile(forReading: url, commonFormat: .pcmFormatFloat32, interleaved: false)
    let read = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length))!
    try file.read(into: read)
    let samples = Array(UnsafeBufferPointer(start: read.floatChannelData![0], count: Int(read.frameLength)))
    return (samples, file, stats)
}

private func zeroCrossings(_ samples: [Float]) -> Int {
    zip(samples, samples.dropFirst()).filter { ($0 < 0) != ($1 < 0) }.count
}

private let tapFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 48_000, channels: 2, interleaved: true)!
private let bluetoothMicFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 24_000, channels: 1, interleaved: false)!

@Test(arguments: [tapFormat, bluetoothMicFormat])
func writes16kMonoWithSameLengthAndPitch(format: AVAudioFormat) throws {
    let (samples, file, stats) = try writeTone(frequency: 440, seconds: 2, format: format)

    #expect(file.fileFormat.sampleRate == 16_000)
    #expect(file.fileFormat.channelCount == 1)
    #expect(file.fileFormat.settings[AVLinearPCMBitDepthKey] as? Int == 16)
    // Same duration: 2 s at 16 kHz, within a few ms of converter latency.
    #expect(abs(samples.count - 32_000) < 160)
    #expect(stats.framesWritten == samples.count)
    // Same pitch: a 440 Hz sine crosses zero 880 times a second.
    #expect(abs(zeroCrossings(samples) - 1_760) < 20)
}

@Test func downmixesStereoInsteadOfDroppingAChannel() throws {
    // Only the right channel has sound. Taking the left channel alone would give silence.
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).wav")
    defer { try? FileManager.default.removeItem(at: url) }
    let writer = try ChannelWriter(url: url, inputFormat: tapFormat)
    let buffer = AVAudioPCMBuffer(pcmFormat: tapFormat, frameCapacity: 4_800)!
    buffer.frameLength = 4_800
    for i in 0..<4_800 {
        buffer.floatChannelData![0][i * 2] = 0
        buffer.floatChannelData![0][i * 2 + 1] = 0.5 * Float(sin(2 * .pi * 440 * Double(i) / 48_000))
    }
    writer.append(buffer, hostTime: 1)
    let stats = writer.finish()

    #expect(!stats.silence.isAllZero)
}

@Test func recordsFirstHostTimeAndDetectsAllZeroAudio() throws {
    let (_, _, stats) = try writeTone(frequency: 440, seconds: 0.5, format: tapFormat, amplitude: 0)

    #expect(stats.firstHostTime == 1_000)
    #expect(stats.silence.isAllZero)
}

@Test func finishWithoutAudio() throws {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).wav")
    defer { try? FileManager.default.removeItem(at: url) }
    let stats = try ChannelWriter(url: url, inputFormat: tapFormat).finish()

    #expect(stats.firstHostTime == nil)
    #expect(stats.framesWritten == 0)
    #expect(!stats.silence.isAllZero)
}

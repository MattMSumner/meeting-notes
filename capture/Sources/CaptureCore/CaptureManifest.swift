import Foundation

/// capture.json: what `notes-capture record` produced, read by the Python pipeline.
public struct CaptureManifest: Codable, Equatable, Sendable {
    public struct Channel: Codable, Equatable, Sendable {
        public let file: String
        /// Seconds from the start of the recording to this channel's first sample, measured
        /// on the shared host clock. Nil if the channel never received audio.
        public let offsetSeconds: Double?
        public let durationSeconds: Double
        /// True if every sample was zero: for the tap, almost certainly a permission problem.
        public let allZero: Bool

        public init(file: String, offsetSeconds: Double?, durationSeconds: Double, allZero: Bool) {
            self.file = file
            self.offsetSeconds = offsetSeconds
            self.durationSeconds = durationSeconds
            self.allZero = allZero
        }
    }

    public let startedAt: Date
    public let sampleRate: Int
    public let channels: [String: Channel]

    public init(startedAt: Date, sampleRate: Int, channels: [String: Channel]) {
        self.startedAt = startedAt
        self.sampleRate = sampleRate
        self.channels = channels
    }

    public func encoded() throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(self)
    }

    public static func decode(_ data: Data) throws -> CaptureManifest {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(CaptureManifest.self, from: data)
    }
}

extension CaptureManifest.Channel {
    public init(file: String, stats: ChannelStats, recordingStart: UInt64, clock: HostClock) {
        self.init(
            file: file,
            offsetSeconds: stats.firstHostTime.map { clock.seconds(from: recordingStart, to: $0) },
            durationSeconds: Double(stats.framesWritten) / outputSampleRate,
            allZero: stats.silence.isAllZero
        )
    }
}

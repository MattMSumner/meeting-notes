// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "NotesCapture",
    // Process taps need 14.4; AVAudioFile.close() needs 15.
    platforms: [.macOS(.v15)],
    targets: [
        // Logic that can be tested without audio hardware or permissions.
        .target(name: "CaptureCore"),
        // The command-line tool: Core Audio, AVFoundation and process plumbing.
        .executableTarget(name: "notes-capture", dependencies: ["CaptureCore"]),
        .testTarget(name: "CaptureCoreTests", dependencies: ["CaptureCore"]),
    ],
    // Core Audio callbacks and Swift 6's strict concurrency checking don't mix well.
    swiftLanguageModes: [.v5]
)

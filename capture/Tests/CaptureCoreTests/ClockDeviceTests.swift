import Testing

@testable import CaptureCore

private let airpods = AudioDeviceInfo(id: 10, uid: "44-1B-88:output", isBuiltIn: false, hasOutput: true)
private let speakers = AudioDeviceInfo(id: 20, uid: "BuiltInSpeakerDevice", isBuiltIn: true, hasOutput: true)
private let builtInMic = AudioDeviceInfo(id: 30, uid: "BuiltInMicrophoneDevice", isBuiltIn: true, hasOutput: false)
private let display = AudioDeviceInfo(id: 40, uid: "Display", isBuiltIn: false, hasOutput: true)

@Test func prefersBuiltInOutputOverBluetoothDefault() {
    #expect(chooseClockDevice(from: [airpods, builtInMic, speakers], defaultOutput: airpods.id) == speakers)
}

@Test func ignoresBuiltInDevicesWithoutOutput() {
    #expect(chooseClockDevice(from: [builtInMic, airpods], defaultOutput: airpods.id) == airpods)
}

@Test func fallsBackToDefaultThenAnyOutput() {
    #expect(chooseClockDevice(from: [display, airpods], defaultOutput: airpods.id) == airpods)
    #expect(chooseClockDevice(from: [display, airpods], defaultOutput: 999) == display)
}

@Test func noOutputDevices() {
    #expect(chooseClockDevice(from: [builtInMic], defaultOutput: 0) == nil)
}

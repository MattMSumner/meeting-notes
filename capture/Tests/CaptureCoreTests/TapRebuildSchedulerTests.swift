import Testing

@testable import CaptureCore

private typealias Reason = TapRebuildScheduler.Reason

/// Asks the scheduler at each (time, trailing zero seconds) in turn, returning when it
/// said to rebuild and why.
private func rebuilds(
    _ scheduler: inout TapRebuildScheduler, asking checks: [(Double, Double)]
) -> [(Double, Reason)] {
    checks.compactMap { time, zeros in
        scheduler.rebuildReason(at: time, trailingZeroSeconds: zeros).map { (time, $0) }
    }
}

private func times(_ result: [(Double, Reason)]) -> [Double] { result.map(\.0) }
private func reasons(_ result: [(Double, Reason)]) -> [Reason] { result.map(\.1) }

@Test func noRebuildWhileAudioFlowsAndDevicesAreStable() {
    var scheduler = TapRebuildScheduler()
    #expect(rebuilds(&scheduler, asking: [(1, 0), (10, 0), (100, 0.5)]).isEmpty)
}

@Test func rebuildsOnceAfterDeviceChangesSettle() {
    // An idle AirPods mic opening: changes at 0.06-0.15 s.
    var scheduler = TapRebuildScheduler()
    scheduler.deviceChanged(at: 0.06)
    scheduler.deviceChanged(at: 0.12)
    let result = rebuilds(&scheduler, asking: [(1.0, 0), (1.62, 0), (1.9, 0), (10, 0)])
    #expect(times(result) == [1.62])
    #expect(reasons(result) == [.deviceChange])
}

@Test func furtherChangesRestartTheWait() {
    var scheduler = TapRebuildScheduler()
    scheduler.deviceChanged(at: 0)
    #expect(rebuilds(&scheduler, asking: [(1.4, 0)]).isEmpty)
    scheduler.deviceChanged(at: 1.4)
    #expect(times(rebuilds(&scheduler, asking: [(2.0, 0), (2.9, 0), (3.5, 0)])) == [2.9])
}

@Test func rebuildsWhenTheTapGoesSilent() {
    // What the AirPods switch did: audio until ~4 s, then exact zeros.
    var scheduler = TapRebuildScheduler()
    let result = rebuilds(&scheduler, asking: [(4.5, 0.5), (5.0, 1.0), (5.5, 1.5)])
    #expect(times(result) == [5.0])
    #expect(reasons(result) == [.silence])
}

@Test func silenceRebuildsAreRateLimited() {
    // Nothing playing: zeros forever. Rebuild every few seconds, not every check.
    var scheduler = TapRebuildScheduler()
    let checks = stride(from: 3.0, through: 12.0, by: 0.25).map { ($0, $0) }
    #expect(times(rebuilds(&scheduler, asking: checks)) == [3, 6, 9, 12])
}

@Test func noSilenceRebuildTooSoonAfterCreatingTheTap() {
    var scheduler = TapRebuildScheduler(startedAt: 10)
    #expect(times(rebuilds(&scheduler, asking: [(11, 1), (12.9, 2.9), (13, 3)])) == [13])
}

@Test func aDeviceChangeRebuildAlsoResetsTheSilenceTimer() {
    var scheduler = TapRebuildScheduler()
    scheduler.deviceChanged(at: 0.1)
    let result = rebuilds(&scheduler, asking: [(1.6, 1.6), (2.0, 2.0), (4.7, 4.7)])
    #expect(times(result) == [1.6, 4.7])
    #expect(reasons(result) == [.deviceChange, .silence])
}

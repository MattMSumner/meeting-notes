import Foundation

/// Re-runs this binary as its own "responsible process" for privacy (TCC) checks, then
/// exits with the child's status. Returns without doing anything in the child.
///
/// Launched from a terminal, macOS attributes permission requests to the terminal app.
/// Terminals don't declare NSAudioCaptureUsageDescription, so system audio is denied
/// silently: no prompt, no error, all-zero buffers. Disclaiming responsibility makes macOS
/// use this app's own Info.plist and permissions instead.
///
/// `responsibility_spawnattrs_setdisclaim` is private API, also used by Chromium, Qt and LLDB.
func relaunchDisclaimingResponsibility() {
    let marker = "NOTES_CAPTURE_DISCLAIMED"
    guard ProcessInfo.processInfo.environment[marker] == nil else { return }

    typealias SetDisclaim = @convention(c) (UnsafeMutablePointer<posix_spawnattr_t?>, Int32) -> Int32
    guard let symbol = dlsym(UnsafeMutableRawPointer(bitPattern: -2), "responsibility_spawnattrs_setdisclaim"),
          let path = Bundle.main.executablePath
    else {
        warn("can't disclaim responsibility; system audio may be silently blocked")
        return
    }
    let setDisclaim = unsafeBitCast(symbol, to: SetDisclaim.self)

    var attributes: posix_spawnattr_t?
    posix_spawnattr_init(&attributes)
    defer { posix_spawnattr_destroy(&attributes) }
    _ = setDisclaim(&attributes, 1)

    // Forward stop signals to the child, so stopping the parent stops the recording
    // cleanly. Set up before spawning, so a signal that arrives in between isn't lost (or
    // fatal to the parent, orphaning the child). The child gets default handling back.
    let stopSignals = [SIGINT, SIGTERM, SIGHUP]
    var defaults = sigset_t()
    sigemptyset(&defaults)
    stopSignals.forEach { sigaddset(&defaults, $0) }
    posix_spawnattr_setsigdefault(&attributes, &defaults)
    posix_spawnattr_setflags(&attributes, Int16(POSIX_SPAWN_SETSIGDEF))

    let forwarding = DispatchQueue(label: "forward-signals")
    var child: pid_t = 0
    var pending: Int32?
    for sig in stopSignals {
        signal(sig, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: sig, queue: forwarding)
        source.setEventHandler {
            if child > 0 { kill(child, sig) } else { pending = sig }
        }
        source.resume()
        forwardedSignals.append(source)
    }

    setenv(marker, "1", 1)
    var argv: [UnsafeMutablePointer<CChar>?] = CommandLine.arguments.map { strdup($0) } + [nil]
    defer { argv.forEach { free($0) } }

    var spawned: pid_t = 0
    let status = posix_spawn(&spawned, path, nil, &attributes, &argv, environ)
    guard status == 0 else {
        forwardedSignals.forEach { $0.cancel() }
        stopSignals.forEach { signal($0, SIG_DFL) }
        warn("posix_spawn failed (\(status)); system audio may be silently blocked")
        return
    }
    forwarding.sync {
        child = spawned
        if let pending { kill(child, pending) }
    }
    var childStatus: Int32 = 0
    while waitpid(spawned, &childStatus, 0) == -1 && errno == EINTR {}
    exit((childStatus & 0x7f) == 0 ? (childStatus >> 8) & 0xff : 1)
}

private var forwardedSignals: [DispatchSourceSignal] = []

func warn(_ message: String) {
    FileHandle.standardError.write(Data("notes-capture: \(message)\n".utf8))
}

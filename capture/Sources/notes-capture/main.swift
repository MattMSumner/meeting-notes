import Foundation

let usage = """
    usage: notes-capture record --out DIR   record mic and system audio until Ctrl-C
           notes-capture check              check mic and system audio permissions
    """

relaunchDisclaimingResponsibility()

let arguments = Array(CommandLine.arguments.dropFirst())
do {
    switch arguments.first {
    case "record":
        guard arguments.count == 3, arguments[1] == "--out" else {
            warn(usage)
            exit(2)
        }
        exit(try record(to: URL(fileURLWithPath: arguments[2], isDirectory: true)))
    case "check":
        exit(try checkCapture())
    default:
        warn(usage)
        exit(2)
    }
} catch {
    warn("error: \(error)")
    exit(1)
}

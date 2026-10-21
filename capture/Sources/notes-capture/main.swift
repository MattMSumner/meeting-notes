import Foundation

let usage = """
    usage: notes-capture record --out DIR   record mic and system audio until Ctrl-C
           notes-capture check              check mic and system audio permissions
           notes-capture calendar --from ISO8601 --to ISO8601
                                            print the calendar events in a window as JSON
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
    case "calendar":
        let dates = ISO8601DateFormatter()
        guard arguments.count == 5, arguments[1] == "--from", arguments[3] == "--to",
            let from = dates.date(from: arguments[2]), let to = dates.date(from: arguments[4])
        else {
            warn(usage)
            exit(2)
        }
        exit(try printEvents(from: from, to: to))
    default:
        warn(usage)
        exit(2)
    }
} catch {
    warn("error: \(error)")
    exit(1)
}

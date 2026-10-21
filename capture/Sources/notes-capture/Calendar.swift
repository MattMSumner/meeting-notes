import EventKit
import Foundation

/// Prints the events in a time window as JSON, for `notes` to pick the current meeting
/// from. Reads every calendar macOS syncs, including Google ones added in System Settings
/// > Internet Accounts; no calendar app needs to be open.
///
/// Deliberately a thin reader: choosing the event is done (and tested) in Python.
func printEvents(from start: Date, to end: Date) throws -> Int32 {
    let store = EKEventStore()
    guard requestCalendarAccess(store) else {
        warn("""
            calendar access denied. Allow NotesCapture in System Settings > Privacy & Security > \
            Calendars (Full Access).
            """)
        return 1
    }
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let events = store.events(matching: predicate).map(CalendarEvent.init)
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    encoder.keyEncodingStrategy = .convertToSnakeCase
    encoder.dateEncodingStrategy = .iso8601
    FileHandle.standardOutput.write(try encoder.encode(events))
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    return 0
}

private func requestCalendarAccess(_ store: EKEventStore) -> Bool {
    let done = DispatchSemaphore(value: 0)
    var granted = false
    store.requestFullAccessToEvents { allowed, _ in
        granted = allowed
        done.signal()
    }
    done.wait()
    return granted
}

private struct CalendarEvent: Encodable {
    struct Attendee: Encodable {
        let name: String?
        let email: String?
        let status: String
        let isMe: Bool
    }

    let title: String
    let start: Date
    let end: Date
    let allDay: Bool
    let calendar: String
    let cancelled: Bool
    /// My response: "accepted", "declined", "tentative", "pending" or "unknown". Events
    /// without attendees (my own blocks) are "accepted".
    let myStatus: String
    let attendees: [Attendee]

    init(_ event: EKEvent) {
        title = event.title ?? ""
        start = event.startDate
        end = event.endDate
        allDay = event.isAllDay
        calendar = event.calendar?.title ?? ""
        cancelled = event.status == .canceled
        // People only: Google lists booked rooms and equipment as attendees too.
        let people = (event.attendees ?? []).filter {
            $0.participantType == .person || $0.participantType == .unknown
        }
        attendees = people.map { participant in
            Attendee(
                name: participant.name,
                email: participant.url.absoluteString.hasPrefix("mailto:")
                    ? String(participant.url.absoluteString.dropFirst("mailto:".count)) : nil,
                status: describe(participant.participantStatus),
                isMe: participant.isCurrentUser
            )
        }
        myStatus = attendees.first(where: \.isMe)?.status ?? "accepted"
    }
}

private func describe(_ status: EKParticipantStatus) -> String {
    switch status {
    case .accepted: "accepted"
    case .declined: "declined"
    case .tentative: "tentative"
    case .pending: "pending"
    default: "unknown"
    }
}

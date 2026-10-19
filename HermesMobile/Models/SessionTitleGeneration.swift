import Foundation

/// WebUI's title regeneration is a one-shot write using the latest exchange.
/// It leaves host preferences unchanged, but marks this session's title as
/// generated, so configured adaptive title refresh can update it again later.
struct SessionTitleGenerationRequest: Encodable {
    let sessionID: String
    let preferLatest = true

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case preferLatest = "prefer_latest"
    }
}

struct SessionTitleGenerationResponse: Decodable {
    struct Session: Decodable {
        let sessionId: String?
        let title: String?
    }

    let session: Session?
    let title: String?
    let ok: Bool?
    let error: String?

    /// Only the server's confirmed title may replace the local label. Keep the
    /// requested session identity even if a malformed response names another one.
    func validatedTitle(for sessionID: String) throws -> String {
        if let error = Self.nonEmpty(error) { throw SessionTitleGenerationError(serverMessage: error) }
        guard ok != false,
              session?.sessionId == nil || session?.sessionId == sessionID,
              let resolved = Self.nonEmpty(session?.title) ?? Self.nonEmpty(title) else {
            throw SessionTitleGenerationError(serverMessage: nil)
        }
        return resolved
    }

    private static func nonEmpty(_ value: String?) -> String? {
        guard let text = value?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { return nil }
        return text
    }
}

struct SessionTitleGenerationError: LocalizedError {
    let serverMessage: String?

    var errorDescription: String? {
        serverMessage ?? String(localized: "The server could not generate a conversation name.")
    }
}

/// Owns the list's naming work. Revoking a view's ownership remains effective
/// even if a request ignores cancellation or its server is selected again.
@MainActor
final class SessionTitleGenerationTask {
    private var task: Task<Void, Never>?
    private var generation: UUID?

    @discardableResult
    func start(server: URL, currentServer: @escaping @MainActor () -> URL?,
               operation: @escaping @MainActor () async -> Bool,
               completion: @escaping @MainActor (Bool) -> Void) -> Task<Void, Never>? {
        guard currentServer() == server else { return nil }
        cancel()
        let generation = UUID()
        self.generation = generation
        let task = Task { [weak self] in
            guard !Task.isCancelled, self?.generation == generation,
                  currentServer() == server else { return }
            let result = await operation()
            guard !Task.isCancelled, let self, self.generation == generation,
                  currentServer() == server else { return }
            self.task = nil
            completion(result)
        }
        self.task = task
        return task
    }

    func cancel() {
        generation = nil
        task?.cancel()
        task = nil
    }
}

/// Direct Hermes has no title-generation contract. Never send its rows to the
/// legacy WebUI route, even when the same screen displays both backend types.
enum SessionTitleGenerationAvailability {
    static func canGenerate(sessionID: String?, isHermes: Bool, isReadOnly: Bool,
                            isOffline: Bool, isBusy: Bool) -> Bool {
        guard let sessionID, !sessionID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        return !isHermes && !isReadOnly && !isOffline && !isBusy
    }
}

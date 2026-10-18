"""Portable checks of the production title contract, not an iOS build/test substitute."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SessionTitleGenerationTests(unittest.TestCase):
    def test_delayed_unauthorized_is_scoped_to_the_owning_view_and_server(self):
        source = ROOT / "HermesMobile/Models/SessionTitleGeneration.swift"
        swift = r'''
import Foundation

@MainActor final class DelayedNaming {
    var started: CheckedContinuation<Void, Never>?
    var response: CheckedContinuation<Bool, Never>?
    var unauthorized = false

    func run() async -> Bool {
        await withCheckedContinuation { continuation in
            response = continuation
            started?.resume()
            started = nil
        }
    }

    func waitForRequest(_ start: () -> Void) async {
        await withCheckedContinuation { continuation in
            started = continuation
            start()
        }
    }

    func return401() {
        unauthorized = true
        response?.resume(returning: false) // Deliberately ignores cancellation.
        response = nil
    }
}

@main struct NamingOwnershipSmoke {
    @MainActor static func main() async {
        let a = URL(string: "https://a.test")!
        let b = URL(string: "https://b.test")!
        var activeServer: URL? = a
        var errorForwards = 0
        var uiCompletions = 0
        let owner = SessionTitleGenerationTask()

        for scenario in 0..<4 {
            activeServer = a
            let request = DelayedNaming()
            var task: Task<Void, Never>?
            await request.waitForRequest {
                task = owner.start(server: a, currentServer: { activeServer }, operation: {
                    await request.run()
                }, completion: { _ in
                    uiCompletions += 1
                    if request.unauthorized { errorForwards += 1 }
                })
            }
            switch scenario {
            case 0: activeServer = b // No cancellation: identity check alone must protect B.
            case 1:
                activeServer = b
                owner.cancel() // View leaves on server switch.
                activeServer = a // Same URL again must not revive the old ownership.
            case 2: owner.cancel() // Disappearing without a switch also revokes completion.
            default: break // A current owner's real 401 must still reach sign-in routing.
            }
            request.return401()
            await task?.value
            let expected = scenario == 3 ? 1 : 0
            precondition(errorForwards == expected, "Stale 401 reached shared auth")
            precondition(uiCompletions == expected, "Stale request changed toast/haptics/UI")
        }
        var unwantedRequests = 0
        activeServer = a
        let cancelled = owner.start(server: a, currentServer: { activeServer }, operation: {
            unwantedRequests += 1
            return true
        }, completion: { _ in fatalError("A disappeared view cannot complete") })
        owner.cancel()
        await cancelled?.value
        precondition(unwantedRequests == 0, "A task cancelled before it starts must not send a request")
        print("PASS: delayed 401 server switch, A-B-A, disappearance, and current-owner error")
    }
}
'''
        self.compile_and_run(source, swift)

    def compile_and_run(self, source, swift):
        with tempfile.TemporaryDirectory(prefix="hermex-title-", dir=os.environ.get("TMPDIR")) as directory:
            runner = Path(directory) / "TitleContractSmoke.swift"
            executable = Path(directory) / "title-contract-smoke"
            runner.write_text(swift)
            compiled = subprocess.run(
                ["swiftc", "-swift-version", "5", str(source), str(runner), "-o", str(executable)],
                text=True, capture_output=True, timeout=90,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(executable)], text=True, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS:", result.stdout)
            print(result.stdout.strip())

    def test_production_title_contract(self):
        source = ROOT / "HermesMobile/Models/SessionTitleGeneration.swift"
        self.assertTrue(source.is_file(), "Production automatic naming contract is missing")
        swift = r'''
import Foundation

func check(_ value: @autoclosure () -> Bool, _ message: String) {
    guard value() else { fatalError(message) }
}

@main struct TitleContractSmoke {
    static func main() throws {
        let encoder = JSONEncoder()
        let request = try JSONSerialization.jsonObject(with: encoder.encode(
            SessionTitleGenerationRequest(sessionID: "conversation+a%2Fb")
        )) as! [String: Any]
        check(request["session_id"] as? String == "conversation+a%2Fb", "Exact session ID must survive encoding")
        check(request["prefer_latest"] as? Bool == true, "Auto-name must use the latest exchange")
        check(request["sessionId"] == nil, "No camel-case request fields")

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        func response(_ json: String) throws -> SessionTitleGenerationResponse {
            try decoder.decode(SessionTitleGenerationResponse.self, from: Data(json.utf8))
        }
        let success = try response(#"{"session":{"session_id":"s1","title":" Updated title "},"title":"Updated title","status":"llm","future":true}"#)
        let title = try success.validatedTitle(for: "s1")
        check(title == "Updated title", "Use the server-persisted title")
        let fallback = try response(#"{"title":"Top-level title"}"#)
        let fallbackTitle = try fallback.validatedTitle(for: "s1")
        check(fallbackTitle == "Top-level title", "Tolerate a server returning only its top-level title")

        for json in [
            #"{"ok":false,"title":"Not saved"}"#,
            #"{"error":"Generation unavailable","title":"Not saved"}"#,
            #"{"session":{"session_id":"other","title":"Wrong conversation"}}"#,
            #"{"session":{"session_id":"s1","title":"  "}}"#,
            #"{}"#
        ] {
            do {
                _ = try response(json).validatedTitle(for: "s1")
                fatalError("A refused, missing or wrong-session result cannot become success")
            } catch is SessionTitleGenerationError { }
        }
        check(SessionTitleGenerationAvailability.canGenerate(
            sessionID: "s1", isHermes: false, isReadOnly: false, isOffline: false, isBusy: false
        ), "A writable online WebUI session can auto-name")
        for blocked in 0..<5 {
            check(!SessionTitleGenerationAvailability.canGenerate(
                sessionID: blocked == 0 ? "  " : "s1",
                isHermes: blocked == 1, isReadOnly: blocked == 2,
                isOffline: blocked == 3, isBusy: blocked == 4
            ), "Missing IDs, unsupported backends, read-only/offline/busy rows must be blocked")
        }
        print("PASS: production request, response validation and action availability")
    }
}
'''
        self.compile_and_run(source, swift)


if __name__ == "__main__":
    unittest.main()

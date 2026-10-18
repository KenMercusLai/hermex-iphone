# iPhone fork maintenance

## Ownership and scope

- `KenMercusLai/hermex-iphone` is Ken's iPhone feature-request and implementation repository, forked from `uzairansaruzi/hermex`. `hermex-mac` remains separate.
- Ken provides requirements. The assistant maintains code, branches, tests, independent review, PRs, merges and validated delivery within this fork. This repository-specific authorization supersedes upstream's per-push approval convention, but does not authorize unrelated repositories.
- Open a fork issue with the requested behavior and acceptance criteria before implementation. Do not move the completion boundary after the work starts.
- Keep changes minimal and preserve upstream provenance and the MIT license. Verify current upstream `master` and the real producer/consumer contract before changing either side.
- Use feature branches and an independent review before merge. Keep the issue open and the PR draft when required verification is blocked. A merged PR or passing source check does not prove an installable iPhone build.

## Safety boundaries

- No production Hermes/WebUI changes, restarts, tunnels, session mutations or credential changes without separate authorization. Contract research is read-only; an integration mutation uses only a disposable session created for that test.
- No upstream App Store Connect, TestFlight, signing-team or release-account operations. Existing upstream signing and store automation are reference material, not this fork's publishing authority.
- GitHub Actions are disabled for this fork. Do not add CI as a substitute for the agreed local/Conductor testing workflow.
- Keep private host addresses, credentials, conversations and build logs containing secrets out of public issues and commits.

## Verification and delivery

- Follow `AGENTS.md` for architecture, isolation, native quality and source placement. Fork-specific ownership and verification boundaries in this guide take precedence over upstream release practices.
- Use full Xcode and an iOS Simulator for the affected app tests and an integrated interaction pass. Free Personal Team device signing is sufficient for development when the configured capabilities allow it; it does not enable TestFlight or upstream push entitlements.
- A Command Line Tools-only host can run portable Swift logic and source parsing checks, but cannot build or execute the iOS app. Record those results separately and do not label them simulator/device validation.
- Leave precise commands, results, known blockers and the remaining acceptance checks on the issue/PR. Never ship a fabricated IPA or claim unsigned compile-only output is installable.
- Before claiming remote delivery, read back the exact fork, branch/PR commit and issue state.

# Migration state and verification gates

Order: [ai-bridge #100](https://github.com/Starrkiing/ai-bridge/issues/100); provisioning: #101.

**This PR is not a byte-identical migration of the currently deployed ChatGPT Sites dashboard.** Its original Sites-managed source, `/api/update-instructions`, all 20 source outputs, original manifest, original data digest and collector internals are inaccessible through the present GitHub-only connection. Do not equate the reduced three-source US proxy with the prior independently collected dashboard or claim global / FX / Cboe parity. Continue operating the old Sites task until five *verified*, consecutive weekday receipts and acceptance.

## What is actually supplied

- `collector.py`: independently written, key-free Python-standard-library requests for FRED WALCL, FRED RRPONTSYD, and US Treasury Fiscal Data TGA closing balance; aligned daily **US-only** values and fail-closed parsing
- `receipts/YYYY-MM-DDTHH-MM-SSZ.json`: generated per run with source URLs, latest as-of dates, **SHA-256 of response bytes**, schedule-adjusted expected dates, observed values, and digest. Never overwrite previous receipt filenames. Automated PRs do not merge themselves
- `dist/api/provenance.json`: static latest receipt for public provenance and a visible **LATE** / **FETCH_FAILED** state; no green-run freshness assumption
- `site/index.html`: no-server-runtime dashboard. Explicit omissions: SPX gamma, dark pool, global decomposition, FX, forward forecast and narrative
- `test_collector.py`: fixtures for source units, TGA closing-balance row, held-back observations, unavailable sources and deterministic arithmetic to **1e-6 USD bn**. These are *fixture arithmetic tests, not proof of parity with Sites*

## Source schedule and known limitations

WALCL is Wednesday-level H.4.1 weekly and generally announced Thursday; TGA is daily Treasury DTS, generally released following business day; RRPONTSYD is a NY Fed-backed daily FRED series. Calendar and schedule rules are conservative approximations; holidays and provider release delays can produce a LATE warning. A LATE warning does not mutate or silently zero out prior values.

- FRED WALCL: https://fred.stlouisfed.org/series/WALCL — USD millions
- Treasury DTS: https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance — USD millions, `open_today_bal` on the TGA Closing Balance row for current DTS format
- FRED RRPONTSYD: https://fred.stlouisfed.org/series/RRPONTSYD — USD billions

The data are a **proxy**, not direct measured money invested in SPY. Source agreements and revision terms apply to redistribution; this repo publishes derived observations and byte hashes, not bulk restricted historical archives.

## Acceptance still pending

1. Run CI (tests); code source hasn't yet had a successful GitHub-hosted collector run.
2. Captain and Grok review source model, TGA semantics, security and freshness.
3. Admiral/authorized maintainer sets Pages Source = GitHub Actions and GitHub Actions permission to open receipt PRs, if not enabled.
4. Run `workflow_dispatch` after merge, confirm receipt artifact, reported LATE/CURRENT status, and Pages URL.
5. Retrieve the *actual Sites code, 20-source output and deployed commit digest* through supported Site access. Add missing global/Cboe/ECB panels and conduct 1e-6 USD bn **real input-by-input parity** checks. This must not be forged with static fixture assertions.
6. Get 5 consecutive weekday public GitHub-hosted receipts before retiring Sites. Preserve the last Sites SHA-256 receipt then.
7. Captain remains sole merge authority; no trading endpoints or private repo content.

The old Sites URL may remain the more complete dashboard until this validation is done.

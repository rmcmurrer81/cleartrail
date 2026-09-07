> Current source release: this repository includes the verified Desktop implementation and a separate no-install browser edition. See [BROWSER-BUILD.md](BROWSER-BUILD.md) to generate the static browser assets from pinned dependencies. Runtime binaries, personal state and the optional voice pack are excluded. Desktop setup requirements below apply to maintainers/users running the local server, not to judges opening the hosted browser build. Historical contest and test notes below retain their original verification scope.

# ClearTrail — Evidence Briefing

Ask what changed and why a decision was made. Keep the exact evidence beside the answer.

**Target:** Alexa+ track of [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/). Deadline: **October 23, 2026, 3 p.m. Eastern / noon Pacific**. This is a local web simulation with a real MCP server; it is not connected to an Alexa device or account.

## Open the app

Double-click **START CLEARTRAIL.cmd**. The app opens at `http://127.0.0.1:8794`. Sources and briefings persist in this folder's `data/` directory. Closing the app does not erase them.

1. Create a project. Use separate projects for unrelated work.
2. Add a PDF, text/Markdown file, or pasted document. Supply its title, document group, revision label, and whether it is notes, a proposal, or a decision record.
3. Use **Add revision** to preserve a newer version beside its original. **Compare** shows exact changes; it does not declare the newer version approved.
4. Ask a question in ordinary language, such as “What is the current launch decision, and why?”
5. Review the findings, supporting quotes, and unresolved conflicts. Click a quote to open the exact saved source. Export a Markdown briefing when ready.

**Try a fictional example** creates three labeled sample records with conflicting launch decisions. It is sample input, not a prewritten AI answer. You can also enter your own text directly.

## What is implemented

- Separate projects, immutable revisions, duplicate-import handling, exact line search and revision diffs.
- PDF/text/Markdown import; PDF citations retain page numbers. Scanned PDFs without extractable text produce an actionable error.
- Sarah is the default built-in evidence assistant: no API key, credits or installed model. She retrieves exact source passages, follows up on the last topic, compares linked revisions through actual MCP tools, flags possible disagreement and saves evidence-backed answers. She abstains when the documents do not match the question. This is bounded retrieval and comparison, not a general language model.
- Optional local Qwen3.5:9b synthesis remains available as a separately selected mode. It reads the same complete source snapshot through MCP and validates returned quotations.
- Literal quote validation before saving. A fabricated quote or an answer prepared while sources change is rejected; no canned answer is substituted.
- Conflicting decision records are explicitly requested in the model response. Source kind/date alone does not establish authority. Conclusions are AI interpretations, even when their quotes match.
- Prior briefings remain available after reload. If new evidence arrives, old briefings are visibly marked as outdated.
- Markdown export includes the quoted evidence and source snapshot hash.

Current briefing limit: at most **16 revisions and 30,000 total text characters per project**. Search and comparison remain available for larger projects; create a focused excerpt project for AI synthesis. Imported files are limited to 5 MB and PDFs to 100 pages. There is no OCR, live external research, email connector, automatic decision approval, or Alexa-device connection.

## Run and test

Python 3.11+; `python -m pip install -r requirements.txt` installs PDF extraction support. The source edition needs Python; the Windows portable ZIP includes its own Python3.14.7 runtime and PDF reader. Sarah works without Ollama. Only the optional Qwen mode requires an already installed local model.

Run `python server.py --open`. Optional arguments: `--port 8795 --state-dir path/to/separate-state`. Run `python -B -m unittest -v test_cleartrail test_sarah` for source, persistence, citation, and live MCP protocol tests. Tests do not call a model.

`verify_browser.cjs` is an optional Playwright integration probe. Set `CLEARTRAIL_PLAYWRIGHT` and `CLEARTRAIL_CHROMIUM` only if using a nonstandard installation; otherwise install Playwright normally. This legacy browser probe targets the older button text; current Sarah browser acceptance is documented below. Its sources are explicitly fictional engineering inputs.

## MCP interface

Endpoint: `http://127.0.0.1:8794/mcp`, MCP **2025-11-25 Streamable HTTP** with JSON POST responses. Initialize a session, send `notifications/initialized`, then use `tools/list` / `tools/call`. Send `Accept: application/json, text/event-stream` and the matching protocol/session headers. DELETE closes the session; optional GET streaming is not offered.

Each launch rotates a local Bearer token in `data/mcp-token.txt`. The app binds only to loopback and checks Host/Origin. Keep that token and `data/` private. The browser uses the real MCP tools for sources, search, comparison, saved briefings, and export. The local AI client retrieves its evidence and recent questions through MCP before synthesis.

Tools: list/create projects; import/list/read sources; search evidence; compare revisions; get complete bounded context; list/export briefings. This is a focused evidence workflow, not a general autonomous agent.

## Provenance and contest status

ClearTrail is a new September 6, 2026 implementation inspired by the owner's older ContextGate idea. ContextGate's old hackathon is over; this is not a resubmission under its old name. Existing ContextGate memory/revision/catalog code was read for design context, not copied into this app. Its repository at the inspected revision includes broader company-memory and web-console work; no claim is made that its full application was merely its standalone deterministic chat fixture.

The MCP transport/client pattern is adapted from the owner's new Carry On prototype, also built September 6. ClearTrail has separate ports, data, tools, and user outcomes: documentary evidence and decision briefings, while Carry On handles departure/task planning. No personal Video Studio/KiraWorld state or protected SetSignal Antigravity code is imported.

[Official rules](https://amazonappdev2026.devpost.com/rules) permit materially distinct multiple submissions, a simulated Alexa+ experience using entrants' chosen agentic tools, and a self-hosted MCP path. Submission still needs a public licensed repository, a public demo under three minutes, and product feedback. The repository exists; the complete submission and owner acceptance are still pending. Alexa+ track cash prizes are $25,000 / $15,000 / $4,000, with separate AWS-credit components of $15,000 / $5,000 / $1,000. Eligibility and judging are determined by the organizers; no prize result is promised.

## Evidence status

Fifteen CPU tests pass, including a real MCP handshake/call/close, project isolation, source integrity, changed-evidence rejection, quote rejection, and saved/exported briefings. The browser accepted three newly entered revisions, restored them after reload, searched exact conflicting lines, and displayed a real revision diff with zero JavaScript errors.

A read-only PDF import check loaded the six-page morning project review and validated a literal page-1 quotation; the check used no model. The final live browser run used a real local Qwen call (9.821 seconds), preserved the conflicting June 12 / June 13 decisions as unresolved, verified literal source quotations, opened a highlighted quote, exported Markdown, and restored the same briefing after reload. No JavaScript errors occurred. An earlier model-format defect is preserved in an explicitly named initial-format-defect receipt; validation was tightened and the final run passed. Exact-quote validation proves quotation fidelity, not the correctness of every interpretation.


## Sarah update — September 7, 2026

Twenty-five CPU/HTTP tests pass, including real MCP reads with all external/provider requests rejected, exact decimal amounts, conflicting decisions, proposal labels, follow-up topic isolation, missing-evidence abstention, immutable revisions, restart and Markdown export. Six real Edge browser prompts passed using a bare Python process with site packages disabled; highlighted quotes, actual revision diff, export, reload and 390px mobile layout passed with no JavaScript errors. These engineering checks do not replace the owner’s acceptance review.

Sarah shows selected evidence excerpts; not every kind of natural-language inference or contradiction is supported. Different wording in similar decision records is labelled a possible disagreement for review. Source labels and dates do not establish authority. No paid APIs were called.


## September 7 dashboard and approved voice update

ClearTrail supports office, home, research, community and other evidence projects. Its office example is explicitly fictional and creates a separate project. Sarah answers onboarding questions before uploads. Save as evidence lets you review and keep your own exact wording; conversation alone does not modify sources.

The dashboard shows actual saved source counts by source label, linked revisions, saved reviews, and possible conflicting wording in the selected review. Open any source or revision to read the original. Source labels and newer revisions do not establish approval. Standalone dated record headings do not count as conflicting decisions.

The approved custom voice runs with the separate optional Windows `sarah-voice-pack`, placed beside this application folder. Choose **Turn voice on**, then ask a question. The visible state changes while speech is prepared and played. Pause and Hear reply control playback. Speech is limited to a concise reply; the full evidence remains on screen. It uses the pack's own embedded runtime and CPU model, without a provider key or usage credits. If the pack is absent, written conversation remains available.

The default written Sarah assistant is bounded retrieval and workflow logic, not a general-purpose language model. Optional Ollama mode remains explicit. No installed model is required for the default workflow.


## Fixed screens and exact document pages

The September 7 fixed-4 build uses separate Overview, Sources, Versions, Review and Sarah screens. The current workflow is checked at 3440×1311, 1920×1080, 1366×768, 768×1024, 390×844 and 320×568. Sources, replies and results use Previous/Next controls instead of requiring long page scrolling. Exact source pages are measured to fit and preserve every original character, including line breaks and Unicode. Search results open the matching original text. The source upload form keeps earlier revisions separate.

The Windows ZIP includes its own runtime and works without an installed model or provider key. Its optional custom voice still uses the separate owner voice pack. The separate ordinary-browser edition is included under `browser/`; BROWSER-BUILD.md explains its pinned build and static hosting. The Windows ZIP and the browser edition use separate storage.

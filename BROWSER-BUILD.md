# Rebuild the no-install browser edition

Maintainer prerequisite: Python3.10+ with internet access to the pinned public dependency URLs. No pip packages, API keys, model, cloud account or payment are required. The deployed browser app requires no Python installation on the judge device.

Run `python build_browser.py`. It creates a new `build/browser` folder, fetching six hash-pinned Pyodide runtime files and, where used, the pinned pypdf wheel. All runtime binaries stay outside Git source. The PDF package is rebuilt from individually hash-verified Python source members. Its archive compression and browser-files.json hash can differ from the original ZIP; the Python bytes remain exact. All other application/runtime bytes must match the verified release or the build fails. Existing output folders are never overwritten; use `--output another/new/folder` for a second build.

Serve build/browser over HTTPS (or localhost for development). For a local smoke check: `python -m http.server 8000 --directory build/browser`, then open http://localhost:8000. Serve .mjs as JavaScript and .wasm as application/wasm. File:// is unsupported. Publish the complete generated folder; the Python source repository alone is not a static deployment.

Written Sarah runs locally in browser WebAssembly with IndexedDB. No voice pack/model is included. Browser transport simulations are labeled by the app; this build does not establish a connected Alexa account or a live network MCP server. ShiftBrief browser does not execute the separate Desktop Strands integration. Persistent data is in the browser profile, not cloud sync. Keep workspace backups.

Review browser-build-receipt.json next to the output for all generated hashes. Upstream license texts/source links are included under browser/licenses or browser/runtime/licenses. Pyodide/MPL, CPython/PSF and pypdf/BSD notices remain applicable alongside this application's MIT license. Dependencies are unmodified apart from repacking pypdf source files; no generated user state or credentials belong in build output.

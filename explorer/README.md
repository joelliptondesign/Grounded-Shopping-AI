# Local repository explorer

Documentation shell, system explorer and Phase 5 UI gallery for Grounded Shopping AI. This is separate from the shopping application and its Python server. It reads a curated set of repository text sources; it does not call models, load environment files, or change source content.

## Start

Requires Node.js 22 or newer. From the repository root:

```sh
npm ci --prefix explorer --ignore-scripts --no-audit --no-fund
npm start --prefix explorer
```

Open [localhost:8766](http://localhost:8766). Stop with Control+C. To choose a different local port, set `EXPLORER_PORT` for that process. The server binds to 127.0.0.1, validates Host/Origin, serves only its own shell/resources, and does not expose an arbitrary filesystem endpoint.

Dependencies and their lockfile belong to this directory. `node_modules/` is deliberately excluded by the explorer-local ignore file; existing repository ignore rules remain untouched. Generated bundles and snapshots are created in OS temporary directories, not alongside authored files. The server removes its owned generated directory on normal shutdown. `npm run build --prefix explorer` performs a build check and writes a snapshot/bundle to a printed temporary directory; this output is not a standalone hosted site because the UI uses the local snapshot/freshness endpoints.

## Browse

Overview presents Project Context. Documentation groups current source documents by topic, with tables, code blocks, anchors and rendered Mermaid diagrams. Search covers curated current pages and system node labels/implementation paths. System presents selectable Live, synthetic-evidence, presentation-fixture and separate Demo parts. Each part links to its responsibility document, related parts, and raw implementation sources. Stable node/view routes preserve browser history and source-panel selection. The map is curated explanation, not an observed runtime trace. UI Gallery uses the actual shopper document in an isolated same-origin frame. Ten named synthetic states cover recommendations, comparisons, suggested replies and a deliberate missing-product error. Switch examples, clear/reset the preview, inspect inputs and sources, and read controlled click events. The interface stays minimal with brand links and an active-tab underline.

View source opens the snapshot's original text and its SHA-256 hash. Implementation links and explicit linked historical/verification documents open the same source panel, labeled by classification. Included uncommitted content is visible. Snapshot provenance records HEAD, dirty status, generation time and included source hashes. These are identity/freshness details, not approval or correctness certification.

Refresh snapshot rebuilds from current repository files. A 15-second check (and window focus) compares hashes and Git metadata, showing a stale notice until refreshed. A missing required page stops refresh and preserves the previous valid snapshot. Server loss is labeled; it is never reported as current content.

## Sources and boundaries

[Manifest](../docs/explorer/manifest.json) owns stable IDs, titles, grouping and explicit source paths; existing Markdown owns prose. Direct Markdown links from curated pages and required system manifest references add permitted text files to the snapshot. There is no recursive scan or full-code search. Missing/excluded links explain their limitation. Binary image references appear as labeled text; image preview is outside Phase 3. Hidden paths, environment/secrets, logs, caches, unsupported files and symlinks are excluded. The manifest requires unique IDs/sources and system IDs, related pages and edge endpoints are validated. Required files, documentation anchors and optional implementation symbols must resolve; symbol line numbers are generated from current snapshot content. Gallery IDs, named examples, fixture provenance and the existing preview contract are validated. An intentional error fixture must fail with its declared message.

Raw HTML is escaped and comments omitted from the reading view; original source text is preserved in the source panel. Documents are never compiled as Vue/JS. Mermaid runs in strict mode; diagram configuration directives are rejected, SVG navigation/event handlers are removed, and failed diagrams keep readable source. Remote links open separately; document images are not fetched. The shell's parser/diagram dependencies are bundled locally. The shopper preview serves pinned React/ReactDOM/Babel packages and the Nunito font locally. After dependency installation, gallery browsing requires neither CDN access nor shopping credentials. This is a development tool, not a sandbox for arbitrary hostile repositories.

## Verify

```sh
npm test --prefix explorer
npm run build --prefix explorer
```

Tests cover source scope, symlinks, manifest validation, escaping, link routing, classification, missing files and snapshot drift. Browser verification is separate. [Phase 3 evidence](../docs/explorer/PHASE-3-REPORT.md) records current checks and limits. [Phase 4 evidence](../docs/explorer/PHASE-4-REPORT.md) records system-map verification. [Phase 5 evidence](../docs/explorer/PHASE-5-REPORT.md) records gallery checks; Groundwork extraction remains deferred.

## Preview resources

Only the fixed preview document/scripts and one synthetic-example product image have executable/media routes. The document requires `?preview=1`. Runtime source and the local image are served from the snapshot, with included hashes and freshness checks; no shopping endpoints are provided. The frame retains the existing runtime's inline/evaluated script requirements, while its CSP limits scripts, fonts and connections to the local server. An explorer-only resource mapping uses the runtime's existing `__resources` hook; vendored runtime and shopper source remain unchanged. The explorer lockfile pins local runtime packages; package assets are copied at server startup and require a restart after dependency changes. This is a trusted local development preview, not a sandbox for executing hostile code.

The local `/api/preview-audit` counter records attempted shopping session requests during this server run. It supports bounded interaction verification, not general network telemetry. Reset reloads the selected input without changing its route and retries startup if needed. Switching examples reuses the mounted renderer instead of recreating its runtime. A bounded same-origin readiness probe can recover a missed startup signal. Snapshot refresh recreates the frame when its source identity changes. On small screens the fixed shopper surface scales to fit while preserving its existing UI.

## Pilot acceptance

[Phase 6 checks and limits](../docs/explorer/PHASE-6-REPORT.md) cover core navigation, all gallery states, source inspection, keyboard/mobile use, refresh recovery and preserved Demo rendering. Pattern descriptions explain what to inspect; About this example retains fixture provenance. Content links use the brand color and the active pattern uses a thin tab underline. Broader accessibility and long-term browser reliability are not established by this bounded pass.

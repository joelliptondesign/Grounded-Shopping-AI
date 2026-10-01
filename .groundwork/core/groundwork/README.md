# Schema runtime and build

Normal commands use validators.cjs with Node 22+ and Git; no runtime package install is required. JSON Schemas are authoritative. The generated validator uses Ajv 8.17.1, bundled by esbuild 0.25.10. AJV-LICENSE accompanies bundled runtime code. Build dependencies and their integrity hashes are pinned in package-lock.json.

From this directory:

```sh
npm ci --ignore-scripts
npm run build
```

Then run npm test from the repository root. The runtime rejects stale schema/validator pairs. Never edit validators.cjs by hand. Changes to modules, schemas, shared instructions and resolved project config invalidate relevant review fingerprints. No source-project test runner is included.

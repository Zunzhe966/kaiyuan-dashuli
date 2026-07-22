# Snapshot and Release Provenance Implementation Plan

> **Owner:** GPT-5.6 reviewer/publisher. This plan must not be executed by the DeepSeek data worker.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every tracked machine snapshot reproducible from the formal graph and make every production deployment prove both its catalog content and source commit.

**Architecture:** `data/domains/**` and `graph/edges.yaml` remain the canonical inputs. Both tracked snapshot exporters become callable deterministic functions, and regression tests rebuild into temporary directories and compare with tracked files. The site exporter adds a content-derived `catalog_hash` to every metadata document and optionally embeds the checked-out Git revision; GitHub Actions passes the revision and the post-deploy probe compares revision, hash, node count, and edge count.

**Tech Stack:** Python 3.12+, `unittest`, JSON, SHA-256, GitHub Actions, Cloudflare Wrangler.

---

## File Map

- `scripts/published_catalog.py`: canonical hash helpers shared by exports.
- `scripts/export_catalog_v1.py`: deterministic V1 catalog export and metadata provenance.
- `scripts/export_atlas_json.py`: deterministic legacy aggregate export.
- `scripts/build_static_site.py`: pass source revision into the site machine API.
- `tests/test_published_catalog.py`: catalog hash behavior.
- `tests/test_export_catalog_v1.py`: tracked `dist/v1` consistency and provenance fields.
- `tests/test_export_atlas_json.py`: tracked `dist/atlas-index.json` consistency.
- `tests/test_build_static_site.py`: source revision reaches site metadata.
- `tests/test_surface_consistency.py`: deployment workflow checks all provenance fields.
- `.github/workflows/verify.yml`: build the verified site with the checked-out revision.
- `.github/workflows/pages-deploy.yml`: build and probe the exact verified revision.
- `dist/v1/**`: regenerated V1 snapshot.
- `dist/atlas-index.json`: regenerated legacy aggregate snapshot.

### Task 1: Lock the tracked V1 snapshot to the formal graph

**Files:**
- Modify: `tests/test_export_catalog_v1.py`
- Regenerate later: `dist/v1/**`

- [ ] **Step 1: Write the failing snapshot comparison test**

Add imports and a test that rebuilds from the formal graph while preserving the tracked timestamp:

```python
from scripts.atlas_lib import load_edges, load_nodes

@staticmethod
def _snapshot_content(path: Path):
    if path.suffix != ".json":
        return path.read_bytes()
    return json.loads(path.read_text(encoding="utf-8"))

def test_tracked_catalog_snapshot_matches_current_graph(self):
    tracked = Path("dist/v1")
    tracked_meta = json.loads((tracked / "meta.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        rebuilt = Path(directory) / "v1"
        export_catalog(
            rebuilt,
            load_nodes(None),
            load_edges(),
            generated_at=tracked_meta["generated_at"],
        )
        tracked_files = sorted(
            path.relative_to(tracked) for path in tracked.rglob("*") if path.is_file()
        )
        rebuilt_files = sorted(
            path.relative_to(rebuilt) for path in rebuilt.rglob("*") if path.is_file()
        )
        self.assertEqual(tracked_files, rebuilt_files)
        for relative in tracked_files:
            self.assertEqual(
                self._snapshot_content(tracked / relative),
                self._snapshot_content(rebuilt / relative),
                relative.as_posix(),
            )
```

- [ ] **Step 2: Run the test and verify the existing defect**

Run:

```bash
.venv/bin/python -m unittest tests.test_export_catalog_v1.ExportCatalogV1Tests.test_tracked_catalog_snapshot_matches_current_graph -v
```

Expected: FAIL because tracked `dist/v1` contains 389 nodes and 406 edges while the formal graph contains 495 nodes and 660 edges.

- [ ] **Step 3: Leave the test red until Tasks 2 and 3 define final metadata**

Do not regenerate hundreds of files yet. Keeping the test red prevents an intermediate snapshot format from being committed.

### Task 2: Make the legacy aggregate snapshot deterministic and testable

**Files:**
- Modify: `scripts/export_atlas_json.py`
- Create: `tests/test_export_atlas_json.py`
- Regenerate later: `dist/atlas-index.json`

- [ ] **Step 1: Write failing function and tracked-snapshot tests**

```python
import json
import tempfile
import unittest
from pathlib import Path

from scripts.atlas_lib import load_edges, load_nodes
from scripts.export_atlas_json import export_atlas_index


class ExportAtlasJsonTests(unittest.TestCase):
    def test_export_uses_explicit_stable_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "atlas.json"
            export_atlas_index(
                output,
                {"alpha": {"domain": "devtools", "name": "Alpha", "tag_list": []}},
                [],
                generated_at="2026-07-22T00:00:00Z",
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["generated_at"], "2026-07-22T00:00:00Z")
            self.assertEqual(payload["node_count"], 1)

    def test_tracked_atlas_snapshot_matches_current_graph(self):
        tracked = Path("dist/atlas-index.json")
        tracked_payload = json.loads(tracked.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "atlas.json"
            export_atlas_index(
                rebuilt,
                load_nodes(None),
                load_edges(),
                generated_at=tracked_payload["generated_at"],
            )
            self.assertEqual(
                json.loads(tracked.read_text(encoding="utf-8")),
                json.loads(rebuilt.read_text(encoding="utf-8")),
            )
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_export_atlas_json -v
```

Expected: ERROR because `export_atlas_index` does not exist.

- [ ] **Step 3: Extract the deterministic exporter**

Implement:

```python
from published_catalog import stable_generated_at

def export_atlas_index(output: Path, nodes: dict, edges: list[dict], generated_at: str) -> None:
    payload = {
        "name": "kaiyuan-dashuli",
        "title": "开源大梳理",
        "version": "0.2.0",
        "generated_at": generated_at,
        # existing repository, domains, node projection and edges stay unchanged
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    nodes = load_nodes(None)
    edges = load_edges()
    export_atlas_index(OUT, nodes, edges, stable_generated_at())
    print(f"wrote {OUT} nodes={len(nodes)} edges={len(edges)}")
    return 0
```

- [ ] **Step 4: Run the tests**

Expected: the explicit timestamp test passes and the tracked snapshot test fails with the known 389/406 versus 495/660 mismatch.

### Task 3: Add content and revision provenance to generated site metadata

**Files:**
- Modify: `scripts/published_catalog.py`
- Modify: `scripts/export_catalog_v1.py`
- Modify: `scripts/build_static_site.py`
- Modify: `tests/test_published_catalog.py`
- Modify: `tests/test_export_catalog_v1.py`
- Modify: `tests/test_build_static_site.py`

- [ ] **Step 1: Write failing catalog hash tests**

```python
from scripts.published_catalog import stable_catalog_hash

def test_catalog_hash_ignores_node_and_edge_order(self):
    records = [build_public_record("example-tool", SAMPLE)]
    edges = [
        {"from": "a", "to": "b", "type": "alternative_to"},
        {"from": "a", "to": "c", "type": "integrates_with"},
    ]
    self.assertEqual(
        stable_catalog_hash(records, edges),
        stable_catalog_hash(list(reversed(records)), list(reversed(edges))),
    )

def test_catalog_hash_changes_with_visible_content(self):
    first = [build_public_record("example-tool", SAMPLE)]
    second = [build_public_record("example-tool", dict(SAMPLE, summary="Changed"))]
    self.assertNotEqual(stable_catalog_hash(first, []), stable_catalog_hash(second, []))
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_published_catalog.PublishedCatalogTests.test_catalog_hash_ignores_node_and_edge_order tests.test_published_catalog.PublishedCatalogTests.test_catalog_hash_changes_with_visible_content -v
```

Expected: ERROR because `stable_catalog_hash` does not exist.

- [ ] **Step 3: Implement the canonical catalog hash**

```python
def stable_catalog_hash(records: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    canonical = {
        "nodes": sorted(records, key=lambda record: record["id"]),
        "edges": sorted(
            edges,
            key=lambda edge: json.dumps(
                edge, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        ),
    }
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

- [ ] **Step 4: Write failing metadata provenance tests**

Extend the export test call with `source_revision="abc123"` and assert:

```python
self.assertEqual(meta["source_revision"], "abc123")
self.assertRegex(meta["catalog_hash"], r"^[0-9a-f]{64}$")
```

Add a site build test that calls:

```python
build_site(output, nodes, edges, "https://atlas.example", source_revision="abc123")
meta = json.loads((output / "api/v1/meta.json").read_text())
self.assertEqual(meta["source_revision"], "abc123")
```

- [ ] **Step 5: Verify RED**

Run the two targeted test modules. Expected: failure because the exporter and site builder do not accept or emit `source_revision` and `catalog_hash`.

- [ ] **Step 6: Pass optional revision through the export boundary**

Change the signatures to:

```python
def export_catalog(..., generated_at: str, source_revision: str | None = None) -> None:
def build_site(..., base_url: str, source_revision: str | None = None) -> None:
```

Build metadata as a local dictionary, always add `catalog_hash`, and add `source_revision` only when non-empty. Add `--source-revision` to `build_static_site.py` and pass it into `build_site`.

- [ ] **Step 7: Run targeted tests**

Expected: all published catalog, catalog export and static site tests pass except the two intentionally stale tracked-snapshot tests.

### Task 4: Make GitHub Actions build and probe exact provenance

**Files:**
- Modify: `.github/workflows/verify.yml`
- Modify: `.github/workflows/pages-deploy.yml`
- Modify: `tests/test_surface_consistency.py`

- [ ] **Step 1: Strengthen the workflow contract test first**

Add assertions that both workflows pass `--source-revision`, and that the deploy probe compares `catalog_hash` and `source_revision` in addition to counts:

```python
verify = Path(".github/workflows/verify.yml").read_text(encoding="utf-8")
self.assertIn("--source-revision", verify)
self.assertIn("--source-revision", workflow)
self.assertIn('"catalog_hash"', workflow)
self.assertIn('"source_revision"', workflow)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_surface_consistency.SurfaceConsistencyTests.test_pages_deploy_waits_for_verified_main_and_uses_a_supported_probe_identity -v
```

Expected: FAIL because current workflows only compare node and edge counts.

- [ ] **Step 3: Pass the checked-out revision into both builds**

In each workflow build step:

```bash
SOURCE_REVISION="$(git rev-parse HEAD)"
.venv/bin/python scripts/build_static_site.py \
  --output build/site \
  --base-url https://kai-yuan-da-shu-li.pages.dev \
  --source-revision "$SOURCE_REVISION"
```

- [ ] **Step 4: Compare the full deployment identity**

The post-deploy probe reads these expected fields from built metadata:

```python
keys = ("node_count", "edge_count", "catalog_hash", "source_revision")
if live is not None and all(live.get(key) == built.get(key) for key in keys):
    break
```

Failure and success logs must print the hash and revision without printing secrets.

- [ ] **Step 5: Run the workflow contract and static site tests**

Expected: PASS.

### Task 5: Regenerate snapshots once and close the defect

**Files:**
- Regenerate: `dist/v1/**`
- Regenerate: `dist/atlas-index.json`

- [ ] **Step 1: Regenerate from the same formal inputs**

```bash
.venv/bin/python scripts/export_catalog_v1.py --output dist/v1
.venv/bin/python scripts/export_atlas_json.py
```

Expected: both exporters report 495 nodes and 660 edges.

- [ ] **Step 2: Re-run the two previously failing snapshot tests**

```bash
.venv/bin/python -m unittest \
  tests.test_export_catalog_v1.ExportCatalogV1Tests.test_tracked_catalog_snapshot_matches_current_graph \
  tests.test_export_atlas_json.ExportAtlasJsonTests.test_tracked_atlas_snapshot_matches_current_graph -v
```

Expected: PASS.

- [ ] **Step 3: Run complete local verification**

```bash
.venv/bin/python scripts/validate_graph.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/run_retrieval_eval.py
git diff --check
```

Expected: graph `19/495/660 OK`, all tests pass, retrieval `67/67`, and no whitespace errors.

- [ ] **Step 4: Commit in reviewable boundaries**

Commit code, tests and workflows first:

```bash
git add scripts tests .github/workflows
git commit -m "ci: verify catalog release provenance"
```

Commit generated snapshots separately:

```bash
git add dist/v1 dist/atlas-index.json
git commit -m "data: rebuild canonical machine snapshots"
```

- [ ] **Step 5: Push, open a PR, and require cloud evidence**

Push the feature branch, open a PR, and wait for `verify / test-and-build`. After merge, require `main` verify, `pages-deploy`, and live metadata to agree on `source_revision`, `catalog_hash`, node count and edge count. If Cloudflare authentication still fails, record that external blocker and continue Schema V2 work without claiming deployment stability.

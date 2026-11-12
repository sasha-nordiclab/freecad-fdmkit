# fdmkit: agent notes

Developing fdmkit; modelling rules: `skill/SKILL.md`, `rules.md`, `fem.md`. History: `git log -p AGENTS.md`.

Workflow: one working FCStd per project, history in Git; one small change -> focused check -> save the same file -> Git commit. No versioned copies, backup folders or per-revision scripts/reports unless requested.

## Setup
- Target: FreeCAD 27.1 weekly build 20261103, macOS arm64 (26.3 unsupported). Probe the API in the running FreeCAD.
- Layout: `fdmkit/__init__.py` core (helpers, features, checks, assembly, `help()`, `body()`, `run()`); `machining.py` CNC/CAM; `drawing.py` TechDraw dims; `tests.py` selftest (`--reload` reloads all). `Init.py` autoload; `tools/fc.py` client; `fdmkit_mcp/server.py` MCP server.
- The repo is symlinked as `~/Library/Application Support/FreeCAD/v27-1/Mod/fdmkit`.
- After editing: `python3 tools/fc.py --reload && python3 tools/fc.py --selftest` and `uvx ruff check`. Selftest (hidden documents) stays all-OK; add a check per new function.
- `docs_sync`: every public call needs `` `name( `` in the README table, its name in the MCP DESCRIPTION, and a signature in DESCRIPTION or `help()` (`_HELP`). `instructions_len`: INSTRUCTIONS <= 4096 bytes (Claude Code cuts longer ones). `description_len`: DESCRIPTION <= 6000 chars. MCP texts quote `rules.md "Section"`: keep those headings (prefix match).

## Kit rules
- Native PartDesign only (no Part::Feature blobs); one call = one transaction = one line; sketch helpers leave DoF 0.
- `run()`: namespace = `__all__` + `App` + `Gui` (`?expr` is always aborted). Parses first (`ERR parse`). `_alive(d)` guards commit/abort when a call closes the document (`reopen()`). `_finish` refuses a pad/pocket that changes nothing. `_autosave()` saves at most every 300 s after a write call. A failed batch rolls back, so a following `undo()` undoes the previous call.
- Errors: no console observer exists, so `_report_scan()` reads the Report view (`QTextEdit` 'Report view'), keeps error lines for `errors()`, appends to `~/Library/Logs/fdmkit/freecad.log`; they arrive after the call ("since the last call"). `mcp.log` there logs every call (5 MB rotation).
- Hidden documents: Gui document (selection helpers work), no ActiveView. `_body()` looks for `pdbody` in every 3D view (CAM simulator/sheet tabs have no active Body) and skips CAM tool-bit Bodies (ToolBit makes its own `BitBody`; `cam_job` adds one last).
- `check(*links)` checks assembled local parts, `check()` authoring Bodies; `case()` does not solve the Assembly. Fasteners objects: proxy module `Fasteners*`.
- i10g link view providers expose `ShapeAppearance`, not `ShapeMaterial`: `tools/patches/i10g-shapeappearance.patch`; `i10g_video()` refuses without it.
- `tools/orca_slice.py` needs OrcaSlicer 2.5+: user presets are copied into a scratch `--datadir` (`user/default`, `type` key added, `system` symlinked); the CLI resolves system parents from the `.opc` packs itself.
- FreeCAD crashes and their workarounds: `KNOWN_ISSUES.md`.
- en_DK locale: sheet values as formulas (`'=40.5'`); unit tokens (`h m s g l t mm deg in ...`) are rejected as aliases. 27.1 updates sheet dependents itself; no sheet observer (985 vs 2 ms per P()). Activate the document in its own call before editing (rollback belongs to the document active at call entry).

## Probed facts
- Tip: `body.newObject()` of a pattern/Mirrored leaves the Tip on the original; `_pattern()`/`mirror()` set it. Patterns get BaseFeature only on recompute: compare volumes after `_rc`.
- DressUp (Defeaturing, Thickness) on an earlier feature drops later features: Tip faces only. Thickness `Reversed=True` (default) = inwards; OCC fails on a grooved cylinder.
- PathPattern `RelativeToFirst=False` (default) can miss the solid silently: kit sets True. PointPattern: sketch circle centres, first = original.
- LinearPattern `Mode` Extent/Spacing (Spacing reads `Offset`); grid via `Direction2`/`Occurrences2`/`Mode2`/`Offset2`; `SuppressedIndices` flat = i*Occurrences2 + j (`SuppressedPositions` = (i, j)); indices set before `Occurrences` are dropped, so `linear()` sets them last (`polar` keeps them). `Part::LinkArrayLinear`: `Spacing` reads `Offset`, `Extent` reads `Length`.
- Assembly RigidGroup and Snapshot are App::FeaturePython proxies working without an active assembly; its selftest prints a harmless traceback (#34056). `mass()` uses OCC solid properties; the 'Default' material density 1e-9 kg/mm³ is a placeholder.
- Regions: `MakeInternals` is False for Python sketches; `InternalShape` is sketch-local, `getSubObject('InternalFaceN')` global; N = index in `InternalShape.Faces` + 1 (outer region has holes cut out). Support = `Profile` LinkSub `(sketch, ['InternalFace2', ...])`; `Profile = sketch` = whole sketch. Deleting another contour remaps N; deleting the region leaves `?InternalFaceN`, Invalid, old shape.
- `StartOffset` runs along the feature (pad +normal, pocket along the cut = -normal), `Reversed` flips both; Revolution `StartOffset` is an angle. `side='two'`: hidden `Length2` default (pad 10, pocket 5). Hole: `ThreadType` takes `ThreadSize` from the diameter and replaces `Diameter` by the tap drill; `DrillPoint='Angled'` adds a cone below `Depth`.
- `Gui.Selection.getSelectionEx('', 0)` gives the Body with subname `pad.;#14:1;...F.Face6`; `getSubObject(sub, retType=1)` gives the leaf; 'Body.Face6' is the Tip's face.
- `SketchObject.solve()` marks a clean sketch Touched (recompute debt, undo step); DoF is stored in the file, so checks solve only Touched sketches.
- `full()` repoints a lost joint reference only on detached joints (a joint without Detach would jump to the part origin); the others are reported.
- `Mesh.foraminate` and `nearestFacetOnRay` hit on both sides of the ray (filter by direction) and graze chords at edges (confirm on the exact solid). Draft clone of a PartDesign feature keeps its sketch frame: Placement = `index * feature.Placement`.
- CAM: CAM_SimulatorGL is 3-axis, lists only `Job*`, opens as an MDI tab; work-plane ops store paths in the plane frame; no lathe ops; Rotary Surface needs opencamlib + a rotary Machine (not wrapped).

## Upstream issues, still reproducing on 27.1 20261103
Repro: `FREECAD_USER_HOME=$(mktemp -d) freecadcmd x.py`. Drop a workaround when its repro passes.
- #34054 `Body.newObject()` of Mirrored/PolarPattern leaves the Tip behind: `_pattern()`/`mirror()` set the Tip.
- #34055 Thickness/Defeaturing on an earlier feature drops later ones: Tip faces only.
- #33685 deleting objects with sheet expressions segfaults the next sheet change: clear expressions, recompute, delete (rules.md "API traps").
- #33798 (not ours) `exportPageAsPdf` segfault, not re-tested: `run()` refuses it.

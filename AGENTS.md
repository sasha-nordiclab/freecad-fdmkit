# fdmkit: agent notes

These notes cover developing fdmkit itself. For modelling, see `skill/SKILL.md` and `skill/rules.md`.

- Target: FreeCAD 26.3 RC1 on macOS arm64; also keep the 2026-09-29 weekly working. The API is checked with probes against the running FreeCAD, not from memory.
- Layout:
  - `fdmkit/__init__.py` is the whole kit.
  - `Init.py` is the autoload entry.
  - `tools/fc.py` is the XML-RPC client.
  - `fdmkit_mcp/server.py` is the MCP server: one tool, `run`, no dependencies.
- This repo is symlinked as `~/Library/Application Support/FreeCAD/v26-3/Mod/fdmkit`.
- After editing, run `python3 tools/fc.py --reload && python3 tools/fc.py --selftest`. The selftest must stay all-OK; add a check for each new function.
- Rules:
  - Only native PartDesign: no Part::Feature blobs.
  - Each call is one transaction and returns one line.
  - Sketch helpers leave the sketch at DoF 0.
- `run()` namespace (`_ns()`): the `__all__` calls plus `App` and `Gui` for both `?expr` reads and transactions. Before 2026-10-20 `?expr` had no `Gui` and transactions had no `App` (NameError).
- Hidden documents (selftest) still have a Gui document, so selection-based helpers (`freeze_all`, `thaw_all`) are testable there.
- FreeCAD 26 view providers of links expose `ShapeAppearance` (a material list), not `ShapeMaterial`; addons written for 0.19/0.21 break on it. Our fix for i10g is `tools/patches/i10g-shapeappearance.patch`; `i10g_video()` refuses to run without it.
- Locale is en_DK, so Spreadsheet values are written as formulas (`'=40.5'`).
- FreeCAD rejects unit tokens (`h m s g l t mm deg in ...`) as alias names.
- Spreadsheet alias changes in the tested weekly needed `_SheetObserver` to touch dependents. Keep the workaround unless an isolated RC1 regression test proves it unnecessary.
- 26.3 properties used by the kit include StartType/StartOffset/StartReference, Common on subtractive features, Hole cosmetic threads and PolarPattern SuppressedIndices. Probe property availability and enumeration values before adding more features.
- `run()` must survive a call that closes the active document (`reopen()`): `_alive(d)` guards the commit and abort, which used to fail with "Cannot access attribute 'abortTransaction' of deleted object". `run()` refuses any expression containing `exportPageAsPdf`, which crashed FreeCAD 26.3.
- Model checks (`check`, `lint`, `case`, `sel`, `reopen`) came from the ORWO 828 revision (2026-10-24). There a PartDesign Hole whose sketch was tangent to the cylinder dropped one of two holes between recomputes, and features left at an absolute Z drifted when the parent part grew. Fasteners objects are recognised by a proxy module starting with `Fasteners`. The selftest covers each check; tangent detection was verified on the ORWO model (six tangent sketches found with the standoff set to 0).

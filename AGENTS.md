# fdmkit: agent notes

These notes cover developing fdmkit itself. For modelling, see `skill/SKILL.md` and `skill/rules.md`.

- Target: FreeCAD 26.3dev weekly (OCC 8.0.1, Py 3.13, macOS). The API is checked with probes against the running FreeCAD, not from memory.
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
- Locale is en_DK, so Spreadsheet values are written as formulas (`'=40.5'`).
- FreeCAD rejects unit tokens (`h m s g l t mm deg in ...`) as alias names.
- 26.3dev bug: a change to an aliased cell does not touch its dependents. `_SheetObserver` works around it.

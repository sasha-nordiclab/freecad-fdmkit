# fdmkit

A small FreeCAD kit that lets an AI agent (Claude Code, Codex or any MCP client) build parametric parts for FDM printing in the FreeCAD you have open, while you watch the model grow in the GUI.

It exposes **one MCP tool**, `run(expr)`. The agent sends a short batch of calls such as `sk('base','XY'); rect('base','w','d'); pad('base','h')`. fdmkit runs the batch as one undoable transaction and returns one line: `OK`, the numbers asked for, or the error and the step that failed.

## What it does

- **Native PartDesign only.** Bodies, datum planes, sketches, Pad, Pocket and Revolve: the same model you would build by hand, editable in the GUI afterwards. No imported meshes, no `Part::Feature` blobs.
- **Fully constrained sketches.** Every sketch helper (`rect`, `circ`, `slot`, `poly`, `fil`) adds its own constraints. A call fails and rolls back unless the sketch ends at 0 degrees of freedom.
- **Sizes live in a spreadsheet.** `P(w=40, d='w/2')` writes to a `params` sheet. Sketches and features refer to the parameters by name, so changing one value updates the whole part.
- **One call, one transaction.** If any step of a batch fails, the whole batch is undone and the reply names the failing step. `undo()` reverts the last batch. Documents that have a file are saved at most every 5 minutes.
- **Checks.** `chk()` reports broken features, sketches not at 0 degrees of freedom and a body that is not one valid solid; `why(name)` explains one failure, and `tree()` prints the feature tree.
- **FDM rules for the agent.** [`skill/rules.md`](skill/rules.md) covers walls, overhangs, holes, fits, edges and print orientation. [`skill/fem.md`](skill/fem.md) is a method for strength checks with FreeCAD FEM and CalculiX. The MCP server sends a short version of these rules to the agent when it connects.
- **Print time and grams.** [`tools/orca_slice.py`](tools/orca_slice.py) slices an STL with the OrcaSlicer CLI using your own presets and reads the time and filament weight from the G-code.

## Requirements

- macOS. The paths in `tools/fc.py` and `tools/orca_slice.py` are macOS paths; on Linux or Windows, change them.
- FreeCAD 26.3 development build. fdmkit is developed and tested on the weekly build of 2026-09-29 (OCC 8.0.1, Python 3.13); older versions are untested. When FreeCAD changes, the Report view asks you to run the selftest.
- The [FreeCAD MCP addon](https://github.com/neka-nat/freecad-mcp) (`FreeCADMCP`), for its XML-RPC server on `127.0.0.1:9875`. fdmkit uses only that RPC server, not the addon's own MCP server.
- Python 3.10 or newer on the host for the MCP server. It has no dependencies.
- Optional: OrcaSlicer, for `orca_slice.py`.

## Install

1. Clone the repository and link it into FreeCAD's `Mod` folder. The folder name depends on the FreeCAD version; for the 26.3 builds it is `v26-3`:

   ```sh
   git clone https://github.com/sasha-nordiclab/fdmkit.git
   ln -s "$PWD/fdmkit" "$HOME/Library/Application Support/FreeCAD/v26-3/Mod/fdmkit"
   ```

   If your folder is different, also change `MOD` in [`tools/fc.py`](tools/fc.py).

2. Install the FreeCAD MCP addon from the Addon Manager. Start its RPC server from the **MCP Addon** workbench, and turn on **Auto-Start** so it starts with FreeCAD.

3. Restart FreeCAD. The Report view shows the fdmkit version line once the kit has loaded.

4. Check the connection. The selftest builds a throwaway part and checks every function:

   ```sh
   python3 tools/fc.py --selftest
   ```

5. Register the MCP server with your agent.

   Claude Code:

   ```sh
   claude mcp add fdmkit -- python3 /path/to/fdmkit/fdmkit_mcp/server.py
   ```

   Codex (`~/.codex/config.toml`):

   ```toml
   [mcp_servers.fdmkit]
   command = "python3"
   args = ["/path/to/fdmkit/fdmkit_mcp/server.py"]
   tool_timeout_sec = 180
   ```

6. Optional, for Claude Code: copy or link [`skill/`](skill/) into `~/.claude/skills/fdmkit/` so that the agent loads the modelling workflow and the FDM rules when it needs them.

## Use

Ask the agent for a part in plain words. To call fdmkit yourself from a terminal:

```sh
python3 tools/fc.py "new('Clip'); P(w=40, d=20, h=6)"
python3 tools/fc.py "sk('base','XY'); rect('base','w','d'); pad('base','h')"
python3 tools/fc.py "plane('top','XY','h'); sk('hole','top'); circ('hole',4.4); pocket('hole')"
python3 tools/fc.py "chk()"
```

After editing the kit, reload it without restarting FreeCAD, then run the selftest:

```sh
python3 tools/fc.py --reload && python3 tools/fc.py --selftest
```

### Calls

| Call | Does |
|---|---|
| `new(name)` | New document with a Body and a `params` sheet |
| `P(name=val, ...)` / `P()` | Set parameters / list them |
| `plane(name, base='XY', offset=0)` | Datum plane on an origin plane or on another datum |
| `sk(name, on='XY')` | Sketch on an origin plane or a datum |
| `rect(sk, w, h, x=0, y=0, at='c')` | Rectangle, centred (`'c'`) or from its bottom-left corner (`'bl'`) |
| `circ(sk, d, x, y)` | Circle |
| `slot(sk, length, width, x, y, angle)` | Slot with round ends |
| `poly(sk, [(x, y), ...])` | Closed polygon |
| `fil(sk, (x, y), r)` | Sketch fillet at the corner nearest to the point |
| `pad(sk, len, side='one', reverse=False)` | Pad; `side` is `'one'`, `'two'` or `'sym'` |
| `pocket(sk, depth='through')` | Pocket |
| `revolve(sk, angle=360, axis='V_Axis')` | Revolution |
| `dim(sk, 'r1_w', val)` | Change one named sketch dimension |
| `chk()` / `why(name)` / `tree()` | Checks, one failure explained, feature tree |
| `undo()` | Undo the last batch |

Lengths and angles take a number, a parameter name or an expression such as `'wall*2'`.

## Security

fdmkit runs code in FreeCAD through the addon's XML-RPC server, and the copy it was developed with has no token. Any program on the same computer that can reach `127.0.0.1:9875` can run arbitrary Python inside FreeCAD. Keep the addon's **Remote Connections** setting off, so that the server stays on localhost.

## Known FreeCAD 26.3dev issues it works around

- Changing a spreadsheet cell that is referenced by its alias does not update the model. fdmkit installs a document observer that marks the sheet's dependents as changed.
- With a decimal-comma locale, numbers written to the spreadsheet are stored as formulas (`'=40.5'`).
- FreeCAD rejects unit names (`h`, `m`, `s`, `g`, `l`, `t`, `mm`, `deg`, `in`, ...) as aliases, so parameters cannot be called that.

## License

[CC BY-NC-SA 4.0](LICENSE): free to use, change and share for non-commercial purposes, with attribution, under the same license.

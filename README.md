# fdmkit

A small FreeCAD kit that lets an AI agent (Claude Code, Codex or any MCP client) build parametric parts for FDM printing in the FreeCAD you have open, while you watch the model grow in the GUI.

It exposes **one MCP tool**, `run(expr)`. The agent sends a short batch of calls such as `sk('base','XY'); rect('base','w','d'); pad('base','height')`. fdmkit runs the batch as one undoable transaction and returns one line: `OK`, the numbers asked for, or the error and the step that failed.

## What it does

- **Native PartDesign only.** Bodies, datum planes, sketches, Pad, Pocket, Hole, Revolution, Groove and patterns: the same model you would build by hand, editable in the GUI afterwards. No imported meshes, no `Part::Feature` blobs.
- **Fully constrained sketches.** Every sketch helper (`rect`, `circ`, `slot`, `poly`, `fil`) adds its own constraints. A call fails and rolls back unless the sketch ends at 0 degrees of freedom.
- **Sizes live in a spreadsheet.** `P(w=40, d='w/2')` writes to a `params` sheet. Sketches and features refer to the parameters by name, so changing one value updates the whole part.
- **One call, one transaction.** If any step of a batch fails, the whole batch is undone and the reply names the failing step. `undo()` reverts the last committed batch and names it; right after an ERR (already rolled back) it refuses once. `?expr` reads discard any change they make. Documents that have a file are saved at most every 5 minutes.
- **Checks.** `chk()` reports broken features, sketches not at 0 degrees of freedom and a body that is not one valid solid; `why(name)` explains one failure, and `tree()` prints the feature tree.
- **FDM rules for the agent.** [`skill/rules.md`](skill/rules.md) covers walls, overhangs, holes, fits, edges and print orientation. [`skill/fem.md`](skill/fem.md) is a method for strength checks with FreeCAD FEM and CalculiX. The MCP server sends a short version of these rules to the agent when it connects.
- **Print time and grams.** [`tools/orca_slice.py`](tools/orca_slice.py) slices an STL with the OrcaSlicer CLI using your own presets and reads the time and filament weight from the G-code.

## Requirements

- macOS. The paths in `tools/fc.py` and `tools/orca_slice.py` are macOS paths; on Linux or Windows, change them.
- FreeCAD 26.3 or newer. fdmkit is tested on 26.3 RC1/RC2 and the 27.1 weekly build of 2026-10-27; older versions are untested. When FreeCAD changes, the Report view asks you to run the selftest.
- The [FreeCAD MCP addon](https://github.com/neka-nat/freecad-mcp) (`FreeCADMCP`), for its XML-RPC server on `127.0.0.1:9875`. fdmkit uses only that RPC server, not the addon's own MCP server.
- Python 3.10 or newer on the host for the MCP server. It has no dependencies.
- Optional: OrcaSlicer, for `orca_slice.py`.

## Install

1. Clone the repository and link it into FreeCAD's `Mod` folder. The folder name depends on the FreeCAD version: `v26-3` for 26.3, `v27-1` for the 27.1 weekly builds:

   ```sh
   git clone https://github.com/sasha-nordiclab/freecad-fdmkit.git fdmkit
   ln -s "$PWD/fdmkit" "$HOME/Library/Application Support/FreeCAD/v27-1/Mod/fdmkit"
   ```

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
python3 tools/fc.py "new('Clip')"
python3 tools/fc.py "P(w='40 mm', d='20 mm', height='6 mm')"
python3 tools/fc.py "sk('base','XY'); rect('base','w','d'); pad('base','height')"
python3 tools/fc.py "plane('top','XY','height'); sk('hole','top'); circ('hole',4.4); pocket('hole')"
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
| `midplane(name, a, b)` | Datum plane midway between two planes or faces (bisector if they are not parallel) |
| `sk(name, on='XY')` | Sketch on an origin plane or a datum |
| `rect(sk, w, h, x=0, y=0, at='c')` | Rectangle, centred (`'c'`) or from its bottom-left corner (`'bl'`) |
| `circ(sk, d, x, y)` | Circle |
| `slot(sk, length, width, x, y, angle)` | Slot with round ends |
| `poly(sk, [(x, y), ...])` | Closed polygon |
| `fil(sk, (x, y), r)` | Sketch fillet at the corner nearest to the point |
| `half(sk)` | Keep the upper half of a symmetric sketch, close along its horizontal axis and preserve driving dimensions |
| `regions(sk)` | Closed regions of a sketch (26.3 internal faces): name, area, an inner point for `at=`, holes |
| `remap(feature, *at)` | Point a Pad/Pocket at the regions under the given sketch points again after a sketch edit lost them; no points = whole sketch |
| `pad(sk, len, side='one', reverse=False, start='profile', offset=0, reference=None, at=None, length2=None)` | Pad; `side` is `'one'`, `'two'` (needs `length2`) or `'sym'`; `at=(x, y)` or a list pads only the sketch regions under those points |
| `pocket(sk, depth='through', side='one', reverse=False, start='profile', offset=0, reference=None, operation='subtract', at=None, depth2=None)` | Pocket; `operation='common'` keeps the intersection; `at=` as for `pad` ; `side='two'` needs `depth2` |
| `hole(sk, diameter, depth='through', start='profile', offset=0, reference=None, thread_type=None, thread_size=None, model_thread=False, cosmetic_thread=True, operation='subtract', drill_point='flat')` | PartDesign Hole; blind holes have a flat floor at `depth` (`'angled'` adds the drill cone below it); threaded: `diameter` is the nominal size (4 → M4x0.7) and the result names the thread and tap drill; cosmetic threads do not make printable thread geometry |
| `revolve(sk, angle=360, axis='V_Axis', start='profile', offset=0, reference=None, type='angle', up_to=None)` | Revolution; `type` is `'angle'`, `'up_to_face'`, `'up_to_first'` or `'up_to_last'`; also accepts `side`, `reverse`, `project_axis` |
| `groove(sk, angle=360, axis='V_Axis', start='profile', offset=0, reference=None, operation='subtract', type='angle', up_to=None)` | Subtractive revolution; `type` is `'angle'`, `'up_to_face'`, `'up_to_first'` or `'through'`; also accepts `side`, `reverse`, `project_axis` |
| `linear(features, direction, count, step=None, extent=None, direction2=None, count2=1, suppressed=())` | Native LinearPattern along an origin axis or edge; `direction2`/`count2` make a grid in one feature; `suppressed` takes indices or `(i, j)` grid pairs |
| `polar(features, occurrences, axis='Z', angle=360, suppressed=())` | Native PolarPattern; suppressed instance indices start at zero |
| `circular(features, rings, radial, tangential, axis='Z', symmetry=1)` | CircularPattern: concentric rings `radial` apart, instances `tangential` apart along each ring |
| `path_pattern(features, path, count=None, spacing=None, align=False)` | PathPattern along an edge or sketch; the first instance is the original |
| `point_pattern(features, points)` | PointPattern at the points or circle centres of a sketch (or `'Feature.VertexN'`); the first point marks the original |
| `defeature(faces)` / `thickness(faces, value, mode='skin', join='arc', inward=True)` | Remove faces and heal the solid / shell with the faces open (`mode='recto_verso'` = half on each side) |
| `mirror(features, plane='XY')` / `move(feature, after)` | Native mirror and feature tree reordering |
| `dim(sk, 'r1_w', val)` | Change one named sketch dimension |
| `chk(body=None)` / `why(name)` / `tree()` | Checks of one Body (default the active one), one failure explained, feature tree |
| `undo()` | Undo the last committed batch and name it; refuses once right after an ERR |
| `errors(keep=False)` | New errors and tracebacks from FreeCAD's Report view since the last call, one line; when FreeCAD reported errors since the previous call, the result ends with ` \| FreeCAD report: N new errors since the last call`. Also logged to `~/Library/Logs/fdmkit/freecad.log`; the MCP server logs every call to `~/Library/Logs/fdmkit/mcp.log` |
| `selftest()` | Build throwaway parts in hidden documents and check every call; one line with the failures |
| `focus(body, ...)` / `full()` | Recompute only these Bodies until `full()`, which recomputes everything and solves every Assembly |
| `freeze(name, ...)` / `thaw(name, ...)` | Std_ToggleFreeze on heavy objects (Assembly, gears, STEP parts) |
| `freeze_all()` / `thaw_all()` | Freeze or thaw every object except links, parts and groups (animations, view-only work) |
| `i10g_video(delay_ms=300)` | Render the document's Inbetweening (i10g) `Animation` to its output file without blocking the call; hidden links are dropped from the steps |
| `check(*bodies)` | Whole document: one valid solid per Body, no object in error, sketches at DoF 0, no volume intersection between Bodies, every Fasteners object on a hole axis |
| `lint()` | Known traps: features whose sketch region or reference was lost (`?InternalFaceN`), Hole sketch tangent to a cylinder, countersink apex on the hole floor, deactivated sketches placed by plain numbers, expressions that reach into another Body, unused params aliases |
| `case('alias' or 'sheet.alias', value)` | Parametric stress test: set the value, `check()`, restore it (TechDraw pages paused meanwhile) |
| `cnc(*bodies, skip=(), cutter=None, holes=False)` | CNC check, lathe + 4-axis mill: sharp inside corners without a reachable floor, fillets below the cutter radius, unreachable milled faces, narrow/deep slots, lathe grooves, deep holes, thin walls; `cnc_show()` / `cnc_restore()` paint the faces |
| `cam_job(name, body, stock, azimuth, cutter)`, `cam_slot(job, p1, p2, depth)`, `cam_sim(job)`, `cam_del(job)` | Native CAM setup per A-axis index, Slot op in part coordinates, CAM_SimulatorGL, CAM teardown |
| `sel()` | The GUI selection (planes, cylinders, circles, vertices) and, for two items, the distance, the angle between their axes or normals and the distance of parallel hole axes |
| `mass(*objs, density=None)` | Volume, mass (material or `density` in g/cm³), centre of gravity and principal moments |
| `link_array(source, kind, count, step, axis, angle, path, points, into)` | Part link array (`'linear'`, `'polar'`, `'path'`, `'point'`): App::Link instances that Assembly joints can attach to |
| `rigid_group(*links)` / `snapshot(name)` / `snapshot_restore(name, solve=True)` | Assembly Rigid Group joint; store and restore a pose (placements and visibility) |
| `reopen()` | Save, close, reopen and recompute the active document |

Lengths and angles take a number, a parameter name or an expression such as `'wall*2'`.

A call that starts with `?` is read-only: no transaction, no recompute, no autosave. Both kinds of call see the functions above plus `App` and `Gui`; import other modules inside the call.

For the 26.3 start modes, use `start='offset', offset='wall'` or `start='reference', reference='top_plane'`. Start references must be origin or datum planes or a sketch region `(sk, (x, y))`; the offset runs along the feature (a pocket's into its cut); `up_to`, paths and faces also take `'Feature.Face3'` / `'sketch.Edge1'`, as `sel()` prints them. Every pattern call makes the pattern the Body Tip and fails if the pattern changes nothing. `hole` accepts FreeCAD thread type and size names reported by that build; a cosmetic thread is metadata/visualization and does not appear as helical STL geometry. `polar` counts the original as one occurrence. Unsupported 26.3 properties fail with a clear error instead of silently changing the model.

## Security

fdmkit runs code in FreeCAD through the addon's XML-RPC server, and the copy it was developed with has no token. Any program on the same computer that can reach `127.0.0.1:9875` can run arbitrary Python inside FreeCAD. Keep the addon's **Remote Connections** setting off, so that the server stays on localhost.

## Known FreeCAD 26.3/27.1 issues it works around

- Changing a spreadsheet cell that is referenced by its alias does not update the model. fdmkit installs a document observer that marks the sheet's dependents as changed.
- With a decimal-comma locale, numbers written to the spreadsheet are stored as formulas (`'=40.5'`).
- Link view providers have `ShapeAppearance` instead of `ShapeMaterial`, which breaks the Inbetweening (i10g) animation workbench. Apply `tools/patches/i10g-shapeappearance.patch` in its `Mod/Inbetweening` folder (`patch -p1 < ...`); `i10g_video()` checks for it.
- FreeCAD rejects unit names (`h`, `m`, `s`, `g`, `l`, `t`, `mm`, `deg`, `in`, ...) as aliases, so parameters cannot be called that.

## License

[CC BY-NC-SA 4.0](LICENSE): free to use, change and share for non-commercial purposes, with attribution, under the same license.

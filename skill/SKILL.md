---
name: fdmkit
description: Model FDM and metal CNC parts in the user's running FreeCAD through the fdmkit MCP tool run(expr) — native PartDesign, sketches at DoF 0, sizes in the params sheet; CNC checks (cnc()) and native CAM cutter simulation (cam_job/cam_slot/cam_sim). Use for any FreeCAD modelling, editing or checking ("сделай модель", "поправь", "добавь паз", "проверь", "проверь под ЧПУ/токарку").
---

# fdmkit

All modelling goes through MCP `fdmkit.run(expr)`. No raw FreeCAD scripts, no screenshots.
The user watches the model in the GUI. Reply only with OK, the errors or the numbers.

- Batch related steps into one call: `sk('s','XY'); rect('s','w','d'); pad('s','height')`. It is one transaction, so any ERR rolls back the whole batch.
- Model each Body about its own functional origin/symmetry planes; native Assembly joints position its Links. Use geometric relationships and construction geometry before minimal named dimensions, never per-vertex coordinate grids or mass Block/Fixed. For migration and assembly-aware checks, follow rules.md "Local part coordinates and assembly placement"; use `check(*assembly_link_names)` for locally authored Bodies.
- Every size is a `P(...)` parameter. Pass param names or expressions, not literals: `rect('s','w','d')`.
- Sketches attach to stable origin or datum planes, never generated faces. For parallel loft sections, use one origin plane with each sketch’s expression-driven `AttachmentOffset.Base.z` instead of creating a datum plane per section. Use `plane(name, base, offset)` when a distinct geometric reference is needed. Keep sketches fully constrained and verify the loft after simplifying supports.
- FreeCAD 26.3 starts: `pad`, `pocket`, `revolve`, `groove` and `hole` accept `start='offset', offset=expr` or `start='reference', reference='datum'`. Use a datum or origin plane for references; keep the Body one valid solid.
- Sketch regions (26.3 internals): `pad`/`pocket(..., at=(x, y))` use only the closed regions under sketch-coordinate points; `regions(sk)` lists them; `remap(feature, (x, y))` repairs a feature after `lint()` reports a lost region. Details: rules.md "Sketch regions".
- For holes use `hole(sk,diameter,depth='through')`; blind holes get a flat floor (`drill_point='angled'` adds the cone below depth); threaded holes take the nominal diameter (4 → M4x0.7). `pad`/`pocket(side='two')` need `length2`/`depth2`. `thread_type='ISOMetricProfile'` with `cosmetic_thread=True` stores thread metadata but does not create printable turns. Use `model_thread=True` only when real thread geometry is needed and verify the mesh.
- `pocket`, `groove` and `hole` accept `operation='common'` to retain the intersection. `polar(features,occurrences,axis='Z',suppressed=(...))` uses zero-based instance indices, counting the original. Rows and grids: `linear(features,'X',count,step=,direction2='Y',count2=)`, one feature for 2x2 mount holes.
- FreeCAD 26.3/27.1 calls (when to use which: rules.md "FreeCAD 26.3 / 27.1 features"): `midplane(name, a, b)`; `revolve`/`groove` with `type='up_to_face', up_to=...`, `'up_to_first'`, `'through'` and `project_axis=True`; patterns `circular`, `path_pattern`, `point_pattern` (every pattern becomes the Tip); `defeature(faces)` and `thickness` on faces of the Tip only, `thickness(faces, value, mode='skin'|'recto_verso')`; `mass(*objs, density=)`; Assembly `link_array`, `rigid_group`, `snapshot`/`snapshot_restore`. Faces and edges are named `'Feature.Face3'` / `'sketch.Edge1'`, as `sel()` prints them.
- A result ending in ` | FreeCAD report: N new errors since the last call` means FreeCAD or an addon logged errors: read `errors()` and fix the cause before going on. History: `~/Library/Logs/fdmkit/freecad.log` (FreeCAD errors) and `mcp.log` (every call).
- On ERR call `why(name)`; when in doubt use `tree()` and `chk()`. An ERR has already rolled the batch back; `undo()` reverts the last committed call (and refuses once right after an ERR). `reopen()` clears the undo history.
- After every model change: `reopen()`, `check()` (whole document: solids, errors, DoF, Body intersections, screws on hole axes) and `lint()` (tangent hole sketches, countersink apex on the hole floor, sketches placed by numbers, cross-Body refs, unused params). Stress-test a parametric model with `case('alias', value)`. When the user selected faces, read them with `sel()`.
- Reference every feature to a real datum through params, never to an absolute Z (rules.md, "Feature order and checks"). For reverse engineering from caliper measurements, follow rules.md "Measured reverse engineering".
- Before deleting anything that uses `params` in an expression, clear its expressions and recompute; otherwise the next sheet change segfaults FreeCAD 26.3 (rules.md, API traps).
- Load `rules.md` (next to this file) before choosing walls, clearances, holes, overhangs, print orientation, materials or renders.
- Load `fem.md` before any strength check, load analysis, lightening or reinforcement.
- Before modelling a component, check native FreeCAD features, installed workbenches, standard parts and manufacturer CAD. Prefer a suitable standard solution after verifying its dimensions and interfaces; adapt it through supported parameters. Keep custom printable geometry native and fully constrained.
- Fasteners, heat-set inserts and gears come from the Fasteners and freecad.gears workbenches; do not draw them.
- Animations and exploded-view videos: ExplodedAssembly, i10g or Animate plus Assembly Simulation, not a hand-written placement loop. Follow rules.md "Animations and exploded views": `freeze_all()`, record i10g steps, fixed perspective camera, `i10g_video()` (async), wait for ffmpeg, `thaw_all()` + `full()`. i10g needs `tools/patches/i10g-shapeappearance.patch` on FreeCAD 26.
- `?expr` and normal calls both see `App` and `Gui`; import anything else inside the call.
- Use FreeCAD's standard workbench for each job; the full table of installed workbenches (Sketcher, PartDesign, Part, Spreadsheet, Assembly, Fasteners, freecad.gears, UNI-Rolling-Bearing, SheetMetal, Measure, Material, Fem, Plot, Mesh/MeshPart, Import, TechDraw, Draft, Surface, Inspection, Points/ReverseEngineering, OpenSCAD) is in rules.md, "Standard workbenches for each job". No Placement expressions to position or animate parts.
- Metal CNC parts: follow rules.md "Metal CNC parts" — run `cnc()` after each change with `check()` and `lint()`, show doubtful spots with `cam_job` + `cam_slot` + `cam_sim` (native CAM), remove Jobs with `cam_del()`.
- Export a file only when the user asks for one.

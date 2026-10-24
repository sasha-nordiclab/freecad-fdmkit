---
name: fdmkit
description: Model FDM parts in the user's running FreeCAD through the fdmkit MCP tool run(expr) — native PartDesign, sketches at DoF 0, sizes in the params sheet. Use for any FreeCAD modelling, editing or checking ("сделай модель", "поправь", "добавь паз", "проверь").
---

# fdmkit

All modelling goes through MCP `fdmkit.run(expr)`. No raw FreeCAD scripts, no screenshots.
The user watches the model in the GUI. Reply only with OK, the errors or the numbers.

- Batch related steps into one call: `sk('s','XY'); rect('s','w','d'); pad('s','h')`. It is one transaction, so any ERR rolls back the whole batch.
- Every size is a `P(...)` parameter. Pass param names or expressions, not literals: `rect('s','w','d')`.
- Sketches attach to stable origin or datum planes, never generated faces. For parallel loft sections, use one origin plane with each sketch’s expression-driven `AttachmentOffset.Base.z` instead of creating a datum plane per section. Use `plane(name, base, offset)` when a distinct geometric reference is needed. Keep sketches fully constrained and verify the loft after simplifying supports.
- FreeCAD 26.3 starts: `pad`, `pocket`, `revolve`, `groove` and `hole` accept `start='offset', offset=expr` or `start='reference', reference='datum'`. Use a datum or origin plane for references; keep the Body one valid solid.
- For holes use `hole(sk,diameter,depth='through')`. `thread_type='ISOMetricProfile'` with `cosmetic_thread=True` stores thread metadata but does not create printable turns. Use `model_thread=True` only when real thread geometry is needed and verify the mesh.
- `pocket`, `groove` and `hole` accept `operation='common'` to retain the intersection. `polar(features,occurrences,axis='Z',suppressed=(...))` uses zero-based instance indices, counting the original.
- On ERR call `why(name)`; when in doubt use `tree()` and `chk()`. Undo with `undo()`.
- Before deleting anything that uses `params` in an expression, clear its expressions and recompute; otherwise the next sheet change segfaults FreeCAD 26.3 (rules.md, API traps).
- Load `rules.md` (next to this file) before choosing walls, clearances, holes, overhangs, print orientation, materials or renders.
- Load `fem.md` before any strength check, load analysis, lightening or reinforcement.
- Before modelling a component, check native FreeCAD features, installed workbenches, standard parts and manufacturer CAD. Prefer a suitable standard solution after verifying its dimensions and interfaces; adapt it through supported parameters. Keep custom printable geometry native and fully constrained.
- Fasteners, heat-set inserts and gears come from the Fasteners and freecad.gears workbenches; do not draw them.
- Animations and exploded-view videos: ExplodedAssembly, i10g or Animate plus Assembly Simulation, not a hand-written placement loop. Follow rules.md "Animations and exploded views": `freeze_all()`, record i10g steps, fixed perspective camera, `i10g_video()` (async), wait for ffmpeg, `thaw_all()` + `full()`. i10g needs `tools/patches/i10g-shapeappearance.patch` on FreeCAD 26.
- `?expr` and normal calls both see `App` and `Gui`; import anything else inside the call.
- Use FreeCAD's standard workbench for each job; the full table of installed workbenches (Sketcher, PartDesign, Part, Spreadsheet, Assembly, Fasteners, freecad.gears, UNI-Rolling-Bearing, SheetMetal, Measure, Material, Fem, Plot, Mesh/MeshPart, Import, TechDraw, Draft, Surface, Inspection, Points/ReverseEngineering, OpenSCAD) is in rules.md, "Standard workbenches for each job". No Placement expressions to position or animate parts.
- Export a file only when the user asks for one.

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
- On ERR call `why(name)`; when in doubt use `tree()` and `chk()`. Undo with `undo()`.
- Load `rules.md` (next to this file) before choosing walls, clearances, holes, overhangs, print orientation, materials or renders.
- Load `fem.md` before any strength check, load analysis, lightening or reinforcement.
- Fasteners, heat-set inserts and gears come from the Fasteners and freecad.gears workbenches; do not draw them.
- Export a file only when the user asks for one.

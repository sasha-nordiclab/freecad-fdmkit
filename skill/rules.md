# FDM rules — Bambu A1, 0.4 nozzle, 0.2 layer

## Standard FreeCAD solutions first
- Before designing a component or mechanism, check native FreeCAD features, installed workbenches, standard parts, and manufacturer CAD for a suitable solution. Check purchased hardware such as bearings, fasteners, gears, and pulleys before drawing substitutes.
- Prefer a standard component when its dimensions, interfaces, and required adjustability fit the design. Resize through supported parameters, verify the dimensions and source, and record the choice in the project handoff.
- Keep custom printable parts as native, fully constrained parametric geometry. Create custom hardware or adapters when no suitable standard solution meets the requirements. A verified envelope is enough when detailed hardware geometry is unnecessary.

## Standard workbenches for each job
Use FreeCAD's own tools and workbenches instead of hand-made scripts or geometry. Installed in FreeCAD 26.3 (built-in + user `Mod`):

| Workbench | Use it for | Not for |
| --- | --- | --- |
| Sketcher | every 2D profile, fully constrained (DoF 0), dimensions from `params` | — |
| PartDesign | all printable parts: pads, pockets, holes (with countersinks), revolves, lofts, patterns, mirrors | purchased parts |
| Part | reference envelopes and purchased-part stand-ins, booleans on non-printed shapes, Check Geometry, cross-sections | printable parts |
| Spreadsheet | the `params` sheet: drivers, derived values, report cells | geometry |
| Assembly | assemblies of linked Bodies: Grounded/Fixed/Slider/Revolute/Cylindrical joints, Gears/Belt/RackPinion couplings, joint limits for ranges of motion, Simulation for movement, BOM, exploded views | — |
| ExplodedAssembly (user) | exploded views of an assembly with trajectories, bolt groups, camera animation | joint motion (use Assembly Simulation) |
| Inbetweening / i10g (user) | animation steps of placement, visibility and colour with interpolation; PNG, MP4, GIF export (patched for macOS: frames stream to ffmpeg stdin) | — |
| Animate (user) | trajectories with timed poses, image-sequence export | its Server object (runs network commands with `exec`) |
| Fasteners (user) | screws, nuts, washers, inserts, threaded rods | — |
| freecad.gears (user) | gears, racks, timing pulleys (GT2 `TimingGear`) | — |
| UNI-Rolling-Bearing (user) | visual bearing models; the dimensional envelope stays a native Body | — |
| SheetMetal (user) | bent sheet-metal parts and flat patterns | printed parts |
| Measure | distances, angles and clearances the user should see in the model | — |
| Material | material cards on Bodies (PETG, TPU, stainless) for mass and FEM | — |
| Fem | strength checks with gmsh + CalculiX (`fem.md`) | — |
| Plot | charts of results (FEM curves, sweeps) | — |
| Mesh, MeshPart | STL export and import for slicing and scans, mesh checks and repair | modelling printable parts |
| Import | STEP/IGES of manufacturer CAD (keep it in `reference/`, unmodified) | — |
| TechDraw | drawings with dimensions when the user asks | — |
| Draft | annotations, working planes, simple 2D layout; Link arrays of repeated components | printable features (use PartDesign patterns) |
| Surface | freeform surfaces where loft/sweep cannot follow the shape | prismatic parts |
| Inspection | comparing a model with a scan or mesh (e.g. the JOBO drum scan) | — |
| Points, ReverseEngineering | point clouds and scans turned into reference geometry | final printable geometry |
| OpenSCAD | importing existing `.scad` files only | new parts |
| CAM, BIM, Robot | not used for FDM parts | — |
| AddonManager | installing a missing workbench, only after the user agrees | — |
| Start, Help, Web, Show, Test, Tux, PieMenu, OpenTheme, FreeCADMCP | UI and infrastructure (FreeCADMCP is fdmkit's RPC); do not change them | — |

- Do not position or animate parts with Placement expressions on links or Bodies; that is the Assembly workbench's job. Fasteners workbench screws in a document without an Assembly are the exception: drive each screw's Placement by an expression of the same params as its hole, so it follows the hole (`check()` verifies every screw sits on a hole axis).
- In Assembly joints, set `Detach1`/`Detach2` and give `Placement1`/`Placement2` explicitly, driven by `params` expressions, so the joints do not depend on OCC face orientation. A Distance joint driven by a parameter gives a deterministic position for a slider; suppress it to run the slider's Simulation.
- Simulation motion formulas for Revolute joints are in radians (`2*pi*time` = 1 rev/s).
- Animations and exploded-view videos: use ExplodedAssembly, i10g or Animate (plus Assembly Simulation for joint motion) instead of a hand-written placement loop; the procedure is in "Animations and exploded views" below.

## Orientation first
Fix the print orientation before modelling and keep "model axis → print Z" in mind.

## Walls
- min 0.8; structural ≥ 1.6; heavy ≥ 2.4. Use multiples of the line width.
- User profile for structural parts: 0.4 nozzle, all line widths 0.6, layer 0.2, 3 walls. Walls are multiples of 0.6 and never thinner than 1.8 (3 × 0.6), so a wall is all perimeters with no infill gap.
- FEM assumes solid material, so slice to match. Set wall loops = thickest wall / line width (3.0 / 0.6 = 5) and top/bottom shell layers that cover the thickest plate (3.6 mm = 9 + 9 at 0.2). Then sparse infill has almost nothing left to fill, and it is faster than 100 %. In Bambu, 100 % needs a line pattern (zig-zag); `grid` fails with exit 238.
- Slice with the user's own OrcaSlicer presets (`~/Library/Application Support/OrcaSlicer/user/default`, read-only): `tools/orca_slice.py model.stl ["process"] [overrides]`. Flatten each preset along `inherits` into a temporary copy and run `OrcaSlicer --slice 0 --load-settings "machine;process" --load-filaments filament --outputdir`.
  - The copy keeps `inherits` and `from`.
  - The copy's `compatible_printers` lists both the user printer and its system parent.
  - `curr_bed_type` goes in the process.
  - Orca writes no `result.json`; read the time and grams from the G-code header.
  - Measured: 100 % rectilinear infill was faster than 40 % cubic on thin-walled parts.
- "N walls" means N perimeters: 2 ≈ 0.87 mm, 3 ≈ 1.3 mm.
- Keep ≥ 2 mm of material between a groove or slot and an edge.

## Overhangs and starts
- Nothing steeper than 40° from vertical, except the bed face. Redesign rather than add supports.
- No feature may start in mid-air (tips, rib ends facing the bed). Ribs grow out of a wall at ≤ 40°.
- Add no ribs or supports the user did not ask for.

## Holes and slots
- A hole or slot whose top would be an arch gets a teardrop or diamond top (sides ≤ 35–40°).
- A radial Hole into a cylinder: put its sketch 1 mm outside the surface (and add 1 mm to the depth). A sketch plane tangent to the cylinder makes the FusedFilamentDesign teardrop pocket an invalid shape, and it makes a plain PartDesign Hole drop some of its holes at random: one boolean fails silently, the part stays "valid", and a later recompute brings the hole back or loses another (ORWO 828, 2026-10-24). Drive the standoff by a param; the countersink diameter on the sketch plane is then `csk_d + 2 · standoff · tan(angle / 2)`, so the countersink at the surface stays `csk_d`. `lint()` reports tangent hole sketches.
- A countersink whose apex lands exactly on the hole floor (90°, `HoleCutDiameter / 2 == Depth`) is the same kind of degenerate boolean: make the depth `max(wall, csk_d / 2) + allowance`. `lint()` reports it.
- Horizontal cavities (bores behind bearings, seats in horizontal tubes) trap splash water: add a drain/vent hole at the lowest point and keep crush ribs off that spot.
- Round ends are fine at the bottom of a void. Plain hex-nut pockets print fine as they are.
- An annular groove on a vertical face cannot print. Use a recess without an island, or move the groove to the face that is up in print.

## Fastener edge distance (user rule, 2026-10-18)
- Measure from the largest outline a fastener leaves in the face: the countersink, counterbore or counterdrill diameter as modelled (M4 countersunk: Ø9.2 countersink, Ø9.8 counterdrill), the nut pocket corners, the washer or the head footprint. Not from the hole centre or the shank.
- That outline keeps ≥ 3 mm (the ligament rule) to every outer edge, wall face, fillet, slot, window, neighbouring recess and to the side of any part it sits beside. M4 countersunk: centre ≥ 9.8 / 2 + 3 = 7.9 from each edge (one param, e.g. `fd_edge = (m4_head_d + 0.6) / 2 + 3`). Plain hole without a head: hole edge ≥ 3 mm.
- Size flanges, ears and bases from the fastener (ear width ≥ 2 × 7.9 = 15.8 for one M4 countersunk row), not the other way round. Drive the edge offsets with that param.
- The fillets and chamfers on the outline do not count as material: check the margin after the edge finish.
- Check numerically after every layout change (centre-to-edge minus head radius); do not judge from a picture.

## Edges, by print direction
- Edges horizontal to the bed get a chamfer whose overhang is < 40°.
- Edges running along Z may be filleted.
- Bed edges get a chamfer (elephant foot), never a fillet.
- Upward-facing convex fillets are fine.

## Fits (per side)
- moving 0.25–0.40
- sliding 0.15–0.30
- static 0.10–0.20
- print-in-place ≥ 0.30 (≥ 0.40 is reliable)

## Hole sizes
- Holes print undersized: M3 3.2–3.5, M4 4.2–4.5, M5 5.2–5.5.
- Heat-set inserts need a lead-in chamfer.

## Strength and materials
- XY is stronger than Z: keep tension and bending in the layer plane.
- PETG: general use and warm water baths (PLA creeps at ~40 °C).
- TPU: flexible parts. Slow print; add clearance +0.1.
- ASA/ABS: the A1 is open, so they warp. Avoid long flat parts and sharp corners on the bed, and use a brim. Flag this to the user.

## Before changing anything: understand the part in use
- Ask how it is installed and what touches it before you redesign.
  - How it hangs or mounts.
  - Which faces bear on what, such as a wall it is screwed to.
  - Which loads people actually apply: how hard, how often, sustained or impact.
  - The shape of mating parts: a square jar needs its opening corners, a round one does not.
- Treat a "proven" functional detail as fixed unless the user says otherwise. For example, a ledge that a jar's rib bears on.
- Frame and plate thicknesses next to such a detail may also be functional. Ask before changing the overall height.

## Symmetry first
- Before modelling, find the mirror planes and mirrored pairs: bodies such as Module_A/B, bays about a divider, and paired walls.
- **Copy or mirror?** Decide by comparing asymmetric features: hole and mount coordinates.
  - Never decide by bounding box or feature list.
  - A mirror about the part's own mid-plane has the same bounding box as the original.
- Build one side and derive the other natively:
  - `Part::Mirroring` for a mirror image;
  - `App::Link` for a plain copy.
- Never edit both sides by hand.
- Window, hole and rib layouts must be symmetric about those planes. Every design revision checks the symmetry first.

## Sketch supports and minimal datum planes
- Attach sketches to stable origin planes when they share an orientation. For loft sections at different heights, put each sketch on the same origin plane and drive its `AttachmentOffset.Base.z` with a parameter expression.
- Create a separate datum plane only when it defines a meaningful independent reference or orientation. Do not add one plane merely to place each parallel sketch at a different Z level.
- Build one complete repeated feature before patterning it, when the native pattern can include its constituent features. After simplifying the tree, verify sketch DoF 0, feature validity, and the final shape against the prior model.

## Feature order and checks after every change
- Material that surrounds a hole (bosses, pads) goes **before** the hole in the tree, so the hole cuts it.
- One-sided ThroughAll holes and pockets cut only from their sketch plane forward.
  - Material added behind that plane closes the hole.
  - After adding material near holes, probe along each hole axis and confirm it is empty.
- After adding material, check that nothing crosses the reference faces: the bed face (print Z min) or the mounting face.
  - Compare the bounding box and the face count of those planes before and after.
- Chamfers and fillets reference edges by name. Inserting a feature before them can remap the edges.
  - Add new features after the chamfer, or reselect the chamfer edges geometrically.
- Labels: no A/B or version prefixes. FreeCAD object Names cannot be renamed, so set clean Labels.
- Save the document after each confirmed change. `run()` autosaves every 5 minutes.
- After every model change: `reopen()` (save, close, open, recompute), then `check()` and `lint()`. `check()` covers the whole document: one valid solid per Body, no object in error, sketches at DoF 0, no volume intersection between Bodies, and every Fasteners screw on a hole axis. Also count the holes you expect: a silently dropped hole leaves a valid solid.
- Before handing over a parametric model, run `case('alias', value)` on each main driver (part lengths, diameters, depths, angular datums). It sets the value, runs `check()` and restores the value. It pauses TechDraw pages meanwhile, because their HLR recompute is slow.
- Reference every feature to the real datum it is measured from (a part face, a flange top, the part's top or bottom face, a pattern row) through params. Never use an absolute Z or a number copied from another feature. When a parent part changes (an insert lengthened at the bottom), absolute features stay behind; on ORWO 828 a hole and a window sat 0.5 to 8.8 mm off for this reason. Expressions that read another Body's sketch constraints are fragile too: route the value through a sheet (`lint()` lists them).

## Making a part parametric (for other sizes)
- Put a few driver params at the top of `params` (the size of the thing the part holds). Under them go build, mount and lightening params, then a "Derived" block of formulas. Sketch dimensions reference only these cells.
- Dimension every sketch vertex by a formula (`poly` with expressions). Tie placements, pattern lengths, mirror planes and body offsets to params by expressions; a rotation can be `rotation(vector(..); a) * rotation(..)`.
- Turn optional cuts off with `Suppressed = min(zone sizes; depth * 100) < limit`, so a smaller size never builds a broken pocket.
- Guard positions that can collide when sizes shrink (screws, bosses) with `min()`. Never let a guard put two faces exactly tangent: OCC booleans fail there, so leave 0.5 mm.
- Migrating: build the new body next to the old one inside one transaction, compare the shapes (symmetric-difference volume), then swap the references and delete the old body. Delete the old body first if you want clean object Names.
- Test the parametrisation: set several smaller and larger sizes in a transaction, check one valid solid, holes clear, `chk()` and that the bbox equals the derived length, then abort.
- API traps:
  - **Deleting objects that use the sheet crashes FreeCAD 26.3 (RC1 and RC2).** If an object with expressions referencing `params` (feature, sketch, datum, link or whole Body) is deleted, the next change of a sheet cell segfaults in `Document::recompute` → `DocumentObject::enforceRecompute`, even when a recompute ran in between and even when the whole Body is deleted. Reproduced without fdmkit and without addons (2026-10-18). Workaround that works: clear every expression of the objects to be deleted (`for p, e in list(o.ExpressionEngine): o.setExpression(p, None)`), recompute, then delete. To rebuild a part, build it in a new Body, relink the users, clear the old Body's expressions, then delete it.
  - A Body's `BaseFeature` taken from another Body uses that Body's global placement and is not recomputed when the source moves through expressions (it went stale and collided). Build the variant as its own Body from the same params instead.
  - `Spreadsheet.removeRows()` shifts the cells but leaves stale computed values: dependent cells and features then recompute with old numbers (seen 2026-10-18: `drum_y0` −168.8 instead of −138). After removing or inserting rows, touch every used cell (`sheet.touchCells(c)`), `sheet.recompute()`, `doc.recompute()`, and re-read a few derived values before saving.
  - `Spreadsheet.clearAll()` is not undone by `abortTransaction`; rewrite and clear cells one by one.
  - A PartDesign pattern created from Python does not become the Tip; set `body.Tip` to it.
  - A Hole needs its base recomputed before its properties are set.

## Modelling
- Rounds go in sketches (`fil`), not as fillets on complex edges.
- Thin wall mount: countersunk screws plus a separate backing plate Body with nut pockets, printed flat.

## Lightening: recesses and thin walls before windows
- Through windows in thin walls cost print time: each one adds perimeters and travel. Measured on a 3 mm wall: windows −14 g but +26 min against solid walls.
- First choice: one-sided recesses (pockets) or thinner wall zones where FEM utilisation is low. Same grams as windows, 15 % faster.
  - Leave ≥ 1.8 mm (3 × 0.6) at the floor; depths in steps of 0.6.
  - Use a Pocket with TaperAngle so the closing ramp overhangs ≤ 40° from print vertical: taper 50° on a vertical wall, plus the wall tilt on a tilted wall.
  - Draw the recess sketch on the measured face. A sketch 0.1 mm inside the face leaves a skin film over the recess. Probe the face position with a line common() and do not trust a nominal number.
- Windows only where a through opening is needed (drainage, weight that recesses cannot reach).

## Lightening windows
- Size and place windows from a calculation (see `fem.md`), not by eye or from a decorative pattern.
- Shape:
  - diamonds whose flanks are ≤ 38.7° from print vertical (rise/run 1.25), so they print without supports;
  - all windows drawn on one lattice so the pattern reads as one system.
- Limits: ligament ≥ 3 mm, rim to outline ≥ 6 mm, window ≥ 7 mm wide. No windows next to bolts or impact points.
- One sketch can cut several parallel walls (ThroughAll) when they share a pattern.

## Materials (check the TDS for the Z direction)
- Compare the across-layer values (ZX tensile strength, strain at yield), not only XY.
- Example: ABS Prime has 31 MPa in XY but 11.5 MPa and 0.9 % strain in ZX, so it is brittle across layers.
  - It is a bad choice where walls bend across layers: walls near bolts, dividers that get hit.
  - It warps on the open A1.
- PETG: the default for warm (38 °C) photo-chemistry baths. Both PETG and ABS resist the aqueous C-41 and E-6 chemistry.
- Consider ABS or ASA only above ~55 °C, and only with an enclosure.

## Pictures and renders
- Pictures of a model or assembly come only from FreeCAD's standard image export of the user's real document: `View3D.saveImage` of that document's own 3D view (or File → Export image), with a white background. Set the camera through `fdmkit.run(expr)` and restore it afterwards.
  - Never generate a scene yourself: no copied shapes, temporary documents, re-placed or re-coloured parts, and no compositing, added shadows or cropping into the part. The image must show the model exactly as it is in the document.
  - FEM deflection plots are the only exception, since FreeCAD has no standard export for them.
- Plain white background, pastel colours, no scale bars, captions or numbers on the image. The numbers go in the README or the chat.
- To show loads: colour by deflection (|u|, normalised per load case), use a scaled deformation over a grey outline of the unloaded part, and draw the load arrows.
  - Pick the scale per case so the largest displacement draws at about 20 mm.
- Stories are 1080×1920. Render with VTK from FreeCAD's bundled Python.

## Measured reverse engineering (user rule, 2026-10-24)
Applies when a model is rebuilt from caliper measurements of an original part.
- Ignore deviations of 0.1–0.2 mm; that is the reading error on a worn original.
- Prefer assembled stack checks: the user selects two faces in the GUI and gives the distance. Read them with `sel()`. Change the model where several checks agree. A single reading that breaks an otherwise consistent stack is the outlier.
- When a large deviation appears, first look for a stale reference in the model (a feature left at an absolute Z, a datum from an older version of the part) before you move the feature.
- When the user says the part will be made in metal, the FDM rules (walls, ligaments, overhangs, oversized holes) do not apply. Use metal practice: ISO 273 clearances, tap drills, cosmetic threads, standard screws.

## Fasteners in models (2026-10-24)
- Take screws from the Fasteners workbench. When a standard or size is missing (no DIN 963, no M1 in ISO 2009), add a CSV row as a patch in `tools/patches/` (`fasteners-din963-m1.patch`) instead of drawing the screw. The patch is lost on an add-on update, so re-apply it.
- Fasteners rewrites `Label` on every recompute (`M1x1.4-Screw…`); keep the standard and the installation site in `Label2`.
- Clamped parts get clearance holes and the threaded part gets a tapped hole. A screw that threads into both parts cannot clamp them.

## TechDraw drawings (2026-10-24)
- Export pages with `TechDrawGui.exportPageAsSvg` only; `exportPageAsPdf` crashed FreeCAD 26.3 and `run()` refuses it.
- A dimension that should show a label instead of the value: `Arbitrary = True`, `FormatSpec = 'D7'`; `getRawValue()` still returns the model value.
- Dimensions reference view vertices by index. Find them by coordinates: DrawViewPart vertices are centred on the view's bounding-box centre, DrawViewSection vertices are in model coordinates. Re-bind them after a geometry change.
- The label offsets `X`/`Y` are page millimetres. Hidden-line computation is asynchronous, so read vertices in the next call.
- Set `KeepUpdated = False` on the pages during stress tests.

## Animations and exploded views (2026-10-20)
Proven on the roller stand (`roller-stand/renders/roller_stand_exploded_reel.mp4`, 15 s Reels loop).
- Tool: i10g (Inbetweening). A step stores the placement, visibility and colour of every `App::Link`/`App::Part`; i10g interpolates linearly between steps and streams `View3D.saveImage` frames of the document's own view into ffmpeg. Joint motion (rotating shafts, lifts) comes from Assembly Simulation instead.
- Required local patches of i10g (lost on an Addon Manager update; re-apply):
  - FreeCAD 26 links have `ShapeAppearance` instead of `ShapeMaterial`; without `tools/patches/i10g-shapeappearance.patch` the first step fails with `'Gui.ViewProviderLink' object has no attribute 'ShapeMaterial'`. Apply it in `Mod/Inbetweening` with `patch -p1 < .../fdmkit/tools/patches/i10g-shapeappearance.patch`, then `importlib.reload(i10g)`.
  - macOS video export: frames go to ffmpeg's stdin, ffmpeg found in `/opt/homebrew/bin` (already in the installed copy).
- Procedure:
  1. Plan the stages as translation offsets per link (cumulative: stage k holds everything stage k−1 moved). Explode along the real assembly direction: purchased stacks along their axis in assembly order with a fixed gap, parts lifted off in the order a person would take them off. For a portrait 9:16 video, stack the levels vertically (e.g. drum +300, shafts +150, carriages +60), so the exploded view is tall, not long.
  2. `freeze_all()` before moving anything. It freezes everything except links, parts and groups: the Assembly cannot solve the links back, and i10g's forced `recompute(None, True, True)` after the render takes milliseconds instead of minutes.
  3. Record the steps in one call: set the stage placements, `i10g.Animation(None)` (records step 0), then `addStep()` for each next state. Loop for social media: `0, 0, 1, …, n, n, n−1, …, 0`. `DurationInSeconds` is an integer and is the time from that step to the next (holds = two equal steps). Set `OutputFilename` (in the project's `renders/`), `CustomResolution` `1080x1920`, `Background` `White`, `FPS` 30. End the call with the links back in the assembled state: run() autosaves on commit.
  4. Camera: perspective, a fixed view direction, `fitAll()` on the fully exploded state, then zoom only through `heightAngle`. NaviCube off. Check the exploded frame's content bbox in pixels (≥ 5 % margin each side) before rendering.
  5. `i10g_video()` drops hidden links from every step (i10g would show them with transparency 1 and their edges would float), checks the patch, and starts the render through a `QTimer` so the RPC returns at once. Wait for the ffmpeg process to exit (Bash `run_in_background` with `until ! pgrep -f "ffmpeg.*<name>"`), and do not send fdmkit calls meanwhile.
  6. Check: `ffprobe` (size, fps, frames), a contact sheet of 6–7 frames across the video.
  7. Restore: `thaw_all()`, `full()`, NaviCube back, draw style `As is` (i10g leaves "Flat Lines"), orthographic axonometric view, Fit All. Keep the `Animation` object for a re-render; record it in the project AGENTS.md.
- Known limits: i10g renders in the "Shaded" draw style (no edge lines); interpolation is linear (no easing); steps store absolute placements, so record them again after any assembly change.

## Speed with big documents (user rule, 2026-10-19)
The user waits for every call; slow work is a defect. A full recompute of a document with an Assembly re-solves every joint against heavy shapes (tray, drum, 72-tooth gears) and takes minutes.
- `focus('Body', ...)` before editing parts: fdmkit then recomputes only those Bodies and the params sheet. `full()` once at the end recomputes everything and solves the Assembly.
- Read-only questions start with `?` (`?expr`): no transaction, no rollback recompute, no autosave. Never use `raise Exception(data)` to read: the abort triggers a recompute.
- Both `?expr` and normal calls see the fdmkit calls plus `App` and `Gui`; other modules need an `import` statement in the call (a normal call may hold several statements; the last expression is the result).
- `freeze('StandAssembly', 'Tray', ...)` (Std_ToggleFreeze) for heavy objects that the current step does not change: gears, belts, purchased STEP parts, reference bodies, the Assembly while parts are edited. `thaw()` them before the final check. `freeze('StandAssembly')` freezes only the Assembly and its joint groups, not the linked Bodies; `freeze_all()` / `thaw_all()` freeze or thaw every non-link object (animations, view-only work).
- Batch a whole part edit in one call (sketch changes, features, probes). Split only where a rule demands it (delete: clear expressions, then delete in a separate call). Prefer `Suppressed = True` over deleting a feature: no second call, no crash risk.
- Recompute one object or Body with `d.recompute([objs])`, not `d.recompute()`, in raw code.
- Interference and clearance checks: bounding-box prefilter first; `common()`/`distToShape()` only on pairs that overlap; one lift position per call; skip tray/drum pairs whose relative position does not change with the lift.
- Heavy loops (tessellated overhang scans, 4 rotations of a teardrop) on gear bodies: one evaluation per call, not a sweep.
- Do not touch the 3D view while a call runs: a held mouse button blocks the GUI queue (`mouse buttons held`). If a call times out, wait for it (a background `sleep`) instead of sending more calls.
- Never send a call while a previous one is still running in FreeCAD; check with a cheap `?` read first.

## Design stage: minimal recomputes (user rule, 2026-10-19)
1. Numbers first: settle a layout (lengths, clearances, heights, belts) with params formulas and short calculations, show the table, get the user's OK, then model.
2. Light stand-ins while designing: pulleys as pitch-diameter cylinders, motors as boxes, the tray as a simple drafted box. Swap in real gears, STEP parts and belts only for the final check.
3. The Assembly stays frozen while parts change; `focus()` the edited Bodies; thaw and solve once per stage.
4. Heavy checks (all-pairs interference, overhang scans) only at the end of a stage or on request; between steps use formula clearances and a few `isInside` probes.
5. One part edit per call; `Suppressed` instead of deleting; delete what is no longer needed so the document stays small.

# FDM rules — Bambu A1, 0.4 nozzle, 0.2 layer

Rarely used calls are documented in `help('topic')` (starts regions patterns dressup hole assembly anim drawing cnc cam).

## One working file; history in Git (global user rule)
- One canonical working FCStd per project; save changes to that same file. Git checkpoints and commits are the history and recovery. No version-named model copies, backup/archive folders or per-revision scripts/reports unless explicitly requested.
- One small logical change, focused validation, save the canonical file, Git commit. Batch calls only within that step; no unrelated edits, no open-ended variant search.
- Compare against in-memory geometry or a read-only Git baseline. A project without Git: initialize it and checkpoint the model before editing; preserve unrelated user changes.
- Temporary files for a check go in scratchpad and are cleaned up afterwards; reuse an existing checker/report rather than create another per step. Respect the user's limits on slicing, FEM and time.

## Token economy (user rule)
- Roles: the main session plans, writes the brief and reviews the numbers; one mid-tier subagent (Claude: sonnet) per edit batch runs the calls. Effort medium; high for Assembly joints, cross-document params and check scripts. Never the smallest tier (haiku: results unusable), never a separate read-only inspection agent; a single short read goes from the main session.
- Brief: document, exact change, acceptance numbers, stop conditions. Point to files and sections instead of retyping them.
- Read only what the task needs: the AGENTS.md entry of the edited document and the named rules.md section, each once. Trust "Verified state"; re-measure only what the change touches.
- One `run()` per batch of related edits; `?expr` reads return only the needed numbers; no `tree()` or whole-document dumps unless diagnosing an ERR.
- Between steps a light check of the touched Bodies; the full cold-open, `check()`, `lint()`, `case()` once before the commit.
- Stop at the first unexpected error and report it; do not explore, do not repeat a failing call more than once.
- No screenshots or exports unless asked: the user watches the GUI.
- Reports: params old -> new, objects added/removed, measured numbers, warnings split into new and pre-existing. No narrative; a table only for requested measurements.
- When the user asks for these rules, state them in the chat as well.

## Standard FreeCAD solutions first
- Before designing a component or mechanism, check native FreeCAD features, installed workbenches, standard parts and manufacturer CAD. Check purchased hardware (bearings, fasteners, gears, pulleys) before drawing substitutes.
- Prefer a standard component when its dimensions, interfaces and adjustability fit. Resize through supported parameters, verify dimensions and source, record the choice in the project handoff.
- Custom printable parts stay native, fully constrained parametric geometry. Create custom hardware or adapters only when no standard solution fits; a verified envelope is enough when detailed hardware geometry is unnecessary.

## Standard workbenches for each job
Use FreeCAD's own tools instead of hand-made scripts or geometry. Installed in FreeCAD 27.1 weekly (built-in + user `Mod`):

| Workbench | Use it for | Not for |
| --- | --- | --- |
| Sketcher | every 2D profile, DoF 0, dimensions from `params` | — |
| PartDesign | all printable parts: pads, pockets, holes (countersinks), revolves, lofts, patterns, mirrors | purchased parts |
| Part | reference envelopes, purchased-part stand-ins, booleans on non-printed shapes, Check Geometry, cross-sections | printable parts |
| Spreadsheet | the `params` sheet: drivers, derived values, report cells | geometry |
| Assembly | linked Bodies: Grounded/Fixed/Slider/Revolute/Cylindrical joints, Gears/Belt/RackPinion couplings, joint limits, Simulation, BOM, exploded views | — |
| ExplodedAssembly (user) | exploded views with trajectories, bolt groups, camera animation | joint motion (Assembly Simulation) |
| Inbetweening / i10g (user) | animation steps of placement, visibility, colour; PNG, MP4, GIF export (macOS patch: frames stream to ffmpeg stdin) | — |
| Animate (user) | trajectories with timed poses, image sequences | its Server object (runs network commands with `exec`) |
| Fasteners (user) | screws, nuts, washers, inserts, threaded rods | — |
| freecad.gears (user) | gears, racks, GT2 timing pulleys (`TimingGear`) | — |
| UNI-Rolling-Bearing (user) | visual bearing models; the envelope stays a native Body | — |
| SheetMetal (user) | bent sheet-metal parts, flat patterns | printed parts |
| Measure / Material / Fem / Plot | distances and clearances shown to the user / material cards on Bodies (PETG, TPU, stainless) / strength checks with gmsh + CalculiX (`fem.md`) / charts of results | — |
| Mesh, MeshPart | STL export/import, scans, mesh checks and repair | modelling printable parts |
| Import | STEP/IGES of manufacturer CAD (keep in `reference/`, unmodified) | — |
| TechDraw | drawings with dimensions when the user asks | — |
| Draft | annotations, working planes, simple 2D layout, Link arrays of repeated components | printable features (PartDesign patterns) |
| Surface | freeform surfaces where loft/sweep cannot follow | prismatic parts |
| Inspection | model vs scan or mesh (e.g. the JOBO drum scan) | — |
| Points, ReverseEngineering | point clouds and scans turned into reference geometry | final printable geometry |
| OpenSCAD | importing existing `.scad` files only | new parts |
| CAM | metal CNC: one Job per setup / A-axis index, Ø cutter tool controller, Slot/Pocket/Profile/Drilling, CAM_SimulatorGL (`cam_job`, `cam_slot`, `cam_sim`, `cam_del`) | FDM parts; lathe ops (none) |
| BIM, Robot | not used | — |
| AddonManager | installing a missing workbench, only after the user agrees | — |
| Start, Help, Web, Show, Test, Tux, PieMenu, OpenTheme, FreeCADMCP | UI and infrastructure (FreeCADMCP is fdmkit's RPC); do not change | — |

- No Placement expressions to position or animate links or Bodies: that is the Assembly's job. Exception: Fasteners screws in a document without an Assembly; drive each screw's Placement by an expression of the same params as its hole (`check()` verifies every screw sits on a hole axis).
- Assembly joints: set `Detach1`/`Detach2` and give `Placement1`/`Placement2` explicitly, driven by `params` expressions, so joints do not depend on OCC face orientation. A Distance joint driven by a parameter gives a deterministic slider position; suppress it to run the slider's Simulation.
- Simulation motion formulas of Revolute joints are in radians (`2*pi*time` = 1 rev/s).
- Animations and exploded-view videos: ExplodedAssembly, i10g or Animate (plus Assembly Simulation for joint motion), never a hand-written placement loop; see "Animations and exploded views".

## Orientation first
Fix the print orientation before modelling; keep "model axis → print Z" in mind.

## Walls
- Min 0.8; structural ≥ 1.6; heavy ≥ 2.4. Use multiples of the line width.
- User profile for structural parts: 0.4 nozzle, all line widths 0.6, layer 0.2, 3 walls. Walls are multiples of 0.6, never thinner than 1.8 (3 × 0.6), so a wall is all perimeters with no infill gap.
- FEM assumes solid material, so slice to match: wall loops = thickest wall / line width (3.0 / 0.6 = 5) and top/bottom shell layers covering the thickest plate (3.6 mm = 9 + 9 at 0.2). Sparse infill then has almost nothing left to fill and is faster than 100 %. In Bambu, 100 % needs a line pattern (zig-zag); `grid` fails with exit 238.
- Slice with the user's own OrcaSlicer presets (`~/Library/Application Support/OrcaSlicer/user/default`, read-only): `tools/orca_slice.py model.stl ["process"] [overrides]` (OrcaSlicer 2.5.0, runs through a scratch datadir; Orca writes no `result.json`, read time and grams from the G-code header). Measured: 100 % rectilinear infill was faster than 40 % cubic on thin-walled parts.
- "N walls" means N perimeters: 2 ≈ 0.87 mm, 3 ≈ 1.3 mm.
- Keep ≥ 2 mm of material between a groove or slot and an edge.

## Overhangs and starts
- Nothing steeper than 40° from vertical, except the bed face. Redesign rather than add supports.
- No feature starts in mid-air (tips, rib ends facing the bed). Ribs grow out of a wall at ≤ 40°.
- Add no ribs or supports the user did not ask for.

## Holes and slots
- A hole or slot whose top would be an arch gets a teardrop or diamond top (sides ≤ 35–40°).
- A radial Hole into a cylinder: put its sketch 1 mm outside the surface (and add 1 mm to the depth). A sketch plane tangent to the cylinder makes the FusedFilamentDesign teardrop pocket an invalid shape and makes a plain PartDesign Hole drop some holes at random (one boolean fails silently, the part stays "valid", a later recompute brings the hole back or loses another). Drive the standoff by a param; the countersink diameter on the sketch plane is `csk_d + 2 · standoff · tan(angle / 2)`, so it stays `csk_d` at the surface. `lint()` reports tangent hole sketches.
- A countersink whose apex lands exactly on the hole floor (90°, `HoleCutDiameter / 2 == Depth`) is the same degenerate boolean: make the depth `max(wall, csk_d / 2) + allowance`. `lint()` reports it.
- Horizontal cavities (bores behind bearings, seats in horizontal tubes) trap splash water: add a drain/vent hole at the lowest point and keep crush ribs off that spot.
- Round ends are fine at the bottom of a void. Plain hex-nut pockets print fine as they are.
- An annular groove on a vertical face cannot print. Use a recess without an island, or move the groove to the face that is up in print.

## Fastener edge distance (user rule)
- Measure from the largest outline a fastener leaves in the face: the countersink, counterbore or counterdrill diameter as modelled (M4 countersunk: Ø9.2 countersink, Ø9.8 counterdrill), the nut pocket corners, the washer or the head footprint. Not from the hole centre or the shank.
- That outline keeps ≥ 3 mm (the ligament rule) to every outer edge, wall face, fillet, slot, window, neighbouring recess and to the side of any part it sits beside. M4 countersunk: centre ≥ 9.8 / 2 + 3 = 7.9 from each edge (one param, e.g. `fd_edge = (m4_head_d + 0.6) / 2 + 3`). Plain hole without a head: hole edge ≥ 3 mm.
- Size flanges, ears and bases from the fastener (ear width ≥ 2 × 7.9 = 15.8 for one M4 countersunk row), not the other way round. Drive the edge offsets with that param.
- Fillets and chamfers on the outline do not count as material: check the margin after the edge finish.
- Check numerically after every layout change (centre-to-edge minus head radius), not from a picture.

## Edges, by print direction
- Edges horizontal to the bed get a chamfer whose overhang is < 40°.
- Edges along Z may be filleted. Bed edges get a chamfer (elephant foot), never a fillet. Upward-facing convex fillets are fine.

## Fits (per side)
- moving 0.25–0.40; sliding 0.15–0.30; static 0.10–0.20; print-in-place ≥ 0.30 (≥ 0.40 is reliable).

## Hole sizes
- Holes print undersized: M3 3.2–3.5, M4 4.2–4.5, M5 5.2–5.5.
- Heat-set inserts need a lead-in chamfer.

## Strength and materials
- XY is stronger than Z: keep tension and bending in the layer plane.
- PETG: general use and warm water baths (PLA creeps at ~40 °C).
- TPU: flexible parts. Slow print; add clearance +0.1.
- ASA/ABS: the A1 is open, so they warp. Avoid long flat parts and sharp corners on the bed, use a brim, and flag this to the user.

## Avoid known FreeCAD failures
- Before CAD work, read `../KNOWN_ISSUES.md` and apply documented workarounds before issuing calls. Never repeat a known crash path; logging a repeated failure is not a substitute for applying its workaround (user rule).
- Never `reopen()` a linked source with dependent documents open. Save changes, close dependents before sources, then cold-open the root assembly and its complete dependency graph. `reopen()` only on a standalone document without open dependents.

## Before changing anything: understand the part in use
- Ask how it is installed and what touches it before you redesign: how it hangs or mounts; which faces bear on what (a wall it is screwed to); which loads people actually apply (how hard, how often, sustained or impact); the shape of mating parts (a square jar needs its opening corners, a round one does not).
- A "proven" functional detail (a ledge that a jar's rib bears on) is fixed unless the user says otherwise. Frame and plate thicknesses next to it may be functional too: ask before changing the overall height.

## Symmetry first
- Before modelling, find the mirror planes and mirrored pairs (Module_A/B, bays about a divider, paired walls).
- **Copy or mirror?** Decide by comparing asymmetric features (hole and mount coordinates), never by bounding box or feature list: a mirror about the part's own mid-plane has the same bounding box as the original.
- Build one side and derive the other natively: `Part::Mirroring` for a mirror image, `App::Link` for a plain copy. Never edit both sides by hand.
- Window, hole and rib layouts must be symmetric about those planes (symmetric layouts). Every design revision checks the symmetry first.

## Local part coordinates and assembly placement
For new multi-part models and for migrating a model built in assembly coordinates. The local origin is a design datum, not a bounding-box centre.

### Frames and constraints
- Turned ring/sleeve: turning axis + a functional axial datum (mid-plane when symmetric, or the mounting shoulder). Pin: own axis and shoulder. Curved segment: its real curvature axis, local plane on its angular symmetry. Do not force symmetry onto intentionally asymmetric features.
- Each source Body at identity Placement in its local frame, origin planes + parameter-driven AttachmentOffsets; datum geometry only for meaningful references. Hide source Bodies in the assembled view, show their App::Links.
- Constrain with coincidence, H/V, equality, parallelism, perpendicularity, tangency, symmetry first; construction axes/lines/points for centres and repeats. Only independent named dimensions (height, radii, wall, pitch, angles, offsets); derive the rest by expressions. No per-vertex X/Y dimensions, no Block/Fixed instead of parametrisation.
- Examples: centred R-Z ring = H/V sides, symmetry about the sketch H axis, InnerRadius, WallThickness, Height. Two hole centres = point symmetry, Equal diameters, HoleDiameter, RowPitch. Symmetric radial opening = construction ray, paired symmetric vertices, one half-angle, independent radial levels.
- Assembly placement belongs to native joints: ground the datum part; Fixed joints for stationary dependents that follow changing dimensions; keep moving Slider/Revolute joints and limits. No Placement expressions on Bodies/Links.

### Migrate without changing the assembled geometry
1. Identify source document, authoring Bodies, Assembly Links, joints, fasteners, dependent CAM/text/drawing objects. Save and Git-checkpoint the canonical file as the baseline (or in-memory assembled geometry); edit the same file, no working copy; never write to a read-only baseline. **Open/activate the intended document in a separate `run()` call before editing it**: rollback belongs to the document active at call entry.
2. Define each parameter-derived transform `F` (new local coordinates -> old source-part frame). With world transform `W`, update it to `W * F` and rebase the shape by `F.inverse()`. Record datum expressions, not just numeric placements (an optional native property container, e.g. LocalDatums, can share them without a Python Proxy).
3. Freeze the Assembly while editing parts. Keep native sketches and history. Rebase sketch geometry **and** origin-relative constraints, supports and AttachmentOffsets together. A dimension between two points is a length: no offset. An expression following an already-rebased sketch is not shifted twice. R-Z profiles: shift axial sketch coordinates; transverse sketches: the support offset; radial pins: also axial shoulder offset and orientation.
4. Clear affected constraint expressions before replacing constraints. Rebuild with geometric relationships and minimal named dimensions; keep names used downstream. No deleting expression-bearing objects before clearing and recomputing (API traps). After each sketch: DoF 0, no redundant/conflicting constraints. Recompute the document before trusting Shape (solving a sketch or recomputing a Body can leave downstream shapes stale).
5. Joint connectors: a detached old connector `J` in the source frame becomes `F.inverse() * J`; keep offsets, limits, axes. Prefer explicit origin references with Detach1/Detach2 and expression-driven Placement1/Placement2 over generated faces. Seed Link placements with `W * F`, thaw, solve. Grounding every part freezes its position; Fixed joints let stationary parts follow parameters.
6. Changed fillet/chamfer/UpToFace references: match transformed baseline edge/face geometry to the recomputed predecessor (centre, length/area, curve/surface, endpoints). Require a unique match within tolerance; never accept the nearest index or a stale Shape of an invalid feature.
7. Rebase consumers: ShapeBinders, decorative text (keep its glyph-centering Placement), clone placements, CAM coordinates. Draft CAM clone of one PartDesign source: `C_new = C_old * S_old.inverse() * F * S_new` (S = that source feature's Placement); verify the clone solids. CAM operation points/azimuths use the new frame. Do not regenerate NC paths or refresh frozen TechDraw pages unless requested; note which drawing sources/views need rebasing.

### Verify and hand over
- Compare each **assembled** result with its baseline by `new.cut(old)` and `old.cut(new)`, plus validity, solid count, functional interfaces. Equal volumes or bounding boxes are not enough; small integration differences can coexist with a zero Boolean difference: report tolerances.
- Flat Assembly of Body Links: `link_names = [o.Name for o in assembly.Group if o.TypeId == 'App::Link']`, then `check(*link_names)`; exclude non-part links, count nothing twice. Nested assemblies: resolve leaf parts into one world frame. Plain `check()` compares authoring Bodies at coincident local origins and reports false intersections.
- `lint()` and, for metal, `cnc()` on local parts; `case(name, value, *link_names)` on main drivers. `case()` recomputes but does not solve the Assembly: also solve and check parameter-dependent joint placements, seeding the free-joint pose if needed. For a migration compare baseline and candidate at the same perturbed values; restore values and pose afterwards.
- Test functional poses through native joints. When a script seeds a free rigid group's placement, move all members consistently before solve (moving one lets the solver share the displacement). Dragging/Simulation is for interactive motion, no replacement animation system.
- Finally `reopen()`, check the Links, `lint()`, confirm DoF 0, valid solids, motion, consumer geometry. Restore visibility, active 3D view, axonometric camera, Fit All. Update the project handoff with local datums and the assembly-aware check command.

## Sketch supports and minimal datum planes
- Attach sketches to stable origin planes (never generated faces) when they share an orientation. Loft sections at different heights: every sketch on the same origin plane, `AttachmentOffset.Base.z` driven by a parameter expression.
- A separate datum plane only for a meaningful independent reference or orientation, never merely to place each parallel sketch at a different Z.
- Radial sketch on 'XZ' (normal -Y) turned to azimuth a about Z: AttachmentOffset `placement(vector(d*sin(a); 0 mm; d*cos(a)); rotation(vector(0; 1; 0); a))`, a = 0 on -Y.
- Build one complete repeated feature before patterning it, when the native pattern can include its constituent features. After simplifying the tree, verify sketch DoF 0, feature validity and the final shape against the prior model.

## Sketch regions
- With `MakeInternals` on, a sketch exposes every closed region as `InternalFaceN`: overlapping contours split into separate regions; a contour inside another is a hole of the outer region and a region of its own. `pad`/`pocket(..., at=(x, y))` (sketch coordinates, params allowed) turns MakeInternals on and uses only the regions under the points; without `at` the whole sketch is the profile.
- One master sketch when the profiles share centres, pitches or symmetry (a base with bosses and pockets at different levels: `start='offset'`). Separate sketches when the profiles sit on different planes or the regions keep changing identity; a clear tree beats fewer sketches.
- Pick regions by a point, never by `InternalFaceN` (numbers follow region order and change when contours are added or deleted). FreeCAD remaps a feature's reference when another contour is deleted (`InternalFace3` → `InternalFace2`, geometry kept), but a feature whose own region vanished keeps `?InternalFaceN`, turns Invalid and shows the old shape. `lint()` reports it; repair with `remap(feature, (x, y))` (`remap(feature)` = whole sketch), then `check()`.
- A region is a start reference too: `start='reference', reference=(sk, (x, y))`. A feature's regions (`Profile`, shown in the GUI as Support) are not the sketch's Attachment: a sketch that moved as a whole is an attachment problem.
- Start offset runs along the feature's own direction: a pad's along the sketch normal, a pocket's along its cut, so `pocket(sk, 2, start='offset', offset=-6)` cuts 4..6 above the sketch; `reverse=True` flips both. A pocket that misses the solid is an ERR.

## Feature order and checks after every change
- Material that surrounds a hole (bosses, pads) goes **before** the hole in the tree, so the hole cuts it.
- One-sided ThroughAll holes and pockets cut only from their sketch plane forward: material added behind that plane closes the hole. After adding material near holes, probe along each hole axis and confirm it is empty.
- After adding material, check that nothing crosses the reference faces (bed face = print Z min, or the mounting face): compare the bounding box and the face count of those planes before and after.
- Chamfers and fillets reference edges by name; inserting a feature before them can remap the edges. Add new features after the chamfer, or reselect its edges geometrically.
- Labels: no A/B or version prefixes. Object Names cannot be renamed, so set clean Labels.
- Save after each confirmed change. `run()` autosaves every 5 minutes.
- After every model change: `reopen()` (save, close, open, recompute), then `check()` and `lint()`. `check()` covers the whole document: one valid solid per Body, no object in error, sketches at DoF 0, no volume intersection between Bodies, every Fasteners screw on a hole axis. Also count the holes you expect: a silently dropped hole leaves a valid solid.
- Before handing over a parametric model, run `case('alias', value)` on each main driver (part lengths, diameters, depths, angular datums). It sets the value, runs `check()` and restores the value; it pauses TechDraw pages meanwhile (their HLR recompute is slow).
- Reference every feature to the real datum it is measured from (a part face, a flange top, the part's top or bottom face, a pattern row) through params. Never an absolute Z or a number copied from another feature: when a parent part changes (an insert lengthened at the bottom), absolute features stay behind (a hole and a window sat 0.5 to 8.8 mm off). Expressions that read another Body's sketch constraints are fragile too: route the value through a sheet (`lint()` lists them).

## Making a part parametric (for other sizes)
- A few driver params at the top of `params` (the size of the thing the part holds); under them build, mount and lightening params, then a "Derived" block of formulas. Sketch dimensions reference only these cells.
- Geometric constraints and construction geometry first, then a minimal set of independent named dimensions driven by params; derive repeated/dependent values instead of dimensioning every vertex. Drive sketch supports, pattern lengths and datum offsets by expressions; native Assembly joints position Bodies through their Links (see "Local part coordinates and assembly placement").
- Turn optional cuts off with `Suppressed = min(zone sizes; depth * 100) < limit`, so a smaller size never builds a broken pocket.
- Guard positions that can collide when sizes shrink (screws, bosses) with `min()`. Never let a guard put two faces exactly tangent (OCC booleans fail): leave 0.5 mm.
- Migrating: see "Local part coordinates and assembly placement". When replacing a Body, compare assembled geometry before swapping references; clear expressions and recompute before deleting the old object; never delete the baseline merely to reuse its Name.
- Test the parametrisation: in a transaction set several smaller and larger sizes, check one valid solid, holes clear, `chk()`, bbox equal to the derived length, then abort.
- API traps:
  - **Deleting objects that use the sheet crashes FreeCAD (27.1 build 20261103, #33685).** If an object with expressions referencing `params` (feature, sketch, datum, link or whole Body) is deleted, the next change of a sheet cell segfaults in `Document::recompute` → `DocumentObject::enforceRecompute`, even after an intermediate recompute and even when the whole Body is deleted. Reproduced without fdmkit and addons. Workaround: clear every expression of the objects to be deleted (`for p, e in list(o.ExpressionEngine): o.setExpression(p, None)`), recompute, then delete. To rebuild a part: build it in a new Body, relink the users, clear the old Body's expressions, delete it.
  - A Body's `BaseFeature` taken from another Body uses that Body's global placement and is not recomputed when the source moves through expressions (it went stale and collided). Build the variant as its own Body from the same params.
  - `Spreadsheet.removeRows()` shifts cells but leaves stale computed values (`drum_y0` −168.8 instead of −138). After removing or inserting rows touch every used cell (`sheet.touchCells(c)`), `sheet.recompute()`, `doc.recompute()`, and re-read a few derived values before saving.
  - `Spreadsheet.clearAll()` is not undone by `abortTransaction`; rewrite and clear cells one by one.
  - A PartDesign pattern created from Python does not become the Tip, so later features skip it; fdmkit's pattern calls set `body.Tip`, raw scripts must too.
  - A Hole needs its base recomputed before its properties are set.

## Modelling
- Rounds go in sketches (`fil`), not as fillets on complex edges.
- Thin wall mount: countersunk screws plus a separate backing plate Body with nut pockets, printed flat.

## FreeCAD 27.1 features: which call
Each call is probed and in `selftest()`; signatures in `help('starts'|'patterns'|'dressup'|'assembly')`.
- `midplane(name, a, b)` instead of a datum offset by half a param; it follows both faces/planes.
- `project_axis=True` revolves about an axis outside the sketch plane; `type='up_to_face', up_to=` ends a Revolution/Groove at a datum or face, `type='through'` grooves all round. Revolution/Groove `start='offset'` takes an angle.
- Patterns: one semantic feature, then repeat it; never one pocket per hole. `linear` row or grid (`direction2`/`count2`: 2x2 mount holes from one hole, pitch a param; `suppressed=[(1, 1)]` skips a corner); `polar` one ring; `circular` concentric rings (`radial` spacing, `tangential` step); `path_pattern` along an edge/sketch (first instance = original, `align=True` follows the tangent); `point_pattern` at sketch points/circle centres (first = original). Suppress instances with `suppressed=`, not extra features. A pattern that changes nothing is an ERR.
- `defeature(faces)` removes holes/fillets/bosses of an imported/base feature and heals the solid; own geometry stays native.
- `thickness(faces, value)`: shell with the faces removed; `mode='recto_verso'` half the wall each side. OCC fails on solids with grooves/many details (`Failed to make thick solid`): shell the simple solid first, add details after.
- `mass(*objs, density=)`: volume, mass, CoG, principal moments. Material density is used unless the object has the 'Default' material.
- `sel()` of two holes/circles/edges gives the axes' angle and, if parallel, their distance.
- Assembly: `link_array()` for repeated identical/purchased parts (App::Link instances, joints attach to any, `into=` puts it into the Assembly); `rigid_group(*links)` instead of Fixed-joint chains; `snapshot(name)` stores a functional pose of free parts, `snapshot_restore(name, solve=True)` re-solves so jointed parts follow.
- Coaxial stepped parts: usually one axial-section sketch + `revolve` beats a master sketch of concentric circles + `pad(at=..., start='offset')`; use regions when the steps are not round or share a non-axial layout.
- One sketch per meaningful set of related dimensions (envelope, mount points, ribs), not one per feature, not one giant master sketch; split a master sketch whose regions keep changing count.
- Sketcher Text and the Group constraint are experimental and GUI-only (no Python path for Text; Group needs the hidden development preview): do not use; for lettering use a stable text workflow and check stroke width (>= 2 lines) and gaps.
- `EnableAsyncRecompute` (on) affects GUI commands only; `fdmkit.run` recomputes synchronously. After `Gui.runCommand(...)` wait and re-read the state.
- PartDesign Boolean tool bodies keep their own placement: no resetting to the origin before a Boolean.
- GUI-only, no call: Sketcher dimension tools picking model edges, broken external geometry flagged in the tree, vertical spreadsheet tables, several documents editable at once, experimental fine-grained recompute (preference; leave off).
- Not re-tested on 27.1 20261103: the `exportPageAsPdf` crash and chamfer hangs; keep the workarounds.

## Lightening: recesses and thin walls before windows
- Through windows in thin walls cost print time (perimeters, travel): on a 3 mm wall windows −14 g but +26 min against solid walls.
- First choice: one-sided recesses (pockets) or thinner wall zones where FEM utilisation is low. Same grams as windows, 15 % faster.
  - Leave ≥ 1.8 mm (3 × 0.6) at the floor; depths in steps of 0.6.
  - Pocket with TaperAngle so the closing ramp overhangs ≤ 40° from print vertical: taper 50° on a vertical wall, plus the wall tilt on a tilted wall.
  - Draw the recess sketch on the measured face: a sketch 0.1 mm inside the face leaves a skin film. Probe the face position with a line common(), not a nominal number.
- Windows only where a through opening is needed (drainage, weight that recesses cannot reach).

## Lightening windows
- Size and place windows from a calculation (`fem.md`), not by eye or from a decorative pattern.
- Shape: diamonds whose flanks are ≤ 38.7° from print vertical (rise/run 1.25), so they print without supports; all windows on one lattice so the pattern reads as one system.
- Limits: ligament ≥ 3 mm, rim to outline ≥ 6 mm, window ≥ 7 mm wide. No windows next to bolts or impact points.
- One sketch can cut several parallel walls (ThroughAll) when they share a pattern.

## Materials (check the TDS for the Z direction)
- Compare the across-layer values (ZX tensile strength, strain at yield), not only XY. Example: ABS Prime has 31 MPa in XY but 11.5 MPa and 0.9 % strain in ZX, so it is brittle across layers: a bad choice where walls bend across layers (walls near bolts, dividers that get hit); it also warps on the open A1.
- PETG: the default for warm (38 °C) photo-chemistry baths. PETG and ABS both resist the aqueous C-41 and E-6 chemistry.
- ABS or ASA only above ~55 °C, and only with an enclosure.

## Pictures and renders
- Pictures of a model or assembly come only from FreeCAD's standard image export of the user's real document: `View3D.saveImage` of that document's own 3D view (or File → Export image), white background. Set the camera through `fdmkit.run(expr)` and restore it afterwards.
  - Never generate a scene: no copied shapes, temporary documents, re-placed or re-coloured parts, no compositing, added shadows or cropping into the part. The image shows the model exactly as it is in the document.
  - FEM deflection plots are the only exception (FreeCAD has no standard export for them).
- Plain white background, pastel colours, no scale bars, captions or numbers on the image; numbers go in the README or the chat.
- To show loads: colour by deflection (|u|, normalised per load case), scaled deformation over a grey outline of the unloaded part, load arrows. Pick the scale per case so the largest displacement draws at about 20 mm.
- Stories are 1080×1920. Render with VTK from FreeCAD's bundled Python.

## Measured reverse engineering (user rule)
For a model rebuilt from caliper measurements of an original part.
- Ignore deviations of 0.1–0.2 mm (reading error on a worn original).
- Prefer assembled stack checks: the user selects two faces in the GUI and gives the distance; read them with `sel()`. Change the model where several checks agree; a single reading that breaks an otherwise consistent stack is the outlier.
- A large deviation: first look for a stale reference in the model (a feature at an absolute Z, a datum from an older version of the part) before moving the feature.
- When the part will be made in metal, the FDM rules (walls, ligaments, overhangs, oversized holes) do not apply: use metal practice (ISO 273 clearances, tap drills, cosmetic threads, standard screws).

## Fasteners in models
- Take screws from the Fasteners workbench. A missing standard or size (no DIN 963, no M1 in ISO 2009): add a CSV row as a patch in `tools/patches/` (`fasteners-din963-m1.patch`; `fasteners-pcb-m3x5-l6.patch` adds length 6 to M3 hex-5.0 PCBSpacer/PCBStandoff) instead of drawing the screw. The patch is lost on an add-on update: re-apply it.
- Insert fasteners only the standard way (user rule): select the hole edges, `Gui.runCommand('FS<Type>')` (`FSISO7045`, `FSPCBStandoff`, …) gives one attached fastener per edge; then set Diameter, Width, Length (recompute between: each enumeration fills after it), orientation with `Invert`, axial position with `Offset`. Never hand-build with `addObject` + `FSScrewObject` or `copyObject`: no view provider, the user cannot see or select them.
  - On an App::Link to an App::Part the edge must be `Child.EdgeN` (`HalfHolesBoard.Edge16`); a flat `EdgeN` makes `getSubObject` return None and the fastener stays at the origin.
  - After a CSV patch in a running FreeCAD, reload that file into `FastenerBase.FsData` (`FSutils.csv2dict`); Fasteners reads the CSVs once at import.
- Fasteners rewrites `Label` on every recompute (`M1x1.4-Screw…`); keep the standard and the installation site in `Label2`.
- Clamped parts get clearance holes and the threaded part a tapped hole. A screw that threads into both parts cannot clamp them.

## TechDraw drawings
- Export pages with `TechDrawGui.exportPageAsSvg` only; `exportPageAsPdf` crashes FreeCAD (#33798) and `run()` refuses it.
- A label instead of the value: `Arbitrary = True`, `FormatSpec = 'D7'`; `getRawValue()` still returns the model value.
- Dimensions reference view vertices by index; find them by coordinates (DrawViewPart vertices are centred on the view's bounding-box centre, DrawViewSection vertices are in model coordinates) and re-bind after a geometry change. Label offsets `X`/`Y` are page mm. Hidden-line computation is asynchronous: read vertices in the next call.
- `KeepUpdated = False` on the pages during stress tests.

## Dimension placement by computation (TechDraw)
Never place labels by looking at exports or pictures. Per sheet: refresh the page once; next call `dim_add(...)` per missing dimension (refs in view coordinates, unscaled, Y up); then `dim_layout(page, inside=(...), keepout=[title block box])`, which ends with `dim_check`. Export once at the end, only when the user asks. `dim_layout(..., apply=False)` plans without writing.
- Frames (probed 27.1): label centre = view.X/Y + dim.X/Y (page mm, Y up); `getArrowPositions()` unscaled, Y up; `getLinearPoints()`/visible vertices/edges scaled, Y DOWN.
- `Fontsize` is the cap height: label width = QFontMetricsF advance x Fontsize / capHeight. An ISO linear label sits ~0.96 x Fontsize above a horizontal / left of a vertical line.
- Lanes: first line 10 mm off the view outline, then 7 mm apart; shortest span nearest the part; non-overlapping spans share a lane; a label wider than its span goes past the far end; dims go to the side of their measured points, flipped when the label leaves the sheet or hits a view. Internal section diameters stay `inside` only when the outside lane would cross many hatched walls; inside labels move to the nearest spot clear of edges, labels and lines.
- The title block is template-specific: pass it as `keepout` (x0, y0, x1, y1, page mm, Y up); `title_block(page)` reads it from the template SVG.
- `view_layout(page)` after the refresh and after `dim_layout` (dims widen the view envelope). Free field = frame minus title block, notes blocks, keepout; views overlapping in x/y move together (projection kept); equal gaps (<= `maxgap` 25), group centred; short captions (<= 3 lines) follow their view; `apply=False` plans; envelopes are estimates.
- `sheet_fit(page)` exports a temp SVG, strips the template, rasterises the ink (QtSvg -> numpy, 5 px/mm) and checks every pixel: inside the frame, outside title block + field row (`title_block`, top 71 on A4 ISO 5457 advanced), projection symbol (`projection_symbol`) and `keepout`, all grown by `margin` 0.5. On failure it moves the drawing by the smallest rigid shift (<= 15 mm) that clears everything (confirm with a second run) or reports the overflow; it reports the free room l/b/r/t. Never judge sheets from pictures; never measure the GUI page scene (stale, see KNOWN_ISSUES.md).
- Sequence per sheet: refresh -> check getVisibleEdges -> dim_add -> dim_layout -> view_layout -> dim_check OK -> `page_sync` -> NEXT call `sheet_fit` OK -> export. Open + updateGui + export in ONE call (a page opened earlier and exported later segfaulted 27.1); frozen pages need `page_sync` after views move or the SVG keeps stale dimension lines.

## Animations and exploded views
- Tool: i10g (Inbetweening). A step stores placement, visibility and colour of every `App::Link`/`App::Part`; i10g interpolates linearly and streams `View3D.saveImage` frames of the document's own view into ffmpeg. Joint motion (rotating shafts, lifts) comes from Assembly Simulation.
- Local i10g patches (lost on an Addon Manager update; re-apply): FreeCAD 26+ links have `ShapeAppearance`, not `ShapeMaterial`; without `tools/patches/i10g-shapeappearance.patch` the first step fails with `'Gui.ViewProviderLink' object has no attribute 'ShapeMaterial'` (in `Mod/Inbetweening`: `patch -p1 < .../fdmkit/tools/patches/i10g-shapeappearance.patch`, then `importlib.reload(i10g)`). macOS video export: frames go to ffmpeg's stdin, ffmpeg in `/opt/homebrew/bin` (already in the installed copy).
1. Plan stages as cumulative translation offsets per link (stage k holds everything stage k−1 moved). Explode along the real assembly direction: purchased stacks along their axis in assembly order with a fixed gap, parts lifted off in the order a person removes them. Portrait 9:16: stack levels vertically (e.g. drum +300, shafts +150, carriages +60).
2. `freeze_all()` before moving anything: the Assembly cannot solve the links back, and i10g's forced `recompute(None, True, True)` after the render takes milliseconds instead of minutes.
3. Record steps in one call: set stage placements, `i10g.Animation(None)` (step 0), `addStep()` per next state. Social loop: `0, 0, 1, …, n, n, n−1, …, 0`. `DurationInSeconds` is an integer, the time from that step to the next (holds = two equal steps). Set `OutputFilename` (project `renders/`), `CustomResolution` `1080x1920`, `Background` `White`, `FPS` 30. End the call with the links assembled again (run() autosaves on commit).
4. Camera: perspective, fixed view direction, `fitAll()` on the fully exploded state, then zoom only via `heightAngle`. NaviCube off. Check the exploded frame's content bbox in pixels (≥ 5 % margin each side) before rendering.
5. `i10g_video()` drops hidden links from every step (i10g would show them with transparency 1 and floating edges), checks the patch, starts the render through a `QTimer` so the RPC returns at once. Wait for ffmpeg to exit (Bash `run_in_background` with `until ! pgrep -f "ffmpeg.*<name>"`); send no fdmkit calls meanwhile.
6. Check: `ffprobe` (size, fps, frames), a contact sheet of 6–7 frames.
7. Restore: `thaw_all()`, `full()`, NaviCube back, draw style `As is` (i10g leaves "Flat Lines"), orthographic axonometric view, Fit All. Keep the `Animation` object for a re-render; record it in the project AGENTS.md.
- Limits: i10g renders "Shaded" (no edge lines); linear interpolation only; steps store absolute placements, so record again after any assembly change.

## Speed with big documents (user rule)
The user waits for every call; slow work is a defect. A full recompute of a document with an Assembly re-solves every joint against heavy shapes (tray, drum, 72-tooth gears) and takes minutes.
- `focus('Body', ...)` before editing parts: fdmkit then recomputes only those Bodies and the params sheet. `full()` once at the end recomputes everything and solves the Assembly.
- Read-only questions start with `?` (`?expr`): no transaction, no rollback recompute, no autosave. Never `raise Exception(data)` to read: the abort triggers a recompute.
- `?expr` and normal calls both see the fdmkit calls plus `App` and `Gui`; other modules need an `import` in the call (a normal call may hold several statements; the last expression is the result).
- `freeze('StandAssembly', 'Tray', ...)` (Std_ToggleFreeze) for heavy objects the current step does not change: gears, belts, purchased STEP parts, reference bodies, the Assembly while parts are edited. `thaw()` them before the final check. `freeze('StandAssembly')` freezes only the Assembly and its joint groups, not the linked Bodies; `freeze_all()` / `thaw_all()` freeze or thaw every non-link object (animations, view-only work).
- Batch a whole part edit in one call (sketch changes, features, probes). Split only where a rule demands it (delete: clear expressions, then delete in a separate call). Prefer `Suppressed = True` over deleting a feature: no second call, no crash risk.
- Raw code: recompute one object or Body with `d.recompute([objs])`, not `d.recompute()`.
- Interference and clearance checks: bounding-box prefilter first; `common()`/`distToShape()` only on overlapping pairs; one lift position per call; skip tray/drum pairs whose relative position does not change with the lift.
- Heavy loops (tessellated overhang scans, 4 rotations of a teardrop) on gear bodies: one evaluation per call, not a sweep.
- Do not touch the 3D view while a call runs: a held mouse button blocks the GUI queue (`mouse buttons held`). If a call times out, wait for it (a background `sleep`) instead of sending more calls.
- Never send a call while a previous one is still running in FreeCAD; check with a cheap `?` read first.

## Design stage: minimal recomputes (user rule)
1. Numbers first: settle a layout (lengths, clearances, heights, belts) with params formulas and short calculations, show the table, get the user's OK, then model.
2. Light stand-ins while designing: pulleys as pitch-diameter cylinders, motors as boxes, the tray as a simple drafted box. Real gears, STEP parts and belts only for the final check.
3. The Assembly stays frozen while parts change; `focus()` the edited Bodies; thaw and solve once per stage.
4. Heavy checks (all-pairs interference, overhang scans) only at the end of a stage or on request; between steps use formula clearances and a few `isInside` probes.
5. One part edit per call; `Suppressed` instead of deleting; delete what is no longer needed so the document stays small.

## Metal CNC parts (lathe + 4-axis mill) (user rule)
- Turning first: every turned part is one `Revolution` of a closed R–Z profile on the Body's XZ plane (vertices by params, DoF 0). Chamfers and inside corner radii go into the profile, not into Chamfer/Fillet features. Ring segments (latches, covers, holders) are a turned ring profile cut to a sector by one shoulder `Groove`, so several parts come from one turned ring.
- Milling on a 4-axis mill whose A axis is the part Z: tool axes ±Z and any radial/horizontal direction (indexing). Inside corners parallel to the cutter axis get the cutter radius `params.CncCornerRadius` (Ø1 cutter → R0.5); a mating outside corner gets a chamfer of at least that size. Floor–wall corners (edge perpendicular to the cutter) stay sharp. A slot is at least the cutter Ø wide and at most 4 × its width deep; a corner cutter sticks out at most 6 × Ø.
- Holes: ISO tap drills (M1 0.75, M1.2 0.95, M1.6 1.25, M3 2.5), ISO 273 clearance, standard screws; radial hole sketches 1 mm outside the cylinder; drilled depth ≤ 8 × Ø. Press-fit pins nominal in nominal (drawing m6/H7).
- Walls ≥ 0.3 until the material is chosen (then from the material); lathe grooves ≥ 0.5 (insert width).
- Check with `cnc()` after every change, with `check()` and `lint()`. `cnc()` sees each Body as one workpiece; `skip=` leaves out non-machined Bodies (films, purchased parts). `cnc_show()` paints the faces, `cnc_restore()` puts the colours back.
- Show the cutter with native CAM, not drawn tool shapes: `cam_job(name, body, stock=<feature before the setup>, azimuth=<A index>)`, `cam_slot(job, p1, p2, depth)` with points in part coordinates, `cam_sim(job)` opens CAM_SimulatorGL. CAM has no lathe operations (the Lathe job type is hidden).
- Not wrapped in fdmkit: per-operation Workplanes give native 3+2 indexing, but the paths are stored in the plane frame and CAM_SimulatorGL is 3-axis, so `cam_job(azimuth=)` stays the way to show a setup. Rotary Surface (4th-axis surfacing) and Planar Surface need opencamlib (`import opencamlib`, in the 27.1 bundle); Rotary Surface also needs a Job Machine with a rotary axis from the CAM Machine Library (Preferences → CAM → Machines). Machine-based post processors: LinuxCNC (tilted work planes), Fanuc, Heidenhain; only when the user sets up real G-code output.
- Remove a Job only with `cam_del()` (CAM's own teardown); deleting the Job object by hand leaves model clones, tool bits and their shape Bodies behind.
- CAM_SimulatorGL opens as an MDI tab; while it is in front, `Gui.ActiveDocument.ActiveView` is that tab (`MDIViewPy`, no `viewAxonometric`), so view code and macros silently skip the camera. Use `gdoc.mdiViewsOfType('Gui::View3DInventor')[0]` (and `Gui.activateView('Gui::View3DInventor', True)` to bring it to the front). Show-all macros hide `Path::` objects and the tool bits' shape Bodies.

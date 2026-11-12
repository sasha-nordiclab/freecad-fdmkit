# FDM rules — Bambu A1, 0.4 nozzle, 0.2 layer

## One working file; history in Git (global user rule)
- Keep one canonical working FCStd per project. Save changes to that same file.
- Use Git checkpoints and commits for history and recovery. Do not make version-named model copies, backup/archive folders or per-revision scripts/reports unless explicitly requested.
- Work incrementally: one small logical change, focused validation, save the canonical file, then a Git commit. Batch calls only within that step; do not combine unrelated edits or run an open-ended variant search.
- Use in-memory geometry or a read-only Git baseline for comparisons. If a project lacks Git, initialize it and checkpoint the existing model before editing; preserve unrelated user changes.
- Temporary files required by a specific check belong in scratchpad and are cleaned up afterwards; reuse an existing checker/report rather than create another per step. Respect the user's limits on slicing, FEM and time.

## Token economy (user rule, 2026-11-12)
- Roles: the main session plans, writes the brief and reviews the numbers; one mid-tier subagent (Claude: sonnet) per edit batch runs the calls. Effort medium; high for Assembly joints, cross-document params and check scripts. Never the smallest tier (haiku: results unusable), never a separate read-only inspection agent; a single short read goes from the main session.
- Brief: document, exact change, acceptance numbers, stop conditions. Point to files and sections instead of retyping them.
- Read only what the task needs: the AGENTS.md entry of the edited document and the named rules.md section, each once. Trust "Verified state"; re-measure only what the change touches.
- Calls: one `run()` per batch of related edits; `?expr` reads that return only the needed numbers; no `tree()` or whole-document dumps unless diagnosing an ERR.
- Checks: a light check of the touched Bodies between steps; the full cold-open, `check()`, `lint()`, `case()` once before the commit.
- Stop at the first unexpected error and report it; do not explore, and do not repeat a failing call more than once.
- No screenshots or exports unless asked: the user watches the GUI.
- Reports: params old -> new, objects added/removed, the measured numbers, warnings split into new and pre-existing. No narrative; a table only for requested measurements.
- When the user asks for these rules, state them in the chat as well.

## Standard FreeCAD solutions first
- Before designing a component or mechanism, check native FreeCAD features, installed workbenches, standard parts, and manufacturer CAD for a suitable solution. Check purchased hardware such as bearings, fasteners, gears, and pulleys before drawing substitutes.
- Prefer a standard component when its dimensions, interfaces, and required adjustability fit the design. Resize through supported parameters, verify the dimensions and source, and record the choice in the project handoff.
- Keep custom printable parts as native, fully constrained parametric geometry. Create custom hardware or adapters when no suitable standard solution meets the requirements. A verified envelope is enough when detailed hardware geometry is unnecessary.

## Standard workbenches for each job
Use FreeCAD's own tools and workbenches instead of hand-made scripts or geometry. Installed in FreeCAD 27.1 weekly, with the 26.3 features (built-in + user `Mod`):

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
| CAM | metal CNC parts: one Job per setup / A-axis index, Ø cutter tool controller, Slot/Pocket/Profile/Drilling ops, CAM_SimulatorGL (fdmkit `cam_job`, `cam_slot`, `cam_sim`, `cam_del`) | FDM parts; lathe ops (none in 26.3) |
| BIM, Robot | not used | — |
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

## Local part coordinates and assembly placement

Use this for new multi-part models and when migrating an existing model built in assembly coordinates. The local origin is a design datum, not an arbitrary bounding-box centre. Proven on ORWO 828 (2026-10-30): 12 parts, 47 fully constrained sketches, native moving joints, preserved assembled solids and CAM setups.

### Choose the frames and constraints

- For a turned ring or sleeve, use the turning axis and a functional axial datum: its mid-plane when the height is symmetric, or a mounting shoulder when dimensions start there. For a pin, use its own axis and shoulder. For a curved segment, retain its real curvature axis and align a local plane with its angular symmetry. Do not force symmetry onto intentionally asymmetric features.
- Build each source Body at identity Placement in that local frame. Use its origin planes and parameter-driven AttachmentOffsets; add datum geometry only for meaningful references. Hide source Bodies in the assembled view and show their App::Links.
- Constrain geometry with coincidence, H/V, equality, parallelism, perpendicularity, tangency and symmetry first. Use construction axes/lines/points for centres and repeated features. Add only independent, named dimensions (height, radii, wall, pitch, angles, offsets); derive dependent sizes with expressions. Do not substitute per-vertex X/Y dimensions or Block/Fixed for editable parametrisation.
- Examples: a centred R-Z ring profile uses H/V sides, symmetry about the sketch H axis, InnerRadius, WallThickness and Height. Two hole centres use native point symmetry, Equal diameters, one HoleDiameter and RowPitch. A symmetric radial opening can use a construction ray, paired symmetric vertices, one half-angle and the independent radial levels.
- Assembly placement belongs to native joints. Ground the assembly datum part; connect stationary dependents with Fixed joints when they must follow changing dimensions. Keep moving Slider/Revolute joints and their limits. Avoid Placement expressions on Bodies/Links.

### Migrate without changing the assembled geometry

1. Identify the exact source document, authoring Bodies, Assembly Links, joints, fasteners and dependent CAM/text/drawing objects. Save and Git-checkpoint the canonical working file. Use that checkpoint/in-memory assembled geometry as the baseline and edit the same file; do not create a working copy. **Open/activate the intended document in a separate `run()` call before editing it**: a transaction opened on the previous document cannot roll back edits in the newly opened document. Do not write changes to a read-only comparison baseline.
2. Define each parameter-derived transform `F` from new local coordinates to the old source-part frame (the old assembly frame when the source was at identity). With an existing world transform `W`, update it to `W * F` while rebasing the part shape by `F.inverse()`. Record the datum expressions, not just the current numeric placements. An optional native property container (for example LocalDatums with Frame/Joint Placement properties) can share these expressions without a custom Python Proxy.
3. Freeze the Assembly while editing parts. Preserve native sketches and feature history. Rebase sketch geometry **and** origin-relative dimensional constraints, supports and AttachmentOffsets consistently. A dimension between two geometry points is a length and must not receive a translation offset. An expression following another already-rebased sketch must not be shifted twice. R-Z profiles often need their axial sketch coordinates shifted; transverse sketches usually need their support offset shifted. Radial pins also need the axial shoulder offset and orientation rebased.
4. Clear affected constraint expressions before replacing constraints. Rebuild with geometric relationships and minimal named dimensions; preserve required names used downstream. Do not delete expression-bearing objects until their expressions are cleared and recomputed (see API traps). Verify DoF 0 and absence of redundant/conflicting constraints after each sketch. Recompute the document before trusting Shape: solving a sketch or recomputing only a Body can leave downstream cached shapes stale.
5. Rebase joint connectors: for a detached old connector `J` expressed in the source part frame, use `F.inverse() * J`. Preserve offsets, limits and intended joint axes. Prefer explicit origin references with Detach1/Detach2 and expression-driven Placement1/Placement2 to arbitrary generated faces. Seed Link placements with `W * F`, thaw and solve. Grounding every part freezes its current position; Fixed joints let stationary parts follow parameter changes.
6. Repair changed fillet/chamfer/UpToFace references by matching transformed baseline edge/face geometry to the recomputed predecessor (centre, length/area, curve/surface and endpoints as needed). Require a unique match within tolerance; never silently accept the nearest index or a stale Shape from an invalid feature.
7. Rebase consumers as well: ShapeBinders, decorative text, clone placements and CAM coordinates. Preserve a text shape's intrinsic glyph-centering Placement when composing transforms. For the tested Draft CAM clone of one PartDesign source, preserving its setup requires `C_new = C_old * S_old.inverse() * F * S_new`, where S is that source feature's Placement; verify the actual clone solids. CAM operation points/azimuths must use the part's new frame for future rebuilds. Do not regenerate NC paths or refresh frozen TechDraw pages unless requested; document which drawing sources/views will need rebasing before a future refresh.

### Verify and hand over

- Compare each **assembled** result against its baseline using both `new.cut(old)` and `old.cut(new)`, plus validity, solid count and the functional interfaces. Equal volumes or bounding boxes alone are insufficient. Small numerical integration differences can coexist with zero Boolean difference; report tolerances and resolve ambiguous results.
- For a flat Assembly of direct Body Links, get `link_names = [o.Name for o in assembly.Group if o.TypeId == 'App::Link']`, then call `check(*link_names)`. Exclude non-part links and avoid counting an Assembly and its children twice. For nested assemblies, resolve leaf parts into one common world frame. Plain `check()` compares authoring Bodies at their coincident local origins and reports false assembly intersections.
- Run `lint()` and, for metal, `cnc()` on local parts. Test main drivers with `case(name, value, *link_names)` where applicable. Since `case()` recomputes but does not explicitly solve the Assembly, also solve and check parameter-dependent joint placements; seed the intended free-joint pose when necessary. For an existing-model migration, comparing baseline and candidate at the same perturbed values verifies that the original design relationships survived. Restore both values and pose afterward.
- Test open/closed or other functional poses through native Assembly joints. When a validation script seeds a free rigid group's placement, move all its members consistently before solve: moving only one member can cause the solver to share the displacement among the group. Use native Assembly dragging/Simulation for interactive motion; this is not a replacement animation system.
- Finally `reopen()`, check the Assembly Links, `lint()`, and confirm DoF 0, valid solids, preserved motion and consumer geometry. Restore the intended visibility, active 3D view, axonometric camera and Fit All. Update the project handoff with local datums and the assembly-aware check command.

## Sketch supports and minimal datum planes
- Attach sketches to stable origin planes when they share an orientation. For loft sections at different heights, put each sketch on the same origin plane and drive its `AttachmentOffset.Base.z` with a parameter expression.
- Create a separate datum plane only when it defines a meaningful independent reference or orientation. Do not add one plane merely to place each parallel sketch at a different Z level.
- Build one complete repeated feature before patterning it, when the native pattern can include its constituent features. After simplifying the tree, verify sketch DoF 0, feature validity, and the final shape against the prior model.

## Sketch regions (26.3 sketch internals, 2026-11-02)
Source: MangoJelly "FreeCAD 26.3 Sketch Internals" (2026-10-31), probed on the 27.1 weekly.
- A sketch with `MakeInternals` on exposes every closed region as `InternalFaceN`: overlapping contours split into separate regions, a contour inside another is a hole of the outer region and a region of its own. `pad`/`pocket(..., at=(x, y))` (sketch coordinates, params allowed) turns MakeInternals on and uses only the regions under the points; without `at` the whole sketch is the profile as before.
- Use one master sketch when the profiles share centres, pitches or symmetry (a base with bosses and pockets at different levels: `start='offset'`). Keep separate sketches when the profiles sit on different planes or the regions keep changing identity; a clear tree beats fewer sketches.
- Pick regions by a point, never by `InternalFaceN`: the numbers follow the region order and change when contours are added or deleted. FreeCAD remaps a feature's reference when another contour is deleted (`InternalFace3` became `InternalFace2` and kept its geometry), but a feature whose own region vanished keeps `?InternalFaceN`, turns Invalid and keeps showing the old shape. `lint()` reports it; repair with `remap(feature, (x, y))` (`remap(feature)` = whole sketch), then `check()`.
- A region is a start reference too: `start='reference', reference=(sk, (x, y))`. Do not confuse a feature's regions (`Profile`, shown in the GUI as Support) with the sketch's Attachment: a sketch that moved as a whole is an attachment problem.
- Start offset runs along the feature's own direction: a pad's offset is along the sketch normal, a pocket's along its cut, so `pocket(sk, 2, start='offset', offset=-6)` cuts 4..6 above the sketch; `reverse=True` flips both. A pocket that misses the solid is an ERR.

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
- Use geometric constraints and construction geometry first, then a minimal set of independent named dimensions driven by params. Derive repeated/dependent values instead of dimensioning every vertex. Drive sketch supports, pattern lengths and datum offsets by expressions; native Assembly joints position Bodies through their Links. See "Local part coordinates and assembly placement".
- Turn optional cuts off with `Suppressed = min(zone sizes; depth * 100) < limit`, so a smaller size never builds a broken pocket.
- Guard positions that can collide when sizes shrink (screws, bosses) with `min()`. Never let a guard put two faces exactly tangent: OCC booleans fail there, so leave 0.5 mm.
- Migrating: Git-checkpoint the model, retain baseline geometry for comparison, and edit the same working file. Preserve native features where practical; if replacing a Body, compare assembled geometry before swapping references. Clear expressions and recompute before deleting the old object; never delete the baseline merely to reuse its Name. See "Local part coordinates and assembly placement".
- Test the parametrisation: set several smaller and larger sizes in a transaction, check one valid solid, holes clear, `chk()` and that the bbox equals the derived length, then abort.
- API traps:
  - **Deleting objects that use the sheet crashes FreeCAD 26.3 (RC1 and RC2).** If an object with expressions referencing `params` (feature, sketch, datum, link or whole Body) is deleted, the next change of a sheet cell segfaults in `Document::recompute` → `DocumentObject::enforceRecompute`, even when a recompute ran in between and even when the whole Body is deleted. Reproduced without fdmkit and without addons (2026-10-18). Workaround that works: clear every expression of the objects to be deleted (`for p, e in list(o.ExpressionEngine): o.setExpression(p, None)`), recompute, then delete. To rebuild a part, build it in a new Body, relink the users, clear the old Body's expressions, then delete it.
  - A Body's `BaseFeature` taken from another Body uses that Body's global placement and is not recomputed when the source moves through expressions (it went stale and collided). Build the variant as its own Body from the same params instead.
  - `Spreadsheet.removeRows()` shifts the cells but leaves stale computed values: dependent cells and features then recompute with old numbers (seen 2026-10-18: `drum_y0` −168.8 instead of −138). After removing or inserting rows, touch every used cell (`sheet.touchCells(c)`), `sheet.recompute()`, `doc.recompute()`, and re-read a few derived values before saving.
  - `Spreadsheet.clearAll()` is not undone by `abortTransaction`; rewrite and clear cells one by one.
  - A PartDesign pattern created from Python does not become the Tip, so later features skip it; fdmkit's pattern calls set `body.Tip`, raw scripts must too.
  - A Hole needs its base recomputed before its properties are set.

## Modelling
- Rounds go in sketches (`fil`), not as fillets on complex edges.
- Thin wall mount: countersunk screws plus a separate backing plate Body with nut pockets, printed flat.

## FreeCAD 26.3 / 27.1 features: which call (2026-10-31)
Source: official release notes 26.3 and the 27.1 weekly changes; each call is probed and in `selftest()`.
- Symmetric datum: `midplane(name, a, b)` (MidPlane attachment) instead of a datum offset by half a param; it follows both faces/planes when they move.
- Rotational features: `project_axis=True` revolves about an axis outside the sketch plane (an origin axis or another feature's edge); `type='up_to_face', up_to=` ends a Revolution/Groove at a datum or face, `type='through'` grooves all round.
- Patterns: one semantic feature, then repeat it; never one pocket per hole. `linear` for a row, or a grid with `direction2`/`count2` (2x2 mount holes from one hole, the pitch a param; skip a corner with `suppressed=[(1, 1)]`); `polar` for one ring; `circular` for concentric rings spaced by `radial` with instances `tangential` apart; `path_pattern` along an edge or sketch (first instance = the original, `align=True` turns instances with the tangent); `point_pattern` at the points or circle centres of a sketch (the first one marks the original). Suppress single instances with `suppressed=` instead of extra features. A pattern that changes nothing is an ERR.
- `defeature(faces)` removes holes/fillets/bosses from an imported or base feature and heals the solid; keep native features for own geometry.
- `thickness(faces, value)`: shell with the faces removed; `mode='recto_verso'` puts half the wall on each side. OCC fails on solids with grooves or many details (`Failed to make thick solid`): shell the simple solid first, then add details.
- `mass(*objs, density=)`: volume, mass, CoG and principal moments (Std_MassProperties exists only as a task panel). Material density is used unless the object has FreeCAD's 'Default' material.
- `sel()` with two holes/circles/edges gives the angle between axes and, for parallel ones, the distance of the axes (26.3 Measure does the same in the GUI).
- Assembly: `link_array()` (Part link arrays) for repeated purchased/identical parts — App::Link instances, no copied geometry, joints attach to any instance, `into=` puts the array into the Assembly. `rigid_group(*links)` instead of chains of Fixed joints. `snapshot(name)` stores a functional pose (open/locked) of free parts; `snapshot_restore(name, solve=True)` re-solves afterwards, so jointed parts follow their joints.
- Revolution/Groove `start='offset'` takes an angle (StartOffset is a PropertyAngle).
- Coaxial stepped parts (bushings, collars): compare one axial-section sketch + `revolve` with a master sketch of concentric circles + `pad(at=..., start='offset')`; usually the revolve is simpler and sturdier. Use regions when the steps are not round or share a non-axial layout.
- One sketch per meaningful set of related dimensions (envelope, mount points, ribs), not one per feature and not one giant master sketch; a master sketch whose regions keep changing count is a reason to split it.
- Sketcher Text and the Group constraint (26.3) are experimental and GUI-only: `Sketcher_CreateText` exists, but a Text constraint cannot be built from Python (probed 27.1 weekly), and Group needs the hidden development preview. Do not use either in a model; for lettering use a stable text workflow and check stroke width (>= 2 lines) and gaps.
- Recompute: `EnableAsyncRecompute` (26.3, on by default) only affects GUI commands; `fdmkit.run` recomputes synchronously. After `Gui.runCommand(...)` wait and re-read the state before using the result.
- PartDesign Boolean tool bodies keep their own placement (26.3): no resetting to the origin before a Boolean.
- GUI-only, no fdmkit call: Sketcher dimension tools pick model edges directly (auto external geometry), broken external geometry is flagged in the tree, vertical spreadsheet configuration tables, several documents editable at once with separate undo, experimental fine-grained recompute (a preference; leave off).
- 27.1 weekly fix: spreadsheet values keep their precision after save/reopen (PR #32464); sheet-expression delete segfault, `exportPageAsPdf` crash and chamfer hangs are untested on 27.1 — keep the workarounds.

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
- Take screws from the Fasteners workbench. When a standard or size is missing (no DIN 963, no M1 in ISO 2009), add a CSV row as a patch in `tools/patches/` (`fasteners-din963-m1.patch`; `fasteners-pcb-m3x5-l6.patch` adds length 6 to M3 hex-5.0 PCBSpacer/PCBStandoff) instead of drawing the screw. The patch is lost on an add-on update, so re-apply it.
- Insert fasteners only the standard way (user, 2026-11-03): select the hole edges, `Gui.runCommand('FS<Type>')` (`FSISO7045`, `FSPCBStandoff`, …) gives one attached fastener per edge; then set Diameter, Width, Length (recompute between: each enumeration fills after it), orientation with `Invert`, axial position with `Offset`. Never hand-build with `addObject` + `FSScrewObject` or `copyObject`: no view provider, the user cannot see or select them.
  - On an App::Link to an App::Part the edge must be `Child.EdgeN` (`HalfHolesBoard.Edge16`); a flat `EdgeN` makes `getSubObject` return None and the fastener stays at the origin.
  - After a CSV patch in a running FreeCAD, reload that file into `FastenerBase.FsData` (`FSutils.csv2dict`); Fasteners reads the CSVs once at import.
- Fasteners rewrites `Label` on every recompute (`M1x1.4-Screw…`); keep the standard and the installation site in `Label2`.
- Clamped parts get clearance holes and the threaded part gets a tapped hole. A screw that threads into both parts cannot clamp them.

## TechDraw drawings (2026-10-24)
- Export pages with `TechDrawGui.exportPageAsSvg` only; `exportPageAsPdf` crashed FreeCAD 26.3 and `run()` refuses it.
- A dimension that should show a label instead of the value: `Arbitrary = True`, `FormatSpec = 'D7'`; `getRawValue()` still returns the model value.
- Dimensions reference view vertices by index. Find them by coordinates: DrawViewPart vertices are centred on the view's bounding-box centre, DrawViewSection vertices are in model coordinates. Re-bind them after a geometry change.
- The label offsets `X`/`Y` are page millimetres. Hidden-line computation is asynchronous, so read vertices in the next call.
- Set `KeepUpdated = False` on the pages during stress tests.

### Dimension placement by computation (2026-11-07)
Never place labels by looking at exports or pictures. Per sheet: refresh the page once; next call
`dim_add(...)` for each missing dimension (refs in view coordinates, unscaled, Y up); then
`dim_layout(page, inside=(...), keepout=[title block box])`; it ends with `dim_check`. Export once
at the end only when the user asks. `dim_layout(..., apply=False)` plans without writing.
- Frames (probed 27.1): label centre = view.X/Y + dim.X/Y (page mm, Y up); `getArrowPositions()`
  unscaled, Y up; `getLinearPoints()`/visible vertices/edges scaled, Y DOWN.
- `Fontsize` is the cap height: label width = QFontMetricsF advance x Fontsize / capHeight.
- ISO linear label sits ~0.96 x Fontsize above a horizontal / left of a vertical line (read from
  the page's arrows).
- Lanes: first line 10 mm off the view outline, then 7 mm apart; shortest span nearest the part;
  non-overlapping spans share a lane; a label wider than its span goes past the far end; dims go
  to the side of their measured points, flipped when the label leaves the sheet or hits a view.
- Keep internal section diameters `inside` only when the outside lane would cross many hatched
  walls; inside labels move to the nearest spot clear of edges, labels and lines.
- The title block is template-specific: pass it as `keepout` (x0, y0, x1, y1, page mm, Y up);
  `title_block(page)` reads it from the template SVG.
- View placement: `view_layout(page)` after the refresh and after `dim_layout` (dims widen the
  view envelope). Free field = frame minus title block, notes blocks, keepout; views overlapping in
  x/y move together (projection kept); equal gaps (<= `maxgap` 25), group centred; short captions
  (<= 3 lines) follow their view. `apply=False` plans. Its envelopes are estimates.
- Exact sheet fit (2026-11-08): `sheet_fit(page)` exports the page to a temp SVG, strips the
  template, rasterises the ink (QtSvg -> numpy, 5 px/mm) and checks every pixel: inside the frame,
  outside title block + field row (`title_block`, top 71 on A4 ISO 5457 advanced), projection
  symbol (`projection_symbol`) and `keepout`, all grown by `margin` 0.5. On failure it finds the
  smallest rigid shift (<= 15 mm) that clears everything and moves the drawing (confirm with a
  second run); if none exists it reports the overflow. Reports the free room l/b/r/t. Never judge
  sheets from pictures; never measure the GUI page scene (stale, see KNOWN_ISSUES.md).
- Sequence per sheet: refresh -> check getVisibleEdges -> dim_add -> dim_layout -> view_layout ->
  dim_check OK -> `page_sync` -> NEXT call `sheet_fit` OK -> export. Open + updateGui + export in
  ONE call (a page opened earlier and exported later segfaulted 27.1); frozen pages need
  `page_sync` after views move or the SVG keeps stale dimension lines.

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

## Metal CNC parts (lathe + 4-axis mill) (user rule, 2026-10-30)
- Turning first: every turned part is one `Revolution` of a closed R–Z profile on the Body's XZ plane (vertices by params, DoF 0). Chamfers and inside corner radii go into the profile, not into Chamfer/Fillet features. Ring segments (latches, covers, holders) are a turned ring profile cut to a sector by one shoulder `Groove`, so several parts come from one turned ring.
- Milling on a 4-axis mill whose A axis is the part Z: tool axes ±Z and any radial/horizontal direction (indexing). Inside corners parallel to the cutter axis get the cutter radius `params.CncCornerRadius` (Ø1 cutter → R0.5); a mating outside corner gets a chamfer of at least that size. Floor–wall corners (edge perpendicular to the cutter) stay sharp. A slot is at least the cutter Ø wide and at most 4 × its width deep; a corner cutter sticks out at most 6 × Ø.
- Holes: ISO tap drills (M1 0.75, M1.2 0.95, M1.6 1.25, M3 2.5), ISO 273 clearance, standard screws; radial hole sketches 1 mm outside the cylinder; drilled depth ≤ 8 × Ø. Press-fit pins nominal in nominal (drawing m6/H7).
- Walls ≥ 0.3 until the material is chosen (then from the material); lathe grooves ≥ 0.5 (insert width).
- Check with `cnc()` after every change, with `check()` and `lint()`. `cnc()` sees each Body as one workpiece; `skip=` leaves out non-machined Bodies (films, purchased parts). `cnc_show()` paints the faces, `cnc_restore()` puts the colours back.
- Show the cutter with native CAM, not with drawn tool shapes: `cam_job(name, body, stock=<feature before the setup>, azimuth=<A index>)`, `cam_slot(job, p1, p2, depth)` with points in part coordinates, `cam_sim(job)` opens CAM_SimulatorGL. CAM has no lathe operations (the Lathe job type is hidden).
- CAM 26.3/27.1 (not wrapped in fdmkit): per-operation Workplanes give native 3+2 indexing, but the paths are stored in the plane frame and CAM_SimulatorGL is 3-axis, so `cam_job(azimuth=)` stays the way to show a setup. Rotary Surface (4th-axis surfacing, out of experimental) and Planar Surface need opencamlib, which the 27.1 bundle has (`import opencamlib`; 26.3 had none), and Rotary Surface also needs a Job Machine with a rotary axis from the CAM Machine Library (Preferences → CAM → Machines). Machine-based post processors: LinuxCNC (tilted work planes), Fanuc, Heidenhain. Use them only when the user sets up real G-code output.
- Remove a Job only with `cam_del()` (CAM's own teardown); deleting the Job object by hand leaves model clones, tool bits and their shape Bodies behind.
- CAM_SimulatorGL opens as an MDI tab; while it is in front, `Gui.ActiveDocument.ActiveView` is that tab (`MDIViewPy`, no `viewAxonometric`), so view code and macros silently skip the camera. Use `gdoc.mdiViewsOfType('Gui::View3DInventor')[0]` (and `Gui.activateView('Gui::View3DInventor', True)` to bring it to the front). Show-all macros hide `Path::` objects and the tool bits' shape Bodies.

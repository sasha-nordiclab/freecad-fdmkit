# FDM rules — Bambu A1, 0.4 nozzle, 0.2 layer

## Orientation first
Fix the print orientation before modelling and keep "model axis → print Z" in mind.

## Walls
- min 0.8; structural ≥ 1.6; heavy ≥ 2.4. Use multiples of the line width.
- "N walls" means N perimeters: 2 ≈ 0.87 mm, 3 ≈ 1.3 mm.
- Keep ≥ 2 mm of material between a groove or slot and an edge.

## Overhangs and starts
- Nothing steeper than 40° from vertical, except the bed face. Redesign rather than add supports.
- No feature may start in mid-air (tips, rib ends facing the bed). Ribs grow out of a wall at ≤ 40°.
- Add no ribs or supports the user did not ask for.

## Holes and slots
- A hole or slot whose top would be an arch gets a teardrop or diamond top (sides ≤ 35–40°).
- Round ends are fine at the bottom of a void. Plain hex-nut pockets print fine as they are.
- An annular groove on a vertical face cannot print. Use a recess without an island, or move the groove to the face that is up in print.

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

## Modelling
- Rounds go in sketches (`fil`), not as fillets on complex edges.
- Thin wall mount: countersunk screws plus a separate backing plate Body with nut pockets, printed flat.

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
- Plain white background, pastel colours, no scale bars, captions or numbers on the image. The numbers go in the README or the chat.
- To show loads: colour by deflection (|u|, normalised per load case), use a scaled deformation over a grey outline of the unloaded part, and draw the load arrows.
  - Pick the scale per case so the largest displacement draws at about 20 mm.
- Stories are 1080×1920. Render with VTK from FreeCAD's bundled Python.

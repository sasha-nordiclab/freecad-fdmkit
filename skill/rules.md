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

## Symmetry first
- Before modelling, find the mirror planes and mirrored pairs: bodies such as Module_A/B, bays about a divider, and paired walls.
- Build one side and derive the other by mirroring. Never edit both sides by hand.
- Window, hole and rib layouts must be symmetric about those planes.
- Every design revision checks the symmetry first.

## Modelling
- Rounds go in sketches (`fil`), not as fillets on complex edges.
- Lightening windows: V or triangle shapes with roofs ≤ 35° from vertical and a rim ≥ 6–7 mm.
- Thin wall mount: countersunk screws plus a separate backing plate Body with nut pockets, printed flat.

# Strength checks and calculated lightening (load on demand)

The reference implementation is the THD CP-Lift holder: `Jobo_CPE2_Bottle_Hanger/scripts/fem/`.

## Tools (all bundled with FreeCAD 26.3)
- Mesh: `…/FreeCAD.app/Contents/Resources/bin/gmsh part.step -3 -order 2 -setnumber Mesh.SecondOrderLinear 1 -clmax 2.5 -clmin 1.0 -format inp`.
  - Without `SecondOrderLinear 1`, curved C3D10 elements fail with "nonpositive jacobian".
- Solve: `…/bin/ccx`, linear static, one STEP per load case.
- Time budget (user rule: slowness is a defect): a contact solve on 114 k nodes / 70 k C3D10 took 72 min. Screen designs with `-clmax 4.5 -clmin 1.5` (≈ 3× fewer nodes), run ccx in the background, and refine only the final variant around the peak. Tell the user the expected run time before starting.
- Put temporary STEP and mesh files only in the scratchpad and delete them afterwards. Never write them into the project unless asked.
- Ask before exporting anything. Do not mesh with chamfers ≤ 0.5 mm, because they make the mesh many times heavier; say so in the report.

## Supports (the most common source of wrong answers)
- Model the mounting as it really is:
  - bolt head on its seat (countersink cone or washer face);
  - shank in the bore;
  - the mounting face in **one-sided contact** with the wall (frictionless).
- Solve the contact with CalculiX itself, not with a hand-written active set (with quadratic tets the node set flip-flops and never settles):
  - a rigid C3D8 plate on the mounting plane (E 2e6, all nodes fixed) as master `S1`, the face nodes as a node slave surface;
  - `*CONTACT PAIR,TYPE=NODE TO SURFACE,ADJUST=0.002`, `*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=LINEAR` with 2e4 MPa/mm;
  - solve at ~100 N, not at a unit load; frictionless zero-gap contact is proportional to the load, so scale the result;
  - if it stalls with "too many cutbacks", the last converged increment scaled by 1/t is the answer.
- **Take the contact plane from the model's own parameters (exact angle and point), then select face nodes by distance to it.** A plane tilted 7.547° instead of 7.5° with a 1e-3 tolerance caught 204 of 10 743 face nodes. The part then bore on a strip and looked 20 × softer and twice as weak. Print the face node count and compare it with the face area.
- Equilibrium with contact: ΣRF over the part (load + seats) must be balanced by the wall alone, so the remainder must point along the wall normal.
- A tightened screw is a preloaded joint. While the load-induced change of the screw force stays below the preload, the seat acts as bonded, so fix all the seat nodes; that is the right linear model.
  - Check it after the solve: sum RF over each seat, take the axial and lateral parts, and scale them by the case force. Measured with full-face contact: up to 201 N axial, 122 N lateral on M4 at 625 N preload.
  - Do not make the seat one-sided "for realism" without modelling the preload. With zero preload and a frictionless wall the part becomes a mechanism: k → 0 and deflections in metres.
  - Do not hold a whole countersink cone sideways while releasing it axially. Its nodes sit at different depths, so it acts as a moment clamp.
- Never clamp a rigid cylinder through the part around a bolt. Any new feature inside that cylinder gets "concreted in" and shows thousands of MPa.
- Sanity checks after each solve:
  - k > 0;
  - deflections of a few mm, not 10⁵;
  - the bearing node count is plausible.
  If a check fails, the supports are wrong. Fix them before reporting.

## Loads
- Sustained loads, such as buoyancy F = ρ·g·V or weights: compare with a creep allowable (safety factor 4).
- Impact by a person (a jar knocked into the part): use the energy method.
  - E = ½mv². Force F = √(2·E·k) = v·√(m·k), where k is the local stiffness at the hit point, from a 1 N unit load.
  - Ask the user how hard the hits are: 0.3 m/s is careful, 0.5 m/s careless, 1 m/s a drop.
  - Safety factor 2.
- Temperature factor: 0.85 at 38 °C for PETG.

## Failure criterion: anisotropic, layers ⟂ print Z
- In-plane stress (σxx, σyy, τxy, plus compressive σzz) is compared with the XY strength X.
- Layer separation (tensile σzz) is compared with the interlayer strength Z.
- Interlayer shear (τxz, τyz) is compared with S.
- FI = √((σ_inplane,vM / X)² + (σzz⁺ / Z)² + (τ_il / S)²). Use the design strengths: TDS value × temperature factor ÷ safety factor.
- Default PETG when no TDS is given: X 40, Z 20, S 15 MPa. Prefer the user's TDS.
- Report peak FI per load case with its location, excluding about 6 mm around supports.

## Calculated lightening
1. Solve the part with solid walls. Get the utilisation field u = FI / allowable (worst case per element).
2. Lay a diamond lattice over each wall. For each cell, take the p90 of u inside the cell and require solidity ρ = clamp(K·u, ρ_min, 1).
   - ρ_min comes from the minimum ligament.
   - The window is the cell diamond scaled by √(1 − ρ).
   - Shrink windows to fit the rim; drop those under 7 mm.
3. K is about 1.8 (stress concentration at a window). Lower K cuts more but raises the peaks at the window tips.
4. Mirror-pair layouts: size each pair by the worse of the two cells, then mirror.
5. Solve again with the windows. Accept when the peaks at the critical points do not move, and p99 of u in the window zones is ≤ ~0.75.

6. Prefer recesses and thin wall zones over windows (see rules.md): thin to 2.4 where u ≤ ~0.5 and to 1.8 where u ≤ ~0.3, with ramps at the zone edges. Then solve again and slice both variants.

## Reinforcement: what works under impact
- With a fixed impact energy, stiffening raises the force. σ grows only like √k, so "more material = stiffer" gains little.
  - Measured: a frame thickened from 3.6 to 4.5 mm cut the peaks by only 10–20 %.
- Large gains come from removing stress concentrations: bigger corner radii, smooth transitions, and spreading the strain energy over more material.
- A local pad with an abrupt edge creates a new peak at that edge. Taper every added pad at 45°, and still verify it with a solve.
- Find the real peak location before reinforcing.
  - Gussets along a divider did nothing because the peak was in the opening corners.
- On wall-bolted parts the governing mode is usually layer peel next to the bolts. A 45° fill in the wall-to-frame junction (leg 4 mm) cut the sustained case by 20 % for +0.2 g. Ribs and pads under the bolt made it worse (new peaks at their ends).
- Before trusting any solve, check equilibrium: ΣRF = applied load, and the sign of the contact reactions.
- Report results as a table: case, force, deflection, peak, peak/allowable, location, Δmass. Change the model only after the user agrees.

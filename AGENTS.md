# fdmkit: agent notes

Global user workflow: one working FCStd per project, history in Git. One small change -> focused check -> save the same file -> Git commit. No versioned model copies, backup/archive folders or per-revision scripts/reports unless explicitly requested. This overrides older copy-based migration notes.

These notes cover developing fdmkit itself. For modelling, see `skill/SKILL.md` and `skill/rules.md`.

- Target: FreeCAD 27.1 weekly (2026-10-27 build) on macOS arm64, which carries the 26.3 features; 26.3 RC2 passed the same selftest before the switch. The API is checked with probes against the running FreeCAD, not from memory.
- Layout:
  - `fdmkit/__init__.py` is the kit core: helpers, sketches, features, checks, assembly, speed, `run()`.
  - `fdmkit/machining.py` holds the CNC/CAM calls, `fdmkit/drawing.py` the TechDraw dimension calls (`dim_add`, `dim_layout`, `dim_check`; frames and rules in its docstring, probed on ORWO 828 sheet 01), `fdmkit/tests.py` the selftest. They import core helpers with `from . import ...`, so `tools/fc.py --reload` reloads fdmkit, machining, drawing, tests, then fdmkit again.
  - `Init.py` is the autoload entry.
  - `tools/fc.py` is the XML-RPC client.
  - `fdmkit_mcp/server.py` is the MCP server: one tool, `run`, no dependencies.
- This repo is symlinked as `~/Library/Application Support/FreeCAD/v27-1/Mod/fdmkit` (FreeCAD keeps one user dir per version; migrating settings copies the link). `tools/fc.py` imports from the repo itself, not from a versioned Mod path.
- After editing, run `python3 tools/fc.py --reload && python3 tools/fc.py --selftest` and `uvx ruff check` (config in ruff.toml). The selftest must stay all-OK; add a check for each new function. Its `docs_sync` check fails when a public call is missing from the MCP description or the README table.
- Rules:
  - Only native PartDesign: no Part::Feature blobs.
  - Each call is one transaction and returns one line.
  - Sketch helpers leave the sketch at DoF 0.
- `run()` namespace (`_ns()`): the `__all__` calls plus `App` and `Gui` for both `?expr` reads and transactions. Before 2026-10-20 `?expr` had no `Gui` and transactions had no `App` (NameError). `?expr` runs inside a transaction that is always aborted, so a read cannot change the model (since 2026-11-02).
- Hidden documents (selftest) still have a Gui document, so selection-based helpers (`freeze_all`, `thaw_all`) are testable there.
- FreeCAD 26 view providers of links expose `ShapeAppearance` (a material list), not `ShapeMaterial`; addons written for 0.19/0.21 break on it. Our fix for i10g is `tools/patches/i10g-shapeappearance.patch`; `i10g_video()` refuses to run without it.
- Locale is en_DK, so Spreadsheet values are written as formulas (`'=40.5'`).
- FreeCAD rejects unit tokens (`h m s g l t mm deg in ...`) as alias names.
- Spreadsheet alias changes in 26.3 needed `_SheetObserver` to touch dependents. 27.1 (20261027) updates direct dependents, alias chains and new aliases by itself (probed 2026-11-02 with the observer removed), and the observer made every P() re-execute every sheet-dependent object (985 ms instead of 2 ms in a 118-object document), so `_boot()` installs it only before 27.
- 26.3 properties used by the kit include StartType/StartOffset/StartReference, Common on subtractive features, Hole cosmetic threads and PolarPattern SuppressedIndices. Probe property availability and enumeration values before adding more features.
- `run()` must survive a call that closes the active document (`reopen()`): `_alive(d)` guards the commit and abort, which used to fail with "Cannot access attribute 'abortTransaction' of deleted object". `run()` refuses any expression containing `exportPageAsPdf`, which crashed FreeCAD 26.3.
- Model checks (`check`, `lint`, `case`, `sel`, `reopen`) came from the ORWO 828 revision (2026-10-24). There a PartDesign Hole whose sketch was tangent to the cylinder dropped one of two holes between recomputes, and features left at an absolute Z drifted when the parent part grew. Fasteners objects are recognised by a proxy module starting with `Fasteners`. The selftest covers each check; tangent detection was verified on the ORWO model (six tangent sketches found with the standoff set to 0).

- CNC/CAM (`cnc`, `cnc_show`, `cnc_restore`, `cam_job`, `cam_slot`, `cam_sim`, `cam_del`) came from the ORWO 828 CNC rebuild (2026-10-30). Verified there: suppressing the drum chamber corner fillets flags exactly those two corners; a 0.8 slot is flagged. Probed 26.3 facts: `Mesh.foraminate` returns hits on both sides of the ray (filter by direction) and grazes mesh chords at edges (confirm a hit on the exact solid); `nearestFacetOnRay` is bidirectional too. A ToolBit creates its own `PartDesign::Body` (`BitBody`), so `_bodies()` leaves those out. A Draft clone of a PartDesign feature keeps the feature's sketch frame: its Placement must be `index * feature.Placement`. CAM_SimulatorGL is 3-axis and lists only objects named `Job*`; it opens as an MDI tab. Job ops on a work plane store the path in the plane frame. CAM has no lathe ops; opencamlib has no wheel for Python 3.13.
- `_autosave()` saves a document with a file at most every 300 s after a write call; agents saw the project file change on disk without a save.

## Agent traps seen in use (fix in the kit or in the tool description)
- `?` inside a batch (`a(); b(); ?expr`) was a bare `SyntaxError ... step 0`, nothing ran. `run()` now parses first and returns `ERR parse` with a hint. Fixed 2026-10-25 (ORWO 828).
- A pad/pocket whose profile points away from the solid returned `OK` with an unchanged volume; the agent had to compare volumes by hand. `_finish` now refuses a feature that changes nothing (`try reverse=True`). Fixed 2026-10-25.
- `pocket(reverse=)` existed but the tool description did not list it, so the agent set `Reversed` by hand. Listed now.
- `new(name)` creates a new document, not a Body; agents used it inside a project and left stray files. The description says so; a `body(name)` helper for the open document is still open.
- Sheet cells set with a bare number are unitless and break mm expressions; the description says `'x mm'`.
- Placing a radial sketch: the XZ sketch normal is −Y; the AttachmentOffset pattern is in the description.

- Local-coordinate workflow (ORWO 828, 2026-10-30): the MCP description/instructions and `skill/rules.md` now specify functional local Body origins, geometric symmetry constraints, native Assembly placement, and baseline-preserving migration. `check(*link_names)` checks assembled local parts; default `check()` checks overlapping authoring Bodies. `case()` does not explicitly solve the Assembly. Activate the canonical document in its own call before editing: transaction rollback belongs to the document active at call entry. No new conversion API was added; this is a modelling procedure.

- 26.3/27.1 features (2026-10-31, from the official 26.3 release notes, probed on the 27.1 weekly): `midplane`, Revolution/Groove `type`/`up_to`, `circular`, `path_pattern`, `point_pattern`, `defeature`, `thickness`, `mass`, `sel()` axis angle, `link_array`, `rigid_group`, `snapshot`/`snapshot_restore`; selftest 88/88. Probed facts:
  - `body.newObject()` leaves the Tip on the pattern's original, so a feature added after `polar()` silently dropped the pattern from the Body shape (a bug in 0.2.0). `_pattern()` now sets `body.Tip`. A pattern gets its BaseFeature only on recompute; compare volumes after `_rc`.
  - PathPattern with `RelativeToFirst=False` (the default) places the original as if it sat at the path start, so every instance can miss the solid without an error; the kit sets True. PointPattern uses circle centres of a sketch, the first centre marks the original.
  - Thickness `Reversed=True` (the default) means inwards; OCC fails ("Failed to make thick solid") on a cylinder with grooves.
  - `Part::LinkArrayLinear` in `Mode='Spacing'` takes the step from `Offset`; `Length` is the extent in `Mode='Extent'`.
  - Assembly RigidGroup joints and Snapshots are App::FeaturePython proxies (`JointObject.RigidGroupJoint`, `CommandCreateSnapshot.Snapshot`) that work without an active assembly; moving one rigid-group member moves the others on recompute.
  - Std_MassProperties exists only as a GUI task panel; `mass()` uses OCC solid properties. FreeCAD's 'Default' material carries a placeholder density of 1e-9 kg/mm³, ignored.
  - CAM Rotary Surface needs opencamlib (present in the 27.1 bundle as `opencamlib`) and a Job Machine with a rotary axis; CAM_SimulatorGL stays 3-axis. Not wrapped.

- Sketch regions (2026-11-02, from the MangoJelly 26.3 Sketch Internals manual, probed on the 27.1 weekly 2026-10-27 build): `pad`/`pocket(at=)`, `regions`, `remap`, region as `start='reference'`, `lint()` lost references; selftest 98/98. Probed facts:
  - `Sketcher::SketchObject.MakeInternals` is False on sketches made from Python; `InternalShape` holds the regions in sketch-local coordinates, `getSubObject('InternalFaceN')` in global ones. N = index in `InternalShape.Faces` + 1; the outer region of nested contours comes with its holes cut out.
  - The GUI's Support of a Pad/Pocket is the `Profile` LinkSub `(sketch, ['InternalFace2', ...])`; `Profile = sketch` is the whole sketch. There is no Support property.
  - Deleting another contour remaps `InternalFace3` → `InternalFace2` automatically; deleting the region itself leaves `?InternalFace3`, State Invalid, and the old shape (volume unchanged).
  - `StartOffset` is measured along the feature direction: pad along +normal, pocket along the cut (−normal); `Reversed` flips both.
  - A failed batch rolls back, so a following `undo()` undoes the previous successful call.

- From freecad_2026_features_workflows.md / freecad_ai_agent_rules_2026.md (2026-11-02): most items were already wrapped; added `linear()` (row or 2D grid in one LinearPattern), rules on pattern choice, revolve vs master-sketch regions, sketch granularity, Sketcher Text, async recompute, and the FreeCAD build in each project handoff; selftest 100/100. Probed facts:
  - LinearPattern: `Mode` Extent/Spacing (Spacing reads `Offset`), `Direction2`/`Occurrences2`/`Mode2`/`Offset2` for a grid, `SuppressedIndices` flat index = i·Occurrences2 + j (`SuppressedPositions` holds the (i, j) pairs). Indices set before `Occurrences` are dropped beyond the current count, so `linear()` sets them last; `polar` keeps them.
  - Revolution `StartOffset` is `App::PropertyAngle`.
  - Sketcher Text: GUI command `Sketcher_CreateText` and `SketchObject.setTextAndFont(constraint, text, font_path, isHeight, isConstruction)` exist, but `Sketcher.Constraint('Text', ...)` rejects every argument form, so there is no Python path; not wrapped. `ShowDevelopmentPreviewFeatures` is off (Group constraint hidden).
  - `EnableAsyncRecompute` is True; it applies to GUI commands (Std_Refresh), `Document.recompute()` from Python stays synchronous.

- Deep review (2026-11-02): 10 reviewer agents probed the kit in hidden documents; 108 findings, the high and medium ones fixed and re-probed, selftest 107/107. Facts worth keeping:
  - `_body()` must skip CAM tool-bit Bodies (`cam_job` adds one as the last Body) and look for `pdbody` in every 3D view: the CAM simulator, sheet or TechDraw tab in front has no active Body, and hidden documents have no ActiveView at all.
  - A Transformed feature created with empty Originals does not move the Tip: `mirror()` must set `body.Tip` like `_pattern()`. A DressUp (Defeaturing, Thickness) whose Base is an earlier feature rebases onto it and silently drops every later feature, so the kit accepts only Tip faces.
  - `Gui.Selection.getSelectionEx('', 0)` gives the container (Body) with subname `pad.;#14:1;...F.Face6`; `getSubObject(sub, retType=1)` gives the leaf feature. 'Body.Face6' names the Tip's Face6, a different face.
  - `SketchObject.solve()` marks an up-to-date sketch Touched (recompute debt and an undo step); DoF and the conflict lists are stored in the file, so checks solve only Touched sketches.
  - Pad/Pocket `side='two'` uses a hidden `Length2` default (pad 10, pocket 5). Hole: setting `ThreadType` picks `ThreadSize` from the current diameter as the nominal size and replaces `Diameter` by the tap drill; `DrillPoint='Angled'` adds the cone below `Depth`.
  - Claude Code cuts MCP server instructions at 4096 characters (the tool description arrives whole); keep `INSTRUCTIONS` below that.
  - `full()` used to repoint every lost joint reference to Face1; a joint without Detach then jumps to the part origin. Only detached joints are repointed now; the others are reported.
- FreeCAD issues filed from these findings (2026-11-02, repro scripts run with `FREECAD_USER_HOME=$(mktemp -d) freecadcmd`): #34054 Body.newObject() of Mirrored/PolarPattern leaves the Tip behind (kit workaround: `_pattern()`/`mirror()` set the Tip); #34055 Thickness/Defeaturing on an earlier feature drops later features (kit: Tip faces only); #33685 sheet-expression delete segfault, confirmed on 27.1 20261027 (kit rule: clear expressions before deleting). #33798 (exportPageAsPdf segfault) is someone else's open issue. Drop each workaround once its issue is fixed and the repro passes.
- Error monitoring (2026-11-02): FreeCAD has no Python console observer, so `_report_scan()` reads new lines of the GUI Report view (`QTextEdit` 'Report view'), keeps error entries (Traceback/Error/Exception...) for `errors()` and appends them to `~/Library/Logs/fdmkit/freecad.log`. Messages reach the Report view through Qt's event loop, after the RPC call that printed them, so `run()` notes errors "since the last call". The MCP server logs every call (expr, seconds, result) to `~/Library/Logs/fdmkit/mcp.log`, rotated at 5 MB. The selftest's rigid_group check makes FreeCAD's Assembly print a harmless traceback (`JointObject.onChanged`: no property 'RigidPlacements' yet); FreeCAD #34056.

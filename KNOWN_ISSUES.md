# Known FreeCAD issues

One dated line per critical FreeCAD failure met through fdmkit: call, documents, symptom, workaround.

- 2026-11-07: FreeCAD 27.1 (build 20261027) crashed in `reopen()` of BottleFrame while Panterla, JoboBottle,
  StorageBox and Purchased were open and BottleFrame had just gained cross-document params
  (`JoboBottle#params...`). The file was saved before the crash; unsaved Panterla joint expression edits were lost.
  Workaround: save dependent documents (`doc.save()`) before `reopen()`; restart FreeCAD and reopen Panterla.
- 2026-11-08: FreeCAD 27.1 segfault in `TechDrawGui.exportPageAsSvg` → `QGSPage::saveSvg` →
  `ViewProviderPage::setTemplateMarkers` (ORWO 828, page Dwg03). The page had been opened with `doubleClicked()` in an
  earlier run() call and its MDI scene had been probed (`findChildren(QGraphicsView)`, repeated `doubleClicked()`);
  the export came in a later call without reopening. Nothing lost (model saved/committed).
  Workaround: open the page (`doubleClicked()`), `Gui.updateGui()` and export in the SAME call (as `ink()` /
  ORWO `export_drawing` do); never probe or keep page scenes across calls.
- 2026-11-08: the TechDraw page's GUI scene (`<Page>View` QGraphicsView, `TechDrawGui.getSceneForPage`) is not a
  reliable source of geometry: on frozen pages (`KeepUpdated=False`) it keeps dimension graphics from an older state
  after views move, empties when the tab is hidden, and `getSceneForPage` returned 0 items. `exportPageAsSvg` builds
  its own up-to-date scene. Workaround: measure the exported SVG (`drawing.ink()` / `sheet_fit()`), not the GUI scene.
- 2026-11-08: frozen TechDraw pages (`KeepUpdated=False`) export stale dimension lines after their views were moved
  (`view_layout`): `dim_check` passes (object data) while the SVG shows dims at old places. Workaround: `page_sync()`
  (KeepUpdated on, touch dims/annotations, recompute) one call before export / `sheet_fit`.
- 2026-11-08: after reopening the ORWO document, frozen pages Dwg10/11/12 had empty view caches (0 visible edges)
  and exported blank views. Workaround: refresh the page (KeepUpdated on, recompute) and assert
  `getVisibleEdges()` is non-empty before export.
- 2026-11-08: on load, CAM ToolBits report `PropertyPythonObject::toString(): failed for ToolBitEndmill` and
  `AttributeError: 'ToolBitEndmill' object has no attribute 'obj'` (×2, harmless so far; CAM jobs untouched).
- 2026-11-08 00:45: FreeCAD 27.1 abort (uncaught std::out_of_range) in `TaskSectionView::makeSectionLabel` on OK of
  the Section View task dialog (GUI edit of an ORWO section view, right after a run() call had renamed page/body
  Labels/Label2 from ORWO828-NN to OptikOldschool-NN). Workaround: none yet; avoid editing section views in the task
  dialog after label renames, set SectionSymbol/Label by Python instead.
- 2026-11-08: `drawing.dim_add` picks `VertexN` by the index in `getVisibleVertexes()`, but DrawViewDimension
  References2D `VertexN` uses a different index (ORWO sheet 07 after a geometry change: refs chosen at
  (-14.4,-5.05)/(-13.71,5.05) measured 8.1 instead of 10.1; inner window edges measured 0). `getLinearPoints()` stays
  stale until the page recomputes, so mapping by probing in one call fails too. Workaround: rebind by hand in the GUI;
  fix dim_add to map indices via a page recompute between calls.

- 2026-11-09: FreeCAD 27.1 weekly 20261027, `App.ActiveDocument.save(); reopen(); check(); lint()` on BottleFrame with Panterla, StorageBox, JoboBottle and Purchased open: RPC disappeared during source-document reopen; rib features were saved and verified after restarting FreeCAD. Workaround: cold-open the complete Panterla dependency graph instead of reopening a linked source in place.

- 2026-11-09: FreeCAD 27.1 weekly 20261027, StorageBox native BathRivetCut with 32 circumscribed prism tools and Panterla passage validation exceeded the 120 s GUI dispatch limit; the GUI task continued and later completed, with no lost save. Use 16-sided tools and bounds-filtered boundary-face clearance checks; never queue another mutation while dispatch is running.

- 2026-11-09: FreeCAD 27.1 weekly 20261027, Part::Prism with Part::AttachExtensionPython in StorageBox after cold-opening Panterla: AttachmentOffset evaluated X=-132.45 while Placement and Shape stayed at X=-132.25 after forced recompute, leaving stale rivet holes. Workaround: deactivate attachment on drilling tools and drive Placement directly from params and an independent datum; all four cold-open parameter cases then passed.

- 2026-11-10: FreeCAD 27.1 weekly 20261027; `full(); App.ActiveDocument.save(); reopen(); check(); lint()` on BottleFrame after widening HookBorderBevel to the full guide profile, with Panterla, StorageBox, JoboBottle, Purchased and OptikOldschool_Film_Edge_Mark_Drum open: next RPC found connection refused. BottleFrame and Panterla were saved; restart and cold-open Panterla verified all three frame bodies, 39 constrained sketches, 32 rivet passages and the guide_setback parameter case. No saved edit was lost. The 2026-11-09 linked-source reopen failure recurred; avoid source reopen with dependent documents open and cold-open Panterla instead.

- 2026-11-10: FreeCAD 27.1 weekly 20261103 (commit "fix errored XLink's file property", PropertyXLink::Save now writes getDocumentPath()): saving BottleFrame writes the spreadsheet's `JoboBottle#params` XLink as an absolute path; StorageBox/Panterla saved in this build got absolute XLinks too (build 20261027 wrote relative names). Re-setting the cells does not help; `_autosave()` spread it to every open document. Fixed in fdmkit: `_XLinkObserver` (installed by `_boot()`) rewrites absolute XLink paths relative to the saved file in `slotFinishSaveDocument`; selftest `xlink_relative` covers it. Reported upstream: FreeCAD#34357.
- 2026-11-10: FreeCAD 27.1 (both 20261027 and 20261103) Assembly `RigidGroupJoint.__init__` assigns ObjectsToRigidGroup before adding RigidPlacements, so its onChanged logs `AttributeError: ... no property 'RigidPlacements'` (seen after every selftest). `rigid_group()` now holds onChanged off during the init.
- 2026-11-10: OrcaSlicer 2.5.0 packs system profiles into `profiles/*.opc`; its CLI fails with "can not resolve preset ... system". `tools/orca_slice.py` picks a bundle with unpacked profiles (OrcaSlicer-Debug 2.4.2) or env `ORCA_APP`.

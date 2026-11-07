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

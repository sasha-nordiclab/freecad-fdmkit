"""fdmkit selftest: builds throwaway parts through run() in hidden documents."""
import math

import FreeCAD as App
import Part

from . import PARAMS, V, _aliases, _body, _init, _ref, _sk_issue, _tipvol, run  # noqa: F401


def selftest():
    """Build a throwaway part through run(); one line with the failures."""
    prev = App.ActiveDocument.Name if App.ActiveDocument else None
    picked = []
    if App.GuiUp:
        import FreeCADGui as Gui
        picked = [(s.DocumentName, s.ObjectName, list(s.SubElementNames) or [''])
                  for s in Gui.Selection.getSelectionEx('', 0)]
    d = App.newDocument('fdmkit_selftest', 'fdmkit_selftest', True, True)
    App.setActiveDocument(d.Name)
    _init(d)
    res = []

    def ck(label, expr, test):
        r = run(expr)
        try:
            ok = bool(test(r))
        except Exception:
            ok = False
        res.append((label, ok, r))

    ok = lambda r: ': OK' in r or r.startswith('P:')
    dof0 = lambda r: r.endswith('DoF 0')
    try:
        ck('P', "P(width=40, depth=20, height=5, r_c=3)", ok)
        ck('P_reserved', "P(h=1)", lambda r: r.startswith('ERR') and 'h' not in _aliases(d.getObject(PARAMS)))
        ck('plane', "plane('base', 'XY')", ok)
        ck('sk', "sk('outline', 'base')", ok)
        ck('rect', "rect('outline', 'width', 'depth')", dof0)
        ck('fil', "fil('outline', (20, 10), 'r_c')", dof0)
        ck('circ', "circ('outline', 6, -12, 0)", dof0)
        ck('slot', "slot('outline', 14, 4, 0, -6.5)", dof0)
        ck('poly', "poly('outline', [(10, 2), (16, 2), (13, 7)])", dof0)
        ck('pad', "pad('outline', 'height')", lambda r: 'bb 40.0x20.0x5.0' in r)
        v5 = _tipvol(d)
        ck('drive', "P(height=6)", lambda r: abs(_tipvol(d) / v5 - 1.2) < 1e-6)
        ck('sk_xz', "sk('prof', 'XZ')", ok)
        ck('rect_bl', "rect('prof', 4, 3, 0, 'height', at='bl')", dof0)
        ck('revolve_start', "revolve('prof', start='offset', offset=0)",
           lambda r: 'bb 40.0x20.0x9.0' in r and d.getObject('revolution').StartType == 'Offset')
        ck('plane_expr', "plane('top', 'base', 'height')", lambda r: r.endswith('z 6'))
        ck('sk_top', "sk('holes', 'top')", ok)
        ck('circ_top', "circ('holes', 4, 12, -5)", dof0)
        n = len(d.Objects)
        ck('rollback', "rect('holes', 'nosuch', 5)",
           lambda r: r.startswith('ERR') and len(d.Objects) == n and _sk_issue(d.getObject('holes')) == '')
        ck('batch_rollback', "sk('b2', 'top'); circ('b2', 3, -15, -6); nosuch()",
           lambda r: r.startswith('ERR step 3') and d.getObject('b2') is None)
        n = len(d.Objects)
        ck('pocket_noop', "sk('far', 'top'); circ('far', 3, 60, 0); pocket('far', 2, reverse=True)",
           lambda r: 'changed nothing' in r and len(d.Objects) == n)
        ck('parse_hint', "chk(); ?d", lambda r: r.startswith('ERR parse') and "'?'" in r)
        ck('pocket', "pocket('holes')", lambda r: r.startswith('pocket: OK'))
        ck('undo', "undo()", lambda r: d.getObject('pocket') is None)
        ck('dim', "dim('outline', 'r1_w', 'width + 2')", lambda r: 'bb 42.0x' in r)
        ck('chk', "chk()", lambda r: r.startswith('OK'))
        ck('undo_after_err', "nosuch()", lambda r: r.startswith('ERR'))
        ck('undo_refuses', "undo()", lambda r: 'rolled back' in r and d.getObject('pad') is not None)
        ck('read_discards', "?App.ActiveDocument.getObject('outline').Label = 'renamed'",
           lambda r: d.getObject('outline').Label == 'outline')
        ck('why', "why('outline')", lambda r: r.startswith('outline: DoF 0'))
        ck('tree', "tree()", lambda r: 'outline:Sketch DoF0' in r and '*' in r)
        ck('focus', f"focus('{_body(d).Name}'); P(height=6)", lambda r: r.startswith('focus: ') and 'height=6' in r)
        ck('full', "full()", lambda r: r == 'full: no assembly; OK')
        ck('freeze', "freeze('pad')", lambda r: r == 'freeze: 1 objects'
           and 'Freezed' in d.getObject('pad').getStatusString())
        ck('thaw', "thaw('pad')", lambda r: r == 'thaw: 1 objects'
           and 'Freezed' not in d.getObject('pad').getStatusString())
        ck('new', "new('fdmkit_new_probe', hidden=True)", lambda r: r.startswith('fdmkit_new_probe')
           and App.ActiveDocument.getObject(PARAMS) is not None)
        if 'fdmkit_new_probe' in App.listDocuments():
            App.closeDocument('fdmkit_new_probe')
        App.setActiveDocument(d.Name)
        ck('docs_sync', "?1", lambda r: not _undocumented())
        ck('ns_read', "?(App.ActiveDocument.Name, 'Gui' in globals())",
           lambda r: d.Name in r and 'True' in r)
        ck('ns_write', "App.ActiveDocument.Name", lambda r: r == d.Name)
        ck('freeze_all', "freeze_all()",
           lambda r: r.startswith('freeze_all:') and int(r.split()[1]) > 0
           and 'Freezed' in d.getObject(PARAMS).getStatusString())
        ck('thaw_all', "thaw_all()",
           lambda r: r.startswith('thaw_all:')
           and not any('Freezed' in o.getStatusString() for o in d.Objects))
        ck('i10g_video', "i10g_video()",
           lambda r: r.startswith('ERR') and 'no Animation' in r)
        d2 = App.newDocument('fdmkit_263_features', 'fdmkit_263_features', True, True)
        try:
            App.setActiveDocument(d2.Name)
            _init(d2)
            ck('pad_start', "sk('block_sk','XY'); rect('block_sk',20,20); "
               "pad('block_sk',6,start='offset',offset=2)",
               lambda r: 'bb 20.0x20.0x6.0' in r and d2.getObject('pad').StartType == 'Offset'
               and abs(d2.getObject('pad').Shape.BoundBox.ZMin - 2) < 1e-6)
            ck('top_datum', "plane('top','XY',8)", ok)
            ck('pocket_common_start', "sk('common_sk','XY'); circ('common_sk',12); "
               "pocket('common_sk',start='reference',reference='top',operation='common')",
               lambda r: 'pocket: OK' in r and d2.getObject('pocket').Operation == 'Common'
               and d2.getObject('pocket').StartType == 'Reference')
            ck('hole', "sk('hole_sk','top'); circ('hole_sk',3); "
               "hole('hole_sk',3)", lambda r: 'hole: OK' in r)
            ck('groove', "sk('groove_sk','XZ'); rect('groove_sk',1,1,4.5,3.5); "
               "groove('groove_sk')", lambda r: 'groove: OK' in r)
            ck('chk_263', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d2.Name)
            App.setActiveDocument(d.Name)
        d3 = App.newDocument('fdmkit_263_patterns', 'fdmkit_263_patterns', True, True)
        try:
            App.setActiveDocument(d3.Name)
            _init(d3)
            ck('pattern_base', "sk('pattern_base_sk','XY'); rect('pattern_base_sk',40,40); "
               "pad('pattern_base_sk',6)", lambda r: 'bb 40.0x40.0x6.0' in r)
            ck('pattern_source', "plane('pattern_top','XY',6); sk('pattern_hole_sk','pattern_top'); "
               "circ('pattern_hole_sk',4,10,0); pocket('pattern_hole_sk')",
               lambda r: 'pocket: OK' in r)
            ck('polar_suppressed', "polar('pocket',4,suppressed=(2,))",
               lambda r: 'polar: OK' in r
               and list(d3.getObject('polar').SuppressedIndices) == [2])
            ck('linear_grid', "sk('grid_sk','pattern_top'); circ('grid_sk',3,-15,-15); pocket('grid_sk',name='grid_hole'); "
               "linear('grid_hole','X',2,step=30,direction2='Y',count2=2,suppressed=[(1,1)])",
               lambda r: 'linear: OK' in r and list(d3.getObject('linear').SuppressedIndices) == [3]
               and sorted({(round(e.Curve.Center.x), round(e.Curve.Center.y)) for e in d3.getObject('linear').Shape.Edges
                           if hasattr(e.Curve, 'Radius') and abs(e.Curve.Radius - 1.5) < 1e-6})
               == [(-15, -15), (-15, 15), (15, -15)])
            ck('linear_extent', "linear('grid_hole','Y',3,extent=30,name='lin_ext')",
               lambda r: 'lin_ext: OK' in r and d3.getObject('lin_ext').Mode == 'Extent')
            ck('thread_cosmetic', "sk('thread_sk','pattern_top'); circ('thread_sk',3); "
               "hole('thread_sk',3,thread_type='ISOMetricProfile')",
               lambda r: 'hole: OK' in r and d3.getObject('hole').CosmeticThread
               and not d3.getObject('hole').ModelThread)
            ck('chk_patterns', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d3.Name)
            App.setActiveDocument(d.Name)
        d6 = App.newDocument('fdmkit_regions', 'fdmkit_regions', True, True)
        try:
            App.setActiveDocument(d6.Name)
            _init(d6)
            ck('regions', "sk('reg_sk','XY'); rect('reg_sk',40,20); rect('reg_sk',8,8,-10,0); "
               "rect('reg_sk',8,8,10,0); regions('reg_sk')",
               lambda r: '3 regions' in r and 'A 672.0' in r and 'holes 2' in r)
            ck('pad_at', "pad('reg_sk',6,name='base',at=(0,8))",
               lambda r: abs(d6.getObject('base').Shape.Volume - 672 * 6) < 1e-6)
            ck('pad_at_reference', "pad('reg_sk',12,name='boss',at=(-10,0),"
               "start='reference',reference=('reg_sk',(-10,0)))",
               lambda r: abs(_tipvol(d6) - (672 * 6 + 64 * 12)) < 1e-6
               and d6.getObject('boss').StartType == 'Reference')
            ck('pad_at_offset', "pad('reg_sk',2,name='cap',at=[(-10,0)],start='offset',offset=12)",
               lambda r: abs(d6.getObject('cap').Shape.BoundBox.ZMax - 14) < 1e-6)
            ck('pad_at_miss', "pad('reg_sk',2,at=(30,0))",
               lambda r: r.startswith('ERR') and 'outside every region' in r)
            ck('pocket_at', "pocket('reg_sk',2,name='notch',at=(0,8),start='offset',offset=-6)",
               lambda r: 'notch: OK' in r and abs(d6.getObject('notch').Shape.Volume - (4928 - 672 * 2)) < 1e-6)
            ck('undo_notch', "undo()", lambda r: d6.getObject('notch') is None)
            ck('lid', "pad('reg_sk',9,name='lid',at=(10,0))", lambda r: 'lid: OK' in r)
            ck('lint_lost_region', "s=App.ActiveDocument.reg_sk; s.delGeometries([i for i,g in "
               "enumerate(s.Geometry) if hasattr(g,'StartPoint') and 5<min(g.StartPoint.x,g.EndPoint.x) "
               "and max(g.StartPoint.x,g.EndPoint.x)<15]); App.ActiveDocument.recompute(); lint()",
               lambda r: 'lid.Profile: lost' in r and 'remap' in r)
            ck('remap', "remap('lid',(0,8))",
               lambda r: 'lid: OK' in r and d6.getObject('lid').Profile[1] == ['InternalFace1']
               and abs(d6.getObject('lid').Shape.BoundBox.ZMax - 14) < 1e-6)
        finally:
            App.closeDocument(d6.Name)
            App.setActiveDocument(d.Name)
        d4 = App.newDocument('fdmkit_existing_helpers', 'fdmkit_existing_helpers', True, True)
        try:
            App.setActiveDocument(d4.Name)
            _init(d4)
            ck('half', "P(half_width=20,half_height=10); sk('half_sk','XY'); "
               "rect('half_sk','half_width','half_height'); half('half_sk')",
               lambda r: 'half_sk.half: DoF 0' in r)
            ck('half_pad', "pad('half_sk',6)", lambda r: 'pad: OK' in r)
            ck('half_slot', "P(sl=30, sw=10); sk('hs','XY'); slot('hs','sl','sw',5,0); half('hs'); P(sl=40, sw=16)",
               lambda r: 'WARN' not in r and abs(Part.makeFace(d4.getObject('hs').Shape, 'Part::FaceMakerBullseye').Area
                                                 - (24 * 16 + math.pi * 64) / 2) < 1e-6
               and d4.getObject('hs').Shape.BoundBox.YMin > -1e-6)
            ck('half_ears', "P(e1=10, e2=10); sk('he','XY'); rect('he','e1',20,-15,0); rect('he','e2',20,15,0); "
               "half('he'); P(e2=14)", lambda r: abs(d4.getObject('he').Shape.BoundBox.XMax - 22) < 1e-6)
            ck('half_diamond', "sk('hd','XY'); poly('hd',[(-10,0),(0,-6),(10,0),(0,6)]); half('hd')",
               lambda r: 'area 120.0 -> 60.0' in r)
            ck('sketch_bad_args', "rect('hd',5,5,at='tr')", lambda r: "expected 'c' or 'bl'" in r)
            ck('mirror', "mirror('pad','XZ')", lambda r: 'Mirrored: OK' in r)
            ck('half_drive', "P(half_width=24,half_height=12)",
               lambda r: r.startswith('P:') and d4.getObject('half_sk').DoF == 0
               and abs(d4.getObject('Mirrored').Shape.BoundBox.XLength - 24) < 1e-6
               and abs(d4.getObject('Mirrored').Shape.BoundBox.YLength - 12) < 1e-6)
            ck('move', "plane('later','XY',6); move('later','pad')",
               lambda r: 'later: after pad' in r)
            ck('chk_existing_helpers', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d4.Name)
            App.setActiveDocument(d.Name)
        d5 = App.newDocument('fdmkit_checks', 'fdmkit_checks', True, True)
        live, tmp = d5.Name, None
        try:
            import os
            import tempfile
            App.setActiveDocument(d5.Name)
            _init(d5)
            ck('check_base', "P(blk=20, blk_h=10); sk('blk_sk','XY'); rect('blk_sk','blk','blk'); "
               "pad('blk_sk','blk_h')", lambda r: 'bb 20.0x20.0x10.0' in r)
            ck('check', "check()", lambda r: r.startswith('check: OK 1 bodies'))
            ck('case', "case('blk_h', 14)",
               lambda r: r.startswith('case blk_h=14: OK')
               and abs(d5.getObject('pad').Shape.BoundBox.ZLength - 10) < 1e-6)
            ck('lint_ok', "lint()", lambda r: r == 'lint: OK')
            ck('lint_traps', "plane('blk_top','XY','blk_h'); sk('csk_sk','blk_top'); circ('csk_sk',3); "
               "hole('csk_sk',3,depth=3); h=App.ActiveDocument.getObject('hole'); "
               "h.HoleCutType='Countersink'; h.HoleCutCountersinkAngle=90; h.HoleCutDiameter=6; "
               "s=App.ActiveDocument.getObject('blk_sk'); s.MapMode='Deactivated'; "
               "s.Placement=App.Placement(App.Vector(0,0,0.5),App.Rotation()); App.ActiveDocument.recompute(); lint()",
               lambda r: 'countersink apex' in r and 'blk_sk: placed by numbers' in r)
            pad_ = d5.getObject('pad')
            zf = {round(f.BoundBox.ZMin, 6): i for i, f in enumerate(pad_.Shape.Faces, 1)
                  if f.Surface.TypeId == 'Part::GeomPlane' and abs(f.BoundBox.ZLength) < 1e-9}
            import FreeCADGui as Gui
            Gui.Selection.clearSelection()
            b5 = _body(d5)
            for z in (min(zf), max(zf)):
                Gui.Selection.addSelection(d5.Name, b5.Name, f'{pad_.Name}.Face{zf[z]}')
            ck('sel', "?sel()", lambda r: ('distance 10.5' in r or 'distance 10' in r)
               and r.startswith(f'{pad_.Name}.Face{zf[min(zf)]} ')   # the feature, not 'Body.FaceN'
               and abs(_ref(r.split()[0])[0].getSubObject(r.split()[0].split('.')[1]).BoundBox.ZMin - min(zf)) < 1e-6)
            Gui.Selection.clearSelection()
            ck('pdf_guard', "?TechDrawGui.exportPageAsPdf", lambda r: 'crashes' in r)
            tmp = tempfile.mkdtemp(prefix='fdmkit_')
            fn = os.path.join(tmp, 'fdmkit_checks.FCStd')
            d5.saveAs(fn)
            ck('reopen', "reopen(True)", lambda r: r.startswith('reopen: OK'))
            live = App.ActiveDocument.Name
        finally:
            if live in App.listDocuments():
                App.closeDocument(live)
            App.setActiveDocument(d.Name)
            if tmp:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)
        d6 = App.newDocument('fdmkit_cnc', 'fdmkit_cnc', True, True)
        try:
            App.setActiveDocument(d6.Name)
            _init(d6)
            ck('cnc_base', "P(cb=20, cb_h=10); sk('cb_sk','XY'); rect('cb_sk','cb','cb'); pad('cb_sk','cb_h')",
               lambda r: 'bb 20.0x20.0x10.0' in r)
            ck('cnc_ok', "cnc()", lambda r: r.startswith('cnc: OK 1/1'))
            ck('cnc_pocket', "plane('cb_top','XY','cb_h'); sk('cb_pk','cb_top'); rect('cb_pk',6,6); "
               "pocket('cb_pk',3)", lambda r: 'pocket: OK' in r)
            ck('cnc_corner', "cnc()", lambda r: r.startswith('cnc: ERR 0/1') and 'corner' in r)
            ck('cnc_show', "cnc_show(); cnc_restore()", lambda r: 'cnc_restore: 1 objects' in r)
            ck('cnc_radius_bare', "P(CncCornerRadius=0.5); cnc()", lambda r: 'cnc: ERR 0/1 bodies, Ø1 ' in r)
            ck('cnc_skip_str', "cnc(skip='Body')", lambda r: 'no bodies to check' in r)
            ck('cam_job', "cam_job('JobT', 'Body', cutter=2)", lambda r: r.startswith('cam_job: OK JobT'))
            ck('cam_not_bit', "chk()", lambda r: r.startswith('OK pocket'))   # not the end mill's Body
            ck('cam_slot', "cam_slot('JobT', (-5, 8, 10), (5, 8, 10), 1)", lambda r: r.startswith('cam_slot: OK'))
            ck('cam_bodies', "check()", lambda r: r.startswith('check: OK 1 bodies'))
            ck('cam_del', "cam_del('JobT')", lambda r: r == 'cam_del: JobT'
               and not [o for o in d6.Objects if o.TypeId.startswith('Path') or getattr(o, 'BitBody', None)])
        finally:
            App.closeDocument(d6.Name)
            App.setActiveDocument(d.Name)
        d7 = App.newDocument('fdmkit_271_patterns', 'fdmkit_271_patterns', True, True)
        try:
            import FreeCADGui as Gui
            App.setActiveDocument(d7.Name)
            _init(d7)
            ck('pat_base', "sk('b7','XY'); rect('b7',60,60); pad('b7',8)", lambda r: 'bb 60.0x60.0x8.0' in r)
            ck('midplane', "plane('t7','XY',8); midplane('m7','XY','t7')", lambda r: 'm7: OK at (0, 0, 4)' in r)
            ck('pat_hole', "sk('h7','m7'); circ('h7',3,10,0); pocket('h7', side='sym')", lambda r: 'pocket: OK' in r)
            ck('circular', "circular('pocket', 2, 8, 5, symmetry=6)",
               lambda r: 'circular: OK' in r and _body(d7).Tip.Name == 'circular')
            ck('pattern_tip', "sk('r7','t7'); circ('r7',3,-20,-20); pocket('r7', name='row7')",
               lambda r: 'row7: OK' in r and d7.getObject('row7').BaseFeature.Name == 'circular')
            hv = math.pi * 1.5 ** 2 * 8
            v0 = d7.getObject('row7').Shape.Volume
            ck('path_pattern', "sk('p7','XY'); poly('p7', [(-20,-20),(20,-20),(20,-19)]); "
               "path_pattern('row7','p7.Edge1',count=5)",
               lambda r: 'path_pattern: OK' in r
               and abs((v0 - d7.getObject('path_pattern').Shape.Volume) / hv - 4) < 1e-6)
            ck('point_noop', "sk('q1','XY'); circ('q1',1,-20,20); point_pattern('row7','q1')",
               lambda r: 'changed nothing' in r and d7.getObject('q1') is None)
            ck('point_pattern', "sk('q3','XY'); circ('q3',1,-20,-20); circ('q3',1,0,25); "
               "point_pattern('row7','q3')", lambda r: 'point_pattern: OK' in r)
            cyl = [f'Face{i}' for i, f in enumerate(d7.getObject('circular').Shape.Faces, 1)
                   if f.Surface.TypeId == 'Part::GeomCylinder' and abs(f.Surface.Radius - 1.5) < 1e-6]
            Gui.Selection.clearSelection()
            for f in cyl[:2]:
                Gui.Selection.addSelection(d7.Name, _body(d7).Name, f'circular.{f}')
            ck('sel_axes', "?sel()", lambda r: 'angle 0°' in r and 'apart' in r and ' D3 ' in r)
            Gui.Selection.clearSelection()
            ck('mass', "mass(density=7.85)", lambda r: r.startswith('mass: Body: V') and '7.85 g/cm³' in r)
            ck('link_linear', "link_array('Body','linear',count=3,step=70,axis='X')",
               lambda r: '3 links' in r and 'bb 200.0x60.0x8.0' in r)
            ck('link_polar', "link_array('Body','polar',count=4,axis='Z',name='ring4')", lambda r: '4 links' in r)
            asm = d7.addObject('Assembly::AssemblyObject', 'Assembly')
            asm.newObject('Assembly::JointGroup', 'Joints')
            links = []
            for i, x in enumerate((0, 80)):
                lk = asm.newObject('App::Link', f'L{i + 1}')
                lk.LinkedObject, lk.Placement.Base = _body(d7), V(x, 0, 0)
                links.append(lk)
            d7.recompute()
            ck('rigid_group', "rigid_group('L1','L2')", lambda r: 'RigidGroupJoint: OK 2 parts' in r)
            ck('snapshot', "snapshot('open')", lambda r: 'open: OK 2 parts' in r)
            links[1].Placement.Base = V(120, 0, 0)
            ck('snapshot_restore', "snapshot_restore('open', solve=False)",
               lambda r: 'restored 2' in r and abs(links[1].Placement.Base.x - 80) < 1e-9)
            ck('chk_271_patterns', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d7.Name)
            App.setActiveDocument(d.Name)
        d8 = App.newDocument('fdmkit_271_features', 'fdmkit_271_features', True, True)
        try:
            App.setActiveDocument(d8.Name)
            _init(d8)
            ck('rot_base', "sk('c8','XY'); circ('c8',40); pad('c8',10)", lambda r: 'bb 40.0x40.0x10.0' in r)
            ck('groove_up_to_face', "sk('g8','XZ'); rect('g8',2,2,19,5); "
               "groove('g8', axis='Z', type='up_to_face', up_to='YZ')",
               lambda r: 'groove: OK V 12447.0' in r and d8.getObject('groove').Type == 'UpToFace')
            ck('groove_through', "sk('g9','XZ'); rect('g9',2,1,-19,1); groove('g9', axis='Z', type='through', name='ring')",
               lambda r: 'ring: OK' in r and d8.getObject('ring').Type == 'ThroughAll')
            ck('type_check', "sk('g10','XZ'); rect('g10',1,1,19,8); groove('g10', type='up_to_face')",
               lambda r: 'needs up_to' in r and d8.getObject('g10') is None)
            d8.addObject('PartDesign::Body', 'Shell')     # Thickness fails on the grooved solid (OCC)
            ck('rot_hole', "sk('c9','XY'); circ('c9',40); pad('c9',10,name='shell_pad'); "
               "plane('t8','XY',10); sk('h8','t8'); circ('h8',6,10,0); pocket('h8',4)",
               lambda r: 'pocket: OK' in r and _body(d8).Name == 'Shell')
            pk = d8.getObject('pocket')
            hole_faces = [f'pocket.Face{i}' for i, f in enumerate(pk.Shape.Faces, 1)
                          if (f.Surface.TypeId == 'Part::GeomCylinder' and f.Surface.Radius < 5)
                          or (f.Surface.TypeId == 'Part::GeomPlane' and abs(f.BoundBox.ZMax - 6) < 1e-6
                              and f.BoundBox.XLength < 7)]
            vfull = d8.getObject('shell_pad').Shape.Volume
            ck('defeature', f"defeature({hole_faces!r})",
               lambda r: 'defeature: OK' in r and abs(d8.getObject('defeature').Shape.Volume - vfull) < 1e-3)
            df = d8.getObject('defeature')
            top = next(f'defeature.Face{i}' for i, f in enumerate(df.Shape.Faces, 1)
                       if f.Surface.TypeId == 'Part::GeomPlane' and abs(f.BoundBox.ZMin - 10) < 1e-6)
            ck('thickness', f"thickness({top!r}, 1)",
               lambda r: 'thickness: OK' in r and 'bb 40.0x40.0x10.0' in r
               and d8.getObject('thickness').Shape.Volume < vfull / 3)
            ck('chk_271_features', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d8.Name)
            App.setActiveDocument(d.Name)
    finally:
        App.closeDocument(d.Name)
        if prev and prev in App.listDocuments():
            App.setActiveDocument(prev)
        if App.GuiUp:
            Gui.Selection.clearSelection()
            for dn, on, subs in picked:
                for sub in subs:
                    try:
                        Gui.Selection.addSelection(dn, on, sub)
                    except Exception:
                        pass
    bad = [f'{label}: {r}' for label, good, r in res if not good]
    return f'selftest {len(res) - len(bad)}/{len(res)}' + (' | ' + ' | '.join(bad) if bad else ' OK')


def _undocumented():
    """Public calls missing from the MCP tool description or the README API table."""
    import fdmkit
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    srv = open(os.path.join(root, 'fdmkit_mcp', 'server.py'), encoding='utf-8').read()
    readme = open(os.path.join(root, 'README.md'), encoding='utf-8').read()
    import re
    return [n for n in fdmkit.__all__ if not re.search(rf'\b{n}\b', srv) or f'`{n}(' not in readme]

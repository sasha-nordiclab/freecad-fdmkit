"""fdmkit CNC/CAM: checks for lathe + 4-axis milled metal parts and native CAM jobs.

Imported by fdmkit/__init__.py; reload order in tools/fc.py: fdmkit, machining, tests, fdmkit.
"""
import math

import FreeCAD as App
import Part

from . import FdmkitError, V, _aliases, _bodies, _doc, _obj, _sheet, _val

# Metal parts machined on a lathe (axis = the Body's turning axis) plus a 4-axis mill whose A axis
# is the part Z: tool axes are +-Z and any direction perpendicular to Z. Cutter radius =
# params.CncCornerRadius (else 0.5) unless cnc(cutter=Ø) says otherwise.
CNC_MIN_WALL = 0.3          # warning until the material is chosen
CNC_MAX_DRILL_LD = 8        # hole depth / diameter
CNC_MAX_MILL_LD = 4         # slot depth / width
CNC_MAX_REACH_D = 6         # corner cutter stick-out / diameter (long-reach end mill)
CNC_LATHE_MIN_GROOVE = 0.5  # grooving insert width
CNC_HOLES = {0.75: 'M1 tap', 0.95: 'M1.2 tap', 1.25: 'M1.6 tap', 2.5: 'M3 tap', 3.3: 'M4 tap', 4.2: 'M5 tap',
             1.0: 'M1 nom/pin', 1.2: 'M1.2 nom/M1 clr', 1.6: 'M1.6 nom/M2 tap', 2.0: 'M2 nom/pin',
             3.0: 'M3 nom/pin', 1.1: 'M1 clr', 1.3: 'M1.2 clr', 1.4: 'M1.2 clr', 1.7: 'M1.6 clr',
             1.8: 'M1.6 clr', 2.2: 'M2 clr', 2.4: 'M2 clr', 3.2: 'M3 clr', 3.4: 'M3 clr'}  # ISO tap drills, ISO 273
_Z = V(0, 0, 1)


def _cnc_par(a, b, tol=1e-3):
    return abs(abs(a.dot(b)) - 1) < tol


def _cnc_tool_axis(v):
    return _cnc_par(v, _Z) or abs(v.z) < 1e-3


def _cnc_coaxial(f, p, d):
    """Face f is a surface of revolution about the line (p, d), or a plane across it."""
    s = f.Surface
    t = s.TypeId
    if t == 'Part::GeomPlane':
        return _cnc_par(s.Axis, d)
    if t == 'Part::GeomSphere':
        return (s.Center - p).cross(d).Length < 1e-4
    if t in ('Part::GeomCylinder', 'Part::GeomCone', 'Part::GeomToroid'):
        c = s.Apex if t == 'Part::GeomCone' else s.Center
        return _cnc_par(s.Axis, d) and (c - p).cross(d).Length < 1e-4
    if t == 'Part::GeomSurfaceOfRevolution':
        return _cnc_par(s.Direction, d) and (s.Location - p).cross(d).Length < 1e-4
    return False


def _cnc_lathe_axis(sh):
    """Turning axis: Z or the axis of a round face (pins), whichever turns the largest area."""
    cands = [(V(), _Z)]
    F = sh.Faces
    for f in F:
        s = f.Surface
        if s.TypeId not in ('Part::GeomCylinder', 'Part::GeomCone', 'Part::GeomToroid') or _cnc_par(s.Axis, _Z):
            continue    # an axis parallel to Z is a drilled hole or a boss, not the A axis
        c = s.Apex if s.TypeId == 'Part::GeomCone' else s.Center
        u, v = f.Surface.parameter(f.CenterOfMass)
        q, n = f.valueAt(u, v), f.normalAt(u, v)
        r = q - c - V(s.Axis) * (q - c).dot(V(s.Axis))
        if r.Length > 1e-9 and n.dot(r) > 0:       # outer surface (a hole's normal points to its axis)
            cands.append((c, s.Axis))
    area = [f.Area for f in F]
    return max(cands, key=lambda a: (sum(x for f, x in zip(F, area) if _cnc_coaxial(f, *a)), a[1] is _Z))


def _cnc_samples(f, n=3, shrink=0.2):
    """(point, normal) on an n x n grid inside face f."""
    u0, u1, v0, v1 = f.ParameterRange
    pts = []
    for i in range(n):
        for j in range(n):
            u = u0 + (u1 - u0) * (shrink + (1 - 2 * shrink) * (i + 0.5) / n)
            v = v0 + (v1 - v0) * (shrink + (1 - 2 * shrink) * (j + 0.5) / n)
            p = f.valueAt(u, v)
            if f.isInside(p, 1e-4, True):
                pts.append((p, f.normalAt(u, v)))
    if not pts:
        u, v = f.Surface.parameter(f.CenterOfMass)
        pts.append((f.valueAt(u, v), f.normalAt(u, v)))
    return pts


def _cnc_hit(mesh, p, d, start=1e-3):
    """Distance to the first mesh hit along d from p, None if the ray escapes (foraminate hits both ways)."""
    ds = [(V(*q) - p).dot(d) for q in mesh.foraminate((p.x, p.y, p.z), (d.x, d.y, d.z)).values()]
    ds = [x for x in ds if x > start]
    return min(ds) if ds else None


def _cnc_escapes(mesh, p, d, sh):
    """Ray p->d leaves the part: mesh first, a mesh hit confirmed on the exact solid (grazing chords)."""
    if _cnc_hit(mesh, p, d) is None:
        return True
    return sh.common(Part.LineSegment(p, p + d * 200).toShape()).Length < 0.005


def _cnc_envelope(sh):
    """Bounding cylinder about Z: (R max, Z min, Z max)."""
    r = max([math.hypot(v.X, v.Y) for v in sh.Vertexes] +
            [f.Surface.Radius for f in sh.Faces if f.Surface.TypeId == 'Part::GeomCylinder'
             and _cnc_par(f.Surface.Axis, _Z) and math.hypot(f.Surface.Center.x, f.Surface.Center.y) < 1e-4])
    return r, sh.BoundBox.ZMin, sh.BoundBox.ZMax


def _cnc_reach(env, q, d):
    """Tool stick-out: distance along d from q until the ray leaves the bounding cylinder."""
    r, z0, z1 = env
    out = []
    a = d.x * d.x + d.y * d.y
    if a > 1e-9:
        b = q.x * d.x + q.y * d.y
        c = q.x * q.x + q.y * q.y - r * r
        out.append((-b + math.sqrt(max(b * b - a * c, 0))) / a)
    if d.z > 1e-9:
        out.append((z1 - q.z) / d.z)
    elif d.z < -1e-9:
        out.append((z0 - q.z) / d.z)
    return max(min(out), 0)


def _cnc_where(p):
    return f'R{math.hypot(p.x, p.y):.2f} {math.degrees(math.atan2(p.y, p.x)):.0f}° Z{p.z:.2f}'


def _cnc_into(f, p, t):
    """(normal, unit tangent of f at p perpendicular to the edge tangent t pointing into f)."""
    n = f.normalAt(*f.Surface.parameter(p))
    v = n.cross(t)
    if v.Length < 1e-9:
        return n, None
    v.normalize()
    return n, (v if f.isInside(p + v * 0.01, 1e-3, True) else -v)


def _cnc_concave(sh, e, f1, f2):
    """Edge e between f1, f2 at its midpoint: (sharp and concave, point). Concave = the point stepped
    into both faces lies outside the solid."""
    u = (e.FirstParameter + e.LastParameter) / 2
    p, t = e.valueAt(u), e.tangentAt(u)
    n1, v1 = _cnc_into(f1, p, t)
    n2, v2 = _cnc_into(f2, p, t)
    if v1 is None or v2 is None or n1.getAngle(n2) <= math.radians(5):
        return False, p
    return not sh.isInside(p + (v1 + v2) * 0.02, 1e-4, True), p


def _cnc_body(b, r):
    """One workpiece: issues by kind, offending face indices, holes."""
    import MeshPart
    sh = b.Shape
    pa, da = _cnc_lathe_axis(sh)
    mesh = MeshPart.meshFromShape(Shape=sh, LinearDeflection=0.02, AngularDeflection=0.2)
    F = sh.Faces
    turned = [_cnc_coaxial(f, pa, da) for f in F]
    env = _cnc_envelope(sh) if _cnc_par(da, _Z) and pa.cross(_Z).Length < 1e-4 else None  # pins: no reach limit
    out = {k: [] for k in ('corner', 'fillet', 'access', 'slot', 'groove', 'hole', 'wall')}
    bad, holes = set(), []

    # concave cylinders off the lathe axis: drilled holes (> 180°) or cutter fillets
    for i, f in enumerate(F):
        s = f.Surface
        if s.TypeId != 'Part::GeomCylinder' or turned[i]:
            continue
        p, n = _cnc_samples(f, 1)[0]
        if (s.Center + s.Axis * (p - s.Center).dot(s.Axis) - p).dot(n) <= 0:
            continue
        hs = [(v.Point - s.Center).dot(s.Axis) for v in f.Vertexes] or [0]
        h = max(hs) - min(hs) if len(f.Vertexes) > 1 else f.Area / (2 * math.pi * s.Radius)
        dia = 2 * s.Radius
        if f.Area / (s.Radius * max(h, 1e-6)) > math.pi * 1.05:
            holes.append(f'Ø{dia:.2f}×{h:.2f} ' + next((v for k, v in CNC_HOLES.items() if abs(k - dia) < 0.011), 'other'))
            if h / dia > CNC_MAX_DRILL_LD:
                out['hole'].append(f'F{i + 1} Ø{dia:.2f} L/D {h / dia:.1f} {_cnc_where(p)}')
                bad.add(i)
        elif s.Radius < r - 0.02 and _cnc_tool_axis(s.Axis):
            out['fillet'].append(f'F{i + 1} R{s.Radius:.2f}<{r:g} {_cnc_where(p)}')
            bad.add(i)

    # sharp concave edges: lathe, or floor-wall with a floor the cutter reaches; else needs R
    e2f = {}
    for k, f in enumerate(F):
        for e in f.Edges:
            e2f.setdefault(e.hashCode(), (e, []))[1].append(k)
    for e, ks in e2f.values():
        fs = sorted(set(ks))
        if len(fs) != 2 or (turned[fs[0]] and turned[fs[1]]):
            continue
        cc, p = _cnc_concave(sh, e, F[fs[0]], F[fs[1]])
        if not cc:
            continue
        t = e.tangentAt((e.FirstParameter + e.LastParameter) / 2)
        ok = False
        for fl in fs:
            f = F[fl]
            if f.Surface.TypeId != 'Part::GeomPlane' and not turned[fl]:
                continue                                    # floor = plane or turned surface (4-axis wrapped floor)
            n, into = _cnc_into(f, p, t)
            if into is None or not _cnc_tool_axis(n):
                continue
            q = p + into * (r + 0.02) + n * 0.02             # cutter centre; footprint rays at 0.9 r round it
            foot = (V(), into * 0.9 * r, into * -0.9 * r, t * 0.9 * r, t * -0.9 * r)
            if (env is None or _cnc_reach(env, q, n) <= CNC_MAX_REACH_D * 2 * r) and \
                    all(_cnc_escapes(mesh, q + o, n, sh) for o in foot):
                ok = True
                break
        if not ok:
            out['corner'].append(f'F{fs[0] + 1}/F{fs[1] + 1} needs R{r:g} {_cnc_where(p)}')
            bad.update(fs)

    # tool access for milled faces
    for i, f in enumerate(F):
        if turned[i] or i in bad:
            continue
        for p, n in _cnc_samples(f, 2):
            dirs = [n] if _cnc_tool_axis(n) else []
            hn = V(n.x, n.y, 0)
            if hn.Length > 1e-6:
                hn.normalize()
                dirs += [hn, _Z.cross(hn), -_Z.cross(hn)]
            dirs += [_Z, -_Z]
            ax = getattr(f.Surface, 'Axis', None)
            if f.Surface.TypeId in ('Part::GeomCylinder', 'Part::GeomCone') and _cnc_tool_axis(ax):
                dirs += [ax, -ax]                           # drill / countersink along the hole axis
            q, ds = p + n * 0.1, [a for a in dirs if n.dot(a) >= -0.01]
            if not (any(_cnc_hit(mesh, q, a) is None for a in ds)
                    or any(sh.common(Part.LineSegment(q, q + a * 200).toShape()).Length < 0.005 for a in ds)):
                out['access'].append(f'F{i + 1} {f.Surface.TypeId[10:]} {_cnc_where(f.CenterOfMass)}')
                bad.add(i)
                break

    # slots and lathe grooves: opposed planar faces closer than the tool
    nb = {k: set() for k in range(len(F))}
    for _, fs in e2f.values():
        for k in fs:
            nb[k].update(x for x in fs if x != k)
    pl = [(i, f, f.normalAt(*f.Surface.parameter(f.CenterOfMass))) for i, f in enumerate(F)
          if f.Surface.TypeId == 'Part::GeomPlane']
    for a, (i, f, n) in enumerate(pl):
        for j, g, m in pl[a + 1:]:
            if n.dot(m) > -0.999:
                continue
            gap = n.dot(g.CenterOfMass - f.CenterOfMass)
            axes = ([_Z] if abs(n.z) < 1e-3 else []) + ([_Z.cross(n).normalize()] if _Z.cross(n).Length > 1e-6 else [])
            depth = min((max(v.Point.dot(x) for v in f.Vertexes) - min(v.Point.dot(x) for v in f.Vertexes)
                         for x in axes), default=0)
            if gap <= 0.02 or (gap >= max(2 * r, CNC_LATHE_MIN_GROOVE) and depth / gap <= CNC_MAX_MILL_LD):
                continue        # nothing to report for this pair: skip the costly overlap test
            if abs(f.distToShape(g)[0] - gap) > 0.01:
                continue
            # lathe groove = both faces turned with a turned floor between them (a milled window has none)
            if turned[i] and turned[j] and any(
                    turned[k] and max(v.Point.dot(n) for v in F[k].Vertexes)
                    - min(v.Point.dot(n) for v in F[k].Vertexes) <= gap + 0.02
                    for k in nb[i] & nb[j] if F[k].Vertexes):
                if gap < CNC_LATHE_MIN_GROOVE - 0.02:
                    out['groove'].append(f'F{i + 1}/F{j + 1} {gap:.2f}<{CNC_LATHE_MIN_GROOVE:g} {_cnc_where(f.CenterOfMass)}')
                    bad.update((i, j))
                continue
            if gap < 2 * r - 0.02:
                out['slot'].append(f'F{i + 1}/F{j + 1} {gap:.2f}<Ø{2 * r:g} {_cnc_where(f.CenterOfMass)}')
                bad.update((i, j))
            elif depth / gap > CNC_MAX_MILL_LD:
                out['slot'].append(f'F{i + 1}/F{j + 1} {gap:.2f} deep {depth:.2f} {_cnc_where(f.CenterOfMass)}')
                bad.update((i, j))

    # thin walls: ray from the face inwards to the opposite side
    worst = {}
    for i, f in enumerate(F):
        for p, n in _cnc_samples(f, 3):
            t = _cnc_hit(mesh, p - n * 0.03, -n, 0.005)     # start beyond the mesh deviation
            if t is not None and t + 0.03 < min(CNC_MIN_WALL, worst.get(i, (9,))[0]):
                worst[i] = (t + 0.03, p)
    for i, (t, p) in sorted(worst.items(), key=lambda kv: kv[1][0]):
        out['wall'].append(f'F{i + 1} {t:.2f}<{CNC_MIN_WALL:g} {_cnc_where(p)}')
        bad.add(i)
    return {'turned': sum(turned), 'faces': len(F), 'holes': holes, 'out': out, 'bad': sorted(bad)}


def _cnc_f(v):
    """Float of a number, Quantity, '1.5 mm' or a params alias."""
    if isinstance(v, str):
        s = _sheet(False)
        try:
            return _val(s, v) if s is not None else App.Units.Quantity(v).Value
        except Exception:
            raise FdmkitError(f'cutter {v!r}: not a length, expression or params alias') from None
    return float(getattr(v, 'Value', v))


def _cnc_radius(d, cutter):
    if cutter is not None:
        return _cnc_f(cutter) / 2
    s = _sheet(False, d)
    if s is not None and 'CncCornerRadius' in _aliases(s):
        v = s.get('CncCornerRadius')        # P(CncCornerRadius=0.5) stores a bare number
        return float(getattr(v, 'Value', v))
    return 0.5


def cnc(*bodies, skip=(), cutter=None, holes=False):
    """CNC check, lathe + 4-axis mill: sharp inside corners without a floor the cutter reaches,
    fillets below the cutter radius, milled faces no tool direction reaches, slots narrower
    than the cutter or too deep, lathe grooves, deep holes, thin walls. holes=True lists holes
    (tap drill / ISO 273 clearance). cnc_show() paints the last result red."""
    d = _doc()
    r = _cnc_radius(d, cutter)
    skip = (skip,) if isinstance(skip, str) else tuple(skip)
    bs = [_obj(n) for n in bodies] if bodies else [b for b in _bodies(d) if b.Name not in skip and b.Label not in skip]
    if not bs:
        raise FdmkitError('cnc: no bodies to check')
    res = {b.Name: _cnc_body(b, r) for b in bs}
    App._fdmkit_cnc = res
    parts = []
    for name, x in res.items():
        issues = [f'{k} ' + ', '.join(v[:3]) + (f' +{len(v) - 3}' if len(v) > 3 else '') for k, v in x['out'].items() if v]
        hs = {}
        for h in x['holes']:
            hs[h] = hs.get(h, 0) + 1
        hl = ', '.join(f'{c}× {h}' for h, c in hs.items()) if holes and hs else ''
        if issues or hl:
            parts.append(f'{name}: ' + '; '.join(issues + ([f'holes {hl}'] if hl else [])))
    nbad = sum(1 for x in res.values() if x['bad'])
    head = f'cnc: {"OK" if not nbad else "ERR"} {len(res) - nbad}/{len(res)} bodies, Ø{2 * r:g} cutter'
    return head + (' | ' + ' | '.join(parts) if parts else '')


def _tip_vo(b):
    return (b.Tip or b).ViewObject


def cnc_show():
    """Paint the faces of the last cnc() red on each Body's Tip (the GUI shows the Tip)."""
    d = _doc()
    res = getattr(App, '_fdmkit_cnc', None)
    if not res:
        raise FdmkitError('run cnc() first')
    saved = getattr(App, '_fdmkit_cnc_saved', {})
    out = []
    for name, x in res.items():
        b = d.getObject(name)
        if b is None or not x['bad'] or not b.ViewObject:
            continue
        vo = _tip_vo(b)
        old = saved.setdefault((d.Name, vo.Object.Name), list(vo.DiffuseColor))
        n = len(b.Shape.Faces)
        base = old if len(old) == n else old[:1] * n
        vo.DiffuseColor = [(1.0, 0.15, 0.15, base[i][3]) if i in x['bad'] else base[i] for i in range(n)]
        out.append(f'{name} {len(x["bad"])}')
    App._fdmkit_cnc_saved = saved
    return 'cnc_show: ' + (', '.join(out) if out else 'nothing to show')


def cnc_restore():
    """Colours back after cnc_show()."""
    d = _doc()
    saved = getattr(App, '_fdmkit_cnc_saved', {})
    done = [k for k in saved if k[0] == d.Name and d.getObject(k[1]) is not None]
    for k in done:
        d.getObject(k[1]).ViewObject.DiffuseColor = saved.pop(k)
    App._fdmkit_cnc_saved = saved
    return f'cnc_restore: {len(done)} objects'


def _cam_index(azimuth):
    """Turns the radial direction at azimuth (deg) to +Z (the part axis Z goes to -X): the A-axis index."""
    return App.Rotation(V(0, 1, 0), -90).multiply(App.Rotation(_Z, -azimuth))


def _cam_drop_tc(d, tc):
    """Remove a tool controller with its tool bit and the bit's shape Body."""
    import Path.Base.Util as PathUtil
    tool = getattr(tc, 'Tool', None)
    if tool is not None:
        bb = getattr(tool, 'BitBody', None)
        if bb is not None:
            bb.removeObjectsFromDocument()
            d.removeObject(bb.Name)
        PathUtil.clearExpressionEngine(tool)
        d.removeObject(tool.Name)
    PathUtil.clearExpressionEngine(tc)
    tc.Proxy.onDelete(tc)
    d.removeObject(tc.Name)


def cam_job(name, body, stock=None, azimuth=None, cutter=None):
    """Native CAM Job for one setup. azimuth = 4-axis index: the Job's model and stock clones turn so
    the radial direction at that azimuth (deg, about Z) is the tool axis +Z (CAM_SimulatorGL is
    3-axis); None = tool along -Z. stock = the feature or Body before this setup (default: the
    CAM bounding box). One Ø cutter tool controller (default 2 × params.CncCornerRadius).
    Job, controller and ops are created hidden (their paths sit in the turned frame)."""
    import Path.Main.Job as PathJob
    import Path.Tool.Controller as PathTC
    from Path.Tool.toolbit import ToolBit
    d = _doc()
    name = name if name.startswith('Job') else 'Job' + name    # CAM_SimulatorGL lists only 'Job*' names
    if d.getObject(name):
        cam_del(name)
    model, src = _obj(body), _obj(stock) if stock else None
    rot = _cam_index(_cnc_f(azimuth)) if azimuth is not None else App.Rotation()
    pl = App.Placement(V(), rot)
    job = PathJob.Create(name, [model])
    if App.GuiUp and job.ViewObject:
        import Path.Main.Gui.Job as PathJobGui
        job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
        job.ViewObject.addExtension('Gui::ViewProviderGroupExtensionPython')
        job.ViewObject.Proxy.deleteOnReject = False
    for m in job.Model.Group:
        m.Placement = pl
    if src is not None:
        old = job.Stock
        st = PathJob.createResourceClone(job, src, 'Stock', 'Stock')
        st.Placement = pl.multiply(src.Placement)          # a PartDesign feature clone keeps its sketch frame
        job.Stock = st
        if old is not None:
            d.removeObject(old.Name)
    for tc in list(job.Tools.Group):                        # the default controller, as Job.onDelete does
        job.Tools.removeObject(tc)
        _cam_drop_tc(d, tc)
    dia = 2 * _cnc_radius(d, cutter)
    bit = ToolBit.from_shape_id('endmill.fcstd', label=f'Ø{dia:g} end mill')
    tool = bit.attach_to_doc(doc=d)
    tool.Diameter, tool.CuttingEdgeHeight, tool.ShankDiameter, tool.Length = dia, max(3 * dia, 3), max(dia, 3), 38
    if tool.ViewObject:
        tool.ViewObject.Visibility = False
    tc = PathTC.Create(f'TC: Ø{dia:g} end mill', tool=tool, toolNumber=1)
    tc.SpindleSpeed, tc.HorizFeed, tc.VertFeed = 20000, 150, 40
    job.Proxy.addToolController(tc)
    d.recompute()
    for o in (job, tc):                                     # paths live in the turned setup frame:
        if o.ViewObject:                                    # view them in cam_sim(), not in the model
            o.ViewObject.Visibility = False
    idx = '' if azimuth is None else f' index {_cnc_f(azimuth):.2f}°'
    return f'cam_job: OK {job.Name}{idx} Ø{dia:g}'


def cam_slot(job, p1, p2, depth, name=None):
    """Slot op of the Job's cutter from p1 to p2 (points on the top surface, PART coordinates),
    down depth along the tool axis. Full-round ends of the cutter radius."""
    import Path.Op.Slot as PathSlot
    d = _doc()
    job = _obj(job)
    pl = job.Model.Group[0].Placement
    a, b = pl.multVec(V(*p1)), pl.multVec(V(*p2))
    top = max(a.z, b.z)
    op = PathSlot.Create(name or 'Slot', parentJob=job)
    if App.GuiUp and op.ViewObject:
        import Path.Op.Gui.Base as PathOpGui
        import Path.Op.Gui.Slot as PathSlotGui
        op.ViewObject.Proxy = PathOpGui.ViewProvider(op.ViewObject, PathSlotGui.Command.res)
    op.ToolController = job.Tools.Group[0]
    for p in ('StartDepth', 'FinalDepth', 'StepDown', 'SafeHeight', 'ClearanceHeight'):
        op.setExpression(p, None)
    op.CustomPoint1, op.CustomPoint2 = V(a.x, a.y, top), V(b.x, b.y, top)
    op.StartDepth, op.FinalDepth, op.StepDown = top, top - _cnc_f(depth), 0.25
    op.SafeHeight, op.ClearanceHeight = top + 1, top + 3
    d.recompute()
    if op.ViewObject:
        op.ViewObject.Visibility = False
    n = len([c for c in op.Path.Commands if c.Name in ('G1', 'G2', 'G3')])
    if not n:
        raise FdmkitError(f'{op.Name}: no path')
    return f'cam_slot: OK {op.Name} {n} cuts, Z {top:.2f}→{top - _cnc_f(depth):.2f} in {job.Name}'


def cam_sim(job):
    """Open CAM_SimulatorGL on the Job and press Play (the simulator tab shows stock, cutter, model)."""
    import Path.Main.Gui.SimulatorGL as SimGL
    job = _obj(job)
    sim = SimGL.CAMSimulation()
    sim.Activate()
    sim.taskForm.form.comboJobs.setCurrentIndex([j.Name for j in sim.jobs].index(job.Name))
    sim.onJobChange()
    sim.SimPlay()
    App._fdmkit_cam_sim = sim
    return f'cam_sim: {job.Name} playing ({len(sim.activeOps)} ops); close the task panel when done'


def cam_del(job):
    """Delete a Job with CAM's own teardown (ops, stock, model clones, tools; expressions first)."""
    job = _obj(job)
    d = job.Document
    name = job.Name
    job.Proxy.onDelete(job)
    d.removeObject(name)
    return f'cam_del: {name}'

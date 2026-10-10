"""fdmkit: lean parametric PartDesign helpers for FDM (FreeCAD 26.3).

Entry point is run(expr): one call = one transaction, result = one line.
Lengths and angles take a number or an expression; bare names of params
aliases are rewritten to params.<name>. Every sketch helper adds its own
constraints and fails (rolling back) unless the sketch ends at DoF 0.
"""
import ast
import math
import re
import time

import FreeCAD as App
import Part
import Sketcher

__version__ = '0.2.0'
__all__ = ['new', 'P', 'plane', 'sk', 'rect', 'circ', 'slot', 'poly', 'fil',
           'half', 'pad', 'pocket', 'hole', 'revolve', 'groove', 'polar', 'mirror', 'move',
           'dim', 'chk', 'why', 'tree',
           'undo', 'selftest']

V = App.Vector
C = Sketcher.Constraint
PARAMS = 'params'
_PREF = 'User parameter:BaseApp/Preferences/Mod/fdmkit'
_ORIGIN = {'XY': 'XY_Plane', 'XZ': 'XZ_Plane', 'YZ': 'YZ_Plane',
           'X': 'X_Axis', 'Y': 'Y_Axis', 'Z': 'Z_Axis'}
_POS = {0: 'edge', 1: 'start', 2: 'end', 3: 'center'}
_ID = re.compile(r'(?<![\w.<])([A-Za-z_]\w*)')


class FdmkitError(Exception):
    pass


# ---------------------------------------------------------------- context
def _doc():
    d = App.ActiveDocument
    if d is None:
        raise FdmkitError('no document; new(name)')
    return d


def _body(d=None):
    d = d or _doc()
    if App.GuiUp:
        import FreeCADGui as Gui
        try:
            b = Gui.getDocument(d.Name).ActiveView.getActiveObject('pdbody')
            if b:
                return b
        except Exception:
            pass
    bodies = [o for o in d.Objects if o.TypeId == 'PartDesign::Body']
    if not bodies:
        raise FdmkitError('no Body; new(name)')
    return bodies[-1]


def _obj(x):
    if not isinstance(x, str):
        return x
    d = _doc()
    o = d.getObject(x) or next(iter(d.getObjectsByLabel(x)), None)
    if o is None:
        raise FdmkitError(f'{x}: not found')
    return o


def _free(name):
    d = _doc()
    if not re.fullmatch(r'[A-Za-z_]\w*', name):
        raise FdmkitError(f'{name}: not an identifier')
    if d.getObject(name) or d.getObjectsByLabel(name):
        raise FdmkitError(f'{name}: exists')


def _bad(o):
    return 'Invalid' in o.State or 'Error' in o.State


def _origin(b, key):
    role = _ORIGIN[key]
    return next(f for f in b.Origin.OriginFeatures if f.Role == role)


# ---------------------------------------------------------------- params
def _sheet(create=True, d=None):
    """The params sheet: Name or Label 'params' in any case ('Params' in older files)."""
    d = d or _doc()
    s = d.getObject(PARAMS) or next(
        (o for o in d.Objects if o.TypeId == 'Spreadsheet::Sheet'
         and PARAMS in (o.Name.lower(), o.Label.lower())), None)
    if s is None and create:
        s = d.addObject('Spreadsheet::Sheet', PARAMS)
    return s


def _aliases(s):
    out = {}
    for c in s.getUsedCells():
        a = s.getAlias(c)
        if a:
            out[a] = c
    return out


def _expr(v):
    """Expression text for v with param aliases qualified as params.<name>."""
    d = App.ActiveDocument
    s = d and _sheet(False, d)
    names = set(_aliases(s)) if s else set()
    return _ID.sub(lambda m: f'{s.Name}.{m[1]}' if m[1] in names else m[1], str(v))


def _val(o, v):
    if isinstance(v, (int, float)):
        return float(v)
    q = o.evalExpression(_expr(v))
    return float(getattr(q, 'Value', q))


def _num(v):
    return '%g' % round(float(getattr(v, 'Value', v)), 6)


def _cell(v):
    # en_DK uses a decimal comma, so numbers go in as formulas
    if isinstance(v, (int, float)):
        return f'={v!r}'
    v = str(v).strip()
    return v if v.startswith('=') else '=' + v


def P(*names, **values):
    """P(wall=1.2, h2='wall*2') sets; P() lists; P('wall') reads."""
    s = _sheet()
    al = _aliases(s)
    for k, v in values.items():
        cell = al.get(k)
        if cell is None:
            row = 1 + max([int(re.sub('[A-Z]+', '', c)) for c in s.getUsedCells()] or [0])
            cell = f'B{row}'
            s.set(f'A{row}', k)
            s.set(cell, _cell(v))
            try:
                s.setAlias(cell, k)
            except Exception:
                s.clear(f'A{row}')
                s.clear(cell)
                raise FdmkitError(f"P: '{k}' rejected by FreeCAD (unit token or invalid)")
            al[k] = cell
        else:
            s.set(cell, _cell(v))
    if values:
        d = _doc()
        d.recompute()
        bad = [o for o in d.Objects if _bad(o)]
        if bad:
            raise FdmkitError('P: ' + '; '.join(f'{o.Name}: {o.getStatusString()}' for o in bad))
    keys = names or (values.keys() if values else al.keys())
    return 'P: ' + ' '.join(f'{k}={_num(s.get(k))}' for k in keys)


class _SheetObserver:
    """Work around 26.3dev: changing an aliased cell does not touch dependents."""

    def slotChangedObject(self, obj, prop):
        try:
            if obj.TypeId != 'Spreadsheet::Sheet' or obj.Document.Restoring:
                return
            for o in obj.InList:
                if 'Touched' not in o.State:
                    o.touch()
        except Exception:
            pass


# ---------------------------------------------------------------- document
def _init(d):
    d.UndoMode = 1
    d.addObject('Spreadsheet::Sheet', PARAMS)
    b = d.addObject('PartDesign::Body', 'Body')
    d.recompute()
    return b


def new(name='Part', hidden=False):
    d = App.newDocument(name, name, hidden)
    b = _init(d)
    if App.GuiUp and not hidden:
        import FreeCADGui as Gui
        try:
            Gui.getDocument(d.Name).ActiveView.setActiveObject('pdbody', b)
        except Exception:
            pass
    return f'{d.Name}: OK'


def plane(name, base='XY', offset=0):
    """Datum plane parallel to an origin plane or another datum plane."""
    _free(name)
    b = _body()
    if base in _ORIGIN:
        ref = _origin(b, base)
    else:
        ref = _obj(base)
        if ref.TypeId not in ('PartDesign::Plane', 'App::Plane'):
            raise FdmkitError(f'plane: {base} is not a plane')
    pl = b.newObject('PartDesign::Plane', name)
    pl.AttachmentSupport = [(ref, '')]
    pl.MapMode = 'FlatFace'
    pl.AttachmentOffset = App.Placement(V(0, 0, _val(pl, offset)), App.Rotation())
    if isinstance(offset, str):
        pl.setExpression('.AttachmentOffset.Base.z', _expr(offset))
    pl.Document.recompute()
    if _bad(pl):
        raise FdmkitError(f'{name}: {pl.getStatusString()}')
    return f'{name}: OK z {_num(pl.Placement.Base.z)}'


def sk(name, on='XY'):
    """Sketch on an origin plane or a datum plane (never on a face)."""
    _free(name)
    b = _body()
    ref = _origin(b, on) if on in _ORIGIN else _obj(on)
    if ref.TypeId not in ('PartDesign::Plane', 'App::Plane'):
        raise FdmkitError(f'sk: {on} is not a plane')
    s = b.newObject('Sketcher::SketchObject', name)
    s.AttachmentSupport = [(ref, '')]
    s.MapMode = 'FlatFace'
    s.Document.recompute()
    return f'{name}: OK on {on}'


# ---------------------------------------------------------------- sketch
def _sk(x):
    s = _obj(x)
    if s.TypeId != 'Sketcher::SketchObject':
        raise FdmkitError(f'{s.Name}: not a sketch')
    return s


def _auto(s, prefix, name):
    used = {c.Name for c in s.Constraints if c.Name}
    if name:
        if any(u.startswith(name + '_') for u in used):
            raise FdmkitError(f'{name}: name used in {s.Name}')
        return name
    i = 1
    while any(u.startswith(f'{prefix}{i}_') for u in used):
        i += 1
    return f'{prefix}{i}'


def _dim(s, cons, name, v):
    i = s.addConstraint(cons)
    s.renameConstraint(i, name)
    if isinstance(v, str):
        s.setExpression('Constraints.' + name, _expr(v))


def _zero(v):
    return isinstance(v, (int, float)) and v == 0


def _place(s, geo, pos, x, y, name):
    for v, axis, kind, suffix in ((x, -2, 'DistanceX', 'x'), (y, -1, 'DistanceY', 'y')):
        if _zero(v):
            s.addConstraint(C('PointOnObject', geo, pos, axis))
        else:
            _dim(s, C(kind, -1, 1, geo, pos, _val(s, v)), f'{name}_{suffix}', v)


def _cname(s, i1):
    c = s.Constraints[i1 - 1]  # solver lists are 1-based
    return f'{c.Name or "c%d" % (i1 - 1)}({c.Type})'


def _sk_issue(s):
    s.solve()
    out = []
    for attr, tag in (('ConflictingConstraints', 'conflict'), ('RedundantConstraints', 'redundant'),
                      ('PartiallyRedundantConstraints', 'partial'), ('MalformedConstraints', 'malformed')):
        ids = list(getattr(s, attr, None) or [])
        if ids:
            out.append(tag + ' ' + ','.join(_cname(s, i) for i in ids))
    if s.DoF:
        free = dict.fromkeys(f'g{g}.{_POS.get(p, p)}' for g, p in s.getGeometryWithDependentParameters())
        out.append(f'DoF {s.DoF} free ' + ' '.join(free))
    if _bad(s):
        out.append(s.getStatusString())
    return '; '.join(out)


def _sk_clash(s):
    """Conflicting, redundant or malformed constraints after a solve."""
    return any(getattr(s, a, None) for a in ('ConflictingConstraints', 'RedundantConstraints',
                                              'PartiallyRedundantConstraints', 'MalformedConstraints'))


def _sk_done(s, label):
    s.Document.recompute()
    err = _sk_issue(s)
    if err:
        raise FdmkitError(f'{s.Name}.{label}: {err}')
    return f'{s.Name}.{label}: DoF 0'


def rect(sketch, w, h, x=0, y=0, at='c', name=None):
    """Rectangle w x h; (x, y) is its centre (at='c') or bottom-left corner (at='bl')."""
    s = _sk(sketch)
    n = _auto(s, 'r', name)
    W, H, X, Y = (_val(s, v) for v in (w, h, x, y))
    x0, y0 = (X - W / 2, Y - H / 2) if at == 'c' else (X, Y)
    p = [V(x0, y0, 0), V(x0 + W, y0, 0), V(x0 + W, y0 + H, 0), V(x0, y0 + H, 0)]
    g = [s.addGeometry(Part.LineSegment(p[i], p[(i + 1) % 4])) for i in range(4)]
    s.addConstraint([C('Coincident', g[i], 2, g[(i + 1) % 4], 1) for i in range(4)]
                    + [C('Horizontal', g[0]), C('Horizontal', g[2]),
                       C('Vertical', g[1]), C('Vertical', g[3])])
    _dim(s, C('DistanceX', g[0], 1, g[0], 2, W), n + '_w', w)
    _dim(s, C('DistanceY', g[1], 1, g[1], 2, H), n + '_h', h)
    if at == 'c':
        cp = s.addGeometry(Part.Point(V(X, Y, 0)), True)
        s.addConstraint(C('Symmetric', g[0], 1, g[2], 1, cp, 1))
        _place(s, cp, 1, x, y, n)
    else:
        _place(s, g[0], 1, x, y, n)
    return _sk_done(s, n)


def circ(sketch, d, x=0, y=0, name=None):
    s = _sk(sketch)
    n = _auto(s, 'c', name)
    g = s.addGeometry(Part.Circle(V(_val(s, x), _val(s, y), 0), V(0, 0, 1), _val(s, d) / 2))
    _dim(s, C('Diameter', g, _val(s, d)), n + '_d', d)
    _place(s, g, 3, x, y, n)
    return _sk_done(s, n)


def slot(sketch, length, width, x=0, y=0, angle=0, name=None):
    """Slot with overall length and width, centred at (x, y), angle in degrees."""
    s = _sk(sketch)
    n = _auto(s, 's', name)
    L, W, X, Y, A = (_val(s, v) for v in (length, width, x, y, angle))
    t = math.radians(A)
    u = V(math.cos(t), math.sin(t), 0)
    c1, c2 = V(X, Y, 0) - u * ((L - W) / 2), V(X, Y, 0) + u * ((L - W) / 2)
    z = V(0, 0, 1)
    a1 = s.addGeometry(Part.ArcOfCircle(Part.Circle(c1, z, W / 2), t + math.pi / 2, t + 3 * math.pi / 2))
    a2 = s.addGeometry(Part.ArcOfCircle(Part.Circle(c2, z, W / 2), t - math.pi / 2, t + math.pi / 2))
    l1 = s.addGeometry(Part.LineSegment(s.Geometry[a1].EndPoint, s.Geometry[a2].StartPoint))
    l2 = s.addGeometry(Part.LineSegment(s.Geometry[a2].EndPoint, s.Geometry[a1].StartPoint))
    cp = s.addGeometry(Part.Point(V(X, Y, 0)), True)
    s.addConstraint([C('Tangent', a1, 2, l1, 1), C('Tangent', l1, 2, a2, 1),
                     C('Tangent', a2, 2, l2, 1), C('Tangent', l2, 2, a1, 1),
                     C('Equal', a1, a2), C('Symmetric', a1, 3, a2, 3, cp, 1)])
    _dim(s, C('Diameter', a1, W), n + '_w', width)
    span = L - W if not isinstance(length, str) and not isinstance(width, str) \
        else f'({length}) - ({width})'
    _dim(s, C('Distance', a1, 3, a2, 3, L - W), n + '_l', span)
    if _zero(angle):
        s.addConstraint(C('Horizontal', l1))
    else:
        _dim(s, C('Angle', l1, t), n + '_a', f'({angle}) * 1 deg' if isinstance(angle, str) else angle)
    _place(s, cp, 1, x, y, n)
    return _sk_done(s, n)


def poly(sketch, pts, name=None):
    """Closed polygon; every vertex is dimensioned from the sketch origin."""
    s = _sk(sketch)
    n = _auto(s, 'p', name)
    vs = [V(_val(s, a), _val(s, b), 0) for a, b in pts]
    k = len(vs)
    g = [s.addGeometry(Part.LineSegment(vs[i], vs[(i + 1) % k])) for i in range(k)]
    s.addConstraint([C('Coincident', g[i], 2, g[(i + 1) % k], 1) for i in range(k)])
    for i, (a, b) in enumerate(pts):
        _place(s, g[i], 1, a, b, f'{n}_{i}')
    return _sk_done(s, n)


def fil(sketch, at, r, name=None):
    """Sketch fillet of radius r at the line corner nearest to point at=(x, y)."""
    s = _sk(sketch)
    n = _auto(s, 'f', name)
    px, py = (_val(s, v) for v in at)
    best = None
    for gi, g in enumerate(s.Geometry):
        if s.getConstruction(gi) or not isinstance(g, Part.LineSegment):
            continue
        for pos, pt in ((1, g.StartPoint), (2, g.EndPoint)):
            dd = (pt.x - px) ** 2 + (pt.y - py) ** 2
            if best is None or dd < best[0]:
                best = (dd, gi, pos)
    if best is None or best[0] > 1e-4:
        raise FdmkitError(f'fil: no corner at {at}')
    n0 = s.GeometryCount
    s.fillet(best[1], best[2], _val(s, r), True, True)
    arc = next(i for i in range(n0, s.GeometryCount) if isinstance(s.Geometry[i], Part.ArcOfCircle))
    _dim(s, C('Radius', arc, _val(s, r)), n + '_r', r)
    return _sk_done(s, n)


def dim(sketch, cname, value):
    """Change a named constraint: number = fixed value, string = expression."""
    s = _sk(sketch)
    i = next((i for i, c in enumerate(s.Constraints) if c.Name == cname), None)
    if i is None:
        raise FdmkitError(f'{s.Name}: no constraint {cname}')
    if isinstance(value, str):
        s.setExpression('Constraints.' + cname, _expr(value))
    else:
        s.setExpression('Constraints.' + cname, None)
        s.setDatum(i, float(value))
    s.Document.recompute()
    r = chk()
    if r.startswith('ERR'):
        raise FdmkitError(r[4:])
    return f'{s.Name}.{cname}: ' + r


_EPS = 1e-6


def _ends(g):
    """{pos: point} of the endpoints (1, 2) and centre (3) of a sketch geometry."""
    if isinstance(g, Part.Point):
        return {1: V(g.X, g.Y, 0)}
    out = {}
    if hasattr(g, 'StartPoint'):
        out[1], out[2] = g.StartPoint, g.EndPoint
    if hasattr(g, 'Center'):
        out[3] = g.Center
    return out


def _side(g):
    """-1 below the H axis, 1 above or on it, 0 crossing it (endpoints on both sides)."""
    e = _ends(g)
    if isinstance(g, Part.Circle):
        c, r = g.Center.y, g.Radius
        return 0 if abs(c) < r - _EPS else (-1 if c < 0 else 1)
    ys = [e[p].y for p in (1, 2) if p in e] or [e[1].y]
    if min(ys) < -_EPS and max(ys) > _EPS:
        return 0
    return -1 if max(ys) < -_EPS else 1


def _axis_cut(g):
    """Point where a crossing line or arc meets y = 0."""
    if isinstance(g, Part.LineSegment):
        a, b = g.StartPoint, g.EndPoint
        t = a.y / (a.y - b.y)
        return V(a.x + t * (b.x - a.x), 0, 0)
    c, r = g.Center, g.Radius
    a0 = math.asin(max(-1.0, min(1.0, -c.y / r)))
    for a in (a0, math.pi - a0, a0 + 2 * math.pi, math.pi - a0 + 2 * math.pi, a0 - 2 * math.pi):
        if g.FirstParameter - _EPS <= a <= g.LastParameter + _EPS:
            return V(c.x + r * math.cos(a), 0, 0)
    raise FdmkitError('half: arc does not cross the axis')


def _find_geo(s, kind, pts, r=None):
    """Index of a non-deleted geometry of this kind whose key points equal pts (any order)."""
    for i, g in enumerate(s.Geometry):
        if type(g).__name__ != kind or (r is not None and abs(getattr(g, 'Radius', 0) - r) > 1e-6):
            continue
        e = _ends(g)
        if len(e) == len(pts) and all(any((e[p] - q).Length < 1e-6 for p in e) for q in pts.values()):
            return i
    return None


def half(sketch):
    """Cut a sketch that is symmetric about its H axis down to the y >= 0 half, in place.
    Kept geometry keeps its index, names and expressions; the cut is closed along the axis.
    Lost dimensions are restored from their mirror images, and the sketch must end at DoF 0."""
    s = _sk(sketch)
    face = lambda: Part.makeFace(s.Shape, 'Part::FaceMakerBullseye').Area
    area0 = face()
    geo = list(s.Geometry)
    side = {i: _side(g) for i, g in enumerate(geo)}
    low = [i for i, k in side.items() if k < 0]
    cross = [i for i, k in side.items() if k == 0]
    if not low:
        raise FdmkitError(f'{s.Name}: nothing below the H axis')
    exprs = {p[len('.Constraints.'):]: e for p, e in s.ExpressionEngine if p.startswith('.Constraints.')}
    # mirror image (above the axis) of every geometry below it, by key points
    mirror = {}
    for i in low:
        g = geo[i]
        pts = {p: V(q.x, -q.y, 0) for p, q in _ends(g).items()}
        mirror[i] = (type(g).__name__, pts, getattr(g, 'Radius', None))
    lost = []
    for c in s.Constraints:
        refs = [(c.First, c.FirstPos), (c.Second, c.SecondPos), (c.Third, c.ThirdPos)]
        if any(gi in mirror for gi, _ in refs):
            lost.append((c, refs, exprs.get(c.Name)))
    # crossing geometry: drop what holds its lower end (except x), then pull that end onto the axis
    ends = []
    crossing_dims = []
    for i in cross:
        g = geo[i]
        pos = 1 if g.StartPoint.y < 0 else 2
        cut = _axis_cut(g)
        drop = []
        for ci, c in enumerate(s.Constraints):
            on = (c.First, c.FirstPos) == (i, pos) or (c.Second, c.SecondPos) == (i, pos)
            if on and not (c.Type == 'DistanceX' and c.First == -1):
                if (c.Type in ('DistanceY', 'Distance') and c.First == i and c.Second == i
                        and {c.FirstPos, c.SecondPos} == {1, 2}
                        and abs(g.StartPoint.y + g.EndPoint.y) < _EPS):
                    crossing_dims.append((i, c.Type, c.FirstPos, c.SecondPos,
                                          c.Value, c.Name, exprs.get(c.Name)))
                drop.append(ci)
        for ci in sorted(drop, reverse=True):
            n = s.Constraints[ci].Name
            if n:
                s.setExpression('Constraints.' + n, None)
            s.delConstraint(ci)
        ends.append((i, pos, cut))
    for c, refs, e in lost:
        if c.Name and e:
            s.setExpression('Constraints.' + c.Name, None)
    keep = {i: (type(geo[i]).__name__, _ends(geo[i]), getattr(geo[i], 'Radius', None)) for i in cross}
    s.delGeometries(sorted(low))
    new = {}
    for i, (kind, pts, r) in keep.items():
        new[i] = _find_geo(s, kind, pts, r)
    pts_on = []
    for i, pos, cut in ends:
        gi = new[i]
        s.addConstraint(C('PointOnObject', gi, pos, -1))
        pts_on.append((cut.x, gi, pos))
    pts_on.sort()
    if len(pts_on) % 2:
        raise FdmkitError(f'{s.Name}: odd number of axis cuts')
    pairs = list(zip(pts_on[::2], pts_on[1::2]))
    for (xa, ga, pa), (xb, gb, pb) in pairs:
        ln = s.addGeometry(Part.LineSegment(V(xa, 0, 0), V(xb, 0, 0)))
        s.addConstraint([C('Coincident', ln, 1, ga, pa), C('Coincident', ln, 2, gb, pb)])
    # restore dimensions that only the lower half carried, on their mirror images
    s.solve()
    for i, _, _ in ends:
        g = geo[i]  # direction from the uncut geometry: the solver may have tilted it
        if not s.DoF or not isinstance(g, Part.LineSegment):
            continue
        d = g.EndPoint - g.StartPoint
        kind = 'Vertical' if abs(d.x) < _EPS else 'Horizontal' if abs(d.y) < _EPS else None
        if kind:
            dof = s.DoF
            k = s.addConstraint(C(kind, new[i]))
            s.solve()
            if s.DoF >= dof or _sk_clash(s):
                s.delConstraint(k)
                s.solve()
    for c, refs, e in lost:
        if not s.DoF:
            break
        if c.Type not in ('Radius', 'Diameter', 'DistanceX', 'DistanceY', 'Distance', 'Equal'):
            continue
        args = []
        if c.Type == 'Equal' and c.First in mirror and c.Second in mirror:
            continue
        for gi, pos in refs:
            if gi is None or gi == -2000:
                continue
            if gi in mirror:
                kind, pts, r = mirror[gi]
                ni = _find_geo(s, kind, pts, r)
                if ni is None:
                    break
                if pos in (1, 2):
                    q = pts[pos]
                    e2 = _ends(s.Geometry[ni])
                    pos = next(p for p in e2 if p != 3 and (e2[p] - q).Length < 1e-6)
                args.append((ni, pos))
            else:
                args.append((gi - sum(1 for j in low if j < gi) if gi >= 0 else gi, pos))
        else:
            sign = -1 if c.Type == 'DistanceY' else 1
            flat = [x for a in args for x in a]
            if c.Type in ('Radius', 'Diameter'):
                cons = C(c.Type, flat[0], c.Value)
            elif c.Type == 'Equal':
                cons = C('Equal', flat[0], flat[2])
            else:
                cons = C(c.Type, *flat, sign * c.Value)
            dof = s.DoF
            k = s.addConstraint(cons)
            s.solve()
            if s.DoF >= dof or _sk_clash(s):
                s.delConstraint(k)
                s.solve()
                continue
            if c.Name:
                s.renameConstraint(k, c.Name)
                if e:
                    s.setExpression('Constraints.' + c.Name, e if sign > 0 else f'-({e})')
    for old, kind, p1, p2, value, cname, e in crossing_dims:
        if not s.DoF:
            break
        dof = s.DoF
        k = s.addConstraint(C(kind, new[old], p1, new[old], p2, value / 2))
        s.solve()
        if s.DoF >= dof or _sk_clash(s):
            s.delConstraint(k)
            s.solve()
            continue
        if cname:
            s.renameConstraint(k, cname)
            if e:
                s.setExpression('Constraints.' + cname, f'({e}) / 2')
    for (xa, ga, pa), (xb, gb, pb) in pairs:
        if not s.DoF:
            break
        for ci, g in enumerate(s.Geometry):
            if not isinstance(g, Part.Point) or not s.getConstruction(ci):
                continue
            if abs(g.X - (xa + xb) / 2) > _EPS or abs(g.Y) > _EPS:
                continue
            dof = s.DoF
            k = s.addConstraint(C('DistanceX', ci, 1, gb, pb, xb - g.X))
            s.solve()
            if s.DoF >= dof or _sk_clash(s):
                s.delConstraint(k)
                s.solve()
            else:
                cname = f'half_{len(s.Constraints)}_center'
                s.renameConstraint(k, cname)
                widths = [c for c in s.Constraints if c.Type == 'DistanceX' and c.Name
                          and abs(abs(c.Value) - (xb - xa)) < _EPS]
                if widths:
                    s.setExpression('Constraints.' + cname,
                                    f'Constraints.{widths[0].Name} / 2')
                break
    r = _sk_done(s, 'half')
    area1 = face()
    if abs(2 * area1 - area0) > 1e-3 * area0:
        raise FdmkitError(f'{s.Name}: half area {area1:.2f} != {area0:.2f} / 2')
    return r + f', area {area0:.1f} -> {area1:.1f}'


# ---------------------------------------------------------------- features
def _shape(sh):
    bb = sh.BoundBox
    return f'V {sh.Volume:.1f} bb {bb.XLength:.1f}x{bb.YLength:.1f}x{bb.ZLength:.1f}'


def _setq(o, prop, v):
    if isinstance(v, str):
        o.setExpression(prop, _expr(v))
    else:
        setattr(o, prop, v)


def _feature(kind, name, sketch):
    if name:
        _free(name)
    s = _sk(sketch)
    f = _body().newObject(kind, name or kind.split('::')[1].lower())
    f.Profile = s
    return f, s


def _finish(f, s):
    prev = f.BaseFeature
    f.Document.recompute()
    bad = [o for o in (s, f) if _bad(o)]
    if bad:
        raise FdmkitError('; '.join(f'{o.Name}: {o.getStatusString()}' for o in bad))
    if not f.Shape.isValid() or len(f.Shape.Solids) != 1:
        raise FdmkitError(f'{f.Name}: solids {len(f.Shape.Solids)}')
    s.Visibility = False
    if prev:
        prev.Visibility = False
    return f'{f.Name}: OK ' + _shape(f.Shape)


_SIDES = {'one': 'One side', 'two': 'Two sides', 'sym': 'Symmetric'}
_STARTS = {'profile': 'Profile plane', 'offset': 'Offset', 'reference': 'Reference'}
_OPERATIONS = {'subtract': 'Subtraction', 'common': 'Common'}


def _need(o, *props):
    missing = [p for p in props if p not in o.PropertiesList]
    if missing:
        raise FdmkitError(f'{o.TypeId}: unavailable properties {", ".join(missing)}')


def _set_start(f, start, offset, reference):
    if start not in _STARTS:
        raise FdmkitError(f"start: expected {', '.join(_STARTS)}")
    if start == 'profile':
        if offset != 0 or reference is not None:
            raise FdmkitError('start=profile takes no offset or reference')
        return
    _need(f, 'StartType')
    if _STARTS[start] not in f.getEnumerationsOfProperty('StartType'):
        raise FdmkitError(f'{f.TypeId}: start={start} unavailable')
    if start == 'offset':
        if reference is not None:
            raise FdmkitError('start=offset takes no reference')
        _need(f, 'StartOffset')
        _setq(f, 'StartOffset', offset)
    else:
        if reference is None or offset != 0:
            raise FdmkitError('start=reference needs a plane and no offset')
        ref = _origin(_body(), reference) if reference in _ORIGIN else _obj(reference)
        if ref.TypeId not in ('PartDesign::Plane', 'App::Plane'):
            raise FdmkitError(f'{reference}: not a plane')
        _need(f, 'StartReference')
        f.StartReference = (ref, [''])
    f.StartType = _STARTS[start]


def _set_operation(f, operation):
    if operation not in _OPERATIONS:
        raise FdmkitError('operation: expected subtract or common')
    _need(f, 'Operation')
    value = _OPERATIONS[operation]
    if value not in f.getEnumerationsOfProperty('Operation'):
        raise FdmkitError(f'{f.TypeId}: operation={operation} unavailable')
    f.Operation = value


def pad(sketch, length, name=None, side='one', reverse=False,
        start='profile', offset=0, reference=None):
    f, s = _feature('PartDesign::Pad', name, sketch)
    _setq(f, 'Length', length)
    f.SideType = _SIDES[side]
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    return _finish(f, s)


def pocket(sketch, depth='through', name=None, side='one', reverse=False,
           start='profile', offset=0, reference=None, operation='subtract'):
    f, s = _feature('PartDesign::Pocket', name, sketch)
    if depth == 'through':
        f.Type = 'ThroughAll'
    else:
        _setq(f, 'Length', depth)
    f.SideType = _SIDES[side]
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    _set_operation(f, operation)
    return _finish(f, s)


def hole(sketch, diameter, depth='through', name=None, start='profile',
         offset=0, reference=None, thread_type=None, thread_size=None,
         model_thread=False, cosmetic_thread=True, operation='subtract'):
    """PartDesign Hole on fully constrained circle centres; cosmetic thread is metadata."""
    f, s = _feature('PartDesign::Hole', name, sketch)
    f.Document.recompute()  # Hole populates its dynamic properties after a base recompute.
    _setq(f, 'Diameter', diameter)
    if depth == 'through':
        f.DepthType = 'ThroughAll'
    else:
        f.DepthType = 'Dimension'
        _setq(f, 'Depth', depth)
    _set_start(f, start, offset, reference)
    _set_operation(f, operation)
    if thread_type is not None:
        if thread_type not in f.getEnumerationsOfProperty('ThreadType'):
            raise FdmkitError(f'hole: thread type {thread_type} unavailable')
        f.Threaded = True
        f.ThreadType = thread_type
        if thread_size is not None:
            if thread_size not in f.getEnumerationsOfProperty('ThreadSize'):
                raise FdmkitError(f'hole: thread size {thread_size} unavailable')
            f.ThreadSize = thread_size
        f.ModelThread = bool(model_thread)
        f.CosmeticThread = bool(cosmetic_thread)
    elif thread_size is not None or model_thread:
        raise FdmkitError('hole: thread_type required for thread_size or model_thread')
    return _finish(f, s)


def _rotation(sketch, kind, angle, axis, name, side, reverse,
              start, offset, reference, project_axis, operation=None):
    if axis not in ('V_Axis', 'H_Axis', 'X', 'Y', 'Z'):
        raise FdmkitError('axis: expected V_Axis, H_Axis, X, Y or Z')
    f, s = _feature(kind, name, sketch)
    f.ReferenceAxis = (s, [axis]) if axis in ('V_Axis', 'H_Axis') else (_origin(_body(), axis), [''])
    _setq(f, 'Angle', angle)
    f.SideType = _SIDES[side]
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    if project_axis:
        _need(f, 'ProjectAxis')
        f.ProjectAxis = True
    if operation is not None:
        _set_operation(f, operation)
    return _finish(f, s)


def revolve(sketch, angle=360, axis='V_Axis', name=None, side='one',
            reverse=False, start='profile', offset=0, reference=None,
            project_axis=False):
    """axis: sketch 'V_Axis'/'H_Axis' or body origin 'X'/'Y'/'Z'."""
    return _rotation(sketch, 'PartDesign::Revolution', angle, axis, name, side,
                     reverse, start, offset, reference, project_axis)


def groove(sketch, angle=360, axis='V_Axis', name=None, side='one',
           reverse=False, start='profile', offset=0, reference=None,
           project_axis=False, operation='subtract'):
    """Subtractive rotational feature, optionally using 26.3 Common mode."""
    return _rotation(sketch, 'PartDesign::Groove', angle, axis, name, side,
                     reverse, start, offset, reference, project_axis, operation)


def _solid_tail(b):
    """Last solid feature of the body (a Tip candidate)."""
    return [o for o in b.Group if o.isDerivedFrom('PartDesign::Feature')][-1]


def polar(features, occurrences, axis='Z', angle=360, suppressed=(), name=None):
    """PartDesign PolarPattern; suppressed uses zero-based instance indices."""
    b = _body()
    fs = [_obj(x) for x in ([features] if isinstance(features, str) else features)]
    if not fs or any(f not in b.Group or not f.isDerivedFrom('PartDesign::Feature') for f in fs):
        raise FdmkitError('polar: originals must be features in the active Body')
    if axis not in ('X', 'Y', 'Z'):
        raise FdmkitError('polar: axis must be X, Y or Z')
    if not isinstance(occurrences, int) or occurrences < 2:
        raise FdmkitError('polar: occurrences must be an integer >= 2')
    if any(not isinstance(i, int) or i < 0 or i >= occurrences for i in suppressed):
        raise FdmkitError('polar: suppressed indices must be 0..occurrences-1')
    if name:
        _free(name)
    f = b.newObject('PartDesign::PolarPattern', name or 'polar')
    f.Originals = fs
    f.Axis = (_origin(b, axis), [''])
    f.Occurrences = occurrences
    _setq(f, 'Angle', angle)
    if suppressed:
        _need(f, 'SuppressedIndices')
        f.SuppressedIndices = sorted(set(suppressed))
    f.Document.recompute()
    if _bad(f) or f.Shape.isNull() or not f.Shape.isValid() or len(f.Shape.Solids) != 1:
        raise FdmkitError(f'{f.Name}: {f.getStatusString()} solids {len(f.Shape.Solids)}')
    for o in fs:
        o.Visibility = False
    return f'{f.Name}: OK ' + _shape(f.Shape)


def move(feature, after):
    """Move a feature or sketch to just after another one in the active body."""
    b = _body()
    f, t = _obj(feature), _obj(after)
    tip_last = b.Tip == _solid_tail(b)
    b.removeObject(f)
    b.insertObject(f, t, True)
    if tip_last:
        b.Tip = _solid_tail(b)
    f.Document.recompute()
    bad = [o for o in b.Group if _bad(o)]
    if bad:
        raise FdmkitError('move: ' + '; '.join(f'{o.Name}: {o.getStatusString()}' for o in bad))
    return f'{f.Name}: after {t.Name}'


def mirror(features, plane='XY', name=None):
    """PartDesign::Mirrored of features (a name or a list) about a body origin plane or datum,
    placed after the last of them."""
    b = _body()
    fs = [_obj(x) for x in ([features] if isinstance(features, str) else features)]
    if name:
        _free(name)
    ref = _origin(b, plane) if plane in _ORIGIN else _obj(plane)
    m = b.newObject('PartDesign::Mirrored', name or 'Mirrored')
    m.Originals = fs
    m.MirrorPlane = (ref, [''])
    last = max(fs, key=b.Group.index)
    if b.Group.index(m) != b.Group.index(last) + 1:
        tip_last = b.Tip == m
        b.removeObject(m)
        b.insertObject(m, last, True)
        b.Tip = _solid_tail(b) if tip_last else b.Tip
    m.Document.recompute()
    if _bad(m) or not m.Shape.isValid() or len(m.Shape.Solids) != 1:
        raise FdmkitError(f'{m.Name}: {m.getStatusString()} solids {len(m.Shape.Solids)}')
    return f'{m.Name}: OK ' + _shape(m.Shape)


# ---------------------------------------------------------------- inspect
def chk():
    """Whole active body: sketches at DoF 0, features valid, one valid solid."""
    b = _body()
    issues = []
    for o in b.Group:
        if o.TypeId == 'Sketcher::SketchObject':
            e = _sk_issue(o)
            if e:
                issues.append(f'{o.Name}: {e}')
        elif _bad(o):
            issues.append(f'{o.Name}: {o.getStatusString()}')
    t = b.Tip
    if t is None or t.Shape.isNull():
        return 'ERR ' + ('; '.join(issues) or 'empty body')
    if not t.Shape.isValid():
        issues.append('tip shape invalid')
    if len(t.Shape.Solids) != 1:
        issues.append(f'solids {len(t.Shape.Solids)}')
    return 'ERR ' + '; '.join(issues) if issues else f'OK {t.Name} ' + _shape(t.Shape)


def why(name):
    o = _obj(name)
    if o.TypeId == 'Sketcher::SketchObject':
        return f'{o.Name}: ' + (_sk_issue(o) or f'DoF 0, {o.ConstraintCount} constraints')
    return f'{o.Name}: {o.getStatusString()} {",".join(o.State)}'


def tree():
    d = _doc()
    b = _body(d)
    s = _sheet(False, d)
    items = [f'{s.Name}({len(_aliases(s))})'] if s else []
    for o in b.Group:
        k = o.TypeId.split('::')[1].replace('SketchObject', 'Sketch')
        extra = f' DoF{o.DoF}' if k == 'Sketch' else ''
        items.append(f'{o.Name}:{k}{extra}' + ('*' if o == b.Tip else '') + ('!' if _bad(o) else ''))
    return ' | '.join(items)


def undo():
    d = _doc()
    if not d.UndoCount:
        raise FdmkitError('undo: nothing to undo')
    d.undo()
    d.recompute()
    return f'undo: OK, {d.UndoCount} left'


# ---------------------------------------------------------------- entry
AUTOSAVE_S = 300
_saved = {}


def _autosave(d):
    """Save a document that has a file at most every AUTOSAVE_S seconds."""
    now = time.time()
    if d.FileName and now - _saved.get(d.Name, 0) >= AUTOSAVE_S:
        d.save()
        _saved[d.Name] = now


def run(expr):
    """Run 'a(); b(); c()' as ONE transaction: one result per call, ' ; '-joined.
    Any failure rolls the whole batch back and names the failing step."""
    d = None if re.fullmatch(r'\s*undo\s*\(\s*\)\s*', expr) else App.ActiveDocument
    if d:
        d.openTransaction(expr[:60])
    out, step = [], 0
    try:
        ns = {k: globals()[k] for k in __all__}
        for step, node in enumerate(ast.parse(expr).body, 1):
            if isinstance(node, ast.Expr):
                r = eval(compile(ast.Expression(node.value), '<fdmkit>', 'eval'), ns)
                out.append('OK' if r is None else str(r))
            else:
                exec(compile(ast.Module([node], []), '<fdmkit>', 'exec'), ns)
        if d:
            d.commitTransaction()
            _autosave(d)
        return ' ; '.join(out) or 'OK'
    except Exception as e:
        if d:
            d.abortTransaction()
            d.recompute()
        msg = str(e) if isinstance(e, FdmkitError) else f'{type(e).__name__}: {e}'
        return f'ERR step {step}: {msg}' + (' (batch rolled back)' if step > 1 else '')


def _boot():
    old = getattr(App, '_fdmkit_observer', None)
    if old:
        App.removeDocumentObserver(old)
    App._fdmkit_observer = _SheetObserver()
    App.addDocumentObserver(App._fdmkit_observer)
    v = App.Version()
    ver = f'{v[0]}.{v[1]}.{v[2]} {v[3].split()[0]}'
    p = App.ParamGet(_PREF)
    last = p.GetString('FreeCADVersion', '')
    msg = f'fdmkit {__version__} · FreeCAD {ver}'
    if last == ver:
        App.Console.PrintMessage(msg + '\n')
    else:
        p.SetString('FreeCADVersion', ver)
        App.Console.PrintWarning(f'{msg} · FreeCAD changed (was {last or "none"}): run fdmkit.selftest()\n')


def _tipvol(d):
    return _body(d).Tip.Shape.Volume


def selftest():
    """Build a throwaway part through run(); one line with the failures."""
    prev = App.ActiveDocument.Name if App.ActiveDocument else None
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
        ck('pocket', "pocket('holes')", lambda r: r.startswith('pocket: OK'))
        ck('undo', "undo()", lambda r: d.getObject('pocket') is None)
        ck('dim', "dim('outline', 'r1_w', 'width + 2')", lambda r: 'bb 42.0x' in r)
        ck('chk', "chk()", lambda r: r.startswith('OK'))
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
            ck('thread_cosmetic', "sk('thread_sk','pattern_top'); circ('thread_sk',3); "
               "hole('thread_sk',3,thread_type='ISOMetricProfile')",
               lambda r: 'hole: OK' in r and d3.getObject('hole').CosmeticThread
               and not d3.getObject('hole').ModelThread)
            ck('chk_patterns', "chk()", lambda r: r.startswith('OK'))
        finally:
            App.closeDocument(d3.Name)
            App.setActiveDocument(d.Name)
        d4 = App.newDocument('fdmkit_existing_helpers', 'fdmkit_existing_helpers', True, True)
        try:
            App.setActiveDocument(d4.Name)
            _init(d4)
            ck('half', "P(half_width=20,half_height=10); sk('half_sk','XY'); "
               "rect('half_sk','half_width','half_height'); half('half_sk')",
               lambda r: 'half_sk.half: DoF 0' in r)
            ck('half_pad', "pad('half_sk',6)", lambda r: 'pad: OK' in r)
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
    finally:
        App.closeDocument(d.Name)
        if prev and prev in App.listDocuments():
            App.setActiveDocument(prev)
    bad = [f'{label}: {r}' for label, good, r in res if not good]
    return f'selftest {len(res) - len(bad)}/{len(res)}' + (' | ' + ' | '.join(bad) if bad else ' OK')

"""fdmkit: lean parametric PartDesign helpers for FDM and CNC (FreeCAD 26.3, 27.1).

Entry point is run(expr): one call = one transaction, result = one line.
Lengths and angles take a number or an expression; bare names of params
aliases are rewritten to params.<name>. Every sketch helper adds its own
constraints and fails (rolling back) unless the sketch ends at DoF 0.
"""
import ast
import math
import os
import re
import time

import FreeCAD as App
import Part
import Sketcher

__version__ = '0.4.0'
__all__ = ['new', 'P', 'plane', 'midplane', 'sk', 'rect', 'circ', 'slot', 'poly', 'fil',
           'half', 'regions', 'remap', 'pad', 'pocket', 'hole', 'revolve', 'groove', 'linear', 'polar', 'circular',
           'path_pattern', 'point_pattern', 'mirror', 'move', 'defeature', 'thickness',
           'dim', 'chk', 'why', 'tree', 'check', 'lint', 'case', 'sel', 'mass', 'reopen',
           'link_array', 'rigid_group', 'snapshot', 'snapshot_restore',
           'undo', 'errors', 'selftest', 'focus', 'full', 'freeze', 'thaw',
           'freeze_all', 'thaw_all', 'i10g_video',
           'cnc', 'cnc_show', 'cnc_restore', 'cam_job', 'cam_slot', 'cam_sim', 'cam_del']

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


def _bits(d):
    """Names of the shape Bodies of CAM tool bits."""
    return {o.BitBody.Name for o in d.Objects if getattr(o, 'BitBody', None) is not None}


def _active_body(d):
    """The GUI active Body of any 3D view of d (a CAM simulator or sheet tab may be in front)."""
    if not App.GuiUp:
        return None
    import FreeCADGui as Gui
    gd = Gui.getDocument(d.Name)
    views = [gd.ActiveView] if gd and gd.ActiveView else []
    try:
        views += list(gd.mdiViewsOfType('Gui::View3DInventor'))
    except Exception:
        pass
    for v in views:
        try:
            b = v.getActiveObject('pdbody')
            if b:
                return b
        except Exception:
            pass
    return None


def _body(d=None):
    """The active Body, else the last part Body (never a CAM tool bit's Body)."""
    d = d or _doc()
    b = _active_body(d)
    if b:
        return b
    bits = _bits(d)
    bodies = [o for o in d.Objects if o.TypeId == 'PartDesign::Body' and o.Name not in bits]
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


_SUB = re.compile(r'(.+)\.((?:Face|Edge|Vertex)\d+)')


def _ref(x, b=None):
    """(object, [sub]) for an origin key of the Body ('XY', 'Z'), an object name,
    or 'Feature.Face3' as sel() prints it."""
    if isinstance(x, tuple):
        return x
    if x in _ORIGIN:
        return _origin(b or _body(), x), ['']
    m = _SUB.fullmatch(x)
    if m:
        return _obj(m[1]), [m[2]]
    return _obj(x), ['']


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
    text = str(v)
    return _ID.sub(lambda m: f'{s.Name}.{m[1]}' if m[1] in names
                   and not re.match(r'\s*\(', text[m.end():]) else m[1], text)


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
    unknown = [k for k in names if k not in al]
    if unknown:
        raise FdmkitError(f'P: no param {", ".join(unknown)}; P() lists them')
    d = _doc()
    before = {o.Name for o in _scope(d) if _bad(o)} if values else set()
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
                raise FdmkitError(f"P: '{k}' rejected by FreeCAD (unit token or invalid)") from None
            al[k] = cell
        else:
            s.set(cell, _cell(v))
    if values:
        _rc(d)
        bad = [o for o in _scope(d) if _bad(o) and o.Name not in before]
        if bad:
            raise FdmkitError('P: ' + '; '.join(f'{o.Name}: {o.getStatusString()}' for o in bad))
    keys = names or (values.keys() if values else al.keys())
    return 'P: ' + ' '.join(f'{k}={_pval(s, k)}' for k in keys)


def _pval(s, k):
    try:
        return _num(s.get(k))
    except Exception:       # text or an error value in the cell
        return repr(str(s.get(k)))


class _SheetObserver:
    """Work around 26.3: changing an aliased cell does not touch dependents. Installed only
    before 27.1, where it made every P() recompute every sheet-dependent object."""

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
    _rc(pl.Document)
    if _bad(pl):
        raise FdmkitError(f'{name}: {pl.getStatusString()}')
    return f'{name}: OK z {_num(pl.Placement.Base.z)}'


def midplane(name, a, b):
    """Datum plane midway between two planes or planar faces (26.3 MidPlane attachment);
    non-parallel ones give the bisector through their intersection line."""
    _free(name)
    body = _body()
    pl = body.newObject('PartDesign::Plane', name)
    (oa, sa), (ob, sb) = _ref(a, body), _ref(b, body)
    pl.AttachmentSupport = [(oa, sa[0]), (ob, sb[0])]
    pl.MapMode = 'MidPlane'
    _rc(pl.Document)
    if _bad(pl):
        raise FdmkitError(f'{name}: {pl.getStatusString()}')
    p, n = pl.Placement.Base, pl.Placement.Rotation.multVec(V(0, 0, 1))
    return f'{name}: OK at ({_num(p.x)}, {_num(p.y)}, {_num(p.z)}) n({_num(n.x)}, {_num(n.y)}, {_num(n.z)})'


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
    _rc(s.Document)
    several = sum(o.TypeId == 'PartDesign::Body' for o in s.Document.Objects) - len(_bits(s.Document)) > 1
    return f'{name}: OK on {on}' + (f' in {b.Name}' if several else '')


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
    # DoF and the conflict lists are stored and survive a reopen; solving an up-to-date sketch
    # would only mark it Touched (recompute debt for the next call) and add an undo step
    if 'Touched' in s.State or 'Invalid' in s.State:
        s.solve()
    out = []
    for attr, tag in (('ConflictingConstraints', 'conflict'), ('RedundantConstraints', 'redundant'),
                      ('PartiallyRedundantConstraints', 'partial'), ('MalformedConstraints', 'malformed')):
        ids = list(getattr(s, attr, None) or [])
        if ids:
            out.append(tag + ' ' + ','.join(_cname(s, i) for i in ids))
    if s.DoF:
        if not s.getGeometryWithDependentParameters():
            s.solve()
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
    _rc(s.Document)
    err = _sk_issue(s)
    if err:
        raise FdmkitError(f'{s.Name}.{label}: {err}')
    return f'{s.Name}.{label}: DoF 0'


def rect(sketch, w, h, x=0, y=0, at='c', name=None):
    """Rectangle w x h; (x, y) is its centre (at='c') or bottom-left corner (at='bl')."""
    if at not in ('c', 'bl'):
        raise FdmkitError(f"rect: at={at!r}: expected 'c' or 'bl'")
    s = _sk(sketch)
    n = _auto(s, 'r', name)
    W, H, X, Y = (_val(s, v) for v in (w, h, x, y))
    if W <= 0 or H <= 0:
        raise FdmkitError(f'rect: size {W:g} x {H:g} must be > 0')
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
    if _val(s, d) <= 0:
        raise FdmkitError(f'circ: diameter {d} must be > 0')
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
    if k < 3 or any((vs[i] - vs[(i + 1) % k]).Length < 1e-6 for i in range(k)):
        raise FdmkitError(f'poly: needs >= 3 distinct consecutive points, got {k}')
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
        s.setDatum(i, App.Units.Quantity(f'{float(value)} deg') if s.Constraints[i].Type == 'Angle'
                   else float(value))
    _rc(s.Document)
    b = s.getParentGeoFeatureGroup()
    if b is None or b.TypeId != 'PartDesign::Body' or b.Tip is None:
        err = _sk_issue(s)        # no solid yet: the sketch is all there is to check
        if err:
            raise FdmkitError(f'{s.Name}: {err}')
        return f'{s.Name}.{cname}: OK DoF 0'
    r = chk(b)
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
    return -1 if min(ys) < -_EPS else 1      # touching the axis from below counts as below


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
    if any(not hasattr(geo[i], 'StartPoint') for i in cross):
        raise FdmkitError(f'{s.Name}: a full circle crosses the H axis; draw it as two arcs')
    # points where a kept edge meets a deleted one on the axis (diamond and hexagon tips)
    tips = []
    for i in low:
        for p, q in _ends(geo[i]).items():
            if p != 3 and abs(q.y) < _EPS:
                for j, g in enumerate(geo):
                    if side[j] > 0:
                        tips += [(q.x, j, pj) for pj, qj in _ends(g).items() if pj != 3 and (qj - q).Length < _EPS]
    # outline of each geometry: connected by coincidences (a width must belong to the same outline)
    link = {i: {i} for i in range(len(geo))}
    for c in s.Constraints:
        if c.Type == 'Coincident' and c.First >= 0 and c.Second >= 0:
            u = link[c.First] | link[c.Second]
            for i in u:
                link[i] = u
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
    for x, j, pj in dict.fromkeys(tips):
        pts_on.append((x, j - sum(1 for k in low if k < j), pj))
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
        if c.Type not in ('Radius', 'Diameter', 'DistanceX', 'DistanceY', 'Distance', 'Equal',
                          'Horizontal', 'Vertical'):
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
                npos = pos
                if pos in (1, 2):       # the mirror image may run the other way
                    q = pts[pos]
                    e2 = _ends(s.Geometry[ni])
                    npos = next(p for p in e2 if p != 3 and (e2[p] - q).Length < 1e-6)
                args.append((ni, npos))
            else:
                args.append((gi - sum(1 for j in low if j < gi) if gi >= 0 else gi, pos))
        else:
            sign = -1 if c.Type == 'DistanceY' else 1
            flat = [x for a in args for x in a]
            if c.Type in ('Horizontal', 'Vertical'):
                if len(args) != 1:
                    continue
                cons = C(c.Type, flat[0])
            elif c.Type in ('Radius', 'Diameter'):
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
    for i in cross:     # an arc centred on the axis keeps its centre there (its mirror held it)
        g = geo[i]
        if not s.DoF or not hasattr(g, 'Center') or abs(g.Center.y) > _EPS:
            continue
        dof = s.DoF
        k = s.addConstraint(C('PointOnObject', new[i], 3, -1))
        s.solve()
        if s.DoF >= dof or _sk_clash(s):
            s.delConstraint(k)
            s.solve()
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
    plain = []
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
                outline = link.get(_orig(gb, low), set())
                widths = [c for c in s.Constraints if c.Type == 'DistanceX' and c.Name and c.Value > 0
                          and abs(c.Value - (xb - xa)) < _EPS and _orig(c.First, low) in outline]
                if widths:
                    s.setExpression('Constraints.' + cname,
                                    f'Constraints.{widths[0].Name} / 2')
                else:
                    plain.append(cname)
                break
    r = _sk_done(s, 'half')
    area1 = face()
    if abs(2 * area1 - area0) > 1e-3 * area0:
        raise FdmkitError(f'{s.Name}: half area {area1:.2f} != {area0:.2f} / 2')
    warn = f'; WARN {", ".join(plain)} plain numbers (no width of that outline): drive them' if plain else ''
    return r + f', area {area0:.1f} -> {area1:.1f}' + warn


def _orig(gi, low):
    """Index before the lower geometries were deleted, of index gi after it."""
    for j in sorted(low):
        if j <= gi:
            gi += 1
    return gi


# ---------------------------------------------------------------- sketch regions
def _faces_of(s):
    """Closed regions of a sketch (26.3 internal faces, sketch-local), MakeInternals on."""
    _need(s, 'MakeInternals', 'InternalShape')
    if not s.MakeInternals:
        s.MakeInternals = True
        s.recompute()
    return s.InternalShape.Faces


def _inner_point(f):
    """A point inside face f: the centre of mass, else the centre of its largest triangle."""
    c = f.CenterOfMass
    if f.isInside(c, 1e-6, True):
        return c
    pts, tris = f.tessellate(0.1)
    area = lambda t: (pts[t[1]] - pts[t[0]]).cross(pts[t[2]] - pts[t[0]]).Length
    t = max(tris, key=area)
    return (pts[t[0]] + pts[t[1]] + pts[t[2]]) / 3


def _region_names(s, at):
    """InternalFaceN of sketch s for each (x, y) point in sketch coordinates."""
    if isinstance(at, (tuple, list)) and len(at) == 2 and not isinstance(at[0], (tuple, list)):
        at = [at]
    faces = _faces_of(s)
    names = []
    for x, y in at:
        p = V(_val(s, x), _val(s, y), 0)
        hit = [i for i, f in enumerate(faces) if f.isInside(p, 1e-6, True)]
        if len(hit) != 1:
            raise FdmkitError(f'{s.Name}: ({_num(p.x)}, {_num(p.y)}) is '
                              + ('outside every region' if not hit else 'on a region boundary')
                              + f'; regions("{s.Name}") lists inner points')
        n = f'InternalFace{hit[0] + 1}'
        if abs(s.getSubObject(n).Area - faces[hit[0]].Area) > 1e-6:
            raise FdmkitError(f'{s.Name}: {n} does not match region {hit[0]}')
        names.append(n)
    return list(dict.fromkeys(names))


def regions(sketch):
    """Closed regions of a sketch: name, area, an inner point (x, y) for at=, hole count."""
    s = _sk(sketch)
    faces = _faces_of(s)
    if not faces:
        raise FdmkitError(f'{s.Name}: no closed regions')
    out = []
    for i, f in enumerate(faces):
        p = _inner_point(f)
        holes = f' holes {len(f.Wires) - 1}' if len(f.Wires) > 1 else ''
        out.append(f'InternalFace{i + 1} A {f.Area:.1f} at ({_num(p.x)}, {_num(p.y)}){holes}')
    return f'{s.Name}: {len(faces)} regions: ' + ' | '.join(out)


def remap(feature, *at):
    """Point a Pad/Pocket at the regions under points at (sketch coords) after a sketch
    edit lost them; no points = the whole sketch."""
    f = _obj(feature)
    if 'Profile' not in f.PropertiesList or not f.Profile:
        raise FdmkitError(f'{f.Name}: no sketch profile')
    s = _sk(f.Profile[0])
    f.Profile = (s, _region_names(s, list(at))) if at else s
    return _finish(f, s)


# ---------------------------------------------------------------- features
def _shape(sh):
    bb = sh.BoundBox
    return f'V {sh.Volume:.1f} bb {bb.XLength:.1f}x{bb.YLength:.1f}x{bb.ZLength:.1f}'


def _setq(o, prop, v):
    if isinstance(v, str):
        o.setExpression(prop, _expr(v))
    else:
        setattr(o, prop, v)


def _pick(table, value, arg):
    """table[value], or an FdmkitError listing the accepted values."""
    try:
        return table[value]
    except (KeyError, TypeError):
        raise FdmkitError(f'{arg}={value!r}: expected {", ".join(map(str, table))}') from None


def _sketch_body(s):
    """The Body that owns sketch s (a feature must live there), else the active Body."""
    b = s.getParentGeoFeatureGroup()
    return b if b is not None and b.TypeId == 'PartDesign::Body' else _body()


def _feature(kind, name, sketch, at=None):
    if name:
        _free(name)
    s = _sk(sketch)
    sub = _region_names(s, at) if at is not None else None
    f = _sketch_body(s).newObject(kind, name or kind.split('::')[1].lower())
    f.Profile = (s, sub) if sub else s
    return f, s


def _finish(f, s):
    """s = the profile sketch to hide, or None for a feature without one."""
    prev = f.BaseFeature
    _rc(f.Document)
    bad = [o for o in (s, f) if o and _bad(o)]
    if bad:
        raise FdmkitError('; '.join(f'{o.Name}: {o.getStatusString()}' for o in bad))
    if f.Shape.isNull() or not f.Shape.isValid() or len(f.Shape.Solids) != 1:
        raise FdmkitError(f'{f.Name}: ' + ('no shape' if f.Shape.isNull() else f'solids {len(f.Shape.Solids)}'))
    if prev and not prev.Shape.isNull() and abs(f.Shape.Volume - prev.Shape.Volume) < 1e-6:
        hint = ('profile misses the solid or points away: try reverse=True'
                if 'Reversed' in f.PropertiesList and f.TypeId != 'PartDesign::Thickness'
                else 'nothing to cut or remove there')
        raise FdmkitError(f'{f.Name}: changed nothing (V {f.Shape.Volume:.1f}); {hint}')
    if s:
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
            raise FdmkitError('start=reference needs a plane or sketch region and no offset')
        _need(f, 'StartReference')
        if isinstance(reference, tuple):   # (sketch, (x, y)): the region under the point
            s = _sk(reference[0])
            f.StartReference = (s, _region_names(s, reference[1]))
        else:
            ref = _origin(_body(), reference) if reference in _ORIGIN else _obj(reference)
            if ref.TypeId not in ('PartDesign::Plane', 'App::Plane'):
                raise FdmkitError(f'{reference}: not a plane; a sketch region is (sketch, (x, y))')
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


def _set_side(f, side, length2):
    """SideType; side='two' needs its own second length (FreeCAD's hidden default is 5-10 mm)."""
    f.SideType = _pick(_SIDES, side, 'side')
    if (side == 'two') != (length2 is not None):
        raise FdmkitError("side='two' needs the second length (length2/depth2), other sides take none")
    if length2 == 'through':
        f.Type2 = 'ThroughAll'
    elif length2 is not None:
        f.Type2 = 'Length'
        _setq(f, 'Length2', length2)


def pad(sketch, length, name=None, side='one', reverse=False,
        start='profile', offset=0, reference=None, at=None, length2=None):
    """at: (x, y) or [(x, y), ...] in sketch coords picks only the regions under
    those points (26.3 sketch internals); None pads the whole sketch.
    side='two' pads length one way and length2 the other."""
    f, s = _feature('PartDesign::Pad', name, sketch, at)
    _setq(f, 'Length', length)
    _set_side(f, side, length2)
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    return _finish(f, s)


def pocket(sketch, depth='through', name=None, side='one', reverse=False,
           start='profile', offset=0, reference=None, operation='subtract', at=None, depth2=None):
    f, s = _feature('PartDesign::Pocket', name, sketch, at)
    if depth == 'through':
        f.Type = 'ThroughAll'
    else:
        _setq(f, 'Length', depth)
    _set_side(f, side, depth2)
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    _set_operation(f, operation)
    return _finish(f, s)


_DRILL = {'flat': 'Flat', 'angled': 'Angled'}


def hole(sketch, diameter, depth='through', name=None, start='profile',
         offset=0, reference=None, thread_type=None, thread_size=None,
         model_thread=False, cosmetic_thread=True, operation='subtract', drill_point='flat'):
    """PartDesign Hole on fully constrained circle centres; cosmetic thread is metadata.
    Threaded: diameter is the nominal size (4 -> M4x0.7) unless thread_size is given;
    FreeCAD then sets the tap drill diameter. drill_point='angled' adds the 118° cone
    BELOW depth (it can pierce a thin floor); 'flat' keeps the floor at depth."""
    if thread_type is None and (thread_size is not None or model_thread):
        raise FdmkitError('hole: thread_type required for thread_size or model_thread')
    point = _pick(_DRILL, drill_point, 'drill_point')
    f, s = _feature('PartDesign::Hole', name, sketch)
    _rc(f.Document)  # Hole populates its dynamic properties after a base recompute.
    if depth == 'through':
        f.DepthType = 'ThroughAll'
    else:
        f.DepthType = 'Dimension'
        _setq(f, 'Depth', depth)
        f.DrillPoint = point
    _set_start(f, start, offset, reference)
    _set_operation(f, operation)
    thread = ''
    if thread_type is not None:
        if thread_type not in f.getEnumerationsOfProperty('ThreadType'):
            raise FdmkitError(f'hole: thread type {thread_type} unavailable')
        f.Threaded = True
        f.ThreadType = thread_type
        sizes = f.getEnumerationsOfProperty('ThreadSize')
        if thread_size is None:     # nominal from the diameter: 4 -> 'M4x0.7'
            nom = _num(_val(f, diameter))
            thread_size = next((z for z in sizes if re.fullmatch(rf'M{re.escape(nom)}x[\d.]+', z)), None)
            if thread_size is None:
                raise FdmkitError(f'hole: no {thread_type} size for nominal {nom}; '
                                  f'thread_size= one of {", ".join(sizes[:12])} ...')
        elif thread_size not in sizes:
            raise FdmkitError(f'hole: thread size {thread_size!r} unavailable; '
                              f'e.g. {", ".join(z for z in sizes if z.startswith("M3") or z.startswith("M4"))}')
        f.ThreadSize = thread_size
        f.ModelThread = bool(model_thread)
        f.CosmeticThread = bool(cosmetic_thread)
    else:
        _setq(f, 'Diameter', diameter)
    r = _finish(f, s)
    if thread_type is not None:
        thread = f', {f.ThreadSize} drill {_num(f.Diameter)}'
    return r + thread


_TYPES = {'angle': 'Angle', 'up_to_face': 'UpToFace', 'up_to_first': 'UpToFirst',
          'up_to_last': 'UpToLast', 'through': 'ThroughAll'}


def _set_type(f, type, up_to):
    if type not in _TYPES or _TYPES[type] not in f.getEnumerationsOfProperty('Type'):
        raise FdmkitError(f'{f.TypeId}: type={type} unavailable')
    if (type == 'up_to_face') != (up_to is not None):
        raise FdmkitError('type=up_to_face needs up_to (a plane or Feature.FaceN); other types take none')
    f.Type = _TYPES[type]
    if up_to is not None:
        f.UpToFace = _ref(up_to)


def _rotation(sketch, kind, angle, axis, name, side, reverse,
              start, offset, reference, project_axis, type, up_to, operation=None):
    if axis not in ('V_Axis', 'H_Axis', 'X', 'Y', 'Z'):
        raise FdmkitError('axis: expected V_Axis, H_Axis, X, Y or Z')
    f, s = _feature(kind, name, sketch)
    f.ReferenceAxis = (s, [axis]) if axis in ('V_Axis', 'H_Axis') else (_origin(_body(), axis), [''])
    _setq(f, 'Angle', angle)
    f.SideType = _pick(_SIDES, side, 'side')
    f.Reversed = reverse
    _set_start(f, start, offset, reference)
    _set_type(f, type, up_to)
    if project_axis:
        _need(f, 'ProjectAxis')
        f.ProjectAxis = True
    if operation is not None:
        _set_operation(f, operation)
    return _finish(f, s)


def revolve(sketch, angle=360, axis='V_Axis', name=None, side='one',
            reverse=False, start='profile', offset=0, reference=None,
            project_axis=False, type='angle', up_to=None):
    """axis: sketch 'V_Axis'/'H_Axis' or body origin 'X'/'Y'/'Z'.
    type: 'angle', 'up_to_face' (up_to = plane or Feature.FaceN), 'up_to_first', 'up_to_last'."""
    return _rotation(sketch, 'PartDesign::Revolution', angle, axis, name, side,
                     reverse, start, offset, reference, project_axis, type, up_to)


def groove(sketch, angle=360, axis='V_Axis', name=None, side='one',
           reverse=False, start='profile', offset=0, reference=None,
           project_axis=False, operation='subtract', type='angle', up_to=None):
    """Subtractive rotational feature, optionally using 26.3 Common mode.
    type: 'angle', 'up_to_face' (up_to = plane or Feature.FaceN), 'up_to_first', 'through'."""
    return _rotation(sketch, 'PartDesign::Groove', angle, axis, name, side,
                     reverse, start, offset, reference, project_axis, type, up_to, operation)


def _solid_tail(b):
    """Last solid feature of the body (a Tip candidate)."""
    return [o for o in b.Group if o.isDerivedFrom('PartDesign::Feature')][-1]


def _pattern(kind, who, features, name, suppressed):
    """New PartDesign pattern of features in the active Body, suppressed instances set."""
    b = _body()
    fs = [_obj(x) for x in ([features] if isinstance(features, str) else features)]
    if not fs or any(f not in b.Group or not f.isDerivedFrom('PartDesign::Feature') for f in fs):
        raise FdmkitError(f'{who}: originals must be features in the active Body')
    if any(not isinstance(i, int) or i < 0 for i in suppressed):
        raise FdmkitError(f'{who}: suppressed indices must be integers >= 0')
    if name:
        _free(name)
    f = b.newObject(kind, name or who)
    b.Tip = f       # newObject leaves Tip on the original: later features would skip the pattern
    f.Originals = fs
    _suppressed.pop(f.Name, None)       # a rolled-back call may have left one for this name
    if suppressed:
        _need(f, 'SuppressedIndices')
        _suppressed[f.Name] = sorted(set(suppressed))
    return f, fs


_suppressed = {}    # pattern name -> indices, set once the counts are known


def _pattern_done(f, fs):
    idx = _suppressed.pop(f.Name, None)
    if idx:     # set last: FreeCAD drops indices beyond the current count
        f.SuppressedIndices = idx
        if list(f.SuppressedIndices) != idx:
            raise FdmkitError(f'{f.Name}: suppressed {idx} outside the instances')
    _rc(f.Document)
    prev = f.BaseFeature                # a pattern gets its BaseFeature on recompute
    if _bad(f) or f.Shape.isNull() or not f.Shape.isValid() or len(f.Shape.Solids) != 1:
        raise FdmkitError(f'{f.Name}: {f.getStatusString()} solids {len(f.Shape.Solids)}')
    if prev and abs(f.Shape.Volume - prev.Shape.Volume) < 1e-6:
        raise FdmkitError(f'{f.Name}: changed nothing (V {f.Shape.Volume:.1f}); instances miss the solid')
    for o in fs:
        o.Visibility = False
    return f'{f.Name}: OK ' + _shape(f.Shape)


def polar(features, occurrences, axis='Z', angle=360, suppressed=(), name=None):
    """PartDesign PolarPattern; suppressed uses zero-based instance indices."""
    if axis not in ('X', 'Y', 'Z'):
        raise FdmkitError('polar: axis must be X, Y or Z')
    if not isinstance(occurrences, int) or occurrences < 2:
        raise FdmkitError('polar: occurrences must be an integer >= 2')
    if any(isinstance(i, int) and i >= occurrences for i in suppressed):
        raise FdmkitError('polar: suppressed indices must be 0..occurrences-1')
    f, fs = _pattern('PartDesign::PolarPattern', 'polar', features, name, suppressed)
    f.Axis = (_origin(_body(), axis), [''])
    f.Occurrences = occurrences
    _setq(f, 'Angle', angle)
    return _pattern_done(f, fs)


def linear(features, direction, count, step=None, extent=None, direction2=None, count2=1,
           step2=None, extent2=None, reverse=False, reverse2=False, suppressed=(), name=None):
    """PartDesign LinearPattern along an origin axis or 'Feature.EdgeN': count instances step
    apart (or spread over extent); direction2/count2 make a grid in one feature (step2/extent2
    default to step/extent). suppressed:
    zero-based indices, on a grid (i, j) pairs = instance i along direction, j along direction2."""
    if not isinstance(count, int) or count < 1 or not isinstance(count2, int) or count2 < 1 \
            or count * count2 < 2:
        raise FdmkitError('linear: count and count2 must be integers >= 1, together >= 2')
    if (count2 > 1) != (direction2 is not None):
        raise FdmkitError('linear: direction2 and count2 > 1 go together')
    idx = []
    for i in suppressed:
        k = i[0] * count2 + i[1] if isinstance(i, tuple) and len(i) == 2 else i
        if not isinstance(k, int) or not 0 <= k < count * count2:
            raise FdmkitError(f'linear: suppressed {i} outside the {count}x{count2} instances')
        idx.append(k)
    f, fs = _pattern('PartDesign::LinearPattern', 'linear', features, name, ())
    for sfx, dirn, n, st, ex, rev in (('', direction, count, step, extent, reverse),
                                      ('2', direction2, count2,
                                       step if step2 is None and extent2 is None else step2,
                                       extent if step2 is None and extent2 is None else extent2, reverse2)):
        if dirn is None:
            continue
        if (st is None) == (ex is None) and n > 1:
            raise FdmkitError(f'linear: give step{sfx} or extent{sfx}')
        setattr(f, 'Direction' + sfx, _ref(dirn))
        setattr(f, 'Occurrences' + sfx, n)
        setattr(f, 'Reversed' + sfx, rev)
        if st is not None:
            setattr(f, 'Mode' + sfx, 'Spacing')      # Spacing takes the step from Offset
            _setq(f, 'Offset' + sfx, st)
        elif ex is not None:
            setattr(f, 'Mode' + sfx, 'Extent')
            _setq(f, 'Length' + sfx, ex)
    if idx:
        _need(f, 'SuppressedIndices')
        _suppressed[f.Name] = sorted(set(idx))
    return _pattern_done(f, fs)


def circular(features, rings, radial, tangential, axis='Z', symmetry=1,
             start_at_shape=True, suppressed=(), name=None):
    """PartDesign CircularPattern (26.3): `rings` concentric circles `radial` apart about an
    origin axis, instances `tangential` apart along each circle, the count per circle a multiple
    of `symmetry`; start_at_shape = the first circle passes through the original."""
    if axis not in ('X', 'Y', 'Z'):
        raise FdmkitError('circular: axis must be X, Y or Z')
    if not all(isinstance(n, int) and n >= 1 for n in (rings, symmetry)):
        raise FdmkitError('circular: rings and symmetry must be integers >= 1')
    f, fs = _pattern('PartDesign::CircularPattern', 'circular', features, name, suppressed)
    f.Axis = (_origin(_body(), axis), [''])
    f.NumberCircles = rings
    f.Symmetry = symmetry
    f.StartAtShape = start_at_shape
    _setq(f, 'RadialDistance', radial)
    _setq(f, 'TangentialDistance', tangential)
    return _pattern_done(f, fs)


def path_pattern(features, path, count=None, spacing=None, align=False, suppressed=(), name=None):
    """PartDesign PathPattern (26.3) along an edge ('sketch.Edge1', 'Feature.Edge4') or a whole
    sketch: count instances spread over the path, spacing apart, or both. The first instance is the
    original (RelativeToFirst); align turns instances with the path tangent."""
    if count is None and spacing is None:
        raise FdmkitError('path_pattern: give count, spacing or both')
    f, fs = _pattern('PartDesign::PathPattern', 'path_pattern', features, name, suppressed)
    f.Path = _ref(path)
    f.RelativeToFirst = True    # False places the original as if it sat at the path start
    f.Align = align
    f.SpacingMode = ('Fixed count' if spacing is None else 'Fixed spacing' if count is None
                     else 'Fixed count and spacing')
    if count is not None:
        f.Count = count
    if spacing is not None:
        _setq(f, 'Spacing', spacing)
    return _pattern_done(f, fs)


def point_pattern(features, points, suppressed=(), name=None):
    """PartDesign PointPattern (26.3) at the points of a sketch (or 'Feature.VertexN');
    the first point is the original's position."""
    f, fs = _pattern('PartDesign::PointPattern', 'point_pattern', features, name, suppressed)
    f.PointObject = _ref(points)
    return _pattern_done(f, fs)


def _faces(faces, who):
    """(Tip feature, [FaceN, ...]) from 'Feature.Face3' names of the Body Tip ('Body.Face3' too).
    A dress-up on an earlier feature rebases onto it and drops every later feature."""
    refs = [_ref(x) for x in ([faces] if isinstance(faces, str) else faces)]
    if not refs or len({o.Name for o, _ in refs}) != 1 or any(not s[0].startswith('Face') for _, s in refs):
        raise FdmkitError(f"{who}: faces must be 'Feature.FaceN' of one feature")
    base, b = refs[0][0], _body()
    if base == b:
        base = b.Tip
    if base != b.Tip:
        raise FdmkitError(f'{who}: faces must be on the Tip {b.Tip.Name if b.Tip else "(none)"}, not {base.Name} '
                          '(an earlier feature would drop the later ones); name them on the Tip')
    return base, [s[0] for _, s in refs]


def defeature(faces, name=None):
    """PartDesign Defeaturing (26.3): removes the faces ('Feature.Face7' or a list) and heals the
    solid, e.g. holes, fillets or bosses of an imported base feature."""
    if name:
        _free(name)
    base, subs = _faces(faces, 'defeature')
    f = _body().newObject('PartDesign::Defeaturing', name or 'defeature')
    f.Base = (base, subs)
    return _finish(f, None)


_THICK = {'skin': 'Skin', 'recto_verso': 'RectoVerso'}
_JOINS = {'arc': 'Arc', 'intersection': 'Intersection'}


def thickness(faces, value, mode='skin', join='arc', inward=True, name=None):
    """PartDesign Thickness: hollow the solid, removing the faces. mode 'skin' = a wall of value
    inside the faces (inward=False: outside), 'recto_verso' (26.3) = half the value on each
    side; join 'arc' or 'intersection'."""
    if name:
        _free(name)
    base, subs = _faces(faces, 'thickness')
    f = _body().newObject('PartDesign::Thickness', name or 'thickness')
    f.Base = (base, subs)
    _setq(f, 'Value', value)
    f.Mode = _pick(_THICK, mode, 'mode')
    f.Join = _pick(_JOINS, join, 'join')
    f.Reversed = inward                 # FreeCAD's Reversed (default True) means inwards
    return _finish(f, None)


def move(feature, after):
    """Move a feature or sketch to just after another one in the active body."""
    b = _body()
    f, t = _obj(feature), _obj(after)
    before = {o.Name for o in b.Group if _bad(o)}
    tip_last = b.Tip == _solid_tail(b)
    b.removeObject(f)
    b.insertObject(f, t, True)
    if tip_last:
        b.Tip = _solid_tail(b)
    _rc(f.Document)
    bad = [o for o in b.Group if _bad(o) and o.Name not in before]
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
        b.removeObject(m)
        b.insertObject(m, last, True)
    if b.Tip is None or b.Group.index(m) > b.Group.index(b.Tip):
        b.Tip = m       # else the mirrored half is outside the Body shape (same trap as patterns)
    _rc(m.Document)
    if _bad(m) or not m.Shape.isValid() or len(m.Shape.Solids) != 1:
        raise FdmkitError(f'{m.Name}: {m.getStatusString()} solids {len(m.Shape.Solids)}')
    return f'{m.Name}: OK ' + _shape(m.Shape)


# ---------------------------------------------------------------- inspect
def chk(body=None):
    """Whole Body (default the active one): sketches at DoF 0, features valid, one valid solid."""
    b = _obj(body) if body else _body()
    if b.TypeId != 'PartDesign::Body':
        raise FdmkitError(f'{b.Name}: not a Body')
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
    """Undo the last committed call. Right after an ERR (rolled back, nothing to undo) it
    refuses once, naming what a second undo() would revert."""
    d = _doc()
    if not d.UndoCount:
        raise FdmkitError('undo: nothing to undo')
    last = d.UndoNames[0] if d.UndoNames else '?'
    if _rolled_back.pop(d.Name, False):
        raise FdmkitError(f"undo: the last call was rolled back, nothing to undo from it; "
                          f"undo() again reverts '{last}'")
    d.undo()
    _rc(d)
    return f"undo: reverted '{last}', {d.UndoCount} left"


# ---------------------------------------------------------------- model checks
def _bodies(d):
    """Part Bodies with a solid: not the shape Bodies of CAM tool bits."""
    bits = _bits(d)
    return [o for o in d.Objects if o.TypeId == 'PartDesign::Body' and o.Tip and o.Name not in bits]


def _fasteners(d):
    """Fasteners workbench objects (screws, nuts, washers)."""
    return [o for o in d.Objects if o.TypeId == 'Part::FeaturePython'
            and type(getattr(o, 'Proxy', None)).__module__.startswith('Fasteners')]


def _line_dist(p, c, n):
    """Distance from point p to the line through c along unit vector n."""
    w = p - c
    return (w - n * w.dot(n)).Length


def _off_axis(d, bodies):
    """Fasteners whose axis runs through no cylindrical face of the given Bodies."""
    cyl = [(f.Surface.Axis, f.Surface.Center) for b in bodies for f in b.Shape.Faces
           if f.Surface.TypeId == 'Part::GeomCylinder']
    out = []
    for o in _fasteners(d):
        pl = o.getGlobalPlacement()
        ax = pl.Rotation.multVec(V(0, 0, 1))
        dist = [_line_dist(pl.Base, c, a) for a, c in cyl if abs(abs(a.dot(ax)) - 1) < 1e-4]
        if not dist or min(dist) > 1e-3:
            out.append(o.Name)
    return out


def check(*bodies):
    """Whole document: each Body one valid solid, no object in error, sketches at DoF 0,
    no volume intersection between Bodies, every Fasteners object on a hole axis."""
    d = _doc()
    bs = [_obj(n) for n in bodies] if bodies else _bodies(d)
    issues = []
    for b in bs:
        s = b.Shape
        if s.isNull():
            issues.append(f'{b.Name}: no shape')
        elif not s.isValid() or len(s.Solids) != 1:
            issues.append(f'{b.Name}: {len(s.Solids)} solids' + ('' if s.isValid() else ', invalid'))
    for o in d.Objects:
        if o.TypeId.startswith('TechDraw'):
            continue
        if o.TypeId == 'Sketcher::SketchObject':
            e = _sk_issue(o)
            if e:
                issues.append(f'{o.Name}: {e}')
        elif _bad(o):
            issues.append(f'{o.Name}: {o.getStatusString()}')
    ok = [b for b in bs if not b.Shape.isNull() and b.Shape.isValid()]
    for i, a in enumerate(ok):
        for b in ok[i + 1:]:
            if a.Shape.BoundBox.intersect(b.Shape.BoundBox):
                v = a.Shape.common(b.Shape).Volume
                if v > 1e-5:
                    issues.append(f'{a.Name} x {b.Name} {v:.4g} mm3')
    issues += [f'{n}: off hole axis' for n in _off_axis(d, bs)]
    if issues:
        return 'check: ERR ' + '; '.join(issues)
    return f'check: OK {len(bs)} bodies, {len(_fasteners(d))} fasteners'


def _tangent_hole(h):
    """Name of the cylinder radius a Hole sketch circle sits tangent to, or None."""
    prof = h.Profile[0] if h.Profile else None
    base = h.BaseFeature.Shape if h.BaseFeature else None
    if prof is None or base is None or base.isNull():
        return None
    body = h.getParentGeoFeatureGroup()
    pl = prof.getGlobalPlacement()
    if body is not None:            # BaseFeature.Shape is in the Body's own frame
        pl = body.getGlobalPlacement().inverse().multiply(pl)
    n = pl.Rotation.multVec(V(0, 0, 1))
    for g in prof.Geometry:
        if getattr(g, 'TypeId', '') != 'Part::GeomCircle':
            continue
        c = pl.multVec(g.Center)
        for f in base.Faces:
            s = f.Surface
            if s.TypeId == 'Part::GeomCylinder' and abs(s.Axis.dot(n)) < 1e-6 \
                    and abs(_line_dist(c, s.Center, s.Axis) - s.Radius) < 1e-6:
                return s.Radius
    return None


_LINK_SUBS = ('App::PropertyLinkSub', 'App::PropertyLinkSubList',
              'App::PropertyLinkSubChild', 'App::PropertyLinkSubGlobal')


def _lost_refs(o):
    """[(property, ['?Face3', ...])] of element references that no longer resolve."""
    out = []
    for prop in o.PropertiesList:
        try:
            if o.getTypeIdOfProperty(prop) not in _LINK_SUBS:
                continue
            v = getattr(o, prop)
        except Exception:
            continue
        pairs = [v] if isinstance(v, tuple) and len(v) == 2 and not isinstance(v[0], tuple) else (v or [])
        subs = []
        for pair in pairs:
            if pair and len(pair) == 2:
                subs += [pair[1]] if isinstance(pair[1], str) else list(pair[1] or [])
        lost = [x for x in subs if x.startswith('?') or '.?' in x]
        if lost:
            out.append((prop, lost))
    return out


def lint():
    """Traps found in real models: a Hole sketch tangent to a cylinder (OCC drops holes
    at random), a countersink apex on the hole floor, deactivated sketches placed by
    plain numbers, expressions reaching into another Body, unused params aliases."""
    d = _doc()
    out = []
    for h in d.Objects:
        if h.TypeId != 'PartDesign::Hole':
            continue
        r = _tangent_hole(h)
        if r is not None:
            out.append(f'{h.Name}: sketch tangent to R{r:g}, put it 1 mm outside')
        if h.HoleCutType == 'Countersink' and h.DepthType == 'Dimension':
            apex = h.HoleCutDiameter.Value / 2 / math.tan(math.radians(h.HoleCutCountersinkAngle.Value) / 2)
            if abs(apex - h.Depth.Value) < 1e-6:
                out.append(f'{h.Name}: countersink apex on the hole floor')
    for o in d.Objects:
        for prop, lost in _lost_refs(o):
            # 26.3 keeps the old shape of a feature whose sketch region or face vanished
            fix = f'remap("{o.Name}", (x, y))' if prop == 'Profile' else 'set it again'
            out.append(f'{o.Name}.{prop}: lost {",".join(lost)}, {fix}')
    for o in d.Objects:
        if o.TypeId == 'Sketcher::SketchObject' and getattr(o, 'MapMode', '') == 'Deactivated' \
                and 'Placement' not in dict(o.ExpressionEngine) and o.Placement.Base.Length > 1e-9:
            out.append(f'{o.Name}: placed by numbers')
    body_of = {o.Name: o.getParentGeoFeatureGroup() for o in d.Objects
               if o.getParentGeoFeatureGroup() is not None
               and o.getParentGeoFeatureGroup().TypeId == 'PartDesign::Body'}
    for o in d.Objects:
        own = body_of.get(o.Name)
        if own is None:
            continue
        for prop, e in o.ExpressionEngine:
            for ref in dict.fromkeys(re.findall(r'(?<![\w.])([A-Za-z_]\w*)\.', e)):
                other = body_of.get(ref)
                if other is not None and other != own:
                    out.append(f'{o.Name}.{prop.lstrip(".")} -> {ref} in {other.Name}')
    s = _sheet(False, d)
    if s:
        used = ' '.join(e for o in d.Objects if o.TypeId != 'Spreadsheet::Sheet' for _, e in o.ExpressionEngine)
        used += ' ' + ' '.join(sh.getContents(c) for sh in d.Objects if sh.TypeId == 'Spreadsheet::Sheet'
                               for c in sh.getUsedCells() if sh.getContents(c).startswith('='))
        out += [f'{s.Name}.{a}: unused' for a in _aliases(s) if not re.search(rf'\b{re.escape(a)}\b', used)]
    return 'lint: ' + ('; '.join(out) if out else 'OK')


def case(name, value, *bodies):
    """Set one sheet value, check(), restore it: a parametric stress test in one call.
    name is 'alias' (params) or 'sheet.alias'. TechDraw pages pause updating meanwhile."""
    d = _doc()
    sheet, alias = name.split('.', 1) if '.' in name else (PARAMS, name)
    sh = _sheet(False, d) if sheet == PARAMS else _obj(sheet)
    cell = _aliases(sh).get(alias) if sh else None
    if cell is None:
        raise FdmkitError(f'case: {name} not found')
    old = sh.getContents(cell)
    if isinstance(value, (int, float)):     # a bare number keeps the old cell's unit ('14' on '10 mm')
        unit = getattr(sh.get(alias), 'Unit', None)
        if unit is not None and str(unit) != 'Unit: ()' and getattr(sh.get(alias), 'UserString', ''):
            value = f'{value} {sh.get(alias).UserString.split()[-1]}'
    pages = [p for p in d.Objects if p.TypeId == 'TechDraw::DrawPage' and p.KeepUpdated]
    for p in pages:
        p.KeepUpdated = False
    try:
        sh.set(cell, _cell(value))
        sh.recompute()
        d.recompute()
        r = check(*bodies)
    finally:
        sh.set(cell, old)
        sh.recompute()
        d.recompute()
        for p in pages:
            p.KeepUpdated = True
    return f'case {name}={value}: ' + r.split(': ', 1)[1]


def _describe(sh):
    if sh.ShapeType == 'Vertex':
        p = sh.Point
        return f'vertex ({p.x:.4g}, {p.y:.4g}, {p.z:.4g})'
    if sh.ShapeType == 'Face':
        s = sh.Surface
        if s.TypeId == 'Part::GeomPlane':
            n = sh.normalAt(0, 0)
            if abs(abs(n.z) - 1) < 1e-9:
                return f'plane Z {sh.BoundBox.ZMin:.4g}'
            return f'plane n({n.x:.3g}, {n.y:.3g}, {n.z:.3g})'
        if hasattr(s, 'Radius'):
            return (f'{s.TypeId[10:].lower()} R{s.Radius:.4g} D{2 * s.Radius:.4g}'
                    f' Z {sh.BoundBox.ZMin:.4g}..{sh.BoundBox.ZMax:.4g}')
        return s.TypeId[10:].lower()
    if sh.ShapeType == 'Edge':
        c = sh.Curve
        if hasattr(c, 'Radius'):
            return f'circle R{c.Radius:.4g} at ({c.Center.x:.4g}, {c.Center.y:.4g}, {c.Center.z:.4g})'
        return f'edge L{sh.Length:.4g}'
    return sh.ShapeType


def _axis(sh):
    """(point, unit direction) of a cylinder or cone face, a circle or line edge, a plane
    normal; None for other shapes."""
    if sh.ShapeType == 'Face':
        s = sh.Surface
        if s.TypeId in ('Part::GeomCylinder', 'Part::GeomCone'):
            return s.Center, V(s.Axis).normalize()
        if s.TypeId == 'Part::GeomPlane':
            return sh.Vertexes[0].Point, sh.normalAt(0, 0)
    elif sh.ShapeType == 'Edge':
        c = sh.Curve
        if c.TypeId == 'Part::GeomCircle':
            return c.Center, V(c.Axis).normalize()
        if c.TypeId == 'Part::GeomLine':
            return sh.Vertexes[0].Point, (sh.Vertexes[-1].Point - sh.Vertexes[0].Point).normalize()
    return None


def sel():
    """What is selected in the GUI and, for two items, the distance between them, the angle
    between their axes/normals and, for parallel holes or circles, the distance of the axes."""
    import FreeCADGui as Gui
    items, shapes = [], []
    for s in Gui.Selection.getSelectionEx('', 0):
        for sub in s.SubElementNames:
            sh = s.Object.getSubObject(sub)
            if sh is None or sh.isNull():
                continue
            shapes.append(sh)
            leaf = sub.split('.')[-1] or sub
            own = s.Object.getSubObject(sub, retType=1) if '.' in sub else s.Object
            # the leaf object (pad, sketch), not the container: 'Body.Face6' would name the Tip's Face6
            items.append(f'{(own or s.Object).Name}.{leaf} {_describe(sh)}')
    if not items:
        return 'sel: nothing selected'
    if len(shapes) == 2:
        a, b = shapes
        dist = a.distToShape(b)[0]
        if all(x.ShapeType == 'Face' and x.Surface.TypeId == 'Part::GeomPlane' for x in shapes):
            na = a.normalAt(0, 0)
            if abs(abs(na.dot(b.normalAt(0, 0))) - 1) < 1e-9:
                dist = abs((b.Vertexes[0].Point - a.Vertexes[0].Point).dot(na))
        items.append(f'distance {dist:.4g}')
        xa, xb = _axis(a), _axis(b)
        if xa and xb:
            ang = math.degrees(math.acos(min(1.0, abs(xa[1].dot(xb[1])))))
            items.append(f'angle {ang:.4g}°')
            round_ = [x for x in shapes if x.ShapeType == 'Edge' or x.Surface.TypeId != 'Part::GeomPlane']
            if ang < 1e-6 and len(round_) == 2:
                items.append(f'axes {(xb[0] - xa[0]).cross(xa[1]).Length:.4g} apart')
    return ' | '.join(items)


def _density(o):
    """g/cm³ of the object's (or its linked object's) material; None for FreeCAD's 'Default'."""
    for x in (o, getattr(o, 'LinkedObject', None)):
        m = getattr(x, 'ShapeMaterial', None)
        if m is not None and m.Name != 'Default' and m.PhysicalProperties.get('Density'):
            q = App.Units.Quantity(m.PhysicalProperties['Density']).getValueAs('g/cm^3')
            return float(getattr(q, 'Value', q))
    return None


def mass(*objs, density=None):
    """Volume, mass, centre of gravity and principal moments of Bodies, Links or shapes (the
    Std_MassProperties numbers, which only exist in its task panel). density (g/cm³) overrides
    the materials; without either only volume and CoG. Coordinates in each object's parent frame."""
    d = _doc()
    objs = [_obj(o) for o in objs] or _bodies(d)
    out, tot_m, tot_v, mom = [], 0.0, 0.0, V()
    for o in objs:
        solids = o.Shape.Solids
        if not solids:
            raise FdmkitError(f'mass: {o.Name} has no solid')
        v = sum(s.Volume for s in solids)
        cog = sum((s.CenterOfMass * s.Volume for s in solids), V()) * (1 / v)
        rho = density if density is not None else _density(o)
        line = f'{o.Name}: V {v:.4g} mm³ CoG ({cog.x:.4g}, {cog.y:.4g}, {cog.z:.4g})'
        if rho is not None:
            m = v * rho / 1000                                  # g
            line += f' m {m:.4g} g ({rho:g} g/cm³)'
            if len(solids) == 1:                                # mm^5 × g/mm³ → kg·mm²
                i1, i2, i3 = solids[0].PrincipalProperties['Moments']
                line += f' I {i1 * rho / 1e6:.4g}/{i2 * rho / 1e6:.4g}/{i3 * rho / 1e6:.4g} kg·mm²'
            tot_m += m
            mom += cog * m
        tot_v += v
        out.append(line)
    if len(objs) > 1 and tot_m:
        c = mom * (1 / tot_m)
        out.append(f'total: V {tot_v:.4g} mm³ m {tot_m:.4g} g CoG ({c.x:.4g}, {c.y:.4g}, {c.z:.4g})')
    return 'mass: ' + ' | '.join(out)


def reopen(hidden=False):
    """Save, close and reopen the active document, then recompute it."""
    d = _doc()
    fn = d.FileName
    if not fn:
        raise FdmkitError('reopen: the document has no file')
    d.save()
    App.closeDocument(d.Name)
    nd = App.openDocument(fn, hidden)
    App.setActiveDocument(nd.Name)
    nd.recompute()
    bad = [o.Name for o in nd.Objects if _bad(o)]
    return f'reopen: OK {nd.Name}' + (', errors ' + ','.join(bad) if bad else '')


# ---------------------------------------------------------------- links and assembly
_LINK_ARRAYS = {'linear': 'Part::LinkArrayLinear', 'polar': 'Part::LinkArrayPolar',
                'path': 'Part::LinkArrayPath', 'point': 'Part::LinkArrayPoint'}


def link_array(source, kind, count=None, step=None, axis=None, angle=360, path=None,
               points=None, into=None, name=None):
    """Part link array (26.3): instances of source as App::Link elements, no copied geometry;
    Assembly joints can attach to any instance. linear: count, step apart along axis; polar:
    count over angle about axis; path: count along path ('sketch.Edge1'); point: at the points
    of a sketch. axis 'X'|'Y'|'Z' of the source's Origin, or an edge or datum line.
    into = Assembly or App::Part to hold it (default: the document root)."""
    if kind not in _LINK_ARRAYS:
        raise FdmkitError(f"link_array: kind {', '.join(_LINK_ARRAYS)}")
    d = _doc()
    src = _obj(source)
    if name:
        _free(name)
    holder = src if hasattr(src, 'Origin') else None
    if axis in _ORIGIN and holder is None:
        raise FdmkitError(f'link_array: {src.Name} has no Origin; give an edge or datum line')
    f = d.addObject(_LINK_ARRAYS[kind], name or f'{kind}_array')
    f.LinkedObject = src
    if kind in ('linear', 'polar'):
        if not isinstance(count, int) or count < 2 or axis is None:
            raise FdmkitError(f'link_array {kind}: count >= 2 and axis needed')
        f.Occurrences = count
        if kind == 'linear':
            if step is None:
                raise FdmkitError('link_array linear: step needed')
            f.Direction = _ref(axis, holder)
            f.Mode = 'Spacing'
            _setq(f, 'Offset', step)                # Spacing mode: Offset = distance between instances
        else:
            f.Axis = _ref(axis, holder)
            _setq(f, 'Angle', angle)
    elif kind == 'path':
        if path is None or not isinstance(count, int) or count < 1:
            raise FdmkitError('link_array path: path and an integer count >= 1 needed')
        f.Path = _ref(path)
        f.Count = count
        f.RelativeToFirst = True
    else:
        if points is None:
            raise FdmkitError('link_array point: points needed')
        f.PointObject = _ref(points)
        f.RelativeToFirst = True
    if into:
        _obj(into).addObject(f)
    _rc(d)
    if _bad(f) or f.ElementCount < 1:
        raise FdmkitError(f'{f.Name}: {f.getStatusString()} elements {f.ElementCount}')
    bb = f.Shape.BoundBox
    return f'{f.Name}: OK {f.ElementCount} links of {src.Name} bb {bb.XLength:.1f}x{bb.YLength:.1f}x{bb.ZLength:.1f}'


def _assembly_of(objs, who):
    asm = next((p for p in objs[0].InList if p.TypeId == 'Assembly::AssemblyObject'), None)
    if asm is None or any(asm not in o.InList for o in objs):
        raise FdmkitError(f'{who}: parts must sit directly in one Assembly')
    return asm


def rigid_group(*parts, name=None):
    """Assembly Rigid Group joint (26.3): the parts (Links of one Assembly) keep their relative
    placements and move as one; replaces chains of Fixed joints."""
    import JointObject
    import UtilsAssembly
    objs = [_obj(p) for p in parts]
    if len(objs) < 2:
        raise FdmkitError('rigid_group: at least 2 parts')
    asm = _assembly_of(objs, 'rigid_group')
    if name:
        _free(name)
    j = UtilsAssembly.getJointGroup(asm).newObject('App::FeaturePython', name or 'RigidGroupJoint')
    JointObject.RigidGroupJoint(j, objs)
    if App.GuiUp and j.ViewObject:
        JointObject.ViewProviderRigidGroupJoint(j.ViewObject)
    _rc(j.Document)
    if _bad(j):
        raise FdmkitError(f'{j.Name}: {j.getStatusString()}')
    return f'{j.Name}: OK {len(objs)} parts in {asm.Name}'


def _the_assembly(assembly):
    if assembly:
        return _obj(assembly)
    asms = [o for o in _doc().Objects if o.TypeId == 'Assembly::AssemblyObject']
    if len(asms) != 1:
        raise FdmkitError(f'{len(asms)} assemblies: name one with assembly=')
    return asms[0]


def snapshot(name, assembly=None):
    """Assembly Snapshot (26.3): store placements and visibility of the Assembly's movable parts
    under name (a state such as 'open'/'locked'); called again with the same name it re-captures."""
    import CommandCreateSnapshot as Snap
    import UtilsAssembly
    asm = _the_assembly(assembly)
    s = _doc().getObject(name)
    if s is None:
        _free(name)
        s = UtilsAssembly.getSnapshotGroup(asm).newObject('App::FeaturePython', name)
        Snap.Snapshot(s)
        if App.GuiUp and s.ViewObject:
            Snap.ViewProviderSnapshot(s.ViewObject)
    elif getattr(getattr(s, 'Proxy', None), 'captureState', None) is None:
        raise FdmkitError(f'{name}: not a snapshot')
    else:
        s.Proxy.captureState(s)
    return f'{s.Name}: OK {len(s.Components)} parts of {asm.Name}'


def snapshot_restore(name, solve=True):
    """Put the Assembly back into a stored snapshot; solve=True re-solves the joints after it
    (joints win over the stored placements of jointed parts)."""
    s = _obj(name)
    if getattr(getattr(s, 'Proxy', None), 'restoreState', None) is None:
        raise FdmkitError(f'{name}: not a snapshot')
    s.SolveOnActivation = solve
    s.Proxy.restoreState(s)
    return f'{s.Name}: restored {len(s.Components)} parts'


# ---------------------------------------------------------------- speed
_focus = {}   # doc Uid -> list of Body names whose recompute is enough


def _focus_objs(d):
    """Objects to recompute and check under focus(): params, the focused Bodies and the active
    one, and new top-level objects (link arrays); None when focus is off."""
    names = _focus.get(d.Uid)
    if not names:
        return None
    try:
        names = list(dict.fromkeys(names + [_body(d).Name]))
    except FdmkitError:
        pass
    objs = [d.getObject(PARAMS)] if d.getObject(PARAMS) else []
    for n in names:
        b = d.getObject(n)
        if b is None:
            continue
        objs.append(b)
        objs.extend(o for o in getattr(b, 'Group', []) if not o.TypeId.startswith('App::'))
    objs.extend(o for o in d.Objects if 'Touched' in o.State and o not in objs
                and o.getParentGeoFeatureGroup() is None and not o.TypeId.startswith('Assembly::'))
    return objs


def _rc(d):
    """Recompute only the focused Bodies (and the params sheet) when focus() is set,
    else the whole document. A full recompute also re-solves every Assembly."""
    objs = _focus_objs(d)
    if objs is None:
        d.recompute()
    else:
        d.recompute(objs)


def _scope(d):
    """Objects whose state matters now: the focused Bodies (+ params), else all."""
    objs = _focus_objs(d)
    return list(d.Objects) if objs is None else objs


def _fix_joint_refs(d):
    """Assembly joints that lost their element ('?FaceN') after a part change. A joint with
    Detach{n} (explicit placement) only needs a valid element: point it at Face1. Any other
    joint would jump to the part origin, so it is left broken and reported."""
    fixed, lost = 0, []
    for o in d.Objects:
        for n in ('1', '2'):
            ref = getattr(o, 'Reference' + n, None)
            if not (ref and ref[0] and ref[1] and any(str(x).startswith('?') or '.?' in str(x) for x in ref[1])):
                continue
            if getattr(o, 'Detach' + n, False):
                setattr(o, 'Reference' + n, (ref[0], ['Face1']))
                fixed += 1
            else:
                lost.append(f'{o.Name}.Reference{n} {ref[1][0]}')
    return fixed, lost


def _show_tips(d):
    """In every Body show only the Tip feature; hide other features and sketches
    (a feature inserted mid-tree otherwise stays visible and hides later cuts)."""
    for b in d.Objects:
        if b.TypeId != 'PartDesign::Body':
            continue
        for o in b.Group:
            vo = getattr(o, 'ViewObject', None)
            if vo is None or o.TypeId.startswith('App::'):
                continue
            want = o == b.Tip
            if vo.Visibility != want:
                vo.Visibility = want


def focus(*bodies):
    """focus('Carriage') - recompute only these Bodies (+ params) until full().
    Use while editing parts of a big document with an Assembly."""
    d = _doc()
    miss = [n for n in bodies if d.getObject(n) is None]
    if miss:
        raise FdmkitError(f'focus: no {miss}')
    _focus[d.Uid] = list(bodies)
    return f'focus: {", ".join(bodies) or "off"}'


def full():
    """Leave focus, recompute everything and solve every Assembly once."""
    d = _doc()
    _focus.pop(d.Uid, None)
    d.recompute()
    fixed, lost = _fix_joint_refs(d)
    d.recompute()
    _show_tips(d)
    out = []
    for a in d.Objects:
        if a.TypeId == 'Assembly::AssemblyObject' and hasattr(a, 'solve'):
            out.append(f'{a.Name} solve {a.solve()}')
    d.recompute()
    bad = [o.Name for o in d.Objects if _bad(o)]
    if fixed:
        out.append(f'{fixed} detached joint refs -> Face1')
    if lost:
        out.append('lost joint refs ' + ', '.join(lost))
    return 'full: ' + ('; '.join(out) or 'no assembly') + (f'; invalid {bad}' if bad else '' if lost else '; OK')


def _toggle_freeze(names, want):
    import FreeCADGui as Gui
    d = _doc()
    objs = []
    for n in names:
        o = d.getObject(n)
        if o is None:
            raise FdmkitError(f'freeze: no {n}')
        objs.append(o)
        objs.extend(x for x in getattr(o, 'Group', []) if not x.TypeId.startswith('App::'))
    objs = [o for o in objs if ('Freezed' in o.getStatusString()) != want]
    if objs:
        Gui.Selection.clearSelection()
        for o in objs:
            Gui.Selection.addSelection(o)
        Gui.runCommand('Std_ToggleFreeze', 0)
        Gui.Selection.clearSelection()
    return len(objs)


def freeze(*names):
    """freeze('Tray', 'StandAssembly') - Std_ToggleFreeze: skip heavy objects in recomputes."""
    return f'freeze: {_toggle_freeze(names, True)} objects'


def thaw(*names):
    """thaw(...) - undo freeze()."""
    return f'thaw: {_toggle_freeze(names, False)} objects'


# Objects that carry no geometry to recompute; freeze_all() leaves them alone so
# link placements (animations) and group membership keep working.
_NO_FREEZE = ('App::Link', 'App::Part', 'App::DocumentObjectGroup',
              'App::DocumentObjectGroupPython', 'App::Origin', 'App::Line',
              'App::Plane', 'App::Point')


def _set_frozen(objs, want):
    import FreeCADGui as Gui
    objs = [o for o in objs if ('Freezed' in o.getStatusString()) != want]
    if objs:
        Gui.Selection.clearSelection()
        for o in objs:
            Gui.Selection.addSelection(o)
        Gui.runCommand('Std_ToggleFreeze', 0)
        Gui.Selection.clearSelection()
    return len(objs)


def freeze_all():
    """Freeze every object except links, parts and groups: a forced recompute (i10g ends
    every render with one) then takes milliseconds and the Assembly solver cannot pull
    moved links back. Undo with thaw_all(), then full()."""
    d = _doc()
    n = _set_frozen([o for o in d.Objects if o.TypeId not in _NO_FREEZE], True)
    return f'freeze_all: {n} objects'


def thaw_all():
    """Thaw every frozen object of the document (marks them touched: run full() next)."""
    d = _doc()
    n = _set_frozen([o for o in d.Objects if 'Freezed' in o.getStatusString()], False)
    return f'thaw_all: {n} objects'


def i10g_video(delay_ms=300):
    """Render the document's i10g Animation to its OutputFilename without blocking the RPC.
    Drops hidden objects from every step (i10g would show hidden links with transparency 1,
    leaving their edges floating) and checks the FreeCAD 26 ShapeAppearance patch.
    Prepare first: steps recorded, camera set, freeze_all(). Wait for ffmpeg to exit."""
    d = _doc()
    a = d.getObject('Animation')
    if a is None or not a.Group:
        raise FdmkitError('i10g_video: no Animation with steps in this document')
    try:
        from freecad.i10g import i10g
    except ImportError:
        raise FdmkitError('i10g_video: Inbetweening (i10g) is not installed') from None
    if not hasattr(i10g, 'getShapeMaterial'):
        raise FdmkitError('i10g_video: i10g lacks the FreeCAD 26 ShapeAppearance patch '
                          '(getShapeMaterial/setShapeMaterial, rules.md "Animations")')
    hidden = {o.Name for o in d.Objects if o.TypeId == 'App::Link' and not o.Visibility}
    pruned = 0
    for s in a.Group:
        st = s.DocState
        drop = hidden.intersection(st)
        if drop:
            for n in drop:
                st.pop(n)
            s.DocState = st
            pruned += len(drop)
    anim = i10g.Animation.getInstance()
    i10g.STATE['animation'] = anim
    from PySide import QtCore
    QtCore.QTimer.singleShot(int(delay_ms), anim.video)
    res = a.CustomResolution or a.Resolution
    return (f'i10g_video: {len(a.Group)} steps, {anim.getTotalFrames()} frames {res} '
            f'@{a.FPS} -> {a.OutputFilename}; {pruned} hidden entries dropped')


# ---------------------------------------------------------------- FreeCAD report
LOG_DIR = os.path.expanduser('~/Library/Logs/fdmkit')
_ERR_ENTRY = re.compile(r'Traceback|Error|Exception|Segmentation fault|Assertion|failed')
_STAMP = re.compile(r'^\d\d:\d\d:\d\d\s')
_report = {'seen': 0, 'pending': []}


def _report_lines():
    """Lines of the GUI Report view; [] without a GUI."""
    if not App.GuiUp:
        return []
    import FreeCADGui as Gui
    from PySide import QtWidgets
    w = Gui.getMainWindow().findChild(QtWidgets.QTextEdit, 'Report view')
    return w.toPlainText().splitlines() if w else []


def _report_scan():
    """Error entries added to the Report view since the last scan (a cleared view starts over).
    They are kept for errors() and appended to LOG_DIR/freecad.log."""
    try:
        lines = _report_lines()
    except Exception:
        return []
    start = _report['seen'] if _report['seen'] <= len(lines) else 0
    _report['seen'] = len(lines)
    entries = []
    for ln in lines[start:]:
        if _STAMP.match(ln) or not entries:
            entries.append([ln])
        else:
            entries[-1].append(ln)
    new = []
    for entry in entries:
        cut = next((i for i, x in enumerate(entry) if x.strip() == '--- code ---'), None)
        e = entry[:cut] if cut else entry      # the RPC server echoes the failing code after its error
        if not _ERR_ENTRY.search(' '.join(e)):
            continue
        last = next((x.strip() for x in reversed(e) if x.strip()), '')
        head = e[0].strip()
        new.append(head if last == head else f'{head} … {last}')
    if new:
        _report['pending'] += new
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, 'freecad.log'), 'a', encoding='utf-8') as f:
                f.write(''.join(f'{time.strftime("%Y-%m-%d")} {x}\n' for x in new))
        except OSError:
            pass
    return new


def errors(keep=False):
    """New errors and tracebacks in FreeCAD's Report view since the last errors() (addons,
    recomputes, the GUI, the RPC server): one line, repeated messages counted. keep=True
    leaves them pending. All of them are also in ~/Library/Logs/fdmkit/freecad.log."""
    _report_scan()
    got = list(_report['pending'])
    if not keep:
        _report['pending'] = []
    if not got:
        return 'errors: none'
    count = {}
    for x in got:
        key = _STAMP.sub('', x).strip()
        count[key] = count.get(key, 0) + 1
    return f'errors: {len(got)} | ' + ' | '.join(f'{k[:220]}' + (f' ×{n}' if n > 1 else '') for k, n in count.items())


# ---------------------------------------------------------------- entry
AUTOSAVE_S = 300
_saved = {}
_rolled_back = {}   # doc name -> True after a call that was rolled back (see undo())


def _autosave(d):
    """Save a document that has a file at most every AUTOSAVE_S seconds."""
    now = time.time()
    if d.FileName and now - _saved.get(d.Name, 0) >= AUTOSAVE_S:
        d.save()
        _saved[d.Name] = now


def _ns():
    """Namespace of run(): the fdmkit calls plus App and, with a GUI, Gui."""
    ns = {k: globals()[k] for k in __all__}
    ns['App'] = App
    try:
        import FreeCADGui as Gui
        ns['Gui'] = Gui
    except ImportError:
        pass
    return ns


def _alive(d):
    """False once the document was closed inside the call (reopen())."""
    try:
        return bool(d.Name)
    except Exception:
        return False


def run(expr):
    """Run 'a(); b(); c()' as ONE transaction: one result per call, ' ; '-joined.
    Any failure rolls the whole batch back and names the failing step.
    '?expr' is read-only: its document changes are discarded, no recompute, no autosave."""
    expr = expr.strip()
    if expr.replace(' ', '') in ('errors()', 'errors(keep=True)'):
        return _run(expr)
    # the Report view gets messages from Qt's event loop, so an error of the previous call often
    # arrives only now: count everything new since the last call
    n = len(_report_scan())
    r = _run(expr)
    n += len(_report_scan())
    return r + (f' | FreeCAD report: {n} new error{"s" * (n > 1)} since the last call, errors() lists them'
                if n else '')


def _run(expr):
    if 'exportPageAsPdf' in expr:
        return 'ERR exportPageAsPdf crashes FreeCAD 26.3; use TechDrawGui.exportPageAsSvg'
    try:
        ast.parse(expr[1:].strip() if expr.startswith('?') else expr)
    except SyntaxError as e:
        hint = ("; '?' marks the whole expr as read-only and goes only at its very start,"
                " never inside a batch" if re.search(r'[;\n]\s*\?', expr) else '')
        return f'ERR parse: {e.msg} at col {e.offset}{hint}'
    if expr.startswith('?'):
        d = App.ActiveDocument
        if d:   # a read must not change the model: whatever it wrote is aborted below
            d.openTransaction('?read')
        try:
            ns = _ns()
            mod = ast.parse(expr[1:].strip())
            last = mod.body.pop() if mod.body and isinstance(mod.body[-1], ast.Expr) else None
            exec(compile(mod, '<fdmkit?>', 'exec'), ns)
            r = eval(compile(ast.Expression(last.value), '<fdmkit?>', 'eval'), ns) if last else None
            return 'OK' if r is None else _line(str(r))
        except Exception as e:
            return _line(f'ERR read: {type(e).__name__}: {e}')
        finally:
            if d and _alive(d):
                d.abortTransaction()
    d = None if re.fullmatch(r'\s*undo\s*\(\s*\)\s*', expr) else App.ActiveDocument
    if d:
        d.openTransaction(expr[:60])
    out, step = [], 0
    try:
        ns = _ns()
        for step, node in enumerate(ast.parse(expr).body, 1):
            if isinstance(node, ast.Expr):
                r = eval(compile(ast.Expression(node.value), '<fdmkit>', 'eval'), ns)
                out.append('OK' if r is None else str(r))
            else:
                exec(compile(ast.Module([node], []), '<fdmkit>', 'exec'), ns)
        if d and _alive(d):
            d.commitTransaction()
            _rolled_back.pop(d.Name, None)
            try:
                _autosave(d)
            except Exception as e:     # committed; only the save failed
                out.append(f'WARN autosave failed: {e}')
        return _line(' ; '.join(out) or 'OK')
    except Exception as e:
        same = d is not None and _alive(d) and App.ActiveDocument == d
        if d and _alive(d):
            d.abortTransaction()
            _rc(d)
            _rolled_back[d.Name] = True
        msg = str(e) if isinstance(e, FdmkitError) else f'{type(e).__name__}: {e}'
        if same or d is None:
            tail = ' (batch rolled back)' if step > 1 else ''
        else:   # reopen()/new()/closeDocument inside the batch: the rollback reached only the old document
            tail = ' (the active document changed during the call: earlier steps may NOT be rolled back)'
        return _line(f'ERR step {step}: {msg}' + tail)


def _line(s):
    """One line: FreeCAD expression errors span several lines."""
    return ' '.join(x.strip() for x in s.splitlines() if x.strip())


def _boot():
    old = getattr(App, '_fdmkit_observer', None)
    if old:
        App.removeDocumentObserver(old)
    App._fdmkit_observer = None
    if int(App.Version()[0]) < 27:   # 27.1 updates alias dependents (and chains) by itself
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


# the CNC/CAM checks and the selftest live in their own modules; they use the helpers above
from .machining import (CNC_HOLES, CNC_LATHE_MIN_GROOVE, CNC_MAX_DRILL_LD,  # noqa: E402,F401
                        CNC_MAX_MILL_LD, CNC_MAX_REACH_D, CNC_MIN_WALL,
                        cam_del, cam_job, cam_sim, cam_slot, cnc, cnc_restore, cnc_show)
from .tests import selftest  # noqa: E402

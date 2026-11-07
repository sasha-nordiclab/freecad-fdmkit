"""TechDraw dimensions placed and checked by computation: no export, no pictures.

Frames, probed on FreeCAD 27.1 (ORWO 828 sheet 01, 2026-11-07), all in page millimetres:
- label centre = (view.X + dim.X, view.Y + dim.Y), Y up (QGIDatumLabel is set from its centre);
- dim.getArrowPositions(): view frame, unscaled, Y up (times view.Scale);
- dim.getLinearPoints(), view.getVisibleVertexes()/getVisibleEdges(): view frame, scaled, Y DOWN;
- ViewObject.Fontsize is the cap height: text width = QFontMetricsF advance * Fontsize / capHeight;
- an ISO linear label sits `off` beside its dimension line (2.7 at Fontsize 2.8, measured from the
  arrows of the page): above a horizontal line, left of a vertical one.
Layout rules (ISO 129-1 practice): first line `first` mm off the view outline, further lines
`pitch` mm apart, the shortest span nearest the part, spans that do not overlap share a line,
a label wider than its span goes past the far end. Labels must not touch labels, visible edges,
other dimension/extension lines, other views, the sheet frame or a keepout box.
Read view geometry one call after a page refresh (hidden lines are computed asynchronously).
"""
import math
import re

import FreeCAD as App

LINEAR = ('DistanceX', 'DistanceY')
FRAME = (20, 10, 10, 10)        # ISO 5457 drawing frame: left, bottom, right, top
_SPEC = re.compile(r'%[-+ #0]*\d*(?:\.(\d+))?([fFeEgGw])')


def _page(page):
    p = App.ActiveDocument.getObject(page) if isinstance(page, str) else page
    if p is None or p.TypeId != 'TechDraw::DrawPage':
        raise ValueError(f'no TechDraw page {page!r}')
    return p


def _dims(p):
    return [v for v in p.Views if v.TypeId == 'TechDraw::DrawViewDimension']


def _parts(p):
    return [v for v in p.Views if hasattr(v, 'getVisibleEdges')]


def _sep():
    try:
        from PySide import QtCore
        return str(QtCore.QLocale().decimalPoint())
    except Exception:
        return '.'


def _text(dim, value=None, sep=None):
    """The label as TechDraw draws it from FormatSpec (%.Nf, %.Nw = no trailing zeros)."""
    spec = dim.FormatSpec
    if getattr(dim, 'Arbitrary', False):
        return spec
    m = _SPEC.search(spec)
    if not m:
        return spec
    v = dim.getRawValue() if value is None else value
    n = int(m.group(1) or 2)
    s = f'{v:.{n}f}'
    if m.group(2) == 'w' and '.' in s:
        s = s.rstrip('0').rstrip('.')
    elif m.group(2) not in 'fFw':
        s = (m.group(0)) % v
    return spec[:m.start()] + s.replace('.', sep or _sep()) + spec[m.end():]


def _width(text, fs, font):
    try:
        from PySide import QtGui
        f = QtGui.QFont(font)
        f.setPixelSize(1000)
        fm = QtGui.QFontMetricsF(f)
        return fm.horizontalAdvance(text) * fs / fm.capHeight()
    except Exception:
        return 0.65 * fs * len(text)


def _collect(p):
    views = {v.Name for v in _parts(p)}
    out = []
    for o in _dims(p):
        refs = o.References2D
        if not refs or refs[0][0].Name not in views:
            continue
        vo = getattr(o, 'ViewObject', None)
        fs = vo.Fontsize.Value if vo else 3.5
        t = _text(o)
        out.append(dict(o=o, v=refs[0][0], kind=o.Type, text=t, w=_width(t, fs, vo.Font if vo else ''),
                        h=1.4 * fs, fs=fs, X=o.X.Value, Y=o.Y.Value))
    return out


def _offset(items):
    """Label centre to dimension line, from the arrows the page drew (median); None if unknown."""
    xs = []
    for it in items:
        if it['kind'] not in LINEAR:
            continue
        try:
            a = it['o'].getArrowPositions()
        except Exception:
            continue
        if len(a) < 2:
            continue
        s = it['v'].Scale
        xs.append(it['Y'] - a[0].y * s if it['kind'] == 'DistanceX' else a[0].x * s - it['X'])
    xs.sort()
    return xs[len(xs) // 2] if xs else None


def _geo(it, off):
    v = it['v']
    vx, vy = v.X.Value, v.Y.Value
    cx, cy = vx + it['X'], vy + it['Y']
    w, h, k = it['w'], it['h'], it['kind']
    it['rect'] = ((cx - h / 2, cy - w / 2, cx + h / 2, cy + w / 2) if k == 'DistanceY'
                  else (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    if k not in LINEAR:
        return
    if 'pts' not in it:
        it['pts'] = [(vx + q.x, vy - q.y) for q in it['o'].getLinearPoints()][:2]
    pts = it['pts']
    if k == 'DistanceX':
        ly = cy - off
        a, b = sorted(x for x, _ in pts)
        it['line'] = ((a, ly), (b, ly))
        it['ext'] = [((x, y), (x, ly)) for x, y in pts]
    else:
        lx = cx + off
        a, b = sorted(y for _, y in pts)
        it['line'] = ((lx, a), (lx, b))
        it['ext'] = [((x, y), (lx, y)) for x, y in pts]


def _span(it):
    i = 0 if it['kind'] == 'DistanceX' else 1
    return tuple(sorted(q[i] for q in it['pts']))


class _Grid:
    """Points bucketed per 1 mm cell; hit(rect) = any point strictly inside."""

    def __init__(self, pts):
        self.g = {}
        for x, y in pts:
            self.g.setdefault((math.floor(x), math.floor(y)), []).append((x, y))

    def hit(self, r):
        for i in range(math.floor(r[0]), math.floor(r[2]) + 1):
            for j in range(math.floor(r[1]), math.floor(r[3]) + 1):
                for x, y in self.g.get((i, j), ()):
                    if r[0] < x < r[2] and r[1] < y < r[3]:
                        return True
        return False


def _edge_pts(v, step=0.4):
    vx, vy = v.X.Value, v.Y.Value
    pts = []
    for e in v.getVisibleEdges():
        try:
            pts.extend((vx + q.x, vy - q.y) for q in e.discretize(Distance=step))
        except Exception:
            pass
    return pts


def _bbox(pts):
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _ov(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _seg_hits(r, a, b):
    """Axis-aligned segment a-b crosses the open rectangle r."""
    if abs(a[0] - b[0]) < 1e-9:
        return r[0] < a[0] < r[2] and min(a[1], b[1]) < r[3] and max(a[1], b[1]) > r[1]
    if abs(a[1] - b[1]) < 1e-9:
        return r[1] < a[1] < r[3] and min(a[0], b[0]) < r[2] and max(a[0], b[0]) > r[0]
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.4))
    return any(r[0] < a[0] + (b[0] - a[0]) * i / n < r[2] and r[1] < a[1] + (b[1] - a[1]) * i / n < r[3]
               for i in range(n + 1))


def _segs(it):
    return ([it['line']] if 'line' in it else []) + it.get('ext', [])


def _hits(it, items, grid, ctx, gap=0.5):
    """Why this label/its lines conflict with the rest; [] = clean."""
    r = it['rect']
    g = (r[0] - gap, r[1] - gap, r[2] + gap, r[3] + gap)
    out = []
    x0, y0, x1, y1 = ctx['frame']
    if r[0] < x0 or r[1] < y0 or r[2] > x1 or r[3] > y1:
        out.append('off sheet')
    if any(_ov(r, k) for k in ctx['keepout']):
        out.append('keepout')
    own = it['v'].Name
    out += ['on view ' + n for n, b in ctx['boxes'].items() if n != own and _ov(r, b)]
    if grid.hit(r):
        out.append('on edge')
    for o in items:
        if o is it:
            continue
        if _ov(g, o['rect']):
            out.append('label ~ ' + o['short'])
        elif any(_seg_hits(r, *s) for s in _segs(o)):
            out.append('on line of ' + o['short'])
        elif any(_seg_hits(o['rect'], *s) for s in _segs(it)):
            out.append('line over ' + o['short'])
        if 'line' in it and 'line' in o and _cross(it['line'], o['line']):
            out.append('crosses ' + o['short'])
    return out


def _cross(a, b):
    """A horizontal and a vertical dimension line cross."""
    h, v = (a, b) if abs(a[0][1] - a[1][1]) < 1e-9 else (b, a)
    if abs(h[0][1] - h[1][1]) > 1e-9 or abs(v[0][0] - v[1][0]) > 1e-9:
        return False
    return (min(h[0][0], h[1][0]) < v[0][0] < max(h[0][0], h[1][0])
            and min(v[0][1], v[1][1]) < h[0][1] < max(v[0][1], v[1][1]))


def _context(p, items, keepout):
    W, H = p.Template.Width.Value, p.Template.Height.Value
    l, b, r, t = FRAME
    edges = {v.Name: _edge_pts(v) for v in _parts(p)}
    pre = p.Name
    for it in items:
        n = it['o'].Name
        it['short'] = n[len(pre):] if n.startswith(pre) and len(n) > len(pre) else n
    return dict(frame=(l, b, W - r, H - t), keepout=[tuple(k) for k in keepout],
                boxes={n: _bbox(ps) for n, ps in edges.items() if ps},
                grid=_Grid([q for ps in edges.values() for q in ps]))


def _prepare(page, keepout):
    p = _page(page)
    items = _collect(p)
    off = _offset(items)
    if off is None:
        off = 0.96 * (items[0]['fs'] if items else 3.5)
    for it in items:
        _geo(it, off)
    return p, items, off, _context(p, items, keepout)


def _report(p, items, ctx):
    bad = []
    for it in items:
        h = _hits(it, items, ctx['grid'], ctx)
        if h:
            bad.append(f"{it['short']}: {', '.join(dict.fromkeys(h))}")
    if not bad:
        return f'dim_check {p.Name}: OK {len(items)} dims'
    return f'dim_check {p.Name}: ERR {len(bad)} | ' + ' | '.join(bad)


def dim_check(page, keepout=()):
    """Conflicts of every dimension label on the page: other labels, visible edges, other
    dimension/extension lines, other views, sheet frame, keepout boxes (x0, y0, x1, y1 page mm, Y up);
    and dimension lines that cross. Pure computation from the native objects."""
    p, items, _, ctx = _prepare(page, keepout)
    return _report(p, items, ctx)


def _pack(spans, gap=1.0):
    """spans [(a, b, label_len)], shortest first -> [(lane, along)]: a label wider than its span
    goes past the far end; spans that do not overlap share a lane."""
    lanes, out = [], []
    for a, b, L in spans:
        along = (a + b) / 2 if L + 2 * gap <= b - a else b + L / 2 + 1.5
        occ = (min(a, along - L / 2) - gap, max(b, along + L / 2) + gap)
        i = next((i for i, ln in enumerate(lanes) if all(occ[1] <= o0 or occ[0] >= o1 for o0, o1 in ln)),
                 len(lanes))
        if i == len(lanes):
            lanes.append([])
        lanes[i].append(occ)
        out.append((i, along))
    return out


def _side(it, B):
    if it['kind'] == 'DistanceX':
        return 'top' if sum(y for _, y in it['pts']) / 2 > (B[1] + B[3]) / 2 else 'bottom'
    return 'right' if sum(x for x, _ in it['pts']) / 2 > (B[0] + B[2]) / 2 else 'left'


def _limit(side, B, ctx, vname):
    """Farthest page coordinate a lane on this side may reach: frame, keepout, other views."""
    x0, y0, x1, y1 = ctx['frame']
    obs = list(ctx['keepout']) + [b for n, b in ctx['boxes'].items() if n != vname]
    xo = [o for o in obs if o[0] < B[2] and o[2] > B[0]]
    yo = [o for o in obs if o[1] < B[3] and o[3] > B[1]]
    if side == 'top':
        return min([y1] + [o[1] for o in xo if o[1] >= B[3]])
    if side == 'bottom':
        return max([y0] + [o[3] for o in xo if o[3] <= B[1]])
    if side == 'right':
        return min([x1] + [o[0] for o in yo if o[0] >= B[2]])
    return max([x0] + [o[2] for o in yo if o[2] <= B[0]])


def _line(side, B, lane, first, step):
    return {'top': B[3] + first + lane * step, 'bottom': B[1] - first - lane * step,
            'right': B[2] + first + lane * step, 'left': B[0] - first - lane * step}[side]


def _capacity(side, B, lim, first, step, off, h):
    """Lanes that fit: the far edge of lane i (label or line) stays inside `lim`."""
    n = 0
    while n < 50:
        ln = _line(side, B, n, first, step)
        far = {'top': ln + off + h / 2, 'bottom': ln - 1, 'right': ln + 1, 'left': ln - off - h / 2}[side]
        if (side in ('top', 'right') and far > lim) or (side in ('bottom', 'left') and far < lim):
            return n
        n += 1
    return n


def _depth(it, side, B):
    """How deep inside the view the measured points lie, seen from this side."""
    xs, ys = [x for x, _ in it['pts']], [y for _, y in it['pts']]
    return {'top': B[3] - max(ys), 'bottom': min(ys) - B[1], 'right': B[2] - max(xs), 'left': min(xs) - B[0]}[side]


def _lanes(grp):
    grp.sort(key=lambda t: _span(t)[1] - _span(t)[0])
    plan = _pack([(*_span(t), t['w']) for t in grp])
    return plan, 1 + max((lane for lane, _ in plan), default=-1)


def _assign(items, ctx, off, sides, first, pitch, fixed):
    """Lanes per view and axis within the room each side has. On overflow the dimension whose points
    lie deepest in the view goes to the other side if it fits there, else inside. -> inside list."""
    inside = []
    by = {}
    for it in items:
        by.setdefault((it['v'].Name, it['kind']), []).append(it)
    for (vn, kind), grp in by.items():
        B = ctx['boxes'][vn]
        step = max(pitch, grp[0]['h'] + 2)
        pair = ('top', 'bottom') if kind == 'DistanceX' else ('right', 'left')
        cap = {s: _capacity(s, B, _limit(s, B, ctx, vn), first, step, off, grp[0]['h']) for s in pair}
        on = {s: [t for t in grp if sides[t['o'].Name] == s] for s in pair}
        while True:
            over = next((s for s in pair if _lanes(on[s])[1] > cap[s]), None)
            if over is None:
                break
            movable = [t for t in on[over] if t['o'].Name not in fixed] or on[over]
            # overall sizes stay outside: the shortest span goes first, the deeper one on a tie
            t = min(movable, key=lambda t: (round(_span(t)[1] - _span(t)[0], 1), -_depth(t, over, B)))
            on[over].remove(t)
            other = pair[1] if over == pair[0] else pair[0]
            if t['o'].Name in fixed:
                inside.append(t)
                continue
            if _lanes(on[other] + [t])[1] <= cap[other]:
                on[other].append(t)
                sides[t['o'].Name] = other
                continue
            # a larger span displaces the smallest free one of the other side
            free = [s for s in on[other] if s['o'].Name not in fixed]
            s = min(free, key=lambda s: _span(s)[1] - _span(s)[0]) if free else None
            rest = [x for x in on[other] if x is not s] + [t]
            if s is not None and _span(s)[1] - _span(s)[0] < _span(t)[1] - _span(t)[0] \
                    and _lanes(rest)[1] <= cap[other]:
                on[other] = rest
                sides[t['o'].Name] = other
                inside.append(s)
            else:
                inside.append(t)
        vx, vy = grp[0]['v'].X.Value, grp[0]['v'].Y.Value
        for side in pair:
            plan, _ = _lanes(on[side])
            for it, (lane, along) in zip(on[side], plan):
                line = _line(side, B, lane, first, step)
                if kind == 'DistanceX':
                    it['X'], it['Y'] = along - vx, line + off - vy
                else:
                    it['X'], it['Y'] = line - off - vx, along - vy
                _geo(it, off)
    return inside


def _slide(it, items, ctx, off):
    """Shift a lane label along its own line (within the span, then past either end) until clean."""
    a, b = _span(it)
    k = 'X' if it['kind'] == 'DistanceX' else 'Y'
    v0 = it[k]
    for d in sorted({i * 1.0 for i in range(-int(b - a) - 20, int(b - a) + 21)}, key=abs):
        it[k] = v0 + d
        _geo(it, off)
        if not _hits(it, items, ctx['grid'], ctx):
            return True
    it[k] = v0
    _geo(it, off)
    return False


def dim_layout(page, inside=(), sides=None, first=10, pitch=7, keepout=(), apply=True):
    """Place linear dimensions (DistanceX/DistanceY) on ISO lanes outside their view (rules in the
    module doc) within the room each side has (frame, keepout, other views). On overflow the
    dimension measured deepest inside the view moves to the other side, else inside. `inside` names
    stay inside; inside, Diameter/Radius/Angle labels move only when they conflict (nearest clean
    spot, 1 mm grid). Lane labels slide along their line off other lines. `sides` {name: side}
    forces a side. apply=False plans only."""
    p, items, off, ctx = _prepare(page, keepout)
    inside = set(inside)
    outer = [it for it in items if it['kind'] in LINEAR and it['o'].Name not in inside]
    sides = dict(sides or {})
    fixed = set(sides)
    for it in outer:
        sides.setdefault(it['o'].Name, _side(it, ctx['boxes'][it['v'].Name]))
    demoted = _assign(outer, ctx, off, sides, first, pitch, fixed)
    outer = [it for it in outer if it not in demoted]
    for it in outer:
        if _hits(it, items, ctx['grid'], ctx):
            _slide(it, items, ctx, off)
    moved = 0
    for it in items:
        if it in outer:
            continue
        X0, Y0 = it['X'], it['Y']
        best = None
        for dy in sorted(range(-40, 41), key=abs):
            for dx in (0, 2, -2, 4, -4, 8, -8, 12, -12):
                it['X'], it['Y'] = X0 + dx, Y0 + dy
                _geo(it, off)
                if not _hits(it, items, ctx['grid'], ctx):
                    best = (X0 + dx, Y0 + dy)
                    break
            if best:
                break
        it['X'], it['Y'] = best or (X0, Y0)
        _geo(it, off)
        moved += bool(best and best != (X0, Y0))
    if apply:
        for it in items:
            o = it['o']
            if abs(o.X.Value - it['X']) > 1e-6 or abs(o.Y.Value - it['Y']) > 1e-6:
                o.X, o.Y = it['X'], it['Y']
                o.recompute()
    count = {}
    for it in outer:
        count[sides[it['o'].Name]] = count.get(sides[it['o'].Name], 0) + 1
    lanes = ', '.join(f'{k} {v}' for k, v in sorted(count.items()))
    head = (f"dim_layout {p.Name}: {len(outer)} on lanes ({lanes}), {moved} inside moved"
            + (f", no room outside: {', '.join(t['short'] for t in demoted)}" if demoted else '')
            + ('' if apply else ', plan only'))
    return head + ' | ' + _report(p, items, ctx)


def _vertex(v, x, y, tol=0.05):
    s = v.Scale
    P = [(i, q.x / s, -q.y / s) for i, q in enumerate(v.getVisibleVertexes())]
    if not P:
        raise ValueError(f'{v.Name} has no vertices yet: refresh the page, read in the next call')
    i, px, py = min(P, key=lambda t: (t[1] - x) ** 2 + (t[2] - y) ** 2)
    if math.hypot(px - x, py - y) > tol:
        raise ValueError(f'no vertex at ({x:.3f}, {y:.3f}) in {v.Name}; nearest ({px:.3f}, {py:.3f})')
    return f'Vertex{i}'


def _circle(v, r, x, y, tol=0.01):
    s = v.Scale
    c = []
    for i, e in enumerate(v.getVisibleEdges()):
        cu = getattr(e, 'Curve', None)
        if cu is not None and hasattr(cu, 'Radius') and abs(cu.Radius / s - r) < tol:
            b = e.BoundBox.Center
            c.append(((b.x / s - x) ** 2 + (-b.y / s - y) ** 2, f'Edge{i}'))
    if not c:
        raise ValueError(f'no circle R{r:.3f} in {v.Name}')
    return min(c)[1]


def dim_add(page, view, name, kind, refs, fmt='%.2f'):
    """Native dimension on view vertices picked by view coordinates (unscaled mm, Y up):
    DistanceX/DistanceY/Distance refs = ((x1, y1), (x2, y2)); Diameter/Radius refs = (r, x, y) of the
    circle (radius, centre near x, y). Style copied from the page's first dimension; place it with
    dim_layout()."""
    p = _page(page)
    d = App.ActiveDocument
    v = d.getObject(view) if isinstance(view, str) else view
    sub = (_circle(v, *refs),) if kind in ('Diameter', 'Radius') else tuple(_vertex(v, *q) for q in refs)
    o = d.getObject(name) or d.addObject('TechDraw::DrawViewDimension', name)
    o.Type = kind
    o.References2D = [(v, sub)]
    o.FormatSpec = fmt
    if o not in p.Views:
        p.addView(o)
    ref = next((x for x in _dims(p) if x is not o), None)
    if ref is not None and getattr(o, 'ViewObject', None):
        for a in ('Fontsize', 'Arrowsize', 'LineWidth', 'Font', 'Color'):
            try:
                setattr(o.ViewObject, a, getattr(ref.ViewObject, a))
            except Exception:
                pass
    o.recompute()
    return f'dim_add: {o.Name} {kind} {_text(o)} on {v.Name} {sub}'


def title_block(page):
    """Title block box (x0, y0, x1, y1 page mm, Y up) read from the template SVG: the text cluster
    in the lower right part, widened to the frame. None if the template has no such texts."""
    p = _page(page)
    W, H = p.Template.Width.Value, p.Template.Height.Value
    try:
        s = open(p.Template.Template, encoding='utf-8').read()
    except Exception:
        return None
    pts = [(float(a), float(b)) for a, b in re.findall(r'<text[^>]*?\bx="([\d.]+)"[^>]*?\by="([\d.]+)"', s)]
    tb = [(x, y) for x, y in pts if x > W / 3 and 0.7 * H < y < H - FRAME[1]]
    if not tb:
        return None
    return (min(x for x, _ in tb) - 3, FRAME[1], W - FRAME[2], H - (min(y for _, y in tb) - 4))


def _annot_box(o):
    fs = getattr(o, 'TextSize', 3.5)
    fs = getattr(fs, 'Value', fs)
    lines = [str(t) for t in getattr(o, 'Text', [])] or ['']
    w = max(_width(t, fs, getattr(o, 'Font', '')) for t in lines)
    ls = getattr(o, 'LineSpace', 80)
    h = len(lines) * fs * (1 + max(ls, 20) / 100.0)
    x, y = o.X.Value, o.Y.Value
    return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def _grow(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _clusters(env, i):
    """Names grouped by overlapping intervals on axis i (0 = x -> columns, 1 = y -> rows)."""
    out = []
    for n in sorted(env, key=lambda n: env[n][i]):
        a, b = env[n][i], env[n][i + 2]
        if out and a < out[-1][2]:
            out[-1][0].append(n)
            out[-1][2] = max(out[-1][2], b)
        else:
            out.append([[n], a, b])
    return out


def _field(frame, obst, need):
    """Largest free rectangle inside frame avoiding obstacles; prefer one that fits `need` (w, h)."""
    l, b, r, t = frame
    xs0 = [l] + [o[2] for o in obst if l < o[2] < r]
    xs1 = [r] + [o[0] for o in obst if l < o[0] < r]
    ys0 = [b] + [o[3] for o in obst if b < o[3] < t]
    ys1 = [t] + [o[1] for o in obst if b < o[1] < t]
    best = None
    for x0 in xs0:
        for x1 in xs1:
            for y0 in ys0:
                for y1 in ys1:
                    if x1 <= x0 or y1 <= y0:
                        continue
                    R = (x0, y0, x1, y1)
                    if any(_ov(R, o) for o in obst):
                        continue
                    key = ((x1 - x0) >= need[0] and (y1 - y0) >= need[1], (x1 - x0) * (y1 - y0))
                    if best is None or key > best[0]:
                        best = (key, R)
    return best[1] if best else frame


def _spread(groups, lo, hi, maxgap):
    """groups [[names, a, b]] on one axis -> ({name: shift}, free gap): equal gaps <= maxgap, centred."""
    total = sum(g[2] - g[1] for g in groups)
    n = len(groups)
    gap = (hi - lo - total) / (n + 1)
    inner = max(min(gap, maxgap), 3) if n > 1 else 0
    pos = lo + (hi - lo - total - inner * (n - 1)) / 2
    out = {}
    for names, a, b in groups:
        for nm in names:
            out[nm] = pos - a
        pos += (b - a) + inner
    return out, gap


def view_layout(page, keepout=(), maxgap=25, attach=12, apply=True):
    """Place the part views of a page near the centre of the free drawing field, by computation.
    Field = sheet frame minus the template title block, free annotations (notes, BOM) and `keepout`
    boxes (x0, y0, x1, y1 page mm, Y up). A view's envelope covers its visible edges and its
    dimensions (labels, lines, extension lines) plus annotations within `attach` mm (captions), which
    move with it. Views overlapping in x form columns, in y rows; one shift per column / row keeps
    projection alignment. Columns and rows get equal gaps (at most `maxgap`), the group is centred.
    Refresh the page one call before (needs visible edges). Ends with dim_check. apply=False plans."""
    p = _page(page)
    parts = _parts(p)
    empty = [v.Name for v in parts if not v.getVisibleEdges()]
    if empty:
        raise RuntimeError('view_layout: no visible edges in ' + ', '.join(empty) + '; refresh the page first')
    items = _collect(p)
    off = _offset(items)
    off = off if off is not None else 0.96 * (items[0]['fs'] if items else 3.5)
    env = {v.Name: _bbox(_edge_pts(v)) for v in parts}
    for it in items:
        _geo(it, off)
        n = it['v'].Name
        env[n] = _grow(env[n], it['rect'])
        for s in ([it['line']] if 'line' in it else []) + it.get('ext', []):
            env[n] = _grow(env[n], (min(s[0][0], s[1][0]), min(s[0][1], s[1][1]),
                                    max(s[0][0], s[1][0]), max(s[0][1], s[1][1])))
    obst = [tuple(k) for k in keepout]
    tb = title_block(p)
    if tb:
        obst.append(tb)
    follow = {}
    for o in p.Views:
        if o.TypeId != 'TechDraw::DrawViewAnnotation':
            continue
        box = _annot_box(o)
        short = len(getattr(o, 'Text', [])) <= 3 and not (tb and _ov(box, tb))
        near = [n for n, e in env.items() if short
                and _ov(box, (e[0] - attach, e[1] - attach, e[2] + attach, e[3] + attach))]
        if short and not near:      # caption above/below a view: centre within its x range
            near = [n for n, e in env.items() if e[0] <= o.X.Value <= e[2]]
        if near:
            n = min(near, key=lambda n: (abs((env[n][0] + env[n][2]) / 2 - o.X.Value),
                                         min(abs(env[n][1] - o.Y.Value), abs(env[n][3] - o.Y.Value))))
            follow[o.Name] = n
            env[n] = _grow(env[n], box)
        else:
            obst.append(box)
    W, H = p.Template.Width.Value, p.Template.Height.Value
    frame = (FRAME[0] + 2, FRAME[1] + 2, W - FRAME[2] - 2, H - FRAME[3] - 2)
    cols, rows = _clusters(env, 0), _clusters(env, 1)
    need = (sum(c[2] - c[1] for c in cols), sum(r[2] - r[1] for r in rows))
    F = _field(frame, obst, need)
    dx, gx = _spread(cols, F[0], F[2], maxgap)
    dy, gy = _spread(rows, F[1], F[3], maxgap)
    moves = {n: (round(dx[n], 2), round(dy[n], 2)) for n in env}
    warn = [f'does not fit field (need {need[0]:.0f} x {need[1]:.0f})'] if gx < 0 or gy < 0 else []
    if not apply:
        return dict(field=[round(x, 1) for x in F], moves=moves, follow=follow, warn=warn)
    d = App.ActiveDocument
    for v in parts:
        v.X, v.Y = v.X.Value + moves[v.Name][0], v.Y.Value + moves[v.Name][1]
    for a, n in follow.items():
        o = d.getObject(a)
        o.X, o.Y = o.X.Value + moves[n][0], o.Y.Value + moves[n][1]
    p.recompute()
    moved = ', '.join(f'{n[len(p.Name):] or n} {m[0]:+.1f}/{m[1]:+.1f}' for n, m in moves.items())
    return f'view_layout {p.Name}: field {[round(x) for x in F]} | {moved} | ' + (
        ' '.join(warn) + ' | ' if warn else '') + dim_check(p, keepout=obst)


def _selftest():
    """Pure checks (no page needed): label text, lane packing, point grid, segment hits."""
    class F:
        FormatSpec, Arbitrary = 'Ø%.3f +0.025/0', False
    assert _text(F, 43.6, ',') == 'Ø43,600 +0.025/0'
    F.FormatSpec = '%.2w'
    assert _text(F, 52.0, ',') == '52' and _text(F, 4.25, ',') == '4,25'
    assert _pack([(0, 10, 4), (20, 30, 4), (0, 30, 4)]) == [(0, 5.0), (0, 25.0), (1, 15.0)]
    assert _pack([(0, 3, 6)])[0][1] == 3 + 3 + 1.5          # wider than the span: past the far end
    g = _Grid([(5.5, 5.5)])
    assert g.hit((5, 5, 6, 6)) and not g.hit((6, 6, 7, 7))
    assert _seg_hits((0, 0, 2, 2), (1, -1), (1, 3)) and not _seg_hits((0, 0, 2, 2), (3, -1), (3, 3))
    assert _cross(((0, 1), (4, 1)), ((2, 0), (2, 3))) and not _cross(((0, 1), (4, 1)), ((5, 0), (5, 3)))
    sp, _ = _spread([[['a'], 0, 10], [['b'], 20, 40]], 0, 100, 20)
    assert abs(sp['a'] - 25) < 1e-9 and abs(sp['b'] - 35) < 1e-9   # 30 wide + gap 20, centred
    assert [c[0] for c in _clusters({'a': (0, 0, 10, 5), 'b': (5, 9, 12, 20), 'c': (20, 0, 30, 5)}, 0)] == [['a', 'b'], ['c']]
    assert _field((0, 0, 100, 100), [(50, 0, 100, 30)], (40, 40)) == (0, 30, 100, 100)
    return 'dim_math OK'

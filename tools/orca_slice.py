"""Slice an STL with OrcaSlicer CLI using the user's own presets (read-only copies); print time and grams.

usage: orca_slice.py model.stl ["process preset"] [key=value+key=value ...]
  each extra argument is one variant of overrides; '' = the preset as is.
  default process: 0.20mm NordicLab 0.6 Ballance; env ORCA_MACHINE / ORCA_FILAMENT override the printer / filament.
Temporary files go next to the STL and are deleted afterwards.
"""
import json, os, re, subprocess, sys, pathlib, shutil
ORCA = '/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer'
USER = pathlib.Path.home() / 'Library/Application Support/OrcaSlicer/user/default'
SYS = pathlib.Path('/Applications/OrcaSlicer.app/Contents/Resources/profiles/BBL')
MACHINE = os.environ.get('ORCA_MACHINE', 'Bambu Lab A1 0.4 nozzle - NordicLab')
FILAMENT = os.environ.get('ORCA_FILAMENT', 'AzureFilm PETG HF')
PROCESS = '0.20mm NordicLab 0.6 Ballance'


def load(kind, name):
    for base in (USER, SYS):
        p = base / kind / (name + '.json')
        if p.exists():
            d = json.loads(p.read_text())
            if d.get('inherits'):
                parent = load(kind, d['inherits']); parent.update(d); d = parent
            return d
    raise FileNotFoundError(f'{kind}/{name}')


def flat(kind, name, over, out):
    top = json.loads(next((b / kind / (name + '.json')) for b in (USER, SYS) if (b / kind / (name + '.json')).exists()).read_text())
    d = load(kind, name); d['inherits'] = top.get('inherits', ''); d['from'] = top.get('from', 'User')
    if kind != 'machine':                       # copies only: let the user's printer accept them
        d['compatible_printers'] = [MACHINE] + ([PARENT] if PARENT else []); d['compatible_printers_condition'] = ''
    d.update(over)
    out.write_text(json.dumps(d, indent=1)); return out


def run(stl, process, spec):
    HERE = pathlib.Path(stl).resolve().parent
    over = dict(a.split('=', 1) for a in spec.split('+') if a); over.setdefault('curr_bed_type', 'Textured PEI Plate')
    tag = abs(hash((stl, process, spec)))
    m = flat('machine', MACHINE, {}, HERE / f'om_{tag}.json')
    pr = flat('process', process, over, HERE / f'op_{tag}.json')
    fi = flat('filament', FILAMENT, {}, HERE / f'of_{tag}.json')
    out = HERE / f'oo_{tag}'; shutil.rmtree(out, ignore_errors=True); out.mkdir()
    r = subprocess.run([ORCA, '--slice', '0', '--arrange', '1', '--orient', '0', '--load-settings', f'{m};{pr}',
                        '--load-filaments', str(fi), '--outputdir', str(out), stl], capture_output=True, text=True)
    try:
        g = next(out.rglob('*.gcode')).read_text(errors='ignore')
        head = g[:40000] + g[-40000:]
        t = re.search(r'estimated printing time \(normal mode\) = ([^\n]+)', head) or re.search(r'total estimated time: ([^\n;]+)', head)
        gr = re.search(r'total filament used \[g\] = ([\d.]+)', head) or re.search(r'filament used \[g\] = ([\d.]+)', head)
        print(f"{process} | {spec or 'as is':60s} {t.group(1).strip() if t else '?':>12s} {float(gr.group(1)) if gr else 0:6.1f} g", flush=True)
    except Exception as ex:
        print(process, spec, 'FAILED', r.returncode, (r.stdout + r.stderr)[-600:], ex)
    finally:
        shutil.rmtree(out, ignore_errors=True)
        for f in (m, pr, fi):
            f.unlink(missing_ok=True)


PARENT = json.loads((USER / 'machine' / (MACHINE + '.json')).read_text()).get('inherits', '') if (USER / 'machine' / (MACHINE + '.json')).exists() else ''

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    stl = sys.argv[1]
    process = sys.argv[2] if len(sys.argv) > 2 and '=' not in sys.argv[2] and sys.argv[2] else PROCESS
    specs = [a for a in sys.argv[2:] if a != process] or ['']
    for spec in specs:
        run(stl, process, spec)

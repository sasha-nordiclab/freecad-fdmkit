"""Slice an STL with OrcaSlicer CLI using the user's own presets (read-only copies); print time and grams.

usage: orca_slice.py model.stl ["process preset"] [key=value+key=value ...]
  each extra argument is one variant of overrides; '' = the preset as is.
  default process: 0.20mm NordicLab 0.6 Ballance; env ORCA_MACHINE / ORCA_FILAMENT override the printer / filament.
Temporary files (a scratch OrcaSlicer datadir holding copies of the presets) go next to the STL and are deleted afterwards.
OrcaSlicer 2.5 resolves the system parents itself (profiles are in .opc packs); a preset must sit in the datadir's user/default to be resolved.
"""
import json, os, re, subprocess, sys, pathlib, shutil, tempfile

APP = os.environ.get('ORCA_APP', '/Applications/OrcaSlicer.app')
ORCA = APP + '/Contents/MacOS/OrcaSlicer'
DATA = pathlib.Path.home() / 'Library/Application Support/OrcaSlicer'      # read-only source of presets
MACHINE = os.environ.get('ORCA_MACHINE', 'Bambu Lab A1 0.4 nozzle - NordicLab')
FILAMENT = os.environ.get('ORCA_FILAMENT', 'AzureFilm PETG HF White')
PROCESS = '0.20mm NordicLab 0.6 Ballance'


def put(dd, kind, name, over):
    """Copy the user preset (and user-preset parents) into the scratch datadir; return the copy's path."""
    src = DATA / 'user/default' / kind / (name + '.json')
    d = json.loads(src.read_text())
    if (DATA / 'user/default' / kind / (d.get('inherits', '') + '.json')).exists():
        put(dd, kind, d['inherits'], {})
    d.update(over); d.setdefault('type', kind)
    out = dd / 'user/default' / kind / (name + '.json'); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=1)); return out


def run(stl, process, spec):
    if not pathlib.Path(ORCA).exists():
        sys.exit(f'orca_slice: {ORCA} not found; set ORCA_APP (2.5 or newer: the 2.4 CLI cannot resolve inherited presets)')
    over = dict(a.split('=', 1) for a in spec.split('+') if a); over.setdefault('curr_bed_type', 'Textured PEI Plate')
    dd = pathlib.Path(tempfile.mkdtemp(prefix='orca_', dir=pathlib.Path(stl).resolve().parent))
    r = None
    try:
        (dd / 'system').symlink_to(DATA / 'system')
        m, pr, fi = put(dd, 'machine', MACHINE, {}), put(dd, 'process', process, over), put(dd, 'filament', FILAMENT, {})
        r = subprocess.run([ORCA, '--datadir', str(dd), '--slice', '0', '--arrange', '1', '--orient', '0', '--load-settings', f'{m};{pr}',
                            '--load-filaments', str(fi), '--outputdir', str(dd / 'out'), stl], capture_output=True, text=True, check=False)  # failures are reported below
        g = next((dd / 'out').rglob('*.gcode')).read_text(errors='ignore')
        head = g[:40000] + g[-40000:]
        t = re.search(r'estimated printing time \(normal mode\) = ([^\n]+)', head) or re.search(r'total estimated time: ([^\n;]+)', head)
        gr = re.search(r'total filament used \[g\] = ([\d.]+)', head) or re.search(r'filament used \[g\] = ([\d.]+)', head)
        print(f"{process} | {spec or 'as is':60s} {t.group(1).strip() if t else '?':>12s} {float(gr.group(1)) if gr else 0:6.1f} g", flush=True)
    except Exception as ex:
        print(process, spec, 'FAILED', *((r.returncode, (r.stdout + r.stderr)[-600:]) if r else ()), repr(ex))
    finally:
        shutil.rmtree(dd, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    stl = sys.argv[1]
    process = sys.argv[2] if len(sys.argv) > 2 and '=' not in sys.argv[2] and sys.argv[2] else PROCESS
    specs = [a for a in sys.argv[2:] if a != process] or ['']
    for spec in specs:
        run(stl, process, spec)

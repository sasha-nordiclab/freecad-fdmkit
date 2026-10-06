# fdmkit autoload: sheet observer + version line in the Report view.
try:
    import fdmkit
    fdmkit._boot()
except Exception as e:
    import FreeCAD
    FreeCAD.Console.PrintError(f'fdmkit: load failed: {e}\n')

"""User-facing CLI using the same bundled pipeline and app as the graphical interface."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    python=ROOT/'pipeline/.venv/Scripts/python.exe'
    if not python.exists():raise SystemExit('Apri INSTALLA.bat per preparare H3-documentary.')
    raise SystemExit(subprocess.call([str(python),'-X','utf8',str(ROOT/'pipeline/generate.py'),*sys.argv[1:]],cwd=ROOT/'pipeline'))

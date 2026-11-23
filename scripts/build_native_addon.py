"""Reproducible package of our own add-on, no third-party code/dependencies bundled."""
import argparse
from pathlib import Path
import zipfile

MODULES = ['bridge_service.py', 'bridge_transport.py', 'native_anki.py', 'study_planner.py',
           'deck_maintenance.py', 'audio_experimental.py', 'themes.py']


def build(target):
    root = Path(__file__).resolve().parents[1]
    files = {n: root / 'addons' / 'native_bridge' / n for n in ['__init__.py', 'manifest.json']}
    files.update({n: root / 'scripts' / n for n in MODULES})
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o600 << 16
            archive.writestr(info, path.read_bytes())
    return target


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    print(build(p.parse_args().output))

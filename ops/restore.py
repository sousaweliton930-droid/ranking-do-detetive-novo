"""Restauro offline para destino NOVO: nunca sobrescreve banco existente."""
import argparse
from contextlib import closing
import os
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import connect

def restore(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Backup não encontrado.')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as original:
        if original.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup inválido.')
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with closing(connect(destination)) as target:
                original.backup(target)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    print(restore(args.source.resolve(),args.destination.resolve()))

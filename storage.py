"""Migrações versionadas e cópias consistentes, sem apagar dados existentes."""
import fcntl
from contextlib import closing
import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS = Path(__file__).parent / 'migrations'

def _connect_sqlite(path):
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def backup_database(source, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / ('ranking-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
    # Exclusivo e restrito mesmo se o processo tiver umask permissiva.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(connect(source)) as origin, closing(sqlite3.connect(target)) as copy:
            origin.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup não passou na verificação de integridade.')
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target

def _migrate_sqlite(path, backup_dir, migrations=MIGRATIONS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(str(path) + '.migrate.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existed = path.exists() and path.stat().st_size > 0
        db = connect(path)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied TEXT NOT NULL)')
            db.commit()
            applied = dict(db.execute('SELECT version,checksum FROM schema_migrations'))
            files = sorted(Path(migrations).glob('[0-9]*.sql'))
            if set(applied) - {file.name for file in files}:
                raise RuntimeError('Código anterior ao esquema do banco. Não iniciar rollback incompatível.')
            pending = []
            for file in files:
                checksum = hashlib.sha256(file.read_bytes()).hexdigest()
                if file.name in applied:
                    if applied[file.name] != checksum:
                        raise RuntimeError('Migração aplicada foi modificada: ' + file.name)
                else:
                    pending.append((file, checksum))
            if existed and pending:
                backup_database(path, backup_dir)
            for file, checksum in pending:
                # Nomes e conteúdo são arquivos revisados do repositório, não entrada web.
                version = file.name.replace("'", "''")
                stamp = datetime.now(timezone.utc).isoformat()
                try:
                    db.executescript('BEGIN IMMEDIATE;\n' + file.read_text() + f"\nINSERT INTO schema_migrations VALUES('{version}','{checksum}','{stamp}');\nCOMMIT;")
                except Exception:
                    db.rollback()
                    raise
            return len(pending)
        finally:
            db.close()


def is_postgres(target):
    return str(target).startswith(('postgres://','postgresql://'))

def connect(target):
    if is_postgres(target):
        from postgres_storage import Connection
        return Connection(target)
    return _connect_sqlite(target)

def migrate(target, backup_dir=None, migrations=None):
    if is_postgres(target):
        from postgres_storage import migrate as migrate_pg, MIGRATIONS as PG_MIGRATIONS
        return migrate_pg(target,migrations or PG_MIGRATIONS)
    return _migrate_sqlite(target,backup_dir,migrations or MIGRATIONS)

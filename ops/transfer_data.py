"""Cópia reversível entre SQLite e PostgreSQL, somente para destino vazio."""
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import connect, is_postgres, migrate

TABLES=('users','channels','posts','sheets','entries','revisions','sync_logs','login_limits')

def readonly(source):
    if is_postgres(source):
        db=connect(source)
        db.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    else:
        path=Path(source).resolve()
        if not path.is_file(): raise ValueError('Origem SQLite inexistente.')
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=30)
        db.row_factory=sqlite3.Row
        db.execute('BEGIN')
    return db

def records(db,table):
    # SQLite v1 anterior às migrações não tinha o contador de login.
    if table=='login_limits' and isinstance(db,sqlite3.Connection):
        if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone(): return
    key='client' if table=='login_limits' else 'id'
    cursor=db.execute(f'SELECT * FROM {table} ORDER BY {key}')
    while rows:=cursor.fetchmany(500):
        for row in rows: yield dict(row)

def digest(db,table):
    count=0; checksum=hashlib.sha256()
    for row in records(db,table):
        checksum.update(json.dumps(row,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode())
        checksum.update(b'\n'); count+=1
    return count,checksum.hexdigest()

def transfer(source,target):
    if source==target: raise ValueError('Origem e destino devem ser distintos.')
    # Recusar bancos já utilizados ANTES de alterar o esquema.
    if is_postgres(target):
        db=connect(target)
        try:
            if db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'").fetchone():
                raise ValueError('Use um banco PostgreSQL novo, sem tabelas existentes.')
        finally: db.close()
    elif Path(target).exists():
        raise ValueError('Destino SQLite já existe; escolha um novo arquivo.')
    migrate(target,str(Path(target).parent/'backups') if not is_postgres(target) else None)
    origin=readonly(source); destination=connect(target)
    try:
        destination.execute('BEGIN IMMEDIATE' if not is_postgres(target) else 'BEGIN')
        if is_postgres(target):
            destination.execute('LOCK TABLE '+','.join(TABLES)+' IN EXCLUSIVE MODE')
        if any(destination.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES):
            raise ValueError('Destino não está vazio. Nenhum registro será sobrescrito.')
        audit={}
        for table in TABLES:
            for row in records(origin,table):
                columns=','.join(row.keys())
                placeholders=','.join('?' for _ in row)
                destination.execute(f'INSERT INTO {table}({columns}) VALUES({placeholders})',tuple(row.values()))
            if digest(origin,table)!=digest(destination,table):
                raise RuntimeError('Conferência de cópia falhou; transação revertida.')
            audit[table]=digest(destination,table)[0]
            if is_postgres(target) and table!='login_limits':
                next_id=destination.execute(f'SELECT COALESCE(MAX(id),0)+1 FROM {table}').fetchone()[0]
                destination.execute("SELECT setval(pg_get_serial_sequence(?, 'id'), ?, false)",(table,next_id))
        destination.commit()
        return audit
    except Exception:
        destination.rollback(); raise
    finally:
        origin.rollback(); origin.close(); destination.close()

if __name__=='__main__':
    try:
        source=os.environ['SOURCE_DATABASE']
        target=os.environ['TARGET_DATABASE']
        result=transfer(source,target)
        print('Cópia conferida e concluída. Origem preservada. Registros por tabela:',result)
    except Exception:
        print('Transferência abortada. A origem foi preservada. Confirme banco de destino novo e configurações.',file=sys.stderr)
        sys.exit(1)

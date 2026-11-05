"""Adaptador pequeno para as consultas parametrizadas existentes; sem ORM."""
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg import pq

MIGRATIONS = Path(__file__).parent/'migrations/postgres'

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

def row_factory(cursor):
    names=[column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names,values))

class Connection:
    dialect='postgres'
    def __init__(self,url):
        # autocommit em leituras; as escritas iniciam transação como no SQLite.
        try:
            self.raw=psycopg.connect(url,autocommit=True,row_factory=row_factory,connect_timeout=15,prepare_threshold=None)
        except psycopg.Error:
            raise RuntimeError('Não foi possível conectar ao PostgreSQL. Verifique o segredo e a disponibilidade do banco.') from None
    def execute(self,sql,params=None):
        statement=sql.strip().upper()
        if statement=='BEGIN IMMEDIATE':
            self.raw.execute('BEGIN')
            # Serializa a atualização do contador de login, inclusive em outros hosts.
            return self.raw.execute('SELECT pg_advisory_xact_lock(73920401)')
        if statement.startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP')) and self.raw.info.transaction_status==pq.TransactionStatus.IDLE:
            self.raw.execute('BEGIN')
        # Somente SQL fixo do projeto usa ?. Valores nunca são interpolados.
        query=sql.replace('%','%%').replace('?','%s') if params is not None else sql
        try:
            return self.raw.execute(query,params)
        except psycopg.IntegrityError:
            raise sqlite3.IntegrityError('Restrição de integridade do banco.') from None
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
    def __enter__(self): return self
    def __exit__(self,kind,value,tb):
        self.rollback() if kind else self.commit()
        self.close()

def migrate(url,migrations=MIGRATIONS):
    db=Connection(url)
    try:
        db.execute('BEGIN')
        db.execute('SELECT pg_advisory_xact_lock(73920402)')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied TEXT NOT NULL)')
        applied={row['version']:row['checksum'] for row in db.execute('SELECT version,checksum FROM schema_migrations').fetchall()}
        files=sorted(Path(migrations).glob('[0-9]*.sql'))
        if set(applied)-{file.name for file in files}: raise RuntimeError('Código anterior ao esquema PostgreSQL. Rollback incompatível.')
        count=0
        for file in files:
            checksum=hashlib.sha256(file.read_bytes()).hexdigest()
            if file.name in applied:
                if applied[file.name]!=checksum: raise RuntimeError('Migração PostgreSQL aplicada foi modificada.')
                continue
            # Arquivos revisados e imutáveis. Migrações atuais são somente aditivas.
            db.raw.execute(file.read_text(),prepare=False)
            db.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(file.name,checksum,datetime.now(timezone.utc).isoformat()))
            count+=1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally: db.close()

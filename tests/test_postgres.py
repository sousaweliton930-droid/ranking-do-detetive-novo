"""Integração contra PostgreSQL real, isolada por schema temporário."""
import gzip
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from app import create_app
from storage import connect, migrate
from integrations.sheets import sync_due
from ops.transfer_data import transfer, TABLES, digest, readonly
from ops.export_data import export_data, restore_export
import test_app
from test_app import MAPPING, ROWS

BASE=os.environ.get('TEST_POSTGRES_URL')

@unittest.skipUnless(BASE,'Defina TEST_POSTGRES_URL para executar testes reais PostgreSQL.')
class PostgresTests(test_app.AppTests):
    # Reexecutar os fluxos essenciais existentes usando PostgreSQL real.
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.schema='test_'+uuid.uuid4().hex
        self.admin=psycopg.connect(BASE,autocommit=True)
        self.admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        options=conninfo_to_dict(BASE)
        options['options']='-c search_path='+self.schema
        # URI com options preservada pelo psycopg; app reconhece esquema URI.
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
        parsed=urlsplit(BASE)
        query=dict(parse_qsl(parsed.query)); query['options']=options['options']
        self.url=urlunsplit(parsed._replace(query=urlencode(query,quote_via=quote)))
        self.app=create_app({'TESTING':True,'DATABASE':self.url,'SECRET_KEY':'test-only','SESSION_COOKIE_SECURE':False})
        self.client=self.app.test_client()
    def tearDown(self):
        # Somente o schema exclusivo criado por ESTE teste é descartado.
        self.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.admin.close(); self.temp.cleanup()
    def test_restart_and_next_identity(self):
        with self.app.app_context():
            db=self.app.db(); db.execute("INSERT INTO channels(name) VALUES('Persistência de teste')"); db.commit()
        restarted=create_app({'TESTING':True,'DATABASE':self.url,'SECRET_KEY':'test-only','SESSION_COOKIE_SECURE':False})
        self.assertIn('Persistência de teste'.encode(),restarted.test_client().get('/canais').data)
        self.assertEqual(migrate(self.url),0)
    def test_migration_failure_is_atomic(self):
        folder=Path(self.temp.name)/'migrations'; folder.mkdir()
        from postgres_storage import MIGRATIONS
        for path in MIGRATIONS.glob('*.sql'): (folder/path.name).write_bytes(path.read_bytes())
        (folder/'003_bad.sql').write_text('CREATE TABLE should_rollback(id INTEGER); INVALID SQL;')
        with self.assertRaises(psycopg.Error): migrate(self.url,migrations=folder)
        db=connect(self.url)
        try:
            self.assertIsNone(db.execute("SELECT to_regclass('should_rollback')").fetchone()[0])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],2)
        finally: db.close()
    def test_sync_failure_and_success(self):
        with self.app.app_context():
            db=self.app.db(); db.execute("INSERT INTO channels(name) VALUES('Test only')")
            db.execute('INSERT INTO sheets(channel_id,spreadsheet_id,range_name,mapping,enabled) VALUES(1,?,?,?,1)',('id-test','Data!A:D',json.dumps(MAPPING))); db.commit()
            with patch('integrations.sheets.fetch',side_effect=ValueError('Sem credencial nesta etapa.')): sync_due(db)
            self.assertEqual(db.execute('SELECT status FROM sync_logs').fetchone()[0],'erro')
            db.execute('UPDATE sheets SET last_attempt=NULL'); db.commit()
            with patch('integrations.sheets.fetch',return_value=ROWS): sync_due(db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM entries').fetchone()[0],1)
    def test_transfer_legacy_sqlite_without_mutating_source(self):
        import hashlib, sqlite3
        from storage import MIGRATIONS
        source=Path(self.temp.name)/'legacy.sqlite'
        with sqlite3.connect(source) as db:
            db.executescript((MIGRATIONS/'001_initial.sql').read_text())
            db.execute("INSERT INTO channels(name) VALUES('Legacy test only')")
        checksum=hashlib.sha256(source.read_bytes()).hexdigest()
        # Novo destino SQLite também exercita a reversibilidade sem tocar no legado.
        result=transfer(str(source),str(Path(self.temp.name)/'new.sqlite'))
        self.assertEqual(result['channels'],1)
        self.assertEqual(result['login_limits'],0)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),checksum)
    def test_transfer_roundtrip_and_export(self):
        # Destino PostgreSQL precisa ser novo: schema recém-criado, ainda vazio.
        fresh='test_'+uuid.uuid4().hex
        self.admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(fresh)))
        target=self.url.replace(self.schema,fresh)
        try:
            source=Path(self.temp.name)/'source.sqlite'
            migrate(str(source),str(Path(self.temp.name)/'backups'))
            db=connect(source)
            from werkzeug.security import generate_password_hash
            db.execute('INSERT INTO users(id,username,password) VALUES(7,?,?)',('test-user',generate_password_hash('test-password-only')))
            db.execute("INSERT INTO channels(id,name) VALUES(42,'Canal de teste')")
            db.execute("INSERT INTO posts(title,body,published,created) VALUES('Teste','Conteúdo',1,'2026-01-01')")
            db.execute('INSERT INTO sheets(channel_id,spreadsheet_id,range_name,mapping,enabled) VALUES(42,?,?,?,1)',('test-sheet-id','Data!A:D',json.dumps(MAPPING)))
            from integrations.sheets import import_rows
            sheet=db.execute('SELECT * FROM sheets').fetchone(); import_rows(db,sheet,ROWS)
            import_rows(db,sheet,[ROWS[0],['a','2026-01-01T12:00:00-03:00','2','-1']])
            db.execute("INSERT INTO sync_logs(sheet_id,started,status,message) VALUES(1,'2026-01-01','sucesso','Test only')")
            db.execute("INSERT INTO login_limits VALUES('legacy-test-client',1,0,0)")
            db.commit(); db.close()
            result=transfer(str(source),target)
            self.assertEqual(result['users'],1); self.assertEqual(result['entries'],1)
            self.assertEqual(result['revisions'],1); self.assertEqual(result['sync_logs'],1)
            migrated=create_app({'TESTING':True,'DATABASE':target,'SECRET_KEY':'test-only','SESSION_COOKIE_SECURE':False})
            client=migrated.test_client(); client.get('/')
            with client.session_transaction() as session: token=session['csrf']
            self.assertEqual(client.post('/admin/login',data={'csrf':token,'username':'test-user','password':'test-password-only'}).status_code,302)
            self.assertEqual(client.get('/admin').status_code,200)
            with self.assertRaises(ValueError): transfer(str(source),target)
            back=Path(self.temp.name)/'back.sqlite'; transfer(target,str(back))
            origin=readonly(str(source)); restored=readonly(str(back))
            for table in TABLES: self.assertEqual(digest(origin,table),digest(restored,table))
            origin.close(); restored.close()
            db=connect(target); db.execute("INSERT INTO channels(name) VALUES('Após transferência')"); db.commit()
            self.assertEqual(db.execute('SELECT MAX(id) FROM channels').fetchone()[0],43); db.close()
            backup=Path(self.temp.name)/'backup.jsonl.gz'; export_data(target,backup)
            with gzip.open(backup,'rt') as file: self.assertGreater(len(file.readlines()),2)
            with self.assertRaises(FileExistsError): export_data(target,backup)
            recovery=Path(self.temp.name)/'recovery.sqlite'
            counts=restore_export(backup,recovery)
            self.assertEqual(counts['channels'],2)
            origin=readonly(target); restored=readonly(str(recovery))
            for table in TABLES: self.assertEqual(digest(origin,table),digest(restored,table))
            origin.close(); restored.close()
            with self.assertRaises(ValueError): restore_export(backup,recovery)
        finally:
            self.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(fresh)))

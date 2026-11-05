import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app
from storage import backup_database, connect, migrate
from ops.restore import restore

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root/'ranking.sqlite'
        self.backups = self.root/'backups'
        self.config = {'TESTING':True,'PRODUCTION':True,'SECRET_KEY':'t'*64,
            'DATABASE':str(self.database),'BACKUP_DIR':str(self.backups),
            'PERSISTENT_DATA_DIR':str(self.root),'SESSION_COOKIE_SECURE':True,
            'PUBLIC_ORIGIN':'https://ranking.example.org','TRUSTED_HOSTS':['ranking.example.org']}
    def tearDown(self): self.temp.cleanup()
    def app(self):
        # Somente a detecção de mount do provedor é substituída; banco/HTTP são reais.
        with patch('production.os.path.ismount',return_value=True): return create_app(self.config)
    def test_production_fails_closed(self):
        with self.assertRaises(RuntimeError): create_app(self.config)
        with patch('production.os.path.ismount',return_value=True):
            for changes in ({'SECRET_KEY':'short'},{'SESSION_COOKIE_SECURE':False},{'DATABASE':'relative.sqlite'},{'DATABASE':'/tmp/ephemeral.sqlite'},{'TRUSTED_HOSTS':None}):
                with self.assertRaises(RuntimeError): create_app({**self.config,**changes})
    def test_postgres_production_requires_tls_without_local_disk(self):
        from production import validate_production
        config={**self.config,'DATABASE':'postgresql://user:test-only@example.neon.tech/db?sslmode=require','PERSISTENT_DATA_DIR':'','BACKUP_DIR':''}
        validate_production(config)
        for url in ['postgresql://user:test-only@example.neon.tech/db?sslmode=disable','postgresql://user@example.neon.tech/db?sslmode=require']:
            with self.assertRaises(RuntimeError): validate_production({**config,'DATABASE':url})
    def test_https_public_auth_cookies_and_host(self):
        app=self.app(); client=app.test_client()
        redirect=client.get('/',base_url='http://ranking.example.org')
        self.assertEqual(redirect.status_code,308)
        self.assertEqual(redirect.location,'https://ranking.example.org/')
        response=client.get('/',base_url='https://ranking.example.org')
        self.assertEqual(response.status_code,200)
        self.assertIn('Secure',response.headers['Set-Cookie'])
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('Strict-Transport-Security',response.headers)
        self.assertEqual(client.get('/admin',base_url='https://ranking.example.org').status_code,302)
        self.assertEqual(client.get('/',base_url='https://attacker.example').status_code,400)
        self.assertEqual(client.get('/healthz',base_url='https://ranking.example.org').json['status'],'ok')
    def test_render_hostname_is_used_without_manual_url(self):
        config={k:v for k,v in self.config.items() if k not in ('PUBLIC_ORIGIN','TRUSTED_HOSTS')}
        with patch.dict(os.environ,{'RENDER_EXTERNAL_HOSTNAME':'new-app.onrender.com'}):
            with patch('production.os.path.ismount',return_value=True):
                app=create_app(config)
        self.assertEqual(app.config['PUBLIC_ORIGIN'],'https://new-app.onrender.com')
        self.assertEqual(app.config['TRUSTED_HOSTS'],['new-app.onrender.com'])
        self.assertEqual(app.test_client().get('/healthz',base_url='http://new-app.onrender.com').status_code,200)
    def test_restart_update_backup_and_restore_preserve_data(self):
        first=self.app()
        with first.app_context():
            db=first.db(); db.execute("INSERT INTO channels(name) VALUES('Persistência de teste')"); db.commit()
        second=self.app()
        with second.app_context():
            self.assertEqual(second.db().execute('SELECT name FROM channels').fetchone()[0],'Persistência de teste')
            self.assertEqual(second.db().execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],2)
        target=backup_database(self.database,self.backups)
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        restored=restore(target,self.root/'restored.sqlite')
        with connect(restored) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM channels').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        with self.assertRaises(FileExistsError): restore(target,self.database)
    def test_adopts_existing_database_without_data_loss(self):
        from storage import MIGRATIONS
        with sqlite3.connect(self.database) as db:
            db.executescript((MIGRATIONS/'001_initial.sql').read_text())
            db.execute("INSERT INTO channels(name) VALUES('Existing record')")
        migrate(self.database,self.backups)
        with connect(self.database) as db:
            self.assertEqual(db.execute('SELECT name FROM channels').fetchone()[0],'Existing record')
        self.assertEqual(len(list(self.backups.glob('*.sqlite'))),1)
    def test_failed_migration_rolls_back_and_detects_changes(self):
        folder=self.root/'migrations'; folder.mkdir()
        first=folder/'001.sql'; first.write_text('CREATE TABLE keep(id INTEGER);')
        migrate(self.database,self.backups,folder)
        (folder/'002.sql').write_text('CREATE TABLE should_rollback(id INTEGER); INVALID SQL;')
        with self.assertRaises(sqlite3.Error): migrate(self.database,self.backups,folder)
        with connect(self.database) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0],1)
        first.write_text('CREATE TABLE changed(id INTEGER);')
        with self.assertRaises(RuntimeError): migrate(self.database,self.backups,folder)
    def test_throttle_persists_after_restart(self):
        client=self.app().test_client(); origin='https://ranking.example.org'
        client.get('/',base_url=origin)
        with client.session_transaction(base_url=origin) as session: token=session['csrf']
        for _ in range(5):
            client.post('/admin/login',base_url=origin,data={'username':'absent','password':'invalid','csrf':token})
        client=self.app().test_client(); client.get('/',base_url=origin)
        with client.session_transaction(base_url=origin) as session: token=session['csrf']
        self.assertEqual(client.post('/admin/login',base_url=origin,data={'csrf':token}).status_code,429)

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from werkzeug.security import generate_password_hash
from app import create_app
from integrations.sheets import normalize, import_rows

MAPPING={'id':'ID','date':'Data','stake':'Stake','profit':'Lucro'}
ROWS=[['ID','Data','Stake','Lucro'],['a','2026-01-01T12:00:00-03:00','2','1']]

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'DATABASE':str(Path(self.temp.name)/'test.sqlite'),'SECRET_KEY':'test-only','SESSION_COOKIE_SECURE':False})
        self.client=self.app.test_client()
    def tearDown(self): self.temp.cleanup()
    def token(self):
        self.client.get('/')
        with self.client.session_transaction() as s: return s['csrf']
    def login(self):
        with self.app.app_context():
            db=self.app.db(); db.execute('INSERT INTO users(username,password) VALUES(?,?)',('owner',generate_password_hash('test-password-only'))); db.commit()
        return self.client.post('/admin/login',data={'username':'owner','password':'test-password-only','csrf':self.token()})
    def test_empty_public_pages(self):
        for path in ['/','/atualizacao','/carteira','/canais']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn('Content-Security-Policy',response.headers)
        self.assertIn(b'primeiras an',self.client.get('/').data)
        self.assertEqual(self.client.get('/atualizacao?period=invalid').status_code,400)
    def test_auth_csrf_and_logout(self):
        self.assertEqual(self.client.get('/admin').status_code,302)
        self.assertEqual(self.client.post('/admin',data={'kind':'channel','name':'Blocked'}).status_code,400)
        self.assertEqual(self.login().status_code,302)
        self.assertEqual(self.client.get('/admin').status_code,200)
        self.client.post('/admin/logout',data={'csrf':self.token()})
        self.assertEqual(self.client.get('/admin').status_code,302)
    def test_management_publish_and_escape(self):
        self.login(); token=self.token()
        self.client.post('/admin',data={'kind':'channel','name':'Canal autorizado','url':'https://example.org','csrf':token})
        self.assertIn(b'Canal autorizado',self.client.get('/canais').data)
        self.client.post('/admin',data={'kind':'post','title':'<script>unsafe</script>','body':'Texto','csrf':token})
        self.assertNotIn(b'unsafe',self.client.get('/').data)
        self.client.post('/admin',data={'kind':'post','id':'1','title':'<script>unsafe</script>','body':'Texto','published':'on','csrf':token})
        self.assertIn(b'&lt;script&gt;unsafe',self.client.get('/').data)
    def test_dedup_corrections_and_persistence(self):
        with self.app.app_context():
            db=self.app.db()
            db.execute("INSERT INTO channels(name) VALUES('Authorized test')")
            db.execute('INSERT INTO sheets(channel_id,spreadsheet_id,range_name,mapping) VALUES(1,?,?,?)',('test-sheet-id','Data!A:D',json.dumps(MAPPING)))
            sheet=db.execute('SELECT * FROM sheets').fetchone()
            import_rows(db,sheet,ROWS); import_rows(db,sheet,ROWS); db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM entries').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT occurred FROM entries').fetchone()[0],'2026-01-01T15:00:00+00:00')
            changed=[ROWS[0],['a','2026-01-01T12:00:00-03:00','2','-1']]
            import_rows(db,sheet,changed); db.commit()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],1)
        html=self.client.get('/carteira?period=all').data
        self.assertIn(b'-50.00%',html)
        self.assertIn(b'chart-data',html)
    def test_invalid_data(self):
        for stake,profit,date in [('0','1','2026-01-01'),('2','nan','2026-01-01'),('2','-3','2026-01-01'),('2','1','2099-01-01')]:
            with self.assertRaises(ValueError): normalize([ROWS[0],['a',date,stake,profit]],MAPPING)
        with self.assertRaises(ValueError): normalize([ROWS[0],ROWS[1],ROWS[1]],MAPPING)
    def test_locale_mapping(self):
        mapping={**MAPPING,'date_format':'%d/%m/%Y %H:%M','decimal':','}
        row=normalize([ROWS[0],['x','01/01/2026 12:00','1.000,00','25,50']],mapping)[0]
        self.assertEqual(row[2:],(1000,25.5))
    def test_sync_authorization_errors_and_interval(self):
        from integrations.sheets import sync_due
        with self.app.app_context():
            db=self.app.db()
            db.execute("INSERT INTO channels(name) VALUES('Test only')")
            db.execute('INSERT INTO sheets(channel_id,spreadsheet_id,range_name,mapping) VALUES(1,?,?,?)',('test-sheet-id','Data!A:D',json.dumps(MAPPING))); db.commit()
            with patch.dict('os.environ',{'DATABASE':str(Path(self.temp.name)/'test.sqlite')}):
                with patch('integrations.sheets.fetch') as fetch:
                    sync_due(db); fetch.assert_not_called()
                db.execute('UPDATE sheets SET enabled=1'); db.commit()
                with patch('integrations.sheets.fetch',side_effect=ValueError('Credencial Google não configurada.')):
                    sync_due(db)
                self.assertEqual(db.execute('SELECT status FROM sync_logs').fetchone()[0],'erro')
                self.assertIsNone(db.execute('SELECT last_success FROM sheets').fetchone()[0])
                with patch('integrations.sheets.fetch') as fetch:
                    sync_due(db); fetch.assert_not_called()
                db.execute('UPDATE sheets SET last_attempt=NULL'); db.commit()
                with patch('integrations.sheets.fetch',return_value=ROWS):
                    sync_due(db)
                self.assertIsNotNone(db.execute('SELECT last_success FROM sheets').fetchone()[0])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM entries').fetchone()[0],1)
    def test_login_throttle(self):
        token=self.token()
        for i in range(5): self.client.post('/admin/login',data={'username':'no','password':'no','csrf':token})
        self.assertEqual(self.client.post('/admin/login',data={'csrf':token}).status_code,429)

if __name__=='__main__': unittest.main()

import json
import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from storage import connect, migrate, backup_database
from production import validate_production
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).parent

def now():
    return datetime.now(timezone.utc).isoformat()

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32), DATABASE=os.environ.get('DATABASE', str(ROOT/'instance/data.sqlite')), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','1')=='1', PERMANENT_SESSION_LIFETIME=timedelta(hours=4), MAX_CONTENT_LENGTH=65536)
    render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME','')
    app.config.update(PRODUCTION=os.environ.get('APP_ENV')=='production',
        PERSISTENT_DATA_DIR=os.environ.get('PERSISTENT_DATA_DIR',''),
        BACKUP_DIR=os.environ.get('BACKUP_DIR',str(ROOT/'instance/backups')),
        PUBLIC_ORIGIN=os.environ.get('PUBLIC_ORIGIN','https://'+render_host if render_host else ''),
        TRUSTED_HOSTS=[h.strip() for h in os.environ.get('ALLOWED_HOSTS',render_host).split(',') if h.strip()] or None)
    if app.config['PRODUCTION']:
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if config: app.config.update(config)
    validate_production(app.config)
    if app.config['PRODUCTION']:
        os.umask(0o077)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    def db():
        if 'db' not in g:
            g.db = connect(app.config['DATABASE'])
        return g.db
    app.db = db
    migrate(app.config['DATABASE'], app.config['BACKUP_DIR'])
    @app.teardown_appcontext
    def close(error=None):
        if 'db' in g: g.pop('db').close()
    @app.before_request
    def security():
        if app.config['PRODUCTION'] and not request.is_secure and request.path != '/healthz':
            # Redirecionamento para origem fixa; não confiar no Host ou em headers arbitrários.
            return redirect(app.config['PUBLIC_ORIGIN'] + request.full_path.rstrip('?'), code=308)
        session.setdefault('csrf', secrets.token_hex(32))
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf','')): abort(400)
    @app.after_request
    def headers(response):
        response.headers.update({'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'", 'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Cache-Control':'no-store'})
        if app.config['PRODUCTION']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response
    @app.get('/healthz')
    def health():
        db().execute('SELECT COUNT(*) FROM schema_migrations').fetchone()
        return {'status':'ok', 'release':os.environ.get('RENDER_GIT_COMMIT','local')}
    def private(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            if not session.get('user') or not db().execute('SELECT id FROM users WHERE id=?',(session['user'],)).fetchone(): return redirect(url_for('login'))
            return fn(*a,**kw)
        return wrapped
    @app.get('/')
    @app.get('/<page>')
    def public(page='publicacoes'):
        if page not in ('publicacoes','atualizacao','carteira','canais'): abort(404)
        period=request.args.get('period','1' if page=='atualizacao' else '30')
        if period not in ('1','7','30','90','all'): abort(400)
        channel=request.args.get('channel','')
        if channel and not channel.isdigit(): abort(400)
        sql='SELECT e.*,c.name FROM entries e JOIN sheets s ON s.id=e.sheet_id JOIN channels c ON c.id=s.channel_id WHERE e.occurred<=?'
        args=[now()]
        if period!='all':
            sql+=' AND e.occurred>=?'; args.append((datetime.now(timezone.utc)-timedelta(days=int(period))).isoformat())
        if channel: sql+=' AND c.id=?'; args.append(channel)
        rows=db().execute(sql+' ORDER BY e.occurred',args).fetchall()
        profit=sum(r['profit'] for r in rows); stake=sum(r['stake'] for r in rows)
        return render_template('public.html',page=page, channels=db().execute('SELECT * FROM channels ORDER BY name').fetchall(), posts=db().execute('SELECT * FROM posts WHERE published=1 ORDER BY created DESC').fetchall(), sheets=db().execute('SELECT channel_id,spreadsheet_id FROM sheets').fetchall(), rows=rows,profit=profit,roi=profit/stake*100 if stake else None,period=period,channel=channel,last=db().execute('SELECT MAX(last_success) FROM sheets').fetchone()[0])
    @app.route('/admin/login',methods=['GET','POST'])
    def login():
        if request.method=='POST':
            key=hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
            current=time.time()
            limit=db().execute('SELECT * FROM login_limits WHERE client=?',(key,)).fetchone()
            if limit and limit['blocked_until']>current: abort(429)
            user=db().execute('SELECT * FROM users WHERE username=?',(request.form.get('username',''),)).fetchone()
            valid=check_password_hash(user['password'] if user else generate_password_hash(secrets.token_hex(16)),request.form.get('password',''))
            if user and valid:
                db().execute('DELETE FROM login_limits WHERE client=?',(key,)); db().commit(); session.clear(); session['user']=user['id']; session['csrf']=secrets.token_hex(32); session.permanent=True
                return redirect(url_for('admin'))
            # Serializar a contagem para concorrência e preservar bloqueio após reinício.
            db().execute('BEGIN IMMEDIATE')
            limit=db().execute('SELECT * FROM login_limits WHERE client=?',(key,)).fetchone()
            count=limit['failures']+1 if limit and current-limit['updated']<900 else 1
            until=current+900 if count>=5 else 0
            db().execute('INSERT INTO login_limits VALUES(?,?,?,?) ON CONFLICT(client) DO UPDATE SET failures=excluded.failures,blocked_until=excluded.blocked_until,updated=excluded.updated',(key,count,until,current))
            db().execute('DELETE FROM login_limits WHERE updated<?',(current-86400,))
            db().commit(); flash('Credenciais inválidas. Tente novamente.')
        return render_template('login.html',page='admin')
    @app.post('/admin/logout')
    @private
    def logout():
        session.clear(); return redirect(url_for('public'))
    @app.route('/admin',methods=['GET','POST'])
    @private
    def admin():
        if request.method=='POST':
            f=request.form; kind=f.get('kind'); ident=f.get('id','')
            try:
                if kind=='channel':
                    name=f.get('name','').strip(); link=f.get('url','').strip()
                    if not name or (link and (urlparse(link).scheme!='https' or not urlparse(link).netloc)): raise ValueError('Nome obrigatório e link HTTPS válido.')
                    values=(name,f.get('description',''),link)
                    if ident: db().execute('UPDATE channels SET name=?,description=?,url=? WHERE id=?',values+(int(ident),))
                    else: db().execute('INSERT INTO channels(name,description,url) VALUES(?,?,?)',values)
                elif kind=='post':
                    if not f.get('title','').strip() or not f.get('body','').strip(): raise ValueError('Informe título e conteúdo.')
                    values=(f['title'],f['body'],int('published' in f))
                    if ident: db().execute('UPDATE posts SET title=?,body=?,published=? WHERE id=?',values+(int(ident),))
                    else: db().execute('INSERT INTO posts(title,body,published,created) VALUES(?,?,?,?)',values+(now(),))
                elif kind=='sheet':
                    import re
                    from integrations.sheets import validate_mapping
                    mapping=json.loads(f.get('mapping','{}')); validate_mapping(mapping)
                    if not re.fullmatch(r'[A-Za-z0-9_-]{20,150}',f.get('spreadsheet_id','')): raise ValueError('ID da planilha inválido.')
                    if not f.get('range_name','').strip(): raise ValueError('Informe o intervalo.')
                    values=(int(f['channel_id']),f['spreadsheet_id'],f['range_name'],json.dumps(mapping),int('enabled' in f))
                    if ident: db().execute('UPDATE sheets SET channel_id=?,spreadsheet_id=?,range_name=?,mapping=?,enabled=? WHERE id=?',values+(int(ident),))
                    else: db().execute('INSERT INTO sheets(channel_id,spreadsheet_id,range_name,mapping,enabled) VALUES(?,?,?,?,?)',values)
                else: abort(400)
                db().commit(); flash('Alterações salvas.')
            except (ValueError,KeyError,sqlite3.IntegrityError) as e:
                db().rollback(); flash('Não foi possível salvar. Confira os campos e vínculos. '+(str(e) if isinstance(e,ValueError) else ''))
            return redirect(url_for('admin'))
        return render_template('admin.html',page='admin',channels=db().execute('SELECT * FROM channels').fetchall(),posts=db().execute('SELECT * FROM posts').fetchall(),sheets=db().execute('SELECT * FROM sheets').fetchall(),logs=db().execute('SELECT * FROM sync_logs ORDER BY id DESC LIMIT 50').fetchall())
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.password_option(confirmation_prompt=True)
    def create_admin(username,password):
        if len(password)<12: raise click.ClickException('Use pelo menos 12 caracteres.')
        db().execute('INSERT INTO users(username,password) VALUES(?,?)',(username,generate_password_hash(password))); db().commit(); click.echo('Administrador criado.')
    @app.cli.command('backup')
    def backup():
        target = backup_database(app.config['DATABASE'], app.config['BACKUP_DIR'])
        click.echo('Backup verificado: ' + str(target))
    @app.cli.command('migrate')
    def migrate_command():
        click.echo('Esquema atualizado; dados preservados.')
    @app.cli.command('sync')
    def sync():
        from integrations.sheets import sync_due
        sync_due(db())
    return app

if __name__=='__main__':
    from waitress import serve
    serve(create_app(), host='0.0.0.0',port=int(os.environ.get('PORT','8000')),threads=4)

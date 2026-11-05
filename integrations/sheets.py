"""Google Sheets oficial, somente leitura. IDs estáveis são obrigatórios."""
import json
import math
import os
import fcntl
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

REQUIRED=('id','date','stake','profit')
def validate_mapping(mapping):
    if not isinstance(mapping,dict) or any(not isinstance(mapping.get(k),str) or not mapping[k] for k in REQUIRED):
        raise ValueError('Mapeie id, date, stake e profit para nomes de colunas.')
    if mapping.get('decimal', '.') not in ('.', ','): raise ValueError('Separador decimal inválido.')
    if 'date_format' in mapping and not isinstance(mapping['date_format'],str): raise ValueError('Formato de data inválido.')
    if not isinstance(mapping.get('timezone','America/Sao_Paulo'),str): raise ValueError('Fuso horário inválido.')
    ZoneInfo(mapping.get('timezone','America/Sao_Paulo'))

def normalize(rows,mapping):
    validate_mapping(mapping)
    if not rows: return []
    header=rows[0]
    if any(header.count(mapping[k])!=1 for k in REQUIRED): raise ValueError('Cabeçalhos ausentes ou duplicados.')
    indexes={k:header.index(mapping[k]) for k in REQUIRED}; result=[]; seen=set()
    for row in rows[1:]:
        if not any(str(v).strip() for v in row): continue
        values={k:str(row[i]).strip() if i<len(row) else '' for k,i in indexes.items()}
        ident=values['id']
        if not ident or ident in seen: raise ValueError('ID vazio ou repetido na origem.')
        seen.add(ident)
        date=datetime.strptime(values['date'],mapping['date_format']) if mapping.get('date_format') else datetime.fromisoformat(values['date'].replace('Z','+00:00'))
        if date.tzinfo is None: date=date.replace(tzinfo=ZoneInfo(mapping.get('timezone','America/Sao_Paulo')))
        date=date.astimezone(timezone.utc)
        def number(value):
            if mapping.get('decimal', '.')==',': value=value.replace('.','').replace(',','.')
            return float(value)
        stake=number(values['stake']); profit=number(values['profit'])
        if not math.isfinite(stake) or not math.isfinite(profit) or stake<=0 or profit < -stake or date>datetime.now(timezone.utc): raise ValueError('Data, stake ou lucro inválido.')
        result.append((ident,date.isoformat(),stake,profit))
    return result

def fetch(sheet):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    path=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not path: raise ValueError('Credencial Google não configurada.')
    credentials=Credentials.from_service_account_file(path,scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    with AuthorizedSession(credentials) as client:
        response=client.get('https://sheets.googleapis.com/v4/spreadsheets/'+quote(sheet['spreadsheet_id'],safe='')+'/values/'+quote(sheet['range_name'],safe=''),params={'valueRenderOption':'FORMATTED_VALUE'},timeout=30)
        response.raise_for_status()
        return response.json().get('values',[])

def import_rows(db,sheet,rows):
    items=normalize(rows,json.loads(sheet['mapping']))
    for ident,date,stake,profit in items:
        old=db.execute('SELECT * FROM entries WHERE sheet_id=? AND external_id=?',(sheet['id'],ident)).fetchone()
        if old and (old['occurred'],old['stake'],old['profit'])!=(date,stake,profit):
            db.execute('INSERT INTO revisions(entry_id,previous,changed) VALUES(?,?,?)',(old['id'],json.dumps(dict(old)),datetime.now(timezone.utc).isoformat()))
        db.execute('INSERT INTO entries(sheet_id,external_id,occurred,stake,profit) VALUES(?,?,?,?,?) ON CONFLICT(sheet_id,external_id) DO UPDATE SET occurred=excluded.occurred,stake=excluded.stake,profit=excluded.profit',(sheet['id'],ident,date,stake,profit))
    return len(items)

def sync_due(db):
    interval=max(1,int(os.environ.get('SYNC_INTERVAL_MINUTES','15')))
    # Um único sincronizador por host; implantar com um volume SQLite compartilhado.
    lock_path=os.environ.get('DATABASE','instance/data.sqlite')+'.sync.lock'
    with open(lock_path,'w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        for sheet in db.execute('SELECT * FROM sheets WHERE enabled=1').fetchall():
            started=datetime.now(timezone.utc)
            if sheet['last_attempt'] and started-datetime.fromisoformat(sheet['last_attempt'])<timedelta(minutes=interval): continue
            stamp=started.isoformat()
            db.execute('UPDATE sheets SET last_attempt=? WHERE id=?',(stamp,sheet['id'])); db.commit()
            try:
                count=import_rows(db,sheet,fetch(sheet))
                db.execute('UPDATE sheets SET last_success=? WHERE id=?',(stamp,sheet['id']))
                db.execute('INSERT INTO sync_logs(sheet_id,started,status,message) VALUES(?,?,?,?)',(sheet['id'],stamp,'sucesso',f'{count} entradas validadas.')); db.commit()
            except Exception as exc:
                db.rollback()
                # Não persistir respostas remotas ou conteúdo de credenciais.
                message=str(exc) if isinstance(exc,ValueError) else 'Falha de acesso ou leitura na origem ('+type(exc).__name__+').'
                db.execute('INSERT INTO sync_logs(sheet_id,started,status,message) VALUES(?,?,?,?)',(sheet['id'],stamp,'erro',message)); db.commit()

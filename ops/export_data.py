"""Exportação consistente e privada; executar FORA do disco efêmero Render Free."""
import argparse
import gzip
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ops.transfer_data import TABLES, readonly, records
from storage import connect, migrate

def export_data(source,target):
    db=readonly(source)
    try:
        # 'xb' recusa sobrescrever backups. Não registrar conteúdo, senhas ou URL.
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as file, gzip.GzipFile(fileobj=file,mode='wb') as output:
            output.write((json.dumps({'format':'ranking-detetive-v1'})+'\n').encode())
            counts={table:0 for table in TABLES}
            for table in TABLES:
                for row in records(db,table):
                    output.write((json.dumps({'table':table,'row':row},allow_nan=False)+'\n').encode())
                    counts[table]+=1
            output.write((json.dumps({'complete':counts})+'\n').encode())
    finally:
        db.rollback(); db.close()

def restore_export(source,destination):
    destination=Path(destination)
    if destination.exists(): raise ValueError('Destino existente. Escolha um novo arquivo SQLite.')
    migrate(str(destination),str(destination.parent/'backups'))
    db=connect(destination)
    try:
        db.execute('BEGIN IMMEDIATE')
        counts={table:0 for table in TABLES}; completed=False
        with gzip.open(source,'rt') as file:
            if json.loads(file.readline())!={'format':'ranking-detetive-v1'}: raise ValueError('Formato inválido.')
            for line in file:
                item=json.loads(line)
                if completed: raise ValueError('Conteúdo após encerramento do backup.')
                if 'complete' in item:
                    if item['complete']!=counts: raise ValueError('Contagem divergente.')
                    completed=True; continue
                table=item['table']; row=item['row']
                if table not in TABLES: raise ValueError('Tabela não autorizada no arquivo.')
                columns={r['name'] for r in db.execute(f'PRAGMA table_info({table})').fetchall()}
                if set(row)!=columns: raise ValueError('Colunas incompatíveis com o esquema.')
                db.execute(f"INSERT INTO {table}({','.join(row)}) VALUES({','.join('?' for _ in row)})",tuple(row.values()))
                counts[table]+=1
        if not completed: raise ValueError('Backup incompleto.')
        db.commit(); return counts
    except Exception:
        db.rollback(); raise
    finally: db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--restore-from',type=Path)
    args=parser.parse_args()
    try:
        if args.restore_from:
            restore_export(args.restore_from,args.destination)
            print('Backup restaurado em novo arquivo SQLite. Nenhum banco anterior foi sobrescrito.')
        else:
            export_data(os.environ.get('DATABASE_URL') or os.environ['DATABASE'],args.destination)
            print('Exportação concluída. Guarde o arquivo em armazenamento externo protegido.')
    except Exception:
        print('Exportação falhou. Não use uma cópia incompleta.',file=sys.stderr); sys.exit(1)

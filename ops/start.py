"""Entrada de produção: Flask/Waitress atrás do proxy HTTPS da hospedagem."""
import logging
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from storage import backup_database, is_postgres
from waitress import serve

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app = create_app()

def backups():
    while True:
        try:
            backup_database(app.config['DATABASE'], app.config['BACKUP_DIR'])
            logging.info('Backup consistente concluído e verificado.')
        except Exception:
            logging.exception('Falha no backup; verificar disco e capacidade.')
        # Sem expurgo automático nesta versão; acompanhar espaço e arquivar externamente.
        threading.Event().wait(86400)

if __name__ == '__main__':
    if app.config['PRODUCTION'] and not is_postgres(app.config['DATABASE']):
        threading.Thread(target=backups, daemon=True, name='sqlite-backup').start()
    # A hospedagem termina TLS na borda. Aceitar somente o protocolo encaminhado;
    # esta porta interna não deve ser exposta fora da rede do proxy da hospedagem.
    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT','8000')), threads=4,
          trusted_proxy='*' if app.config['PRODUCTION'] else None,
          trusted_proxy_headers={'x-forwarded-proto'} if app.config['PRODUCTION'] else set(),
          clear_untrusted_proxy_headers=True)

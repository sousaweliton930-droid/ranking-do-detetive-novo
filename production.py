"""Validação de produção: recusa segredos fracos e armazenamento efêmero."""
import os
from pathlib import Path
from urllib.parse import urlparse

def validate_production(config):
    if not config['PRODUCTION']:
        return
    secret = config['SECRET_KEY']
    if not isinstance(secret, str) or len(secret) < 32:
        raise RuntimeError('Produção exige SECRET_KEY externa de pelo menos 32 caracteres.')
    if not config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('Produção exige cookies Secure.')
    root = Path(config['PERSISTENT_DATA_DIR'])
    database = Path(config['DATABASE'])
    backups = Path(config['BACKUP_DIR'])
    if root in (Path('/'),Path('/tmp'),Path('/var/tmp')) or not root.is_absolute() or not root.is_dir() or not os.path.ismount(root):
        raise RuntimeError('Produção exige PERSISTENT_DATA_DIR em um disco montado.')
    for path in (database, backups):
        if not path.is_absolute() or not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
            raise RuntimeError('DATABASE e BACKUP_DIR devem estar dentro do disco persistente.')
    if not config['TRUSTED_HOSTS']:
        raise RuntimeError('Produção exige ALLOWED_HOSTS.')
    origin = urlparse(config['PUBLIC_ORIGIN'])
    if (origin.scheme != 'https' or not origin.hostname or origin.path or origin.query or origin.fragment
            or origin.username or origin.password or origin.hostname not in config['TRUSTED_HOSTS']):
        raise RuntimeError('Produção exige PUBLIC_ORIGIN HTTPS sem barra final.')

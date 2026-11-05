"""Exporta as quatro páginas públicas para GitHub Pages, sem servidor ou Neon."""
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
import os
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
PREFIX = "/ranking-do-detetive-novo/"
PAGES = {"": "index.html", "atualizacao": "atualizacao/index.html", "carteira": "carteira/index.html", "canais": "canais/index.html"}

def main():
    with TemporaryDirectory() as tmp:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("APP_ENV", None)
        os.environ["DATABASE"] = str(Path(tmp) / "site.sqlite")
        os.environ["COOKIE_SECURE"] = "0"
        from app import create_app
        app = create_app()
        client = app.test_client()
        OUT.mkdir(exist_ok=True)
        copytree(ROOT / "static", OUT / "static", dirs_exist_ok=True)
        for route, target in PAGES.items():
            response = client.get("/" + route)
            if response.status_code != 200:
                raise RuntimeError(f"Falha na página {route}: {response.status_code}")
            html = response.get_data(as_text=True)
            html = re.sub(r'<a class="admin-link"[^>]*>.*?</a>', "", html)
            html = html.replace('href="/static/', f'href="{PREFIX}static/')
            html = html.replace('src="/static/', f'src="{PREFIX}static/')
            html = html.replace('href="/"', f'href="{PREFIX}"')
            for slug in ("atualizacao", "carteira", "canais"):
                html = html.replace(f'href="/{slug}"', f'href="{PREFIX}{slug}/"')
            html = html.replace("Os resultados aparecerão após a sincronização de uma planilha autorizada.", "Os resultados serão exibidos quando os dados forem publicados.")
            dest = OUT / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html, encoding="utf-8")
        (OUT / ".nojekyll").touch()
    print("Site estático exportado para", OUT)

if __name__ == "__main__":
    main()

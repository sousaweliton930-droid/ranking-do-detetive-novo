"""Adapters opt-in: nenhuma coleta de redes sociais é ativada."""
from typing import Protocol

class SourceAdapter(Protocol):
    def fetch(self, configuration: dict) -> list[list[str]]: ...

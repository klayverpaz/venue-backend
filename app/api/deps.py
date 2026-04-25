"""Cross-cutting API dependencies (e.g., authenticated user, request context).

DI específica de feature mora em `app/api/v1/<feature>/deps.py`.
Este módulo recebe DIs compartilhadas entre features (ex.: `get_current_user`,
rate limiter) à medida que forem adicionadas.
"""
from __future__ import annotations

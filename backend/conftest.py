"""Testy nikdy nespouštějí worker automatické aktualizace map (ten by volal Graphify a Sonnet).

Fronta se v testech řídí ručně přes `claim()` a `run_one()`; viz docs/mapy-projektu.md.
"""
import os

os.environ['OPORA_MAP_REFRESH_WORKER'] = '0'

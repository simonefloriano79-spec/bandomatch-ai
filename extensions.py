"""
BandoMatch AI - extensions.py
Istanza condivisa di SQLAlchemy da importare in tutti i moduli.
Evita import circolari: i modelli importano db da qui, non da app.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

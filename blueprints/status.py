from flask import Blueprint, jsonify
from datetime import datetime
from sqlalchemy import text
from models.db import db
import psutil
import os

status_bp = Blueprint('status', __name__, url_prefix='/api/v1')

# Timestamp di avvio dell'applicazione
APP_START_TIME = datetime.now()


@status_bp.route('/status', methods=['GET'])
def get_status():
    """
    Endpoint per verificare lo stato dell'applicazione.
    Restituisce:
    - database_status: 'ok' o 'error'
    - uptime: secondi da quando l'app è avviata
    - timestamp: timestamp corrente ISO 8601
    """
    try:
        # Verifica connessione database
        db.session.execute(text('SELECT 1'))
        db_status = 'ok'
    except Exception as e:
        db_status = 'error'
        return jsonify({
            'database_status': db_status,
            'uptime': int((datetime.now() - APP_START_TIME).total_seconds()),
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503
    
    # Calcola uptime in secondi
    uptime_seconds = int((datetime.now() - APP_START_TIME).total_seconds())
    
    return jsonify({
        'database_status': db_status,
        'uptime': uptime_seconds,
        'timestamp': datetime.now().isoformat()
    }), 200
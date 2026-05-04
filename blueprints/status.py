import psutil
import time
from flask import Blueprint, jsonify
from datetime import datetime

status_bp = Blueprint('status', __name__, url_prefix='/api/v1')

# Timestamp di avvio dell'applicazione
APP_START_TIME = time.time()


@status_bp.route('/status', methods=['GET'])
def get_status():
    """
    Endpoint per ottenere lo stato dell'applicazione.
    Restituisce: status, uptime in secondi e memoria usata in MB.
    """
    try:
        # Calcola uptime in secondi
        current_time = time.time()
        uptime_seconds = int(current_time - APP_START_TIME)
        
        # Ottieni memoria usata dal processo corrente
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = round(memory_info.rss / (1024 * 1024), 2)
        
        response = {
            'status': 'ok',
            'uptime_seconds': uptime_seconds,
            'memory_mb': memory_mb,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

from flask import Blueprint, jsonify
from datetime import datetime

health_bp = Blueprint('health', __name__, url_prefix='/api/v1')

@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint that returns system status.
    
    Returns:
        JSON response with status, timestamp (ISO 8601), and version
    """
    try:
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': '3.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

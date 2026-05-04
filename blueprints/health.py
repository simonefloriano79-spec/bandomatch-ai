from flask import Blueprint, jsonify
from datetime import datetime

health_bp = Blueprint('health', __name__, url_prefix='/api/v1')

@health_bp.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint that returns pong with current timestamp."""
    try:
        return jsonify({
            'status': 'pong',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

from flask import Blueprint, jsonify
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/version', methods=['GET'])
def get_version():
    """
    Returns API version and build date.
    
    Returns:
        JSON with version and build_date
    """
    try:
        return jsonify({
            'version': '3.0',
            'build_date': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve version information',
            'details': str(e)
        }), 500

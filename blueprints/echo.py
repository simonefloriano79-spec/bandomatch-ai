from flask import Blueprint, request, jsonify

echo_bp = Blueprint('echo', __name__, url_prefix='/api/v1')

@echo_bp.route('/echo', methods=['POST'])
def echo():
    """
    Echo endpoint that returns the received JSON payload unchanged.
    """
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({
                'error': 'Invalid JSON',
                'message': 'Request body must be valid JSON'
            }), 400
        
        return jsonify(data), 200
    
    except Exception as e:
        return jsonify({
            'error': 'Internal Server Error',
            'message': str(e)
        }), 500

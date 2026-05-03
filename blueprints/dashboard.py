from flask import Blueprint, render_template, jsonify, current_app
from flask_login import login_required, current_user
from models.user import User
from sqlalchemy import exc

dashboard = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard.route('/', methods=['GET'])
@login_required
def dashboard_view():
    """
    Renderizza la pagina dashboard per l'utente loggato.
    """
    try:
        return render_template('dashboard.html', user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard: {str(e)}")
        return render_template('error.html', error='Errore nel caricamento del dashboard'), 500


@dashboard.route('/api/v1/profilo', methods=['GET'])
@login_required
def get_profilo():
    """
    Restituisce i dati del profilo dell'utente loggato in formato JSON.
    """
    try:
        user = current_user
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Utente non trovato'
            }), 404
        
        profilo_data = {
            'success': True,
            'data': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nome': getattr(user, 'nome', ''),
                'cognome': getattr(user, 'cognome', ''),
                'bio': getattr(user, 'bio', ''),
                'avatar_url': getattr(user, 'avatar_url', ''),
                'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None,
                'is_active': user.is_active
            }
        }
        
        return jsonify(profilo_data), 200
    
    except exc.SQLAlchemyError as e:
        current_app.logger.error(f"Database error in get_profilo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Errore nel recupero del profilo'
        }), 500
    
    except Exception as e:
        current_app.logger.error(f"Unexpected error in get_profilo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500

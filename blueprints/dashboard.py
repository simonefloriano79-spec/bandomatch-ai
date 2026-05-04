from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_required, current_user
from models.utente import Utente as User
from app import db

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/', methods=['GET'])
@login_required
def dashboard():
    """
    Renderizza la dashboard principale dell'utente.
    Richiede autenticazione.
    """
    try:
        user = db.session.query(User).filter_by(id=current_user.id).first()
        
        if not user:
            return redirect(url_for('auth.login'))
        
        context = {
            'current_user': user,
            'user_email': user.email,
            'user_name': user.nome,
            'user_id': user.id
        }
        
        return render_template('dashboard.html', **context)
    
    except Exception as e:
        return redirect(url_for('auth.login'))

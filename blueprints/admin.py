from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from models.user import User
from models.bando import Bando
from datetime import datetime, timedelta
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def check_admin():
    """Verifica se l'utente corrente è un admin."""
    if not current_user.is_authenticated:
        return False
    admin_emails = os.getenv('ADMIN_EMAIL', '').split(',')
    return current_user.email in [email.strip() for email in admin_emails if email.strip()]

@admin_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    """Dashboard admin con statistiche utenti e bandi."""
    try:
        if not check_admin():
            return jsonify({'error': 'Accesso negato. Non sei un admin.'}), 403
        
        # Statistiche utenti
        total_users = User.query.count()
        users_today = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
        users_this_week = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        users_this_month = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        active_users = User.query.filter(
            User.last_login >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        # Statistiche bandi
        total_bandi = Bando.query.count()
        bandi_today = Bando.query.filter(
            Bando.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
        bandi_this_week = Bando.query.filter(
            Bando.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        bandi_this_month = Bando.query.filter(
            Bando.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Bandi per stato
        bandi_by_status = Bando.query.with_entities(
            Bando.status, func.count(Bando.id)
        ).group_by(Bando.status).all()
        bandi_status_dict = {status: count for status, count in bandi_by_status}
        
        # Top utenti più attivi (per numero di bandi salvati)
        top_users = User.query.with_entities(
            User.id, User.email, func.count(Bando.id).label('bandi_count')
        ).join(Bando).group_by(User.id).order_by(
            func.count(Bando.id).desc()
        ).limit(5).all()
        
        stats = {
            'users': {
                'total': total_users,
                'today': users_today,
                'this_week': users_this_week,
                'this_month': users_this_month,
                'active_7d': active_users
            },
            'bandi': {
                'total': total_bandi,
                'today': bandi_today,
                'this_week': bandi_this_week,
                'this_month': bandi_this_month,
                'by_status': bandi_status_dict
            },
            'top_users': [
                {'id': u.id, 'email': u.email, 'bandi_count': u.bandi_count}
                for u in top_users
            ]
        }
        
        return render_template('admin/dashboard.html', stats=stats, timestamp=datetime.utcnow())
    
    except Exception as e:
        current_app.logger.error(f'Errore dashboard admin: {str(e)}')
        return jsonify({'error': f'Errore nel caricamento dashboard: {str(e)}'}), 500

@admin_bp.route('/utenti', methods=['GET'])
@login_required
def utenti():
    """Lista tutti gli utenti con filtri e paginazione."""
    try:
        if not check_admin():
            return jsonify({'error': 'Accesso negato. Non sei un admin.'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        
        query = User.query
        
        # Filtro ricerca
        if search:
            query = query.filter(
                (User.email.ilike(f'%{search}%')) |
                (User.nome.ilike(f'%{search}%')) |
                (User.cognome.ilike(f'%{search}%'))
            )
        
        # Paginazione
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        utenti_list = pagination.items
        
        # Arricchisci dati utenti
        utenti_data = []
        for u in utenti_list:
            bandi_count = Bando.query.filter_by(user_id=u.id).count()
            utenti_data.append({
                'id': u.id,
                'email': u.email,
                'nome': u.nome,
                'cognome': u.cognome,
                'created_at': u.created_at,
                'last_login': u.last_login,
                'bandi_count': bandi_count
            })
        
        return render_template(
            'admin/utenti.html',
            utenti=utenti_data,
            pagination=pagination,
            search=search
        )
    
    except Exception as e:
        current_app.logger.error(f'Errore lista utenti: {str(e)}')
        return jsonify({'error': f'Errore nel caricamento utenti: {str(e)}'}), 500

@admin_bp.route('/scraper', methods=['POST'])
@login_required
def scraper():
    """Avvia scraping manuale dei bandi (richiede login admin)."""
    try:
        if not check_admin():
            return jsonify({'error': 'Accesso negato. Non sei un admin.'}), 403

        data = request.get_json(silent=True) or {}
        priorita = data.get('priorita', None)
        fonte = data.get('fonte', None)

        from run_scraper import run_scraper as esegui_scraper
        result = esegui_scraper(priorita=priorita, fonte_singola=fonte)

        return jsonify({'success': True, 'result': result}), 200

    except Exception as e:
        current_app.logger.error(f'Errore scraper: {str(e)}')
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/scraper/cron', methods=['POST'])
def scraper_cron():
    """Endpoint per Railway Cron Job - protetto da CRON_SECRET env var."""
    secret = os.getenv('CRON_SECRET', '')
    auth_header = request.headers.get('Authorization', '')
    if not secret or auth_header != f'Bearer {secret}':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from run_scraper import run_scraper as esegui_scraper
        result = esegui_scraper(priorita=1)  # Solo fonti nazionali prioritarie
        return jsonify({'success': True, 'result': result}), 200
    except Exception as e:
        current_app.logger.error(f'Errore cron scraper: {str(e)}')
        return jsonify({'error': str(e)}), 500

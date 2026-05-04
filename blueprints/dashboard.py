from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.bando import Bando
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@dashboard_bp.route('/home')
@login_required
def home():
    """Pagina principale della dashboard utente."""
    try:
        # Recupera i bandi aperti ordinati per data scraping
        bandi_db = Bando.query.filter_by(stato='APERTO').order_by(
            Bando.data_scraping.desc()
        ).limit(20).all()

        # Costruisce la lista bandi con score simulato (in attesa del motore AI)
        bandi = []
        for b in bandi_db:
            # Score placeholder basato su dati disponibili
            score = 70  # default
            bandi.append({
                'id': b.id,
                'titolo': b.titolo,
                'categoria': b.fonte or 'N/A',
                'scadenza': b.data_scadenza.strftime('%d/%m/%Y') if b.data_scadenza else 'N/A',
                'score': score,
            })

        # Statistiche dashboard
        total_bandi = Bando.query.filter_by(stato='APERTO').count()
        active_matches = len(bandi)
        avg_score = round(sum(b['score'] for b in bandi) / len(bandi), 1) if bandi else 0.0
        last_update = datetime.utcnow().strftime('%d/%m/%Y %H:%M')

        user_name = current_user.email.split('@')[0].capitalize()

        return render_template(
            'dashboard.html',
            bandi=bandi,
            user_name=user_name,
            total_bandi=total_bandi,
            active_matches=active_matches,
            avg_score=avg_score,
            last_update=last_update,
        )
    except Exception as e:
        # Fallback con dati vuoti in caso di errore DB
        return render_template(
            'dashboard.html',
            bandi=[],
            user_name=current_user.email.split('@')[0].capitalize(),
            total_bandi=0,
            active_matches=0,
            avg_score=0.0,
            last_update='N/A',
        )

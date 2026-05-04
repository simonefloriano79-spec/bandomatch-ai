"""
BandoMatch AI — blueprints/admin.py
Pannello di amministrazione protetto da @admin_required.

Route:
  GET  /admin/                → dashboard con statistiche e KPI
  GET  /admin/utenti          → tabella tutti gli utenti + azioni
  POST /admin/utenti/<id>/piano   → aggiorna piano utente
  POST /admin/utenti/<id>/blocca  → attiva/disattiva account
  GET  /admin/abbonati        → tabella utenti Premium e Pro
  GET  /admin/bandi           → tabella bandi nel DB + azioni
  POST /admin/bandi/<id>/stato    → attiva/disattiva bando
  GET  /admin/scraper         → log scraping + pulsante avvia
  POST /admin/scraper/avvia   → avvia scraping manuale
  POST /admin/scraper/cron    → endpoint Railway Cron Job (Bearer token)
  POST /admin/bandi/import    → import bandi in bulk (JSON)
  POST /admin/set-piano       → aggiorna piano utente via API (Bearer token)
"""
import os
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint, render_template, request, jsonify,
    current_app, redirect, url_for, flash
)
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models.utente import Utente, ProfiloAziendale
from models.bando import Bando
from models.analisi import Analisi

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ─────────────────────────────────────────────────────────────────────────────
# Decoratore @admin_required
# ─────────────────────────────────────────────────────────────────────────────

def admin_required(f):
    """Verifica che l'utente sia autenticato e la sua email sia in ADMIN_EMAIL."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        admin_emails = [
            e.strip()
            for e in os.getenv('ADMIN_EMAIL', '').split(',')
            if e.strip()
        ]
        if current_user.email not in admin_emails:
            flash('Accesso riservato agli amministratori.', 'error')
            return redirect(url_for('dashboard.home'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Helper: calcola MRR
# ─────────────────────────────────────────────────────────────────────────────

def _calcola_mrr() -> float:
    """MRR = (n. Premium × 9,90) + (n. Pro × 29,90)."""
    n_premium = Utente.query.filter_by(piano='premium', attivo=True).count()
    n_pro = Utente.query.filter_by(piano='pro', attivo=True).count()
    return round(n_premium * 9.90 + n_pro * 29.90, 2)


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/   — Dashboard principale
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def index():
    """Dashboard admin con KPI e statistiche."""
    oggi = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Utenti
    totale_iscritti = Utente.query.count()
    iscritti_oggi = Utente.query.filter(Utente.data_registrazione >= oggi).count()
    abbonati_premium = Utente.query.filter_by(piano='premium', attivo=True).count()
    abbonati_pro = Utente.query.filter_by(piano='pro', attivo=True).count()
    mrr = _calcola_mrr()

    # Bandi
    totale_bandi = Bando.query.count()
    bandi_aperti = Bando.query.filter_by(stato='APERTO').count()

    # Ultimo scraping
    ultimo_bando = Bando.query.order_by(Bando.data_scraping.desc()).first()
    ultimo_scraping = (
        ultimo_bando.data_scraping.strftime('%d/%m/%Y %H:%M')
        if ultimo_bando and ultimo_bando.data_scraping else 'Mai'
    )

    # Analisi totali
    totale_analisi = Analisi.query.count()

    stats = {
        'totale_iscritti': totale_iscritti,
        'iscritti_oggi': iscritti_oggi,
        'abbonati_premium': abbonati_premium,
        'abbonati_pro': abbonati_pro,
        'mrr': mrr,
        'totale_bandi': totale_bandi,
        'bandi_aperti': bandi_aperti,
        'ultimo_scraping': ultimo_scraping,
        'totale_analisi': totale_analisi,
    }
    return render_template('admin.html', sezione='dashboard', stats=stats)


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/utenti  — Tabella utenti
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/utenti')
@admin_required
def utenti():
    """Tabella di tutti gli utenti con azioni."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '', type=str).strip()

    query = Utente.query
    if search:
        query = query.filter(Utente.email.ilike(f'%{search}%'))

    pagination = query.order_by(Utente.data_registrazione.desc()).paginate(
        page=page, per_page=25, error_out=False
    )

    return render_template(
        'admin.html',
        sezione='utenti',
        utenti=pagination.items,
        pagination=pagination,
        search=search,
    )


@admin_bp.route('/utenti/<int:utente_id>/piano', methods=['POST'])
@admin_required
def aggiorna_piano(utente_id: int):
    """Aggiorna il piano di un utente (form POST)."""
    nuovo_piano = request.form.get('piano', '').strip().lower()
    piani_validi = ('free', 'starter', 'premium', 'pro', 'enterprise')
    if nuovo_piano not in piani_validi:
        flash('Piano non valido.', 'error')
        return redirect(url_for('admin.utenti'))

    utente = Utente.query.get_or_404(utente_id)
    utente.piano = nuovo_piano
    db.session.commit()
    flash(f'Piano di {utente.email} aggiornato a {nuovo_piano}.', 'success')
    return redirect(url_for('admin.utenti'))


@admin_bp.route('/utenti/<int:utente_id>/blocca', methods=['POST'])
@admin_required
def blocca_utente(utente_id: int):
    """Attiva o disattiva un account utente."""
    utente = Utente.query.get_or_404(utente_id)
    utente.attivo = not utente.attivo
    db.session.commit()
    stato = 'attivato' if utente.attivo else 'disattivato'
    flash(f'Account {utente.email} {stato}.', 'success')
    return redirect(url_for('admin.utenti'))


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/abbonati  — Solo Premium e Pro
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/abbonati')
@admin_required
def abbonati():
    """Tabella utenti Premium e Pro."""
    abbonati_list = (
        Utente.query
        .filter(Utente.piano.in_(['premium', 'pro']))
        .order_by(Utente.data_registrazione.desc())
        .all()
    )
    return render_template('admin.html', sezione='abbonati', abbonati=abbonati_list)


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/bandi  — Tabella bandi
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/bandi')
@admin_required
def bandi():
    """Tabella di tutti i bandi nel DB con azioni."""
    page = request.args.get('page', 1, type=int)
    stato_filtro = request.args.get('stato', '', type=str).strip().upper()

    query = Bando.query
    if stato_filtro:
        query = query.filter_by(stato=stato_filtro)

    pagination = query.order_by(Bando.data_scraping.desc()).paginate(
        page=page, per_page=30, error_out=False
    )

    return render_template(
        'admin.html',
        sezione='bandi',
        bandi=pagination.items,
        pagination=pagination,
        stato_filtro=stato_filtro,
    )


@admin_bp.route('/bandi/<int:bando_id>/stato', methods=['POST'])
@admin_required
def aggiorna_stato_bando(bando_id: int):
    """Attiva o disattiva un bando."""
    bando = Bando.query.get_or_404(bando_id)
    nuovo_stato = request.form.get('stato', 'APERTO').strip().upper()
    stati_validi = ('APERTO', 'CHIUSO', 'SOSPESO', 'RIAPERTO')
    if nuovo_stato not in stati_validi:
        flash('Stato non valido.', 'error')
        return redirect(url_for('admin.bandi'))
    bando.stato = nuovo_stato
    bando.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Bando "{bando.titolo[:50]}" impostato a {nuovo_stato}.', 'success')
    return redirect(url_for('admin.bandi'))


# ─────────────────────────────────────────────────────────────────────────────
# GET /admin/scraper  — Log scraping + avvia manuale
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/scraper')
@admin_required
def scraper_panel():
    """Pannello scraper con log ultimi bandi e pulsante avvia."""
    ultimi_bandi = (
        Bando.query
        .order_by(Bando.data_scraping.desc())
        .limit(20)
        .all()
    )
    return render_template('admin.html', sezione='scraper', ultimi_bandi=ultimi_bandi)


@admin_bp.route('/scraper/avvia', methods=['POST'])
@admin_required
def scraper_avvia():
    """Avvia scraping manuale (chiamata AJAX dal pannello admin)."""
    try:
        from run_scraper import run_scraper as esegui_scraper
        result = esegui_scraper(priorita=1)
        return jsonify({'success': True, 'result': result}), 200
    except Exception as e:
        current_app.logger.error(f'Errore scraper manuale: {e}')
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /admin/scraper/cron  — Railway Cron Job (Bearer token)
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/scraper/cron', methods=['POST'])
def scraper_cron():
    """Endpoint per Railway Cron Job — protetto da CRON_SECRET."""
    secret = os.getenv('CRON_SECRET', 'bandomatch2026secret')
    auth_header = request.headers.get('Authorization', '')
    if auth_header != f'Bearer {secret}':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from run_scraper import run_scraper as esegui_scraper
        result = esegui_scraper(priorita=1)
        return jsonify({'success': True, 'result': result}), 200
    except Exception as e:
        current_app.logger.error(f'Errore cron scraper: {e}')
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /admin/bandi/import  — Import bandi in bulk (JSON)
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/bandi/import', methods=['POST'])
def import_bandi():
    """Importa bandi in bulk nel DB PostgreSQL."""
    try:
        data = request.get_json(silent=True) or {}
        bandi_list = data.get('bandi', [])
        if not bandi_list:
            return jsonify({'error': 'Nessun bando fornito'}), 400

        nuovi = aggiornati = errori = 0

        for bd in bandi_list:
            try:
                titolo = (bd.get('titolo') or '')[:500]
                url = (bd.get('url') or '')[:1000]
                if not titolo or not url:
                    errori += 1
                    continue

                def parse_dt(s):
                    if not s:
                        return None
                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(str(s)[:19], fmt)
                        except ValueError:
                            pass
                    return None

                esistente = Bando.query.filter_by(url=url).first()
                if not esistente:
                    esistente = Bando.query.filter_by(titolo=titolo).first()

                if esistente:
                    esistente.stato = bd.get('stato', 'APERTO')
                    esistente.updated_at = datetime.utcnow()
                    aggiornati += 1
                else:
                    nuovo = Bando(
                        titolo=titolo,
                        descrizione=bd.get('descrizione'),
                        url=url,
                        fonte=(bd.get('fonte') or 'Import')[:255],
                        stato=bd.get('stato', 'APERTO'),
                        data_apertura=parse_dt(bd.get('data_apertura')),
                        data_scadenza=parse_dt(bd.get('data_scadenza')),
                        regioni_ammesse=bd.get('regioni_ammesse'),
                        ateco_ammessi=bd.get('ateco_ammessi'),
                        massimale_agevolazione=bd.get('massimale_agevolazione'),
                        percentuale_fondo_perduto=bd.get('percentuale_fondo_perduto'),
                        data_scraping=datetime.utcnow(),
                    )
                    db.session.add(nuovo)
                    nuovi += 1
            except Exception as e:
                current_app.logger.warning(f'Errore bando import: {e}')
                errori += 1

        db.session.commit()
        totale = Bando.query.count()
        return jsonify({
            'success': True, 'nuovi': nuovi,
            'aggiornati': aggiornati, 'errori': errori,
            'totale_db': totale,
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Errore import bandi: {e}')
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /admin/set-piano  — Aggiorna piano via API (Bearer token)
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/set-piano', methods=['POST'])
def set_piano():
    """Aggiorna il piano di un utente — protetto da CRON_SECRET."""
    secret = os.getenv('CRON_SECRET', 'bandomatch2026secret')
    auth_header = request.headers.get('Authorization', '')
    if auth_header != f'Bearer {secret}':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    piano = data.get('piano', '').strip().lower()

    if not email or piano not in ('free', 'starter', 'premium', 'pro', 'enterprise'):
        return jsonify({'error': 'Parametri non validi'}), 400

    utente = Utente.query.filter_by(email=email).first()
    if not utente:
        return jsonify({'error': 'Utente non trovato'}), 404

    utente.piano = piano
    db.session.commit()
    return jsonify({'success': True, 'email': email, 'piano': piano}), 200

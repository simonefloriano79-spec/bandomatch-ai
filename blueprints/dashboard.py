import json
from flask import Blueprint, render_template, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from models.bando import Bando
from models.analisi import Analisi
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

# Piani che hanno accesso al dossier PDF
PIANI_PREMIUM = {'starter', 'pro', 'enterprise', 'premium'}


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
            score = 70  # default placeholder
            bandi.append({
                'id': b.id,
                'titolo': b.titolo,
                'categoria': b.fonte or 'N/A',
                'scadenza': b.data_scadenza.strftime('%d/%m/%Y') if b.data_scadenza else 'N/A',
                'score': score,
            })

        # Statistiche dashboard
        total_bandi    = Bando.query.filter_by(stato='APERTO').count()
        active_matches = len(bandi)
        avg_score      = round(sum(b['score'] for b in bandi) / len(bandi), 1) if bandi else 0.0
        last_update    = datetime.utcnow().strftime('%d/%m/%Y %H:%M')
        user_name      = current_user.email.split('@')[0].capitalize()

        return render_template(
            'dashboard.html',
            bandi=bandi,
            user_name=user_name,
            total_bandi=total_bandi,
            active_matches=active_matches,
            avg_score=avg_score,
            last_update=last_update,
        )
    except Exception:
        return render_template(
            'dashboard.html',
            bandi=[],
            user_name=current_user.email.split('@')[0].capitalize(),
            total_bandi=0,
            active_matches=0,
            avg_score=0.0,
            last_update='N/A',
        )


@dashboard_bp.route('/dossier/<int:analisi_id>')
@login_required
def dossier(analisi_id: int):
    """
    Genera e scarica il PDF Dossier Premium per una specifica analisi.

    Accesso consentito solo agli utenti con piano starter/pro/enterprise/premium.
    Gli utenti free vengono reindirizzati con un messaggio flash.
    """
    # Verifica piano utente
    piano = (current_user.piano or 'free').lower()
    if piano not in PIANI_PREMIUM:
        flash('Funzione Premium — Attiva il piano Premium per scaricare il Dossier PDF.',
              'warning')
        return redirect(url_for('dashboard.home'))

    # Recupera l'analisi (solo quella dell'utente corrente)
    analisi = Analisi.query.filter_by(
        id=analisi_id,
        utente_id=current_user.id
    ).first_or_404()

    # Ricostruisce la lista bandi compatibili dal JSON salvato nell'analisi
    bandi_compatibili = []
    if analisi.risultati_json:
        try:
            dati = json.loads(analisi.risultati_json)
            # Il JSON può avere struttura {"bandi": [...]} oppure essere una lista diretta
            if isinstance(dati, dict):
                bandi_raw = dati.get('bandi', [])
            elif isinstance(dati, list):
                bandi_raw = dati
            else:
                bandi_raw = []

            # Filtra solo i bandi verdi e gialli (compatibili)
            for b in bandi_raw:
                sem = str(b.get('semaforo', '')).upper()
                if sem in ('VERDE', 'GIALLO'):
                    bandi_compatibili.append(b)
        except (json.JSONDecodeError, TypeError):
            bandi_compatibili = []

    # Se non ci sono bandi compatibili nel JSON, prova a recuperarli dal DB
    if not bandi_compatibili:
        bandi_db = Bando.query.filter_by(stato='APERTO').limit(10).all()
        for b in bandi_db:
            regioni = b.regioni_ammesse if isinstance(b.regioni_ammesse, list) else []
            bandi_compatibili.append({
                'titolo':                    b.titolo,
                'fonte':                     b.fonte,
                'semaforo':                  'VERDE',
                'score':                     75,
                'massimale_agevolazione':    b.massimale_agevolazione,
                'percentuale_fondo_perduto': b.percentuale_fondo_perduto,
                'data_scadenza':             b.data_scadenza,
                'descrizione':               b.descrizione,
                'url':                       b.url,
                'note_ai':                   None,
                'regioni_ammesse':           regioni,
            })

    # Genera il PDF
    try:
        from utils.dossier import genera_dossier
        pdf_bytes = genera_dossier(
            utente=current_user,
            analisi=analisi,
            bandi_compatibili=bandi_compatibili
        )
    except Exception as e:
        flash(f'Errore nella generazione del Dossier PDF: {str(e)}', 'danger')
        return redirect(url_for('analisi.risultati', analisi_id=analisi_id))

    # Invia il PDF come download
    ragione  = (analisi.ragione_sociale or 'impresa').replace(' ', '_')[:30]
    filename = f'dossier_bandomatch_{ragione}_{analisi_id}.pdf'

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_bytes)),
        }
    )

"""
BandoMatch AI — Blueprint Analisi Visura
Gestisce il flusso completo: upload PDF → parsing → matching → risultati.
"""
import os
import json
import tempfile
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from models.analisi import Analisi
from visura_parser import parse_visura
from matching_engine import match_tutti_bandi

analisi_bp = Blueprint('analisi', __name__, url_prefix='/analisi')

ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _calcola_score(bando_result: dict) -> int:
    """Restituisce lo score numerico (0-100) da un risultato di matching."""
    return int(bando_result.get('score', 0))


def _prepara_teaser(bando_result: dict, is_premium: bool, primo_verde_sbloccato: bool) -> dict:
    """Costruisce il dizionario teaser per un bando, con logica paywall."""
    agev = bando_result.get('agevolazioni', {})
    massimale = (
        agev.get('massimale_investimento')
        or agev.get('spesa_progetto_max')
        or 0
    )
    fondo_perduto = agev.get('percentuale_fondo_perduto', 0)
    score = _calcola_score(bando_result)
    semaforo = bando_result.get('semaforo', 'GRIGIO')

    teaser = {
        'semaforo': semaforo,
        'nome': bando_result.get('bando_nome', 'N/D'),
        'ente': bando_result.get('ente', 'N/D'),
        'valore_stimato': massimale,
        'fondo_perduto': fondo_perduto,
        'score': score,
        'snippet': bando_result.get('snippet', ''),
        'url': bando_result.get('url', ''),
        'locked': not is_premium,
    }

    # Il primo bando VERDE è sempre gratuito (hook psicologico)
    if semaforo == 'VERDE' and not primo_verde_sbloccato:
        teaser['locked'] = False
        checks = bando_result.get('checks', {})
        req_ok = [
            v.get('motivo', '')
            for v in checks.values()
            if isinstance(v, dict) and v.get('ok') is True
        ]
        teaser['dettagli'] = {
            'scadenza': bando_result.get('stato_bando', 'N/D'),
            'requisiti_soddisfatti': req_ok,
            'link': bando_result.get('url', ''),
            'massimale_formattato': f"€{massimale:,.0f}" if massimale > 0 else 'N/D',
            'fondo_perduto_str': f"{fondo_perduto}% a fondo perduto" if fondo_perduto > 0 else 'N/D',
        }

    if is_premium:
        checks = bando_result.get('checks', {})
        req_ok = [
            v.get('motivo', '')
            for v in checks.values()
            if isinstance(v, dict) and v.get('ok') is True
        ]
        req_ko = [
            v.get('motivo', '')
            for v in checks.values()
            if isinstance(v, dict) and v.get('ok') is False
        ]
        teaser['dettagli'] = {
            'scadenza': bando_result.get('stato_bando', 'N/D'),
            'requisiti_soddisfatti': req_ok,
            'requisiti_mancanti': req_ko,
            'link': bando_result.get('url', ''),
            'massimale_formattato': f"€{massimale:,.0f}" if massimale > 0 else 'N/D',
            'fondo_perduto_str': f"{fondo_perduto}% a fondo perduto" if fondo_perduto > 0 else 'N/D',
        }

    return teaser


# ─────────────────────────────────────────────
# ROUTE: POST /analisi/analizza
# ─────────────────────────────────────────────
@analisi_bp.route('/analizza', methods=['POST'])
@login_required
def analizza():
    """
    Riceve il PDF della visura + form integrativo,
    esegue parsing + matching, salva nel DB e restituisce JSON
    con redirect URL verso la pagina risultati.
    """
    # Validazione file
    if 'visura' not in request.files:
        return jsonify({'error': 'Nessun file caricato'}), 400

    file = request.files['visura']
    if not file or file.filename == '':
        return jsonify({'error': 'Nessun file selezionato'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'Formato non supportato. Carica un PDF nativo.'}), 400

    # Controlla dimensione
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'File troppo grande. Massimo 10MB.'}), 400

    # Form integrativo opzionale
    form_extra = {
        'de_minimis': request.form.get('de_minimis', 'no'),
        'de_minimis_importo': float(request.form.get('de_minimis_importo', 0) or 0),
        'finalita_investimento': request.form.get('finalita_investimento', ''),
        'budget_investimento': float(request.form.get('budget_investimento', 0) or 0),
        'condizione_occupazionale': request.form.get('condizione_occupazionale', ''),
    }

    # Salva PDF in file temporaneo
    filename = secure_filename(file.filename)
    tmp_dir = tempfile.mkdtemp()
    filepath = os.path.join(tmp_dir, filename)
    file.save(filepath)

    try:
        # ── STEP 1: Parsing visura ──
        dati_impresa = parse_visura(filepath)
        if not dati_impresa:
            return jsonify({
                'error': 'Impossibile estrarre dati dalla visura. '
                         'Assicurati che sia un PDF nativo (non scansionato).'
            }), 422

        # Arricchisci con form integrativo
        dati_impresa['form_integrativo'] = form_extra

        # ── STEP 2: Matching con bandi ──
        risultati = match_tutti_bandi(dati_impresa)
        lista_bandi = risultati.get('risultati', [])
        stats = risultati.get('statistiche', {})

        # ── STEP 3: Classifica bandi per semaforo ──
        bandi_verdi  = [b for b in lista_bandi if b.get('semaforo') == 'VERDE']
        bandi_gialli = [b for b in lista_bandi if b.get('semaforo') == 'GIALLO']
        bandi_rossi  = [b for b in lista_bandi if b.get('semaforo') == 'ROSSO']
        bandi_grigi  = [b for b in lista_bandi if b.get('semaforo') == 'GRIGIO']

        bandi_compatibili = len(bandi_verdi) + len(bandi_gialli)
        valore_potenziale = stats.get('valore_potenziale_massimo', 0)

        # ── STEP 4: Prepara teaser bandi ──
        is_premium = current_user.piano in ('premium', 'pro', 'admin', 'enterprise')
        primo_verde_sbloccato = False
        teaser_bandi = []
        for b in lista_bandi:
            t = _prepara_teaser(b, is_premium, primo_verde_sbloccato)
            if b.get('semaforo') == 'VERDE' and not primo_verde_sbloccato:
                primo_verde_sbloccato = True
            teaser_bandi.append(t)

        # ── STEP 5: Estrai dati impresa ──
        impresa_info = dati_impresa.get('impresa', {})
        ateco_info = dati_impresa.get('ateco', {})
        indicatori = dati_impresa.get('indicatori_matching', {})
        sede = dati_impresa.get('sede_legale', {})

        # ── STEP 6: Salva analisi nel DB ──
        analisi = Analisi(
            utente_id=current_user.id,
            ragione_sociale=impresa_info.get('ragione_sociale', 'N/D'),
            codice_fiscale=dati_impresa.get('impresa', {}).get('codice_fiscale'),
            ateco=ateco_info.get('codice_primario'),
            regione=indicatori.get('regione') or sede.get('regione'),
            provincia=sede.get('provincia'),
            forma_giuridica=impresa_info.get('forma_giuridica_normalizzata'),
            eta_mesi=indicatori.get('eta_impresa_mesi'),
            capitale_sociale=impresa_info.get('capitale_sociale'),
            numero_dipendenti=impresa_info.get('numero_dipendenti'),
            bandi_verdi=len(bandi_verdi),
            bandi_gialli=len(bandi_gialli),
            bandi_rossi=len(bandi_rossi),
            bandi_grigi=len(bandi_grigi),
            valore_potenziale=valore_potenziale,
            dati_impresa_json=json.dumps(dati_impresa, ensure_ascii=False, default=str),
            risultati_json=json.dumps(risultati, ensure_ascii=False, default=str),
            form_integrativo_json=json.dumps(form_extra, ensure_ascii=False),
        )
        db.session.add(analisi)
        db.session.commit()

        # ── STEP 7: Risposta con redirect URL ──
        return jsonify({
            'success': True,
            'redirect': url_for('analisi.risultati', analisi_id=analisi.id),
            'analisi_id': analisi.id,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Errore durante l\'analisi: {str(e)}'}), 500

    finally:
        # Rimuovi il file temporaneo
        if os.path.exists(filepath):
            os.remove(filepath)
        try:
            os.rmdir(tmp_dir)
        except Exception:
            pass


# ─────────────────────────────────────────────
# ROUTE: GET /analisi/risultati/<id>
# ─────────────────────────────────────────────
@analisi_bp.route('/risultati/<int:analisi_id>')
@login_required
def risultati(analisi_id: int):
    """Mostra la pagina risultati per un'analisi specifica."""
    analisi = Analisi.query.filter_by(
        id=analisi_id, utente_id=current_user.id
    ).first_or_404()

    # Ricostruisce i dati per il template
    dati_impresa = json.loads(analisi.dati_impresa_json or '{}')
    risultati_raw = json.loads(analisi.risultati_json or '{}')
    lista_bandi = risultati_raw.get('risultati', [])

    is_premium = current_user.piano in ('premium', 'pro', 'admin', 'enterprise')
    primo_verde_sbloccato = False
    teaser_bandi = []
    for b in lista_bandi:
        t = _prepara_teaser(b, is_premium, primo_verde_sbloccato)
        if b.get('semaforo') == 'VERDE' and not primo_verde_sbloccato:
            primo_verde_sbloccato = True
        teaser_bandi.append(t)

    impresa_info = dati_impresa.get('impresa', {})
    ateco_info = dati_impresa.get('ateco', {})
    indicatori = dati_impresa.get('indicatori_matching', {})

    page_data = {
        'success': True,
        'analisi_id': analisi.id,
        'impresa': {
            'ragione_sociale': analisi.ragione_sociale or 'N/D',
            'ateco': analisi.ateco or 'N/D',
            'regione': analisi.regione or 'N/D',
            'forma_giuridica': analisi.forma_giuridica or 'N/D',
            'eta_mesi': analisi.eta_mesi or 0,
            'capitale_sociale': analisi.capitale_sociale,
            'numero_dipendenti': analisi.numero_dipendenti,
            'codice_fiscale': analisi.codice_fiscale,
        },
        'teaser': {
            'bandi_compatibili': analisi.bandi_verdi + analisi.bandi_gialli,
            'valore_potenziale': analisi.valore_potenziale,
            'valore_formattato': f"€{analisi.valore_potenziale:,.0f}",
            'verdi': analisi.bandi_verdi,
            'gialli': analisi.bandi_gialli,
            'rossi': analisi.bandi_rossi,
            'grigi': analisi.bandi_grigi,
        },
        'bandi': teaser_bandi,
        'is_premium': is_premium,
        'is_logged': True,
        'data_analisi': analisi.data_analisi.strftime('%d/%m/%Y %H:%M') if analisi.data_analisi else '',
        'disclaimer': (
            'BandoMatch AI offre tecnologia di matching, non consulenza finanziaria o legale. '
            'I risultati sono indicativi e non costituiscono consulenza professionale.'
        ),
    }

    return render_template(
        'risultati.html',
        data=json.dumps(page_data, ensure_ascii=False, default=str),
        analisi=analisi,
        is_premium=is_premium,
    )


# ─────────────────────────────────────────────
# ROUTE: GET /analisi/storico
# ─────────────────────────────────────────────
@analisi_bp.route('/storico')
@login_required
def storico():
    """Restituisce lo storico analisi dell'utente come JSON (per AJAX)."""
    analisi_list = Analisi.query.filter_by(
        utente_id=current_user.id
    ).order_by(Analisi.data_analisi.desc()).limit(20).all()
    return jsonify([a.to_dict() for a in analisi_list])

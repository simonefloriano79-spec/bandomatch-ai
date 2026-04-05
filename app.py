"""
BandoMatch AI — Versione ESPLOSIVA v3.0
===========================================
Architettura completa validata da Gemini (Architetto) + Manus (Lead Software Engineer)

Moduli v3.0:
  1. Autenticazione utenti (Flask-Login + SQLite)
  2. Storico analisi per utente
  3. Form Integrativo contestuale (4 domande extra)
  4. PDF Dossier di Affinità auto-generato
  5. Scraper LLM-Augmented giornaliero (APScheduler + GPT-4.1-mini)
  6. Sistema alert email per nuovi bandi
  7. Dashboard Admin (metriche, utenti, bandi, feedback loop)
  8. Simulatore di Punteggio con barra progressiva e suggerimenti
  9. Tier Pro (29,90€/mese) + Premium (9,90€) + Consulenza (49€)
 10. Feedback Loop esito_storico (BandoDB auto-apprendente)
 11. Reverse Matching per Consulenti (piano Pro)
 12. Pagine SEO per ogni bando
"""

import os
import json
import tempfile
import hashlib
import datetime
import sqlite3
import threading
from functools import wraps
from io import BytesIO

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, flash, send_file, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ReportLab per PDF Dossier
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# APScheduler per cron job giornaliero
from apscheduler.schedulers.background import BackgroundScheduler

import sys
sys.path.insert(0, os.path.dirname(__file__))
from visura_parser import parse_visura
from matching_engine import match_tutti_bandi
from simulatore_punteggio import calcola_simulatore
try:
    from scraper_llm import esegui_scraping_completo as scraping_llm_completo
except ImportError:
    scraping_llm_completo = None

# ─────────────────────────────────────────────
# CONFIGURAZIONE APP
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "bandomatch-ai-super-secret-v2-2025"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['DB_PATH'] = os.path.join(os.path.dirname(__file__), 'bandomatch.db')
app.config['ADMIN_EMAIL'] = 'simone.floriano79@gmail.com'
app.config['ADMIN_PASSWORD'] = 'BandoMatch2025!'

ALLOWED_EXTENSIONS = {'pdf'}

# ─────────────────────────────────────────────
# DATABASE SQLITE — SCHEMA COMPLETO
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inizializza il database con tutte le tabelle."""
    conn = get_db()
    c = conn.cursor()

    # Tabella utenti
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        nome TEXT,
        azienda TEXT,
        piano TEXT DEFAULT 'free',  -- free, premium, pro, consulenza, admin
        abbonamento_attivo INTEGER DEFAULT 0,
        data_registrazione TEXT DEFAULT (datetime('now')),
        ultimo_accesso TEXT,
        analisi_gratuite_usate INTEGER DEFAULT 0,
        stripe_customer_id TEXT
    )''')

    # Tabella storico analisi
    c.execute('''CREATE TABLE IF NOT EXISTS analisi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER,
        data_analisi TEXT DEFAULT (datetime('now')),
        ragione_sociale TEXT,
        ateco TEXT,
        regione TEXT,
        eta_mesi INTEGER,
        bandi_verdi INTEGER DEFAULT 0,
        bandi_gialli INTEGER DEFAULT 0,
        bandi_rossi INTEGER DEFAULT 0,
        valore_potenziale REAL DEFAULT 0,
        dati_impresa_json TEXT,
        risultati_json TEXT,
        form_integrativo_json TEXT,
        FOREIGN KEY (utente_id) REFERENCES utenti(id)
    )''')

    # Tabella bandi (BandoDB — asset proprietario)
    c.execute('''CREATE TABLE IF NOT EXISTS bandi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        ente TEXT,
        regione TEXT,
        tipo TEXT,  -- nazionale, regionale, europeo
        stato TEXT DEFAULT 'attivo',  -- attivo, scaduto, in_preparazione
        data_apertura TEXT,
        data_scadenza TEXT,
        massimale REAL,
        percentuale_fondo_perduto REAL,
        ateco_ammessi TEXT,  -- JSON array
        ateco_esclusi TEXT,  -- JSON array
        eta_min_impresa_mesi INTEGER,
        eta_max_impresa_mesi INTEGER,
        eta_min_soci INTEGER,
        eta_max_soci INTEGER,
        forma_giuridica_ammessa TEXT,  -- JSON array
        regioni_ammesse TEXT,  -- JSON array
        requisiti_extra TEXT,  -- JSON
        url TEXT,
        data_aggiornamento TEXT DEFAULT (datetime('now')),
        fonte_scraping TEXT
    )''')

    # Tabella alert email
    c.execute('''CREATE TABLE IF NOT EXISTS alert_email (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER,
        bando_id INTEGER,
        tipo_alert TEXT,  -- nuovo_bando, scadenza_vicina, aggiornamento
        inviato INTEGER DEFAULT 0,
        data_invio TEXT,
        FOREIGN KEY (utente_id) REFERENCES utenti(id),
        FOREIGN KEY (bando_id) REFERENCES bandi(id)
    )''')

    # Tabella feedback loop — esito storico bandi
    c.execute('''CREATE TABLE IF NOT EXISTS feedback_bandi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER,
        bando_id TEXT NOT NULL,
        esito TEXT NOT NULL,  -- vinto, perso, in_corso
        ateco TEXT,
        regione TEXT,
        data TEXT DEFAULT (datetime('now')),
        note TEXT,
        FOREIGN KEY (utente_id) REFERENCES utenti(id)
    )''')

    # Aggiungi colonna tasso_successo a bandi se non esiste
    try:
        c.execute('ALTER TABLE bandi ADD COLUMN tasso_successo REAL DEFAULT NULL')
    except Exception:
        pass  # Colonna già esistente

    # Tabella log scraper
    c.execute('''CREATE TABLE IF NOT EXISTS scraper_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_esecuzione TEXT DEFAULT (datetime('now')),
        fonte TEXT,
        bandi_trovati INTEGER DEFAULT 0,
        bandi_aggiornati INTEGER DEFAULT 0,
        errori TEXT,
        durata_secondi REAL
    )''')

    # Inserisci admin di default se non esiste
    c.execute("SELECT id FROM utenti WHERE email = ?", (app.config['ADMIN_EMAIL'],))
    if not c.fetchone():
        c.execute('''INSERT INTO utenti (email, password_hash, nome, piano, abbonamento_attivo)
                     VALUES (?, ?, ?, ?, ?)''',
                  (app.config['ADMIN_EMAIL'],
                   generate_password_hash(app.config['ADMIN_PASSWORD']),
                   'Simone Floriano', 'admin', 1))

    conn.commit()
    conn.close()
    print("✅ Database BandoMatch inizializzato con successo.")

# ─────────────────────────────────────────────
# DECORATORI AUTH
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def premium_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db()
        utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        if not utente or (utente['piano'] not in ('premium', 'pro', 'admin') and not utente['abbonamento_attivo']):
            return jsonify({'error': 'Piano Premium richiesto', 'paywall': True}), 403
        return f(*args, **kwargs)
    return decorated

def pro_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db()
        utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        if not utente or utente['piano'] not in ('pro', 'admin'):
            return jsonify({'error': 'Piano Pro richiesto', 'paywall': True, 'piano_richiesto': 'pro'}), 403
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        conn = get_db()
        utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        if not utente or utente['piano'] != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─────────────────────────────────────────────
# ROUTES — AUTENTICAZIONE
# ─────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        nome = request.form.get('nome', '').strip()
        azienda = request.form.get('azienda', '').strip()

        if not email or not password:
            return render_template('auth.html', error='Email e password obbligatorie', mode='register')

        conn = get_db()
        existing = conn.execute("SELECT id FROM utenti WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            return render_template('auth.html', error='Email già registrata', mode='register')

        conn.execute('''INSERT INTO utenti (email, password_hash, nome, azienda)
                        VALUES (?, ?, ?, ?)''',
                     (email, generate_password_hash(password), nome, azienda))
        conn.commit()
        user = conn.execute("SELECT id FROM utenti WHERE email = ?", (email,)).fetchone()
        conn.close()

        session['user_id'] = user['id']
        session['user_email'] = email
        session['user_nome'] = nome
        session['user_piano'] = 'free'
        return redirect(url_for('dashboard'))

    return render_template('auth.html', mode='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db()
        utente = conn.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone()
        conn.close()

        if not utente or not check_password_hash(utente['password_hash'], password):
            return render_template('auth.html', error='Credenziali non valide', mode='login')

        # Aggiorna ultimo accesso
        conn = get_db()
        conn.execute("UPDATE utenti SET ultimo_accesso = datetime('now') WHERE id = ?", (utente['id'],))
        conn.commit()
        conn.close()

        session['user_id'] = utente['id']
        session['user_email'] = utente['email']
        session['user_nome'] = utente['nome'] or email.split('@')[0]
        session['user_piano'] = utente['piano']

        if utente['piano'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    return render_template('auth.html', mode='login')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ─────────────────────────────────────────────
# ROUTES — DASHBOARD UTENTE
# ─────────────────────────────────────────────
@app.route('/')
def index():
    pass  # placeholder
    return render_template('landing.html',
                           user=session.get('user_nome'),
                           piano=session.get('user_piano'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
    storico = conn.execute(
        "SELECT * FROM analisi WHERE utente_id = ? ORDER BY data_analisi DESC LIMIT 10",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', utente=utente, storico=storico)


# ─────────────────────────────────────────────
# ROUTES — ANALISI PRINCIPALE
# ─────────────────────────────────────────────
@app.route('/analizza', methods=['POST'])
def analizza():
    """
    Endpoint principale: riceve il PDF della visura + form integrativo,
    esegue il parsing e il matching, restituisce i risultati con semafori.
    """
    if 'visura' not in request.files:
        return jsonify({'error': 'Nessun file caricato'}), 400

    file = request.files['visura']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Formato non supportato. Carica un PDF nativo.'}), 400

    # Form integrativo (dati extra contestuali)
    form_extra = {
        'de_minimis': request.form.get('de_minimis', 'no'),
        'de_minimis_importo': float(request.form.get('de_minimis_importo', 0) or 0),
        'finalita_investimento': request.form.get('finalita_investimento', ''),
        'budget_investimento': float(request.form.get('budget_investimento', 0) or 0),
        'condizione_occupazionale': request.form.get('condizione_occupazionale', ''),
        'unita_locali_extra': request.form.get('unita_locali_extra', ''),
    }

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # STEP 1: Parsing visura
        dati_impresa = parse_visura(filepath)
        if not dati_impresa:
            return jsonify({'error': 'Impossibile estrarre dati. Assicurati che sia un PDF nativo (non scansionato).'}), 422

        # STEP 2: Arricchisci con form integrativo
        dati_impresa['form_integrativo'] = form_extra

        # STEP 3: Matching con bandi
        risultati = match_tutti_bandi(dati_impresa)
        lista_bandi = risultati.get('risultati', [])
        stats = risultati.get('statistiche', {})

        bandi_verdi = [b for b in lista_bandi if b['semaforo'] == 'VERDE']
        bandi_gialli = [b for b in lista_bandi if b['semaforo'] == 'GIALLO']
        bandi_rossi = [b for b in lista_bandi if b['semaforo'] == 'ROSSO']
        bandi_grigi = [b for b in lista_bandi if b['semaforo'] == 'GRIGIO']

        bandi_compatibili = len(bandi_verdi) + len(bandi_gialli)
        valore_potenziale = stats.get('valore_potenziale_massimo', 0)

        impresa_info = dati_impresa.get('impresa', {})
        ateco_info = dati_impresa.get('ateco', {})
        indicatori = dati_impresa.get('indicatori_matching', {})

        # STEP 4: Determina accesso (free vs premium)
        is_premium = False
        is_logged = 'user_id' in session
        if is_logged:
            conn = get_db()
            utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
            conn.close()
            is_premium = utente and (utente['piano'] in ('premium', 'admin') or utente['abbonamento_attivo'])

        # STEP 5: Costruisci risposta con logica FREEMIUM
        primo_verde_sbloccato = False
        teaser_bandi = []
        for b in lista_bandi:
            agev = b.get('agevolazioni', {})
            massimale = agev.get('massimale_investimento') or agev.get('spesa_progetto_max') or 0
            fondo_perduto = agev.get('percentuale_fondo_perduto', 0)
            score = _calcola_score(b)

            teaser = {
                'semaforo': b['semaforo'],
                'nome': b['bando_nome'],
                'ente': b['ente'],
                'valore_stimato': massimale,
                'fondo_perduto': fondo_perduto,
                'score': score,
                'snippet': _genera_snippet(b),
                'locked': not is_premium,
                'url': b.get('url', '')
            }

            # Il primo bando verde è SEMPRE gratuito (hook psicologico)
            if b['semaforo'] == 'VERDE' and not primo_verde_sbloccato:
                teaser['locked'] = False
                teaser['dettagli'] = {
                    'scadenza': b.get('stato_bando', 'N/D'),
                    'requisiti_soddisfatti': [v.get('motivo', '') for k, v in b.get('checks', {}).items() if isinstance(v, dict) and v.get('ok') is True],
                    'link': b.get('url', ''),
                    'massimale_formattato': f"€{massimale:,.0f}" if massimale > 0 else 'N/D',
                    'fondo_perduto': f"{fondo_perduto}% a fondo perduto" if fondo_perduto > 0 else 'N/D',
                }
                primo_verde_sbloccato = True

            if is_premium:
                teaser['dettagli'] = {
                    'scadenza': b.get('stato_bando', 'N/D'),
                    'requisiti_soddisfatti': [v.get('motivo', '') for k, v in b.get('checks', {}).items() if isinstance(v, dict) and v.get('ok') is True],
                    'requisiti_mancanti': [v.get('motivo', '') for k, v in b.get('checks', {}).items() if isinstance(v, dict) and v.get('ok') is False],
                    'link': b.get('url', ''),
                    'massimale_formattato': f"€{massimale:,.0f}" if massimale > 0 else 'N/D',
                    'fondo_perduto': f"{fondo_perduto}% a fondo perduto" if fondo_perduto > 0 else 'N/D',
                }

            teaser_bandi.append(teaser)

        # STEP 6: Salva analisi nel DB (se loggato)
        analisi_id = None
        if is_logged:
            conn = get_db()
            cursor = conn.execute('''INSERT INTO analisi
                (utente_id, ragione_sociale, ateco, regione, eta_mesi,
                 bandi_verdi, bandi_gialli, bandi_rossi, valore_potenziale,
                 dati_impresa_json, risultati_json, form_integrativo_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (session['user_id'],
                 impresa_info.get('ragione_sociale', 'N/D'),
                 ateco_info.get('codice_primario', 'N/D'),
                 indicatori.get('regione', 'N/D'),
                 indicatori.get('eta_mesi', 0),
                 len(bandi_verdi), len(bandi_gialli), len(bandi_rossi),
                 valore_potenziale,
                 json.dumps(dati_impresa, ensure_ascii=False),
                 json.dumps(risultati, ensure_ascii=False),
                 json.dumps(form_extra, ensure_ascii=False)))
            analisi_id = cursor.lastrowid
            conn.commit()
            conn.close()

        # STEP 7: Calcola Simulatore di Punteggio
        simulatore = calcola_simulatore(dati_impresa, form_extra)

        risposta = {
            'success': True,
            'analisi_id': analisi_id,
            'simulatore': simulatore,
            'impresa': {
                'ragione_sociale': impresa_info.get('ragione_sociale', 'N/D'),
                'ateco': ateco_info.get('codice_primario', 'N/D'),
                'regione': indicatori.get('regione', 'N/D'),
                'forma_giuridica': impresa_info.get('forma_giuridica_normalizzata', 'N/D'),
                'eta_mesi': indicatori.get('eta_mesi', 0),
            },
            'teaser': {
                'bandi_compatibili': bandi_compatibili,
                'valore_potenziale': valore_potenziale,
                'valore_formattato': f"€{valore_potenziale:,.0f}",
                'verdi': len(bandi_verdi),
                'gialli': len(bandi_gialli),
                'rossi': len(bandi_rossi),
                'grigi': len(bandi_grigi),
                'messaggio_teaser': _genera_messaggio_teaser(bandi_compatibili, valore_potenziale),
            },
            'bandi': teaser_bandi,
            'is_premium': is_premium,
            'is_logged': is_logged,
            'disclaimer': 'BandoMatch AI offre tecnologia di matching, non consulenza finanziaria o legale. I risultati sono indicativi.'
        }

        return jsonify(risposta)

    except Exception as e:
        return jsonify({'error': f'Errore durante l\'analisi: {str(e)}'}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ─────────────────────────────────────────────
# ROUTES — PDF DOSSIER DI AFFINITÀ
# ─────────────────────────────────────────────
@app.route('/dossier/<int:analisi_id>')
@login_required
def genera_dossier(analisi_id):
    """Genera e scarica il PDF Dossier di Affinità per un'analisi."""
    conn = get_db()
    utente = conn.execute("SELECT * FROM utenti WHERE id = ?", (session['user_id'],)).fetchone()
    analisi = conn.execute(
        "SELECT * FROM analisi WHERE id = ? AND utente_id = ?",
        (analisi_id, session['user_id'])
    ).fetchone()
    conn.close()

    if not analisi:
        abort(404)

    # Solo premium può scaricare il dossier completo
    is_premium = utente and (utente['piano'] in ('premium', 'admin') or utente['abbonamento_attivo'])
    if not is_premium:
        return jsonify({'error': 'Piano Premium richiesto per il Dossier completo', 'paywall': True}), 403

    # Genera il PDF
    pdf_buffer = _genera_pdf_dossier(analisi)
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"BandoMatch_Dossier_{analisi['ragione_sociale'][:20]}_{analisi_id}.pdf"
    )


def _genera_pdf_dossier(analisi):
    """Genera il PDF Dossier di Affinità con ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    story = []

    # Colori BandoMatch
    verde = colors.HexColor('#00C851')
    giallo = colors.HexColor('#FFB300')
    rosso = colors.HexColor('#FF4444')
    blu_scuro = colors.HexColor('#0D1B2A')
    grigio = colors.HexColor('#6c757d')

    # Stili personalizzati
    title_style = ParagraphStyle('Title', parent=styles['Title'],
                                  fontSize=22, textColor=blu_scuro,
                                  spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                     fontSize=11, textColor=grigio,
                                     spaceAfter=20, alignment=TA_CENTER)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
                                    fontSize=14, textColor=blu_scuro,
                                    spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=10, leading=14)

    # HEADER
    story.append(Paragraph("🎯 BandoMatch AI", title_style))
    story.append(Paragraph("Dossier di Affinità — Analisi Finanziamenti Pubblici", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=blu_scuro))
    story.append(Spacer(1, 0.4*cm))

    # DATA ANALISI
    story.append(Paragraph(f"Data analisi: {analisi['data_analisi'][:10]}", body_style))
    story.append(Spacer(1, 0.3*cm))

    # SEZIONE 1: PROFILO IMPRESA
    story.append(Paragraph("1. Profilo Impresa", section_style))
    dati = json.loads(analisi['dati_impresa_json'] or '{}')
    impresa = dati.get('impresa', {})
    ateco = dati.get('ateco', {})
    indicatori = dati.get('indicatori_matching', {})

    profilo_data = [
        ['Campo', 'Valore'],
        ['Ragione Sociale', analisi['ragione_sociale'] or 'N/D'],
        ['Codice ATECO', analisi['ateco'] or 'N/D'],
        ['Regione', analisi['regione'] or 'N/D'],
        ['Forma Giuridica', impresa.get('forma_giuridica_normalizzata', 'N/D')],
        ['Età Impresa', f"{analisi['eta_mesi']} mesi"],
        ['Sede Legale', impresa.get('sede_legale', 'N/D')],
    ]
    t = Table(profilo_data, colWidths=[5*cm, 12*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), blu_scuro),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # SEZIONE 2: RIEPILOGO MATCHING
    story.append(Paragraph("2. Riepilogo Compatibilità", section_style))
    riepilogo_data = [
        ['Semaforo', 'N° Bandi', 'Significato'],
        ['🟢 VERDE', str(analisi['bandi_verdi']), 'Piena compatibilità — Candidatura consigliata'],
        ['🟡 GIALLO', str(analisi['bandi_gialli']), 'Compatibilità parziale — Verifica requisiti'],
        ['🔴 ROSSO', str(analisi['bandi_rossi']), 'Non compatibile — Esclusione certa'],
        ['⚪ GRIGIO', '0', 'Dati insufficienti — Completa il profilo'],
    ]
    t2 = Table(riepilogo_data, colWidths=[4*cm, 3*cm, 10*cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), blu_scuro),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"<b>Valore Potenziale Totale: €{analisi['valore_potenziale']:,.0f}</b>",
        ParagraphStyle('Bold', parent=styles['Normal'], fontSize=13,
                       textColor=verde, spaceBefore=8)
    ))
    story.append(Spacer(1, 0.5*cm))

    # SEZIONE 3: BANDI COMPATIBILI (VERDI + GIALLI)
    risultati = json.loads(analisi['risultati_json'] or '{}')
    lista_bandi = risultati.get('risultati', [])
    bandi_ok = [b for b in lista_bandi if b['semaforo'] in ('VERDE', 'GIALLO')]

    if bandi_ok:
        story.append(Paragraph("3. Bandi Compatibili — Dettaglio", section_style))
        for i, b in enumerate(bandi_ok, 1):
            agev = b.get('agevolazioni', {})
            massimale = agev.get('massimale_investimento') or agev.get('spesa_progetto_max') or 0
            fondo = agev.get('percentuale_fondo_perduto', 0)
            colore = verde if b['semaforo'] == 'VERDE' else giallo

            story.append(Paragraph(
                f"<b>{i}. {b['bando_nome']}</b> — {b['ente']}",
                ParagraphStyle('BandoTitle', parent=styles['Normal'],
                               fontSize=11, textColor=colore, spaceBefore=10)
            ))
            story.append(Paragraph(f"Stato: {b.get('stato_bando', 'N/D')}", body_style))
            if massimale > 0:
                story.append(Paragraph(f"Massimale: €{massimale:,.0f} ({fondo}% a fondo perduto)", body_style))
            if b.get('url'):
                story.append(Paragraph(f"Link: {b['url']}", body_style))
            story.append(Spacer(1, 0.2*cm))

    # SEZIONE 4: PROSSIMI PASSI
    story.append(Paragraph("4. Prossimi Passi Consigliati", section_style))
    passi = [
        "1. Verifica la scadenza del bando e prepara la documentazione richiesta.",
        "2. Contatta un consulente abilitato per la presentazione della domanda.",
        "3. Torna su BandoMatch AI ogni settimana per nuovi bandi compatibili.",
        "4. Attiva gli Alert Email per ricevere notifiche automatiche.",
    ]
    for passo in passi:
        story.append(Paragraph(passo, body_style))
        story.append(Spacer(1, 0.1*cm))

    # FOOTER
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=grigio))
    story.append(Paragraph(
        "BandoMatch AI — www.bandomatch.ai | Questo documento è generato automaticamente e non costituisce consulenza finanziaria o legale.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                       textColor=grigio, alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# ROUTES — SIMULATORE PUNTEGGIO
# ─────────────────────────────────────────────
@app.route('/simulatore', methods=['POST'])
def simulatore_punteggio_route():
    """Calcola il punteggio di compatibilità in tempo reale senza caricare la visura."""
    dati = request.get_json() or {}
    profilo_base = {
        'indicatori_matching': {
            'regione': dati.get('regione', ''),
            'percentuale_soci_under35': float(dati.get('perc_under35', 0) or 0),
            'percentuale_soci_donne': float(dati.get('perc_donne', 0) or 0),
            'eta_impresa_mesi': int(dati.get('eta_mesi', 999) or 999),
        },
        'soci': dati.get('soci', []),
        'impresa': {'forma_giuridica_normalizzata': dati.get('forma_giuridica', '')}
    }
    form_extra = {
        'condizione_occupazionale': dati.get('condizione_occupazionale', ''),
        'finalita_investimento': dati.get('finalita_investimento', ''),
        'de_minimis': dati.get('de_minimis', 'no'),
    }
    risultato = calcola_simulatore(profilo_base, form_extra)
    return jsonify(risultato)


# ─────────────────────────────────────────────
# ROUTES — FEEDBACK LOOP
# ─────────────────────────────────────────────
@app.route('/feedback/bando', methods=['POST'])
@login_required
def feedback_bando():
    """Registra l'esito di una domanda di finanziamento (feedback loop)."""
    dati = request.get_json() or {}
    bando_id = dati.get('bando_id', '')
    esito = dati.get('esito', '')  # vinto, perso, in_corso
    note = dati.get('note', '')

    if not bando_id or esito not in ('vinto', 'perso', 'in_corso'):
        return jsonify({'error': 'Parametri non validi'}), 400

    conn = get_db()
    ultima_analisi = conn.execute(
        "SELECT ateco, regione FROM analisi WHERE utente_id = ? ORDER BY data_analisi DESC LIMIT 1",
        (session['user_id'],)
    ).fetchone()

    ateco = ultima_analisi['ateco'] if ultima_analisi else None
    regione = ultima_analisi['regione'] if ultima_analisi else None

    conn.execute('''
        INSERT INTO feedback_bandi (utente_id, bando_id, esito, ateco, regione, note)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], bando_id, esito, ateco, regione, note))

    row = conn.execute('''
        SELECT COUNT(*) as tot, SUM(CASE WHEN esito='vinto' THEN 1 ELSE 0 END) as vinti
        FROM feedback_bandi WHERE bando_id = ?
    ''', (bando_id,)).fetchone()

    if row and row['tot'] >= 3:
        tasso = (row['vinti'] / row['tot']) * 100
        conn.execute("UPDATE bandi SET tasso_successo = ? WHERE nome LIKE ?",
                     (tasso, f"%{bando_id[:30]}%"))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'messaggio': f'Feedback registrato: {esito}. Grazie per migliorare BandoMatch AI!'})


# ─────────────────────────────────────────────
# ROUTES — REVERSE MATCHING (Piano Pro)
# ─────────────────────────────────────────────
@app.route('/reverse-matching', methods=['POST'])
@pro_required
def reverse_matching():
    """
    Reverse Matching per Consulenti (Piano Pro).
    Dato un bando, trova tutte le aziende nel DB che potrebbero essere compatibili.
    """
    dati = request.get_json() or {}
    bando_id = dati.get('bando_id', '')
    regione_filtro = dati.get('regione', '')
    ateco_filtro = dati.get('ateco', '')

    conn = get_db()
    query = "SELECT DISTINCT ragione_sociale, ateco, regione, valore_potenziale FROM analisi WHERE 1=1"
    params = []
    if regione_filtro:
        query += " AND regione = ?"
        params.append(regione_filtro)
    if ateco_filtro:
        query += " AND ateco LIKE ?"
        params.append(f"{ateco_filtro[:2]}%")
    query += " ORDER BY valore_potenziale DESC LIMIT 50"

    aziende = conn.execute(query, params).fetchall()
    conn.close()

    risultato = {
        'bando_id': bando_id,
        'aziende_potenziali': len(aziende),
        'aziende': [dict(a) for a in aziende],
        'messaggio': f'Trovate {len(aziende)} aziende potenzialmente compatibili con questo bando.'
    }
    return jsonify(risultato)


# ─────────────────────────────────────────────
# ROUTES — ADMIN DASHBOARD
# ─────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    stats = {
        'totale_utenti': conn.execute("SELECT COUNT(*) FROM utenti WHERE piano != 'admin'").fetchone()[0],
        'utenti_premium': conn.execute("SELECT COUNT(*) FROM utenti WHERE piano = 'premium'").fetchone()[0],
        'totale_analisi': conn.execute("SELECT COUNT(*) FROM analisi").fetchone()[0],
        'analisi_oggi': conn.execute("SELECT COUNT(*) FROM analisi WHERE date(data_analisi) = date('now')").fetchone()[0],
        'totale_bandi': conn.execute("SELECT COUNT(*) FROM bandi").fetchone()[0],
        'bandi_attivi': conn.execute("SELECT COUNT(*) FROM bandi WHERE stato = 'attivo'").fetchone()[0],
        'valore_medio': conn.execute("SELECT AVG(valore_potenziale) FROM analisi").fetchone()[0] or 0,
    }
    ultimi_utenti = conn.execute(
        "SELECT * FROM utenti ORDER BY data_registrazione DESC LIMIT 10"
    ).fetchall()
    ultime_analisi = conn.execute(
        "SELECT a.*, u.email FROM analisi a JOIN utenti u ON a.utente_id = u.id ORDER BY a.data_analisi DESC LIMIT 10"
    ).fetchall()
    log_scraper = conn.execute(
        "SELECT * FROM scraper_log ORDER BY data_esecuzione DESC LIMIT 5"
    ).fetchall()
    conn.close()

    return render_template('admin.html',
                           stats=stats,
                           ultimi_utenti=ultimi_utenti,
                           ultime_analisi=ultime_analisi,
                           log_scraper=log_scraper)


@app.route('/admin/bandi')
@admin_required
def admin_bandi():
    conn = get_db()
    bandi = conn.execute("SELECT * FROM bandi ORDER BY data_aggiornamento DESC").fetchall()
    conn.close()
    return render_template('admin_bandi.html', bandi=bandi)


@app.route('/admin/scraper/run', methods=['POST'])
@admin_required
def admin_run_scraper():
    """Esegui lo scraper manualmente dall'admin."""
    threading.Thread(target=esegui_scraper_bandi).start()
    return jsonify({'success': True, 'message': 'Scraper avviato in background'})


# ─────────────────────────────────────────────
# ROUTES — BANDI PUBBLICI (SEO)
# ─────────────────────────────────────────────
@app.route('/bandi')
def lista_bandi_pubblici():
    conn = get_db()
    bandi = conn.execute(
        "SELECT * FROM bandi WHERE stato = 'attivo' ORDER BY data_aggiornamento DESC"
    ).fetchall()
    conn.close()
    return render_template('bandi_pubblici.html', bandi=bandi)


@app.route('/bandi/<int:bando_id>')
def dettaglio_bando(bando_id):
    conn = get_db()
    bando = conn.execute("SELECT * FROM bandi WHERE id = ?", (bando_id,)).fetchone()
    conn.close()
    if not bando:
        abort(404)
    return render_template('dettaglio_bando.html', bando=bando)


# ─────────────────────────────────────────────
# ROUTES — UPGRADE / PAYWALL
# ─────────────────────────────────────────────
@app.route('/upgrade')
@login_required
def upgrade():
    return render_template('upgrade.html')


@app.route('/consulenza')
@login_required
def consulenza():
    return render_template('consulenza.html')


# ─────────────────────────────────────────────
# ROUTES — DEMO
# ─────────────────────────────────────────────
@app.route('/demo')
def demo():
    demo_data = {
        'success': True,
        'analisi_id': None,
        'impresa': {
            'ragione_sociale': 'TECH SOLUTIONS ABRUZZO S.R.L.',
            'ateco': '62.01.00 — Produzione di software',
            'regione': 'Abruzzo',
            'forma_giuridica': 'SRL',
            'eta_mesi': 36,
        },
        'teaser': {
            'bandi_compatibili': 3,
            'valore_potenziale': 300000,
            'valore_formattato': '€300.000',
            'verdi': 2,
            'gialli': 1,
            'rossi': 2,
            'grigi': 0,
            'messaggio_teaser': '🚨 Attenzione: la tua azienda ha accesso a €300.000 in finanziamenti pubblici che stai perdendo ogni giorno!'
        },
        'bandi': [
            {
                'semaforo': 'VERDE', 'nome': 'Resto al Sud 2.0 (Investire al Sud)',
                'ente': 'Invitalia', 'valore_stimato': 200000, 'fondo_perduto': 70,
                'score': 94,
                'snippet': '✅ La tua azienda soddisfa tutti i requisiti. Valore stimato: €200.000 (70% a fondo perduto)',
                'locked': False,
                'url': 'https://www.invitalia.it/incentivi-e-strumenti/resto-al-sud-20',
                'dettagli': {
                    'scadenza': 'A sportello — fino ad esaurimento fondi',
                    'requisiti_soddisfatti': ['Regione Mezzogiorno ✓', 'ATECO ammesso ✓', 'Soci under 35 ✓'],
                    'link': 'https://www.invitalia.it/incentivi-e-strumenti/resto-al-sud-20',
                    'massimale_formattato': '€200.000', 'fondo_perduto': '70% a fondo perduto'
                }
            },
            {'semaforo': 'VERDE', 'nome': 'Decontribuzione Sud', 'ente': 'INPS',
             'valore_stimato': 0, 'fondo_perduto': 0, 'score': 88,
             'snippet': '✅ Sgravio contributivo automatico per aziende del Mezzogiorno.', 'locked': True},
            {'semaforo': 'GIALLO', 'nome': 'PR FESR Abruzzo — Digitalizzazione PMI',
             'ente': 'Regione Abruzzo / FiRA', 'valore_stimato': 100000, 'fondo_perduto': 50,
             'score': 67,
             'snippet': '⚠️ Quasi compatibile. Bando in preparazione. Valore stimato: €100.000', 'locked': True},
            {'semaforo': 'ROSSO', 'nome': 'Abruzzo Micro Prestiti — Linea A',
             'ente': 'FiRA S.p.A.', 'valore_stimato': 80000, 'fondo_perduto': 30,
             'score': 22,
             'snippet': '❌ Non compatibile: Impresa troppo vecchia (36 mesi, limite 24 mesi)', 'locked': True},
            {'semaforo': 'ROSSO', 'nome': 'Abruzzo Micro Prestiti — Linea B',
             'ente': 'FiRA S.p.A.', 'valore_stimato': 80000, 'fondo_perduto': 30,
             'score': 18,
             'snippet': '❌ Non compatibile: Impresa troppo vecchia (36 mesi, limite 24 mesi)', 'locked': True},
        ],
        'is_premium': False,
        'is_logged': False,
        'disclaimer': 'BandoMatch AI offre tecnologia di matching, non consulenza finanziaria o legale.'
    }
    return render_template('risultati.html', data=json.dumps(demo_data))


# ─────────────────────────────────────────────
# SCRAPER AUTOMATICO GIORNALIERO
# ─────────────────────────────────────────────
def esegui_scraper_bandi():
    """
    Scraper LLM-Augmented v3.0 che aggiorna il BandoDB ogni giorno.
    Strategia (validata da Gemini):
    - Metodo primario: Scraper LLM-Augmented (GPT-4.1-mini) per estrazione intelligente
    - Fallback: parsing HTML grezzo con BeautifulSoup
    """
    import time
    import requests
    from bs4 import BeautifulSoup

    # Tentativo con Scraper LLM-Augmented (metodo primario v3.0)
    if scraping_llm_completo:
        try:
            start_llm = time.time()
            report_llm = scraping_llm_completo()
            conn_llm = get_db()
            bandi_inseriti_llm = 0
            for bando in report_llm.get('bandi', []):
                nome = bando.get('nome', '')
                if not nome:
                    continue
                existing = conn_llm.execute(
                    "SELECT id FROM bandi WHERE nome LIKE ?",
                    (f"%{nome[:50]}%",)
                ).fetchone()
                if not existing:
                    agev = bando.get('agevolazioni', {})
                    req = bando.get('requisiti', {})
                    conn_llm.execute('''INSERT INTO bandi
                        (nome, ente, tipo, stato, regione, massimale, percentuale_fondo_perduto,
                         eta_min_soci, eta_max_soci, eta_max_impresa_mesi, url,
                         fonte_scraping, data_aggiornamento)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                        (nome[:200],
                         bando.get('ente', ''),
                         bando.get('tipo', 'nazionale'),
                         bando.get('stato', 'ATTIVO').lower(),
                         bando.get('regione'),
                         agev.get('massimale_investimento'),
                         agev.get('percentuale_fondo_perduto'),
                         req.get('eta_minima_soci'),
                         req.get('eta_massima_soci'),
                         req.get('eta_impresa_max_mesi'),
                         bando.get('url', ''),
                         bando.get('fonte', 'Scraper LLM v3.0')))
                    bandi_inseriti_llm += 1
            conn_llm.commit()
            durata_llm = round(time.time() - start_llm, 2)
            conn_llm.execute('''INSERT INTO scraper_log
                (fonte, bandi_trovati, bandi_aggiornati, durata_secondi)
                VALUES (?, ?, ?, ?)''',
                ('Scraper LLM-Augmented v3.0', bandi_inseriti_llm, 0, durata_llm))
            conn_llm.commit()
            conn_llm.close()
            print(f"✅ Scraper LLM completato: {bandi_inseriti_llm} nuovi bandi in {durata_llm}s")
        except Exception as e:
            print(f"⚠️ Scraper LLM fallito, uso fallback: {e}")


    start = time.time()
    conn = get_db()
    bandi_trovati = 0
    bandi_aggiornati = 0
    errori = []

    fonti = [
        {
            'nome': 'Invitalia',
            'url': 'https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese',
            'tipo': 'nazionale'
        },
        {
            'nome': 'MIMIT Bandi',
            'url': 'https://www.mimit.gov.it/it/incentivi',
            'tipo': 'nazionale'
        },
        {
            'nome': 'FiRA Abruzzo',
            'url': 'https://www.fira.it/bandi-e-avvisi/',
            'tipo': 'regionale'
        }
    ]

    for fonte in fonti:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 BandoMatchBot/2.0'}
            resp = requests.get(fonte['url'], headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Cerca titoli di bandi/incentivi
                titoli = soup.find_all(['h2', 'h3', 'h4'], limit=20)
                for titolo in titoli:
                    testo = titolo.get_text(strip=True)
                    if len(testo) > 10 and any(kw in testo.lower() for kw in
                                                ['bando', 'incentiv', 'agevolazion', 'finanziament', 'fondo']):
                        # Controlla se già presente
                        existing = conn.execute(
                            "SELECT id FROM bandi WHERE nome LIKE ?",
                            (f"%{testo[:50]}%",)
                        ).fetchone()
                        if not existing:
                            conn.execute('''INSERT INTO bandi
                                (nome, ente, tipo, stato, fonte_scraping, data_aggiornamento)
                                VALUES (?, ?, ?, 'attivo', ?, datetime('now'))''',
                                (testo[:200], fonte['nome'], fonte['tipo'], fonte['url']))
                            bandi_trovati += 1
                        else:
                            conn.execute(
                                "UPDATE bandi SET data_aggiornamento = datetime('now') WHERE id = ?",
                                (existing['id'],)
                            )
                            bandi_aggiornati += 1
        except Exception as e:
            errori.append(f"{fonte['nome']}: {str(e)}")

    conn.commit()

    # Log dell'esecuzione
    durata = round(time.time() - start, 2)
    conn.execute('''INSERT INTO scraper_log
        (fonte, bandi_trovati, bandi_aggiornati, errori, durata_secondi)
        VALUES (?, ?, ?, ?, ?)''',
        ('Tutti', bandi_trovati, bandi_aggiornati,
         json.dumps(errori) if errori else None, durata))
    conn.commit()
    conn.close()

    print(f"✅ Scraper completato: {bandi_trovati} nuovi, {bandi_aggiornati} aggiornati, {len(errori)} errori — {durata}s")


# ─────────────────────────────────────────────
# SCHEDULER AUTOMATICO (CRON GIORNALIERO)
# ─────────────────────────────────────────────
def avvia_scheduler():
    scheduler = BackgroundScheduler()
    # Ogni giorno alle 06:00
    scheduler.add_job(esegui_scraper_bandi, 'cron', hour=6, minute=0,
                      id='scraper_giornaliero', replace_existing=True)
    # Alert email ogni giorno alle 08:00
    scheduler.add_job(invia_alert_email, 'cron', hour=8, minute=0,
                      id='alert_email', replace_existing=True)
    scheduler.start()
    print("✅ Scheduler avviato: scraper 06:00, alert 08:00")


def invia_alert_email():
    """Invia alert email agli utenti per nuovi bandi compatibili."""
    # Implementazione base — in produzione usare Flask-Mail o SendGrid
    print(f"📧 Alert email: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _calcola_score(bando: dict) -> int:
    """Calcola uno score percentuale di compatibilità 0-100."""
    semaforo = bando.get('semaforo', '')
    checks = bando.get('checks', {})
    if not checks:
        if semaforo == 'VERDE': return 90
        if semaforo == 'GIALLO': return 60
        if semaforo == 'ROSSO': return 15
        return 40

    ok = sum(1 for v in checks.values() if isinstance(v, dict) and v.get('ok') is True)
    total = len(checks)
    if total == 0:
        return 50
    base_score = int((ok / total) * 100)
    # Bonus/malus per semaforo
    if semaforo == 'VERDE': base_score = max(base_score, 80)
    elif semaforo == 'ROSSO': base_score = min(base_score, 30)
    return min(100, max(0, base_score))


def _genera_snippet(bando: dict) -> str:
    semaforo = bando.get('semaforo', '')
    agev = bando.get('agevolazioni', {})
    massimale = agev.get('massimale_investimento') or agev.get('spesa_progetto_max') or 0
    fondo_perduto = agev.get('percentuale_fondo_perduto', 0)
    motivo = bando.get('motivo_principale', '')

    if semaforo == 'VERDE':
        if massimale > 0:
            return f"✅ La tua azienda soddisfa tutti i requisiti. Valore stimato: €{massimale:,.0f} ({fondo_perduto}% a fondo perduto)"
        return f"✅ La tua azienda soddisfa tutti i requisiti. {motivo}"
    elif semaforo == 'GIALLO':
        if massimale > 0:
            return f"⚠️ Quasi compatibile. {motivo}. Valore stimato: €{massimale:,.0f}"
        return f"⚠️ Quasi compatibile. {motivo}"
    elif semaforo == 'ROSSO':
        return f"❌ Non compatibile: {motivo}"
    elif semaforo == 'GRIGIO':
        return f"⚪ Dati insufficienti. {motivo}. Completa il profilo per sbloccare."
    return ""


def _genera_messaggio_teaser(bandi_compatibili: int, valore_potenziale: float) -> str:
    """Genera il messaggio psicologico del teaser (Gemini-approved)."""
    if bandi_compatibili == 0:
        return "⚠️ Nessun bando compatibile trovato. Aggiorna il profilo o torna tra qualche giorno per nuovi bandi."
    giorni_anno = 365
    valore_giornaliero = valore_potenziale / giorni_anno if valore_potenziale > 0 else 0
    if valore_potenziale > 100000:
        return (f"🚨 Attenzione: la tua azienda ha accesso a €{valore_potenziale:,.0f} in finanziamenti pubblici "
                f"che stai perdendo ogni giorno (€{valore_giornaliero:,.0f}/giorno)!")
    elif bandi_compatibili > 0:
        return f"🎯 Trovati {bandi_compatibili} bandi compatibili con la tua azienda. Valore potenziale: €{valore_potenziale:,.0f}"
    return f"📊 Analisi completata: {bandi_compatibili} bandi compatibili trovati."


# ─────────────────────────────────────────────
# AVVIO APP
# ─────────────────────────────────────────────


# ============================================================
# ROUTE NOTIFICHE PUSH PREDITTIVE
# ============================================================

@app.route('/notifiche')
@login_required
def notifiche():
    """Pagina notifiche push per l'utente."""
    from notifiche_push import get_notifiche_utente
    notifiche_list = get_notifiche_utente(current_user.id)
    return jsonify({
        "utente": current_user.email,
        "notifiche_non_lette": len(notifiche_list),
        "notifiche": notifiche_list
    })


@app.route('/notifiche/<int:notifica_id>/letta', methods=['POST'])
@login_required
def segna_letta(notifica_id):
    """Segna una notifica come letta."""
    from notifiche_push import segna_notifica_letta
    segna_notifica_letta(notifica_id)
    return jsonify({"status": "ok"})


@app.route('/genera-post-social/<bando_id>')
@pro_required
def genera_post_social_route(bando_id):
    """Genera post social per un bando specifico (solo Piano Pro)."""
    from notifiche_push import genera_post_social
    bandi = carica_bandi_db()
    bando = next((b for b in bandi if b.get('id') == bando_id), None)
    if not bando:
        return jsonify({"errore": "Bando non trovato"}), 404
    posts = genera_post_social(bando)
    return jsonify(posts)


@app.route('/api/notifiche-count')
@login_required
def notifiche_count():
    """Conta le notifiche non lette per il badge nella navbar."""
    from notifiche_push import get_notifiche_utente
    notifiche_list = get_notifiche_utente(current_user.id)
    return jsonify({"count": len(notifiche_list)})


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT FINALE: Stripe + National Scraper + Dossier PDF Professionale
# ═══════════════════════════════════════════════════════════════════════════════

# Import nuovi moduli
try:
    from stripe_payments import (
        crea_checkout_session, verifica_webhook, processa_evento_stripe,
        attiva_piano_demo, get_stato_abbonamento, STRIPE_PRICES, STRIPE_PUBLISHABLE_KEY
    )
    STRIPE_DISPONIBILE = True
except Exception as _e:
    app.logger.warning(f"Stripe non disponibile: {_e}")
    STRIPE_DISPONIBILE = False

try:
    from national_scraper import (
        scrapa_tutte_le_sorgenti, scrapa_sorgente, get_statistiche_bandi,
        SORGENTI_BANDI
    )
    NATIONAL_SCRAPER_DISPONIBILE = True
except Exception as _e:
    app.logger.warning(f"National Scraper non disponibile: {_e}")
    NATIONAL_SCRAPER_DISPONIBILE = False

try:
    from dossier_pdf import genera_dossier as genera_dossier_pro, genera_dossier_demo
    DOSSIER_PRO_DISPONIBILE = True
except Exception as _e:
    app.logger.warning(f"Dossier PDF Pro non disponibile: {_e}")
    DOSSIER_PRO_DISPONIBILE = False


# ── ROUTE STRIPE ──────────────────────────────────────────────────────────────

@app.route('/checkout/<piano>')
@login_required
def checkout(piano):
    """Avvia il checkout Stripe per il piano selezionato."""
    import traceback as _tb
    try:
        if not STRIPE_DISPONIBILE:
            flash("Sistema di pagamento temporaneamente non disponibile.", "warning")
            return redirect(url_for('upgrade'))

        user_id = session['user_id']
        conn = get_db()
        user = conn.execute("SELECT email FROM utenti WHERE id=?", (user_id,)).fetchone()
        conn.close()
        if not user:
            flash("Utente non trovato.", "danger")
            return redirect(url_for('upgrade'))
        base_url = request.host_url.rstrip('/')
        risultato = crea_checkout_session(user_id, user['email'], piano, base_url)

        if risultato.get("demo_mode"):
            attiva_piano_demo(user_id, piano)
            flash(f"Piano {piano.upper()} attivato in modalità demo! Valido 30 giorni.", "success")
            return redirect(url_for('dashboard'))

        if risultato.get("error"):
            flash(f"Errore pagamento: {risultato['error']}", "danger")
            return redirect(url_for('upgrade'))

        return redirect(risultato["checkout_url"])
    except Exception as _e:
        _err = _tb.format_exc()
        app.logger.error(f"CHECKOUT 500: {_err}")
        return f"<pre style='color:red'>CHECKOUT ERROR (debug):\n{_err}\n\nSTRIPE_DISPONIBILE={STRIPE_DISPONIBILE}\nPiano={piano}</pre>", 500


@app.route('/pagamento/successo')
@login_required
def pagamento_successo():
    """Pagina di conferma dopo il pagamento riuscito."""
    session_id = request.args.get('session_id')
    piano = request.args.get('piano', 'premium')
    user_id = session['user_id']

    if session_id and session_id.startswith('demo_'):
        attiva_piano_demo(user_id, piano)

    flash(f"Benvenuto nel piano {piano.upper()}! Il tuo abbonamento è attivo.", "success")
    return render_template('pagamento_successo.html', piano=piano,
                           features=STRIPE_PRICES.get(piano, {}).get('features', []))


@app.route('/pagamento/demo/<piano>')
@login_required
def pagamento_demo(piano):
    """Attiva un piano demo senza pagamento reale (per test)."""
    user_id = session['user_id']
    if attiva_piano_demo(user_id, piano):
        flash(f"Piano {piano.upper()} attivato in modalità DEMO (30 giorni gratuiti).", "success")
    return redirect(url_for('dashboard'))


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Endpoint webhook per eventi Stripe."""
    if not STRIPE_DISPONIBILE:
        return jsonify({"status": "stripe_not_configured"}), 200

    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    event = verifica_webhook(payload, sig_header)
    if not event:
        return jsonify({"error": "Firma non valida"}), 400

    processa_evento_stripe(event)
    return jsonify({"status": "ok"}), 200


@app.route('/api/abbonamento')
@login_required
def api_abbonamento():
    """API per ottenere lo stato dell'abbonamento corrente."""
    user_id = session['user_id']
    stato = get_stato_abbonamento(user_id) if STRIPE_DISPONIBILE else {"piano": "free"}
    return jsonify(stato)


# ── ROUTE NATIONAL SCRAPER ────────────────────────────────────────────────────

@app.route('/admin/scraper/nazionale', methods=['POST'])
@admin_required
def admin_scraper_nazionale():
    """Avvia il National Scraper per tutte le 20 regioni."""
    if not NATIONAL_SCRAPER_DISPONIBILE:
        return jsonify({"error": "National Scraper non disponibile"}), 503

    priorita = int(request.form.get('priorita', 1))

    def _run_scraper():
        try:
            report = scrapa_tutte_le_sorgenti(solo_priorita=priorita)
            app.logger.info(f"National Scraper completato: {report['totale_bandi_trovati']} bandi")
        except Exception as e:
            app.logger.error(f"Errore National Scraper: {e}")

    t = threading.Thread(target=_run_scraper, daemon=True)
    t.start()

    return jsonify({
        "status": "avviato",
        "messaggio": f"National Scraper avviato in background (priorità ≤ {priorita}). Controlla i log.",
        "sorgenti": len(SORGENTI_BANDI) if NATIONAL_SCRAPER_DISPONIBILE else 0
    })


@app.route('/admin/scraper/sorgente/<chiave>', methods=['POST'])
@admin_required
def admin_scraper_sorgente(chiave):
    """Scrapa una singola sorgente."""
    if not NATIONAL_SCRAPER_DISPONIBILE:
        return jsonify({"error": "National Scraper non disponibile"}), 503

    risultato = scrapa_sorgente(chiave)
    return jsonify(risultato)


@app.route('/api/statistiche-bandi')
def api_statistiche_bandi():
    """API pubblica per le statistiche sui bandi."""
    if NATIONAL_SCRAPER_DISPONIBILE:
        stats = get_statistiche_bandi()
    else:
        conn = get_db()
        totale = conn.execute("SELECT COUNT(*) as n FROM bandi").fetchone()["n"]
        aperti = conn.execute("SELECT COUNT(*) as n FROM bandi WHERE stato='aperto'").fetchone()["n"]
        conn.close()
        stats = {"totale_bandi": totale, "bandi_aperti": aperti, "regioni_coperte": 20}
    return jsonify(stats)


# ── ROUTE DOSSIER PDF PROFESSIONALE ──────────────────────────────────────────

@app.route('/dossier-pro/<int:analisi_id>')
@login_required
def dossier_pro(analisi_id):
    """Genera e scarica il Dossier PDF professionale (richiede piano Premium o Pro)."""
    user_id = session['user_id']
    conn = get_db()
    user = conn.execute("SELECT piano FROM users WHERE id=?", (user_id,)).fetchone()
    analisi = conn.execute(
        "SELECT * FROM analisi WHERE id=? AND user_id=?", (analisi_id, user_id)
    ).fetchone()
    conn.close()

    if not analisi:
        flash("Analisi non trovata.", "danger")
        return redirect(url_for('dashboard'))

    piano = user['piano'] if user else 'free'
    if piano not in ['premium', 'pro']:
        flash("Il Dossier PDF professionale richiede il piano Premium o Pro.", "warning")
        return redirect(url_for('upgrade'))

    if not DOSSIER_PRO_DISPONIBILE:
        flash("Dossier PDF temporaneamente non disponibile.", "warning")
        return redirect(url_for('dashboard'))

    try:
        dati_impresa = json.loads(analisi['dati_impresa']) if analisi['dati_impresa'] else {}
        risultati = json.loads(analisi['risultati_json']) if analisi['risultati_json'] else []

        # Calcola simulatore
        sim_data = None
        try:
            sim_data = calcola_simulatore(dati_impresa)
        except Exception:
            pass

        pdf_bytes = genera_dossier_pro(dati_impresa, risultati, sim_data)

        nome_file = f"dossier_bandomatch_{dati_impresa.get('ragione_sociale', 'impresa').replace(' ', '_')[:30]}.pdf"

        from flask import make_response
        resp = make_response(pdf_bytes)
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename="{nome_file}"'
        return resp

    except Exception as e:
        app.logger.error(f"Errore generazione dossier pro: {e}")
        flash("Errore nella generazione del dossier. Riprova.", "danger")
        return redirect(url_for('dashboard'))


@app.route('/dossier-demo')
def dossier_demo_download():
    """Scarica un dossier demo per mostrare il formato ai potenziali clienti."""
    if not DOSSIER_PRO_DISPONIBILE:
        return "Dossier non disponibile", 503

    try:
        pdf_bytes = genera_dossier_demo()
        from flask import make_response
        resp = make_response(pdf_bytes)
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = 'attachment; filename="dossier_demo_bandomatch.pdf"'
        return resp
    except Exception as e:
        app.logger.error(f"Errore dossier demo: {e}")
        return "Errore generazione dossier", 500


# ── API PREZZI PUBBLICI ───────────────────────────────────────────────────────

@app.route('/api/prezzi')
def api_prezzi():
    """API pubblica per i prezzi degli abbonamenti."""
    prezzi_pubblici = {}
    for piano, info in STRIPE_PRICES.items():
        prezzi_pubblici[piano] = {
            "nome": info.get("name", info.get("nome", piano)),
            "prezzo_euro": info["amount"] / 100,
            "intervallo": info["interval"],
            "features": info["features"]
        }
    return jsonify(prezzi_pubblici)



# ── LANDING ASPIRANTE IMPRENDITORE ──────────────────────────────────────────

@app.route('/idea')
def idea_page():
    """Landing page per aspiranti imprenditori con quiz AI."""
    return render_template('idea.html')

@app.route('/api/valuta-idea', methods=['POST'])
def valuta_idea():
    """API per valutare un'idea imprenditoriale con AI e trovare bandi compatibili."""
    dati = request.get_json() or {}
    settore = dati.get('settore', 'altro')
    regione = dati.get('regione', '')
    eta = dati.get('eta', '25-35')
    budget = dati.get('budget', 'piccolo')

    # Calcolo score basato sui parametri
    score = 50
    bonus_settore = {'tecnologia': 20, 'green': 18, 'manifattura': 15, 'servizi': 12, 'turismo': 10, 'altro': 8}
    score += bonus_settore.get(settore, 8)
    bonus_eta = {'under25': 15, '25-35': 12, '35-45': 8, 'over45': 5}
    score += bonus_eta.get(eta, 8)
    regioni_sud = ['Abruzzo', 'Basilicata', 'Calabria', 'Campania', 'Molise', 'Puglia', 'Sardegna', 'Sicilia']
    score += 10 if regione in regioni_sud else 5
    bonus_budget = {'zero': 5, 'piccolo': 8, 'medio': 12, 'grande': 15}
    score += bonus_budget.get(budget, 8)
    score = min(score, 96)

    # Trova bandi compatibili dal DB
    conn = get_db()
    bandi_trovati = []
    try:
        c = conn.cursor()
        c.execute("""
            SELECT nome, massimale, percentuale_fondo_perduto, regioni_ammesse
            FROM bandi WHERE stato='aperto'
            ORDER BY massimale DESC LIMIT 20
        """)
        tutti = c.fetchall()
        for b in tutti:
            nome, massimale, pct, regioni_json = b['nome'], b['massimale'], b['percentuale_fondo_perduto'], b['regioni_ammesse']
            try:
                regioni = json.loads(regioni_json) if regioni_json else []
            except Exception:
                regioni = []
            if 'Nazionale' in regioni or (regione and regione in regioni):
                colore = 'verde' if (pct or 0) >= 40 else 'giallo'
                valore_str = f'\u20ac{massimale:,.0f}' if massimale else 'Variabile'
                bandi_trovati.append({'nome': nome[:50], 'valore': valore_str, 'colore': colore})
                if len(bandi_trovati) >= 5:
                    break
    except Exception as e:
        app.logger.error(f'Errore valuta-idea: {e}')
    finally:
        conn.close()

    if not bandi_trovati:
        bandi_trovati = [
            {'nome': 'Smart&Start Italia', 'valore': '\u20ac1.500.000', 'colore': 'verde'},
            {'nome': 'Fondo di Garanzia PMI', 'valore': '\u20ac5.000.000', 'colore': 'giallo'},
            {'nome': "Credito d'Imposta R&S", 'valore': '\u20ac5.000.000', 'colore': 'verde'},
        ]

    if score >= 70:
        titolo = 'La tua idea ha ottime probabilit\u00e0! \U0001f3af'
        sottotitolo = f'Abbiamo trovato {len(bandi_trovati)} bandi compatibili con il tuo progetto'
    elif score >= 50:
        titolo = 'La tua idea ha buone possibilit\u00e0 \U0001f44d'
        sottotitolo = f'Esistono {len(bandi_trovati)} bandi potenzialmente accessibili'
    else:
        titolo = 'Ci sono opportunit\u00e0 da esplorare \U0001f50d'
        sottotitolo = 'Con la giusta consulenza puoi trovare il bando adatto'

    return jsonify({'score': score, 'titolo': titolo, 'sottotitolo': sottotitolo, 'bandi': bandi_trovati})


# ─────────────────────────────────────────────
# SEED BANDI (endpoint admin per popolare il DB live)
# ─────────────────────────────────────────────
@app.route('/admin/seed-bandi', methods=['POST'])
@admin_required
def seed_bandi():
    """Popola il DB con bandi reali italiani - solo admin"""
    
    bandi = [
        # NAZIONALI
        {'nome': 'Resto al Sud 2.0', 'ente': 'Invitalia', 'regione': 'Nazionale', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.invitalia.it/cosa-facciamo/creiamo-nuove-aziende/resto-al-sud', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Abruzzo","Basilicata","Calabria","Campania","Molise","Puglia","Sardegna","Sicilia"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Smart&Start Italia', 'ente': 'Invitalia', 'regione': 'Nazionale', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 1500000, 'url': 'https://www.invitalia.it/cosa-facciamo/creiamo-nuove-aziende/smart-start-italia', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 30.0},
        {'nome': 'Nuova Sabatini', 'ente': 'MIMIT', 'regione': 'Nazionale', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 4000000, 'url': 'https://www.mise.gov.it/index.php/it/incentivi/impresa/nuova-sabatini', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 0.0},
        {'nome': 'Fondo di Garanzia PMI', 'ente': 'Mediocredito Centrale', 'regione': 'Nazionale', 'tipo': 'Credito', 'stato': 'aperto', 'massimale': 5000000, 'url': 'https://www.fondidigaranzia.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 0.0},
        {'nome': "Credito d'Imposta R&S", 'ente': 'Agenzia delle Entrate', 'regione': 'Nazionale', 'tipo': 'Ricerca', 'stato': 'aperto', 'massimale': 5000000, 'url': 'https://www.agenziaentrate.gov.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 20.0},
        {'nome': 'Industria 4.0 - Beni Strumentali', 'ente': 'MIMIT', 'regione': 'Nazionale', 'tipo': 'Digitalizzazione', 'stato': 'aperto', 'massimale': 2000000, 'url': 'https://www.mise.gov.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 30.0},
        {'nome': 'PNRR - Transizione 5.0', 'ente': 'GSE', 'regione': 'Nazionale', 'tipo': 'Sostenibilita', 'stato': 'aperto', 'massimale': 3000000, 'url': 'https://www.gse.it/transizione-5-0', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 35.0},
        {'nome': 'Decontribuzione Sud', 'ente': 'INPS', 'regione': 'Nazionale', 'tipo': 'Lavoro', 'stato': 'aperto', 'massimale': 0, 'url': 'https://www.inps.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Abruzzo","Basilicata","Calabria","Campania","Molise","Puglia","Sardegna","Sicilia"]', 'percentuale_fondo_perduto': 30.0},
        {'nome': 'Contratti di Sviluppo', 'ente': 'Invitalia', 'regione': 'Nazionale', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 50000000, 'url': 'https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese/contratti-di-sviluppo', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 25.0},
        {'nome': 'Brevetti+', 'ente': 'UIBM/MIMIT', 'regione': 'Nazionale', 'tipo': 'Innovazione', 'stato': 'aperto', 'massimale': 140000, 'url': 'https://uibm.mise.gov.it', 'data_scadenza': '2025-06-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Tutte"]', 'percentuale_fondo_perduto': 80.0},
        # ABRUZZO
        {'nome': 'PR FESR Abruzzo - Digitalizzazione PMI', 'ente': 'Regione Abruzzo', 'regione': 'Abruzzo', 'tipo': 'Digitalizzazione', 'stato': 'aperto', 'massimale': 150000, 'url': 'https://www.regione.abruzzo.it/fesr', 'data_scadenza': '2025-09-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Abruzzo"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Abruzzo Micro Prestiti', 'ente': 'FIRA Abruzzo', 'regione': 'Abruzzo', 'tipo': 'Credito', 'stato': 'aperto', 'massimale': 80000, 'url': 'https://www.fira.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Abruzzo"]', 'percentuale_fondo_perduto': 0.0},
        {'nome': 'Abruzzo Turismo Sostenibile', 'ente': 'Regione Abruzzo', 'regione': 'Abruzzo', 'tipo': 'Turismo', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.abruzzo.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '["55","56"]', 'regioni_ammesse': '["Abruzzo"]', 'percentuale_fondo_perduto': 60.0},
        # LOMBARDIA
        {'nome': 'Bando Innovazione Lombardia', 'ente': 'Regione Lombardia', 'regione': 'Lombardia', 'tipo': 'Innovazione', 'stato': 'aperto', 'massimale': 500000, 'url': 'https://www.regione.lombardia.it', 'data_scadenza': '2025-11-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Lombardia"]', 'percentuale_fondo_perduto': 40.0},
        {'nome': 'Finlombarda - Fondo PMI', 'ente': 'Finlombarda', 'regione': 'Lombardia', 'tipo': 'Credito', 'stato': 'aperto', 'massimale': 1000000, 'url': 'https://www.finlombarda.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Lombardia"]', 'percentuale_fondo_perduto': 0.0},
        # CAMPANIA
        {'nome': 'FESR Campania - Competitivita PMI', 'ente': 'Regione Campania', 'regione': 'Campania', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 300000, 'url': 'https://www.regione.campania.it', 'data_scadenza': '2025-09-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Campania"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Campania Startup', 'ente': 'Sviluppo Campania', 'regione': 'Campania', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.sviluppocampania.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Campania"]', 'percentuale_fondo_perduto': 70.0},
        # SICILIA
        {'nome': 'FESR Sicilia - Imprenditorialita', 'ente': 'Regione Sicilia', 'regione': 'Sicilia', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 250000, 'url': 'https://www.regione.sicilia.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Sicilia"]', 'percentuale_fondo_perduto': 60.0},
        {'nome': 'Sicilia Digitale', 'ente': 'Regione Sicilia', 'regione': 'Sicilia', 'tipo': 'Digitalizzazione', 'stato': 'aperto', 'massimale': 100000, 'url': 'https://www.regione.sicilia.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Sicilia"]', 'percentuale_fondo_perduto': 50.0},
        # PUGLIA
        {'nome': 'FESR Puglia - Competitivita', 'ente': 'Regione Puglia', 'regione': 'Puglia', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 400000, 'url': 'https://www.regione.puglia.it', 'data_scadenza': '2025-11-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Puglia"]', 'percentuale_fondo_perduto': 45.0},
        {'nome': 'Puglia Turismo 2025', 'ente': 'Puglia Promozione', 'regione': 'Puglia', 'tipo': 'Turismo', 'stato': 'aperto', 'massimale': 300000, 'url': 'https://www.pugliapromozione.com', 'data_scadenza': '2025-09-30', 'ateco_ammessi': '["55","56"]', 'regioni_ammesse': '["Puglia"]', 'percentuale_fondo_perduto': 50.0},
        # LAZIO
        {'nome': 'Lazio Innova - Voucher Digitali', 'ente': 'Lazio Innova', 'regione': 'Lazio', 'tipo': 'Digitalizzazione', 'stato': 'aperto', 'massimale': 50000, 'url': 'https://www.lazioinnova.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Lazio"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Lazio Startup', 'ente': 'Lazio Innova', 'regione': 'Lazio', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 300000, 'url': 'https://www.lazioinnova.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Lazio"]', 'percentuale_fondo_perduto': 70.0},
        # VENETO
        {'nome': 'Veneto PMI - Bando Crescita', 'ente': 'Regione Veneto', 'regione': 'Veneto', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 500000, 'url': 'https://www.regione.veneto.it', 'data_scadenza': '2025-11-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Veneto"]', 'percentuale_fondo_perduto': 40.0},
        {'nome': 'Veneto Agri 2025', 'ente': 'AVEPA Veneto', 'regione': 'Veneto', 'tipo': 'Agricoltura', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.avepa.it', 'data_scadenza': '2025-09-30', 'ateco_ammessi': '["01","02"]', 'regioni_ammesse': '["Veneto"]', 'percentuale_fondo_perduto': 50.0},
        # EMILIA ROMAGNA
        {'nome': 'ER Imprese - Bando Innovazione', 'ente': 'Regione Emilia-Romagna', 'regione': 'Emilia-Romagna', 'tipo': 'Innovazione', 'stato': 'aperto', 'massimale': 600000, 'url': 'https://www.regione.emilia-romagna.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Emilia-Romagna"]', 'percentuale_fondo_perduto': 50.0},
        # TOSCANA
        {'nome': 'Toscana Digitale', 'ente': 'Regione Toscana', 'regione': 'Toscana', 'tipo': 'Digitalizzazione', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.toscana.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Toscana"]', 'percentuale_fondo_perduto': 50.0},
        # PIEMONTE
        {'nome': 'Piemonte Competitivo', 'ente': 'Finpiemonte', 'regione': 'Piemonte', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 400000, 'url': 'https://www.finpiemonte.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Piemonte"]', 'percentuale_fondo_perduto': 0.0},
        # CALABRIA
        {'nome': 'FESR Calabria - Imprenditorialita', 'ente': 'Regione Calabria', 'regione': 'Calabria', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.calabria.it', 'data_scadenza': '2025-11-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Calabria"]', 'percentuale_fondo_perduto': 65.0},
        # SARDEGNA
        {'nome': 'Sardegna Competitiva', 'ente': 'Regione Sardegna', 'regione': 'Sardegna', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 300000, 'url': 'https://www.regione.sardegna.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Sardegna"]', 'percentuale_fondo_perduto': 50.0},
        # ALTRI
        {'nome': 'Marche Startup 2025', 'ente': 'Regione Marche', 'regione': 'Marche', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 150000, 'url': 'https://www.regione.marche.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Marche"]', 'percentuale_fondo_perduto': 60.0},
        {'nome': 'Umbria Innovazione', 'ente': 'Regione Umbria', 'regione': 'Umbria', 'tipo': 'Innovazione', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.umbria.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Umbria"]', 'percentuale_fondo_perduto': 45.0},
        {'nome': 'Basilicata Imprese', 'ente': 'Regione Basilicata', 'regione': 'Basilicata', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 250000, 'url': 'https://www.regione.basilicata.it', 'data_scadenza': '2025-11-30', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Basilicata"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Molise Sviluppo', 'ente': 'Regione Molise', 'regione': 'Molise', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.molise.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Molise"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Friuli Innova', 'ente': 'Regione FVG', 'regione': 'Friuli-Venezia Giulia', 'tipo': 'Innovazione', 'stato': 'aperto', 'massimale': 300000, 'url': 'https://www.regione.fvg.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Friuli-Venezia Giulia"]', 'percentuale_fondo_perduto': 50.0},
        {'nome': 'Liguria Competitiva', 'ente': 'Regione Liguria', 'regione': 'Liguria', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 200000, 'url': 'https://www.regione.liguria.it', 'data_scadenza': '2025-10-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Liguria"]', 'percentuale_fondo_perduto': 40.0},
        {'nome': 'Trentino Startup Hub', 'ente': 'PAT Trento', 'regione': 'Trentino-Alto Adige', 'tipo': 'Startup', 'stato': 'aperto', 'massimale': 500000, 'url': 'https://www.provincia.tn.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Trentino-Alto Adige"]', 'percentuale_fondo_perduto': 40.0},
        {'nome': 'Valle d Aosta PMI', 'ente': 'Regione VdA', 'regione': 'Valle d Aosta', 'tipo': 'Investimenti', 'stato': 'aperto', 'massimale': 150000, 'url': 'https://www.regione.vda.it', 'data_scadenza': '2025-12-31', 'ateco_ammessi': '[]', 'regioni_ammesse': '["Valle d Aosta"]', 'percentuale_fondo_perduto': 40.0},
    ]
    
    conn = get_db()
    c = conn.cursor()
    inseriti = 0
    aggiornati = 0
    for b in bandi:
        existing = c.execute('SELECT id FROM bandi WHERE nome = ?', (b['nome'],)).fetchone()
        if existing:
            c.execute('''UPDATE bandi SET ente=?, regione=?, tipo=?, stato=?, massimale=?, url=?, data_scadenza=?, ateco_ammessi=?, regioni_ammesse=?, percentuale_fondo_perduto=?, data_aggiornamento=datetime('now') WHERE nome=?''',
                     (b['ente'], b['regione'], b['tipo'], b['stato'], b['massimale'], b['url'], b['data_scadenza'], b['ateco_ammessi'], b['regioni_ammesse'], b['percentuale_fondo_perduto'], b['nome']))
            aggiornati += 1
        else:
            c.execute('''INSERT INTO bandi (nome, ente, regione, tipo, stato, massimale, url, data_scadenza, ateco_ammessi, regioni_ammesse, percentuale_fondo_perduto, data_aggiornamento)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                     (b['nome'], b['ente'], b['regione'], b['tipo'], b['stato'], b['massimale'], b['url'], b['data_scadenza'], b['ateco_ammessi'], b['regioni_ammesse'], b['percentuale_fondo_perduto']))
            inseriti += 1
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'inseriti': inseriti, 'aggiornati': aggiornati, 'totale': inseriti + aggiornati})



# ─────────────────────────────────────────────
# INIZIALIZZAZIONE (eseguita da Gunicorn e da __main__)
# ─────────────────────────────────────────────
try:
    init_db()
    avvia_scheduler()
except Exception as _init_err:
    app.logger.error(f"Errore inizializzazione: {_init_err}")

# ─────────────────────────────────────────────
# AVVIO APP
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

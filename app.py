import os
from flask import Flask, redirect, url_for, render_template, request
from flask_login import LoginManager, current_user
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bandomatch.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB max upload

# Usa l'istanza db condivisa da extensions.py (evita import circolari)
from extensions import db
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Per favore accedi per continuare.'
login_manager.login_message_category = 'info'

from models.utente import Utente

@login_manager.user_loader
def load_user(user_id):
    try:
        return Utente.query.get(int(user_id))
    except Exception:
        # Se la query crasha (es. colonne mancanti nel DB), restituisce None
        # per evitare errori 500 su tutte le pagine
        from extensions import db as _db
        _db.session.rollback()
        return None

from blueprints.auth import auth_bp
from blueprints.bandi import bandi_bp
from blueprints.dashboard import dashboard_bp
from blueprints.scraper import scraper_bp
from blueprints.analisi import analisi_bp
from blueprints.admin import admin_bp
from blueprints.enterprise import enterprise_bp

app.register_blueprint(auth_bp,       url_prefix='/auth')
app.register_blueprint(bandi_bp,      url_prefix='/bandi')
app.register_blueprint(dashboard_bp,  url_prefix='/dashboard')
app.register_blueprint(scraper_bp,    url_prefix='/scraper')
app.register_blueprint(analisi_bp,    url_prefix='/analisi')
app.register_blueprint(admin_bp,      url_prefix='/admin')
app.register_blueprint(enterprise_bp, url_prefix='/enterprise')

with app.app_context():
    # ── Migrazione sicura Enterprise ─────────────────────────────────────────
    # Aggiunge le colonne nome_partner e logo_url alla tabella utenti se non
    # esistono ancora. Usa una connessione raw per evitare che SQLAlchemy
    # tenti di caricare il modello prima che le colonne esistano.
    try:
        from sqlalchemy import text as _sql_text
        with db.engine.connect() as _conn:
            if db.engine.dialect.name == 'postgresql':
                _conn.execute(_sql_text(
                    "ALTER TABLE utenti ADD COLUMN IF NOT EXISTS "
                    "nome_partner VARCHAR(255)"
                ))
                _conn.execute(_sql_text(
                    "ALTER TABLE utenti ADD COLUMN IF NOT EXISTS "
                    "logo_url VARCHAR(500)"
                ))
                _conn.commit()
                app.logger.info('Migrazione Enterprise: colonne nome_partner/logo_url verificate.')
    except Exception as _me:
        app.logger.warning(f'Migrazione Enterprise (non critica): {_me}')
    # ─────────────────────────────────────────────────────────────────────────
    db.create_all()
    app.logger.info('db.create_all() completato.')

# Avvia lo scheduler APScheduler per scraping bandi giornaliero alle 06:00 UTC
# Wrappato in try/except per evitare che un errore dello scheduler faccia crashare l'app
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from utils.scheduler import start_scheduler
    _scheduler = BackgroundScheduler()
    start_scheduler(_scheduler, app)
    _scheduler.start()
    app.logger.info("Scheduler APScheduler avviato con successo.")
except Exception as _e:
    app.logger.error(f"Scheduler non avviato (non critico): {_e}")

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('landing.html')

@app.route('/sys/debug-login')
def debug_login():
    """Endpoint temporaneo per diagnosticare l'errore 500 sul login."""
    import traceback
    try:
        from models.utente import Utente
        u = Utente.query.filter_by(email='test@bandomatch.it').first()
        return {'ok': True, 'user': str(u), 'piano': u.piano if u else None}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'traceback': traceback.format_exc()}, 500


@app.route('/sys/migrate-enterprise')
def migrate_enterprise():
    """Endpoint temporaneo per forzare la migrazione Enterprise su Railway."""
    key = os.getenv('MIGRATE_KEY', '')
    if not key or request.args.get('key') != key:
        return {'error': 'Unauthorized'}, 403
    try:
        from sqlalchemy import text, inspect as sa_inspect
        results = []
        with db.engine.connect() as conn:
            insp = sa_inspect(db.engine)
            existing_cols = [c['name'] for c in insp.get_columns('utenti')] if 'utenti' in insp.get_table_names() else []
            if 'nome_partner' not in existing_cols:
                conn.execute(text("ALTER TABLE utenti ADD COLUMN nome_partner VARCHAR(255)"))
                results.append('nome_partner: AGGIUNTA')
            else:
                results.append('nome_partner: GIA PRESENTE')
            if 'logo_url' not in existing_cols:
                conn.execute(text("ALTER TABLE utenti ADD COLUMN logo_url VARCHAR(500)"))
                results.append('logo_url: AGGIUNTA')
            else:
                results.append('logo_url: GIA PRESENTE')
            conn.commit()
        db.create_all()
        return {'ok': True, 'results': results}
    except Exception as e:
        return {'ok': False, 'error': str(e)}, 500


@app.errorhandler(404)
def not_found(error):
    return {'error': 'Risorsa non trovata'}, 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return {'error': 'Errore interno del server'}, 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_ENV') == 'development'
    )

import os
from flask import Flask, redirect, url_for, render_template
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
    return Utente.query.get(int(user_id))

from blueprints.auth import auth_bp
from blueprints.bandi import bandi_bp
from blueprints.dashboard import dashboard_bp
from blueprints.scraper import scraper_bp
from blueprints.analisi import analisi_bp
from blueprints.admin import admin_bp

app.register_blueprint(auth_bp,      url_prefix='/auth')
app.register_blueprint(bandi_bp,     url_prefix='/bandi')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(scraper_bp,   url_prefix='/scraper')
app.register_blueprint(analisi_bp,   url_prefix='/analisi')
app.register_blueprint(admin_bp,     url_prefix='/admin')

with app.app_context():
    db.create_all()

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

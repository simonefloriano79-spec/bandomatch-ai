import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configurazione Database
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'sqlite:///bandomatch.db'
)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Inizializzazione SQLAlchemy
db = SQLAlchemy(app)

# Inizializzazione Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Per favore accedi per continuare.'
login_manager.login_message_category = 'info'

# Import modelli per registrazione con db context
with app.app_context():
    from models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

# Registrazione Blueprints
from blueprints.auth import auth_bp
from blueprints.bandi import bandi_bp
from blueprints.dashboard import dashboard_bp
from blueprints.scraper import scraper_bp

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(bandi_bp, url_prefix='/bandi')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(scraper_bp, url_prefix='/scraper')

# Route principale
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('auth.login'))

# Error handlers
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
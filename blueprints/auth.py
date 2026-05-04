from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models.utente import Utente as User
from app import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registrazione nuovo utente"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validazione
        if not email or not password:
            flash('Email e password sono obbligatorie', 'error')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Le password non corrispondono', 'error')
            return redirect(url_for('auth.register'))
        
        if len(password) < 8:
            flash('La password deve avere almeno 8 caratteri', 'error')
            return redirect(url_for('auth.register'))
        
        # Controlla se email esiste
        try:
            user_exists = User.query.filter_by(email=email).first()
            if user_exists:
                flash('Questa email è già registrata', 'error')
                return redirect(url_for('auth.register'))
            
            # Crea nuovo utente
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password),
                piano='free',
                attivo=True,
                data_registrazione=datetime.utcnow()
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registrazione completata! Accedi con le tue credenziali', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la registrazione: {str(e)}', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login utente"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') is not None
        
        # Validazione
        if not email or not password:
            flash('Email e password sono obbligatorie', 'error')
            return redirect(url_for('auth.login'))
        
        try:
            # Cerca utente
            user = User.query.filter_by(email=email).first()
            
            if not user:
                flash('Email o password errati', 'error')
                return redirect(url_for('auth.login'))
            
            # Verifica password
            if not check_password_hash(user.password_hash, password):
                flash('Email o password errati', 'error')
                return redirect(url_for('auth.login'))
            
            # Controlla se account è attivo
            if not user.attivo:
                flash('Il tuo account è disattivato. Contatta il supporto', 'warning')
                return redirect(url_for('auth.login'))
            
            # Login utente
            login_user(user, remember=remember_me)
            flash(f'Benvenuto, {user.email}!', 'success')
            
            # Reindirizza a next page se presente
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            
            return redirect(url_for('main.index'))
        
        except Exception as e:
            flash(f'Errore durante il login: {str(e)}', 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout utente"""
    try:
        logout_user()
        flash('Logout completato', 'success')
    except Exception as e:
        flash(f'Errore durante il logout: {str(e)}', 'error')
    
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """Profilo utente"""
    try:
        user = User.query.get(current_user.id)
        if not user:
            flash('Utente non trovato', 'error')
            return redirect(url_for('auth.logout'))
        
        return render_template('auth/profile.html', user=user)
    
    except Exception as e:
        flash(f'Errore nel caricamento del profilo: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Aggiorna profilo utente"""
    try:
        user = User.query.get(current_user.id)
        if not user:
            flash('Utente non trovato', 'error')
            return redirect(url_for('auth.logout'))
        
        new_email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '')
        current_password = request.form.get('current_password', '')
        
        # Verifica password attuale se si vuole cambiarla
        if new_password:
            if not current_password or not check_password_hash(user.password_hash, current_password):
                flash('Password attuale errata', 'error')
                return redirect(url_for('auth.profile'))
            
            if len(new_password) < 8:
                flash('La nuova password deve avere almeno 8 caratteri', 'error')
                return redirect(url_for('auth.profile'))
            
            user.password_hash = generate_password_hash(new_password)
        
        # Aggiorna email se cambiata
        if new_email and new_email != user.email:
            email_exists = User.query.filter_by(email=new_email).first()
            if email_exists:
                flash('Questa email è già in uso', 'error')
                return redirect(url_for('auth.profile'))
            user.email = new_email
        
        db.session.commit()
        flash('Profilo aggiornato con successo', 'success')
        return redirect(url_for('auth.profile'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante l\'aggiornamento: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))

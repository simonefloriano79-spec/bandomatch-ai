from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models.utente import Utente as User
from extensions import db
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirm', '')
        if not email or not password:
            flash('Email e password obbligatorie', 'error')
            return redirect(url_for('auth.register'))
        if password != confirm:
            flash('Le password non corrispondono', 'error')
            return redirect(url_for('auth.register'))
        if len(password) < 8:
            flash('Password minimo 8 caratteri', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email già registrata', 'error')
            return redirect(url_for('auth.register'))
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            piano='free',
            attivo=True,
            data_registrazione=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        flash('Registrazione completata!', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') is not None
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Email o password errati', 'error')
            return redirect(url_for('auth.login'))
        if not user.attivo:
            flash('Account disattivato', 'warning')
            return redirect(url_for('auth.login'))
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard.home'))
    return render_template('auth.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout completato', 'success')
    return redirect(url_for('auth.login'))

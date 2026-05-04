from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@dashboard_bp.route('/home')
@login_required
def home():
    return render_template('dashboard.html')

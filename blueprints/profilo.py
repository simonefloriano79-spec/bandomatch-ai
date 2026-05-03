from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from models.user import User
from models.company_profile import CompanyProfile
from extensions import db
import logging

profilo_bp = Blueprint('profilo', __name__, url_prefix='/profilo')
logger = logging.getLogger(__name__)


@profilo_bp.route('', methods=['GET'])
@login_required
def view_profilo():
    """
    Renderizza la pagina profilo aziendale dell'utente loggato.
    GET /profilo
    """
    try:
        company_profile = CompanyProfile.query.filter_by(
            user_id=current_user.id
        ).first()
        
        return render_template(
            'profilo.html',
            company_profile=company_profile,
            user=current_user
        )
    except Exception as e:
        logger.error(f"Errore nel caricamento profilo: {str(e)}")
        return render_template(
            'profilo.html',
            company_profile=None,
            user=current_user,
            error="Errore nel caricamento del profilo"
        ), 500


@profilo_bp.route('/api/v1/profilo', methods=['POST'])
@login_required
def save_profilo():
    """
    Salva i dati del profilo aziendale nel database.
    POST /api/v1/profilo
    
    Payload JSON:
    {
        "company_name": "Nome Azienda",
        "company_description": "Descrizione",
        "industry": "Settore",
        "website": "https://example.com",
        "phone": "+39...",
        "location": "Città",
        "employees_count": "10-50",
        "logo_url": "https://...",
        "social_linkedin": "https://linkedin.com/...",
        "social_instagram": "https://instagram.com/..."
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "message": "Dati non forniti"
            }), 400
        
        # Validazione campi obbligatori
        required_fields = ['company_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    "success": False,
                    "message": f"Campo obbligatorio mancante: {field}"
                }), 400
        
        # Recupera o crea il profilo aziendale
        company_profile = CompanyProfile.query.filter_by(
            user_id=current_user.id
        ).first()
        
        if not company_profile:
            company_profile = CompanyProfile(user_id=current_user.id)
        
        # Aggiorna i campi
        company_profile.company_name = data.get('company_name', company_profile.company_name)
        company_profile.company_description = data.get('company_description', company_profile.company_description)
        company_profile.industry = data.get('industry', company_profile.industry)
        company_profile.website = data.get('website', company_profile.website)
        company_profile.phone = data.get('phone', company_profile.phone)
        company_profile.location = data.get('location', company_profile.location)
        company_profile.employees_count = data.get('employees_count', company_profile.employees_count)
        company_profile.logo_url = data.get('logo_url', company_profile.logo_url)
        company_profile.social_linkedin = data.get('social_linkedin', company_profile.social_linkedin)
        company_profile.social_instagram = data.get('social_instagram', company_profile.social_instagram)
        
        # Salva nel database
        db.session.add(company_profile)
        db.session.commit()
        
        logger.info(f"Profilo aziendale aggiornato per utente {current_user.id}")
        
        return jsonify({
            "success": True,
            "message": "Profilo aziendale salvato con successo",
            "profile_id": company_profile.id
        }), 200
    
    except ValueError as ve:
        db.session.rollback()
        logger.error(f"Errore di validazione: {str(ve)}")
        return jsonify({
            "success": False,
            "message": f"Errore di validazione: {str(ve)}"
        }), 400
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Errore nel salvataggio profilo: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Errore nel salvataggio del profilo aziendale"
        }), 500

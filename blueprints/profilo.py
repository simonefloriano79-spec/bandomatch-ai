from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from models.user import User
from models.profilo_aziendale import ProfiloAziendale
from extensions import db

profilo = Blueprint('profilo', __name__, url_prefix='')


@profilo.route('/profilo', methods=['GET'])
@login_required
def get_profilo():
    """
    Renderizza la pagina del profilo aziendale per l'utente loggato
    """
    try:
        profilo_aziendale = ProfiloAziendale.query.filter_by(
            user_id=current_user.id
        ).first()
        
        return render_template(
            'profilo.html',
            profilo=profilo_aziendale,
            user=current_user
        )
    except Exception as e:
        return render_template(
            'profilo.html',
            profilo=None,
            user=current_user,
            error='Errore nel caricamento del profilo'
        ), 500


@profilo.route('/api/v1/profilo', methods=['POST'])
@login_required
def save_profilo():
    """
    Salva o aggiorna il profilo aziendale dell'utente loggato
    
    Expected JSON:
    {
        "nome_azienda": str,
        "descrizione": str,
        "website": str,
        "telefono": str,
        "email_contatti": str,
        "indirizzo": str,
        "citta": str,
        "provincia": str,
        "cap": str,
        "settore": str,
        "dipendenti": int,
        "logo_url": str (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dati mancanti'
            }), 400
        
        # Validazione campi obbligatori
        required_fields = ['nome_azienda', 'descrizione', 'email_contatti']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Campo obbligatorio mancante: {field}'
                }), 400
        
        # Cerca profilo esistente
        profilo_aziendale = ProfiloAziendale.query.filter_by(
            user_id=current_user.id
        ).first()
        
        if profilo_aziendale:
            # Aggiorna profilo esistente
            profilo_aziendale.nome_azienda = data.get('nome_azienda')
            profilo_aziendale.descrizione = data.get('descrizione')
            profilo_aziendale.website = data.get('website')
            profilo_aziendale.telefono = data.get('telefono')
            profilo_aziendale.email_contatti = data.get('email_contatti')
            profilo_aziendale.indirizzo = data.get('indirizzo')
            profilo_aziendale.citta = data.get('citta')
            profilo_aziendale.provincia = data.get('provincia')
            profilo_aziendale.cap = data.get('cap')
            profilo_aziendale.settore = data.get('settore')
            profilo_aziendale.dipendenti = data.get('dipendenti')
            if data.get('logo_url'):
                profilo_aziendale.logo_url = data.get('logo_url')
        else:
            # Crea nuovo profilo
            profilo_aziendale = ProfiloAziendale(
                user_id=current_user.id,
                nome_azienda=data.get('nome_azienda'),
                descrizione=data.get('descrizione'),
                website=data.get('website'),
                telefono=data.get('telefono'),
                email_contatti=data.get('email_contatti'),
                indirizzo=data.get('indirizzo'),
                citta=data.get('citta'),
                provincia=data.get('provincia'),
                cap=data.get('cap'),
                settore=data.get('settore'),
                dipendenti=data.get('dipendenti'),
                logo_url=data.get('logo_url')
            )
            db.session.add(profilo_aziendale)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profilo salvato con successo',
            'profilo_id': profilo_aziendale.id
        }), 200
    
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Errore nel salvataggio del profilo nel database'
        }), 500
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500

from flask import Blueprint, request, send_file, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import and_
from models.bandi import Bandi
from models.partecipazioni import Partecipazioni
from utils.dossier import generate_dossier_pdf
from db import db
import os

bandi_bp = Blueprint('bandi', __name__, url_prefix='/api/v1/bandi')


@bandi_bp.route('', methods=['GET'])
@login_required
def list_bandi():
    """Lista i bandi disponibili con filtri opzionali"""
    try:
        stato = request.args.get('stato')
        categoria = request.args.get('categoria')
        search = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Bandi.query
        
        if stato:
            query = query.filter_by(stato=stato)
        if categoria:
            query = query.filter_by(categoria=categoria)
        if search:
            query = query.filter(
                or_(
                    Bandi.titolo.ilike(f'%{search}%'),
                    Bandi.descrizione.ilike(f'%{search}%')
                )
            )
        
        paginate = query.paginate(page=page, per_page=per_page)
        
        return jsonify({
            'success': True,
            'data': [bando.to_dict() for bando in paginate.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginate.total,
                'pages': paginate.pages
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f'Errore list_bandi: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500


@bandi_bp.route('/<int:id_bando>', methods=['GET'])
@login_required
def get_bando(id_bando):
    """Recupera un singolo bando"""
    try:
        bando = Bandi.query.get(id_bando)
        if not bando:
            return jsonify({'success': False, 'error': 'Bando non trovato'}), 404
        
        return jsonify({
            'success': True,
            'data': bando.to_dict()
        }), 200
    except Exception as e:
        current_app.logger.error(f'Errore get_bando: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500


@bandi_bp.route('/dossier', methods=['GET'])
@login_required
def get_dossier():
    """Genera e scarica il dossier PDF di un bando"""
    try:
        id_bando = request.args.get('id_bando', type=int)
        
        if not id_bando:
            return jsonify({'success': False, 'error': 'Parametro id_bando obbligatorio'}), 400
        
        bando = Bandi.query.get(id_bando)
        if not bando:
            return jsonify({'success': False, 'error': 'Bando non trovato'}), 404
        
        partecipazioni = Partecipazioni.query.filter_by(
            id_bando=id_bando,
            id_user=current_user.id
        ).all()
        
        if not partecipazioni:
            return jsonify({'success': False, 'error': 'Nessuna partecipazione trovata per questo bando'}), 403
        
        pdf_path = generate_dossier_pdf(
            bando=bando,
            partecipazioni=partecipazioni,
            user=current_user
        )
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'success': False, 'error': 'Errore nella generazione del PDF'}), 500
        
        filename = f"dossier_bando_{id_bando}.pdf"
        
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    
    except ValueError as ve:
        current_app.logger.error(f'Errore validazione get_dossier: {str(ve)}')
        return jsonify({'success': False, 'error': 'Parametri non validi'}), 400
    except Exception as e:
        current_app.logger.error(f'Errore get_dossier: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

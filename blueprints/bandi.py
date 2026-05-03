from flask import Blueprint, request, jsonify
from sqlalchemy import and_, or_
from models.bando import Bando
from models.database import db
import logging

bandi_bp = Blueprint('bandi', __name__, url_prefix='/api/v1')
logger = logging.getLogger(__name__)


@bandi_bp.route('/bandi', methods=['GET'])
def list_bandi():
    """
    GET /api/v1/bandi
    Restituisce lista bandi con filtri opzionali per stato e regione.
    Query parameters:
    - stato: str (opzionale) - es: 'aperto', 'chiuso', 'prossimamente'
    - regione: str (opzionale) - es: 'Lazio', 'Campania'
    - limit: int (opzionale, default 50) - numero massimo risultati
    - offset: int (opzionale, default 0) - offset per paginazione
    """
    try:
        # Recupera parametri query
        stato = request.args.get('stato', None)
        regione = request.args.get('regione', None)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validazione parametri
        if limit > 500:
            limit = 500
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0
        
        # Costruisci query base
        query = Bando.query
        
        # Applica filtri
        filters = []
        
        if stato:
            filters.append(Bando.stato == stato.lower())
        
        if regione:
            filters.append(Bando.regione == regione)
        
        # Combina filtri con AND
        if filters:
            query = query.filter(and_(*filters))
        
        # Conta totale risultati
        total = query.count()
        
        # Applica paginazione e ordina per data di scadenza
        bandi = query.order_by(Bando.data_scadenza.asc()).limit(limit).offset(offset).all()
        
        # Serializza risultati
        risultati = [
            {
                'id': bando.id,
                'titolo': bando.titolo,
                'descrizione': bando.descrizione,
                'stato': bando.stato,
                'regione': bando.regione,
                'data_pubblicazione': bando.data_pubblicazione.isoformat() if bando.data_pubblicazione else None,
                'data_scadenza': bando.data_scadenza.isoformat() if bando.data_scadenza else None,
                'ente': bando.ente,
                'importo': float(bando.importo) if bando.importo else None,
                'url': bando.url
            }
            for bando in bandi
        ]
        
        return jsonify({
            'success': True,
            'data': risultati,
            'pagination': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'returned': len(risultati)
            }
        }), 200
    
    except Exception as e:
        logger.error(f'Errore nel recupero bandi: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Errore nel recupero dei bandi',
            'message': str(e)
        }), 500


@bandi_bp.route('/bandi/dettaglio', methods=['GET'])
def get_bando_dettaglio():
    """
    GET /api/v1/bandi/dettaglio
    Restituisce dettagli di un singolo bando.
    Query parameters:
    - id: int (obbligatorio) - ID del bando
    """
    try:
        # Recupera parametro id
        bando_id = request.args.get('id', None, type=int)
        
        # Validazione parametro
        if not bando_id:
            return jsonify({
                'success': False,
                'error': 'Parametro id mancante o non valido',
                'message': 'Fornisci un id valido come query parameter'
            }), 400
        
        # Recupera bando dal database
        bando = Bando.query.filter_by(id=bando_id).first()
        
        # Verifica se bando esiste
        if not bando:
            return jsonify({
                'success': False,
                'error': 'Bando non trovato',
                'message': f'Nessun bando trovato con id {bando_id}'
            }), 404
        
        # Serializza dettagli completi
        dettaglio = {
            'id': bando.id,
            'titolo': bando.titolo,
            'descrizione': bando.descrizione,
            'stato': bando.stato,
            'regione': bando.regione,
            'provincia': bando.provincia,
            'ente': bando.ente,
            'importo': float(bando.importo) if bando.importo else None,
            'data_pubblicazione': bando.data_pubblicazione.isoformat() if bando.data_pubblicazione else None,
            'data_scadenza': bando.data_scadenza.isoformat() if bando.data_scadenza else None,
            'url': bando.url,
            'settore': bando.settore,
            'destinatari': bando.destinatari,
            'criteri_selezione': bando.criteri_selezione,
            'data_creazione': bando.data_creazione.isoformat() if bando.data_creazione else None,
            'data_aggiornamento': bando.data_aggiornamento.isoformat() if bando.data_aggiornamento else None
        }
        
        return jsonify({
            'success': True,
            'data': dettaglio
        }), 200
    
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Parametro id non valido',
            'message': 'L\'id deve essere un numero intero'
        }), 400
    
    except Exception as e:
        logger.error(f'Errore nel recupero dettaglio bando: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Errore nel recupero del bando',
            'message': str(e)
        }), 500

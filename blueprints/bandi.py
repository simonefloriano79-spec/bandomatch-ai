from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import desc, or_
from models.bando import Bando
from app import db

bandi_bp = Blueprint('bandi', __name__, url_prefix='/bandi')


@bandi_bp.route('/', methods=['GET'])
def lista_bandi():
    """
    Lista tutti i bandi con filtri e paginazione.
    Query params:
    - page: numero pagina (default 1)
    - search: ricerca per titolo/descrizione
    - stato: filtra per stato (APERTO, CHIUSO, in_scadenza)
    """
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '', type=str)
        stato = request.args.get('stato', '', type=str)
        per_pagina = 12

        query = Bando.query

        # Filtro ricerca
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Bando.titolo.ilike(search_term),
                    Bando.descrizione.ilike(search_term)
                )
            )

        # Filtro stato
        if stato == 'aperto':
            query = query.filter(Bando.stato == 'APERTO')
        elif stato == 'chiuso':
            query = query.filter(Bando.stato.in_(['CHIUSO', 'SOSPESO']))
        elif stato == 'in_scadenza':
            from datetime import datetime, timedelta
            oggi = datetime.utcnow()
            fra_giorni = oggi + timedelta(days=7)
            query = query.filter(
                Bando.data_scadenza.between(oggi, fra_giorni),
                Bando.stato == 'APERTO'
            )

        # Ordinamento: più recenti prima
        query = query.order_by(desc(Bando.created_at))

        # Paginazione
        paginate_obj = query.paginate(page=page, per_page=per_pagina, error_out=False)
        bandi = paginate_obj.items
        total_pages = paginate_obj.pages

        # Fonti uniche per filtro (usiamo fonte come "categoria")
        fonti = db.session.query(Bando.fonte).distinct().filter(
            Bando.fonte != None
        ).all()
        categorie = [f[0] for f in fonti if f[0]]

        return render_template(
            'bandi_lista.html',
            bandi=bandi,
            page=page,
            total_pages=total_pages,
            search=search,
            categoria='',
            stato=stato,
            categorie=categorie
        )

    except Exception as e:
        flash(f'Errore nel caricamento dei bandi: {str(e)}', 'error')
        return redirect(url_for('index'))


@bandi_bp.route('/<int:bando_id>', methods=['GET'])
def dettaglio_bando(bando_id):
    """
    Visualizza dettaglio di un singolo bando.
    """
    try:
        bando = Bando.query.get_or_404(bando_id)
        return render_template(
            'dettaglio_bando.html',
            bando=bando
        )
    except Exception as e:
        flash(f'Errore nel caricamento del bando: {str(e)}', 'error')
        return redirect(url_for('bandi.lista_bandi'))


@bandi_bp.route('/api/search', methods=['GET'])
def api_search_bandi():
    """
    API endpoint per ricerca AJAX bandi.
    Query params: q (query), limit (default 10)
    """
    try:
        q = request.args.get('q', '', type=str)
        limit = request.args.get('limit', 10, type=int)

        if not q or len(q) < 2:
            return jsonify([])

        search_term = f"%{q}%"
        risultati = Bando.query.filter(
            or_(
                Bando.titolo.ilike(search_term),
                Bando.descrizione.ilike(search_term)
            ),
            Bando.stato == 'APERTO'
        ).limit(limit).all()

        data = [
            {
                'id': b.id,
                'titolo': b.titolo,
                'fonte': b.fonte,
                'url': url_for('bandi.dettaglio_bando', bando_id=b.id)
            }
            for b in risultati
        ]

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

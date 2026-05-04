from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import desc, or_
from models.utente import Utente as User
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
    - categoria: filtra per categoria
    - stato: filtra per stato (aperto, chiuso, in_scadenza)
    """
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '', type=str)
        categoria = request.args.get('categoria', '', type=str)
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

        # Filtro categoria
        if categoria:
            query = query.filter(Bando.categoria == categoria)

        # Filtro stato
        if stato == 'aperto':
            query = query.filter(Bando.stato == 'aperto')
        elif stato == 'chiuso':
            query = query.filter(Bando.stato == 'chiuso')
        elif stato == 'in_scadenza':
            from datetime import datetime, timedelta
            oggi = datetime.utcnow()
            fra_giorni = oggi + timedelta(days=7)
            query = query.filter(
                Bando.data_scadenza.between(oggi, fra_giorni),
                Bando.stato == 'aperto'
            )

        # Ordinamento: più recenti prima
        query = query.order_by(desc(Bando.data_creazione))

        # Paginazione
        paginate = query.paginate(page=page, per_page=per_pagina, error_out=False)
        bandi = paginate.items
        total_pages = paginate.pages

        # Recupera categorie uniche per filtro
        categorie = db.session.query(Bando.categoria).distinct().filter(
            Bando.categoria != None
        ).all()
        categorie = [c[0] for c in categorie]

        return render_template(
            'bandi/lista.html',
            bandi=bandi,
            page=page,
            total_pages=total_pages,
            search=search,
            categoria=categoria,
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
            'bandi/dettaglio.html',
            bando=bando
        )

    except Exception as e:
        flash(f'Errore nel caricamento del bando: {str(e)}', 'error')
        return redirect(url_for('bandi.lista_bandi'))


@bandi_bp.route('/<int:bando_id>/partecipa', methods=['POST'])
def partecipa_bando(bando_id):
    """
    Registra la partecipazione di un utente a un bando.
    Richiede autenticazione.
    """
    from flask_login import current_user, login_required
    
    @login_required
    def _partecipa():
        try:
            bando = Bando.query.get_or_404(bando_id)
            user = User.query.get(current_user.id)

            if not user:
                flash('Utente non trovato.', 'error')
                return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

            # Verifica se già partecipa
            if user in bando.utenti_partecipanti:
                flash('Sei già iscritto a questo bando.', 'warning')
                return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

            # Verifica stato bando
            if bando.stato != 'aperto':
                flash('Questo bando non è più aperto alle iscrizioni.', 'error')
                return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

            # Aggiungi partecipazione
            bando.utenti_partecipanti.append(user)
            db.session.commit()

            flash('Ti sei iscritto con successo al bando!', 'success')
            return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nella registrazione: {str(e)}', 'error')
            return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

    return _partecipa()


@bandi_bp.route('/<int:bando_id>/ritira', methods=['POST'])
def ritira_bando(bando_id):
    """
    Ritira la partecipazione di un utente da un bando.
    Richiede autenticazione.
    """
    from flask_login import current_user, login_required
    
    @login_required
    def _ritira():
        try:
            bando = Bando.query.get_or_404(bando_id)
            user = User.query.get(current_user.id)

            if not user:
                flash('Utente non trovato.', 'error')
                return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

            if user not in bando.utenti_partecipanti:
                flash('Non sei iscritto a questo bando.', 'warning')
                return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

            # Rimuovi partecipazione
            bando.utenti_partecipanti.remove(user)
            db.session.commit()

            flash('Ti sei ritirato dal bando.', 'success')
            return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nel ritiro: {str(e)}', 'error')
            return redirect(url_for('bandi.dettaglio_bando', bando_id=bando_id))

    return _ritira()


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
            Bando.stato == 'aperto'
        ).limit(limit).all()

        data = [
            {
                'id': b.id,
                'titolo': b.titolo,
                'categoria': b.categoria,
                'url': url_for('bandi.dettaglio_bando', bando_id=b.id)
            }
            for b in risultati
        ]

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

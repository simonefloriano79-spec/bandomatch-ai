from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from app import db
from models.utente import Utente as User
from models.bando import Bando

scraper_bp = Blueprint('scraper', __name__, url_prefix='/scraper')

def admin_only(f):
    """Decorator per verificare se l'utente è admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Accesso negato. Effettua il login.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            flash('Accesso negato. Solo amministratori.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@scraper_bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_only
def scraper_dashboard():
    """Dashboard per il trigger manuale dello scraping."""
    last_scrape = None
    total_bandi = db.session.query(Bando).count()
    
    try:
        last_scrape_record = db.session.query(Bando).order_by(Bando.creato_il.desc()).first()
        if last_scrape_record:
            last_scrape = last_scrape_record.creato_il
    except Exception as e:
        flash(f'Errore nel recupero dati: {str(e)}', 'danger')
    
    return render_template('scraper/dashboard.html', 
                         last_scrape=last_scrape,
                         total_bandi=total_bandi)

@scraper_bp.route('/trigger', methods=['POST'])
@login_required
@admin_only
def trigger_scraping():
    """Endpoint per avviare lo scraping manuale."""
    try:
        results = scrape_bandi()
        flash(f'Scraping completato: {results["added"]} bandi aggiunti, {results["updated"]} aggiornati.', 'success')
        return redirect(url_for('scraper.scraper_dashboard'))
    except Exception as e:
        flash(f'Errore durante lo scraping: {str(e)}', 'danger')
        return redirect(url_for('scraper.scraper_dashboard'))

@scraper_bp.route('/trigger-json', methods=['POST'])
@login_required
@admin_only
def trigger_scraping_json():
    """Endpoint JSON per avviare lo scraping manuale."""
    try:
        results = scrape_bandi()
        return jsonify({
            'status': 'success',
            'message': 'Scraping completato',
            'added': results['added'],
            'updated': results['updated'],
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def scrape_bandi():
    """
    Scrape dei bandi da fonte esterna.
    Restituisce dict con conteggio dei bandi aggiunti e aggiornati.
    """
    added = 0
    updated = 0
    
    try:
        # Esempio: scraping da una fonte pubblica (adattare l'URL e il parsing)
        # Questo è un template generico
        sources = [
            'https://www.bandosmartly.it/api/bandi',  # Placeholder
        ]
        
        for source_url in sources:
            try:
                response = requests.get(source_url, timeout=10)
                response.raise_for_status()
                
                # Parsing della risposta (adattare in base alla fonte)
                data = response.json() if source_url.endswith('/api/bandi') else parse_html(response.text)
                
                for item in data:
                    bando = process_bando_item(item)
                    if bando:
                        if bando.get('is_new'):
                            added += 1
                        else:
                            updated += 1
            
            except requests.exceptions.RequestException as e:
                # Continua con altre fonti se una fallisce
                print(f'Errore durante il scraping di {source_url}: {str(e)}')
                continue
        
        db.session.commit()
        return {'added': added, 'updated': updated}
    
    except Exception as e:
        db.session.rollback()
        raise Exception(f'Errore durante lo scraping: {str(e)}')

def parse_html(html_content):
    """
    Parse HTML dalla risposta.
    Restituisce lista di dict con dati dei bandi.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    bandi = []
    
    try:
        # Adattare i selettori CSS in base alla struttura HTML della fonte
        bandi_elements = soup.find_all('div', class_='bando-item')
        
        for elemento in bandi_elements:
            try:
                titolo = elemento.find('h2', class_='bando-title')
                descrizione = elemento.find('p', class_='bando-description')
                scadenza = elemento.find('span', class_='bando-scadenza')
                
                if titolo:
                    bandi.append({
                        'titolo': titolo.text.strip(),
                        'descrizione': descrizione.text.strip() if descrizione else '',
                        'scadenza': scadenza.text.strip() if scadenza else '',
                    })
            except Exception as e:
                print(f'Errore nel parsing di elemento bando: {str(e)}')
                continue
    
    except Exception as e:
        print(f'Errore nel parsing HTML: {str(e)}')
    
    return bandi

def process_bando_item(item):
    """
    Processa un singolo item di bando.
    Aggiunge o aggiorna il database.
    Restituisce dict con info sull'azione effettuata.
    """
    try:
        # Estrai i dati dall'item (adattare in base alla struttura)
        titolo = item.get('titolo') or item.get('title')
        descrizione = item.get('descrizione') or item.get('description', '')
        scadenza_str = item.get('scadenza') or item.get('deadline', '')
        url = item.get('url', '')
        
        if not titolo:
            return None
        
        # Converti la data di scadenza
        scadenza = parse_date(scadenza_str) if scadenza_str else None
        
        # Cerca se il bando esiste già (per URL o titolo)
        bando_esistente = None
        if url:
            bando_esistente = db.session.query(Bando).filter_by(url=url).first()
        
        if not bando_esistente:
            bando_esistente = db.session.query(Bando).filter_by(titolo=titolo).first()
        
        if bando_esistente:
            # Aggiorna il bando esistente
            bando_esistente.descrizione = descrizione
            bando_esistente.scadenza = scadenza
            bando_esistente.aggiornato_il = datetime.now()
            db.session.add(bando_esistente)
            return {'is_new': False, 'bando_id': bando_esistente.id}
        else:
            # Crea un nuovo bando
            nuovo_bando = Bando(
                titolo=titolo,
                descrizione=descrizione,
                scadenza=scadenza,
                url=url,
                creato_il=datetime.now(),
                aggiornato_il=datetime.now()
            )
            db.session.add(nuovo_bando)
            db.session.flush()  # Per ottenere l'ID
            return {'is_new': True, 'bando_id': nuovo_bando.id}
    
    except Exception as e:
        print(f'Errore nel processamento dell\'item: {str(e)}')
        return None

def parse_date(date_string):
    """
    Converte una stringa di data in oggetto datetime.
    Supporta formati comuni.
    """
    if not date_string:
        return None
    
    formats = [
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d.%m.%Y',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt)
        except ValueError:
            continue
    
    return None

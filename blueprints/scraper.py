import requests
from bs4 import BeautifulSoup
from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models.bando import Bando
from extensions import db
import logging

scraper_bp = Blueprint('scraper', __name__, url_prefix='/api/v1/scraper')
logger = logging.getLogger(__name__)

@scraper_bp.route('/run', methods=['POST'])
def run_scraper():
    """
    Scrape bandi from invitalia.it and save to database.
    Expected JSON payload:
    {
        "url": "https://www.invitalia.it/...",
        "category": "optional_category"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url'
            }), 400
        
        url = data.get('url')
        category = data.get('category', 'General')
        
        # Validate URL
        if not url.startswith('https://www.invitalia.it'):
            return jsonify({
                'success': False,
                'error': 'URL must be from invitalia.it'
            }), 400
        
        # Fetch page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract bandi from page
        bandi_data = _extract_bandi(soup, category)
        
        if not bandi_data:
            return jsonify({
                'success': True,
                'message': 'No bandi found on page',
                'count': 0
            }), 200
        
        # Save to database
        saved_count = _save_bandi_to_db(bandi_data)
        
        return jsonify({
            'success': True,
            'message': f'Successfully scraped and saved {saved_count} bandi',
            'count': saved_count,
            'bandi': bandi_data[:10]  # Return first 10 for preview
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Request error during scraping: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Failed to fetch URL: {str(e)}'
        }), 502
    
    except Exception as e:
        logger.error(f'Unexpected error during scraping: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


def _extract_bandi(soup, category):
    """
    Extract bandi information from BeautifulSoup object.
    Targets common Invitalia page structures.
    """
    bandi_list = []
    
    try:
        # Try to find bandi in common container structures
        # Method 1: Look for div with bando/notice classes
        bando_containers = soup.find_all('div', class_=lambda x: x and ('bando' in x.lower() or 'notice' in x.lower()))
        
        if not bando_containers:
            # Method 2: Look for article elements
            bando_containers = soup.find_all('article')
        
        if not bando_containers:
            # Method 3: Look for specific invitalia patterns
            bando_containers = soup.find_all('div', class_=lambda x: x and ('call' in x.lower() or 'grant' in x.lower()))
        
        for container in bando_containers:
            bando_info = _parse_bando_container(container, category)
            if bando_info and bando_info.get('titolo'):
                bandi_list.append(bando_info)
        
        return bandi_list
    
    except Exception as e:
        logger.error(f'Error extracting bandi: {str(e)}')
        return []


def _parse_bando_container(container, category):
    """
    Parse individual bando container and extract relevant information.
    """
    try:
        bando_info = {}
        
        # Extract title
        title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'a'])
        titolo = title_elem.get_text(strip=True) if title_elem else None
        
        if not titolo or len(titolo) < 5:
            return None
        
        bando_info['titolo'] = titolo[:500]
        
        # Extract description/body
        desc_elem = container.find(['p', 'div'], class_=lambda x: x and ('desc' in x.lower() or 'summary' in x.lower()))
        if not desc_elem:
            desc_elem = container.find('p')
        
        descrizione = desc_elem.get_text(strip=True) if desc_elem else ''
        bando_info['descrizione'] = descrizione[:2000]
        
        # Extract URL
        link_elem = container.find('a', href=True)
        if link_elem:
            href = link_elem['href']
            if not href.startswith('http'):
                href = 'https://www.invitalia.it' + href if href.startswith('/') else 'https://www.invitalia.it/' + href
            bando_info['url'] = href
        
        # Extract deadline (look for common patterns)
        deadline_text = container.get_text()
        deadline_date = _extract_deadline(deadline_text)
        if deadline_date:
            bando_info['scadenza'] = deadline_date
        
        # Set category
        bando_info['categoria'] = category
        
        # Set source
        bando_info['fonte'] = 'invitalia.it'
        
        return bando_info
    
    except Exception as e:
        logger.error(f'Error parsing bando container: {str(e)}')
        return None


def _extract_deadline(text):
    """
    Extract deadline date from text using common patterns.
    Returns datetime object or None.
    """
    import re
    from dateutil import parser as date_parser
    
    try:
        # Common Italian date patterns
        patterns = [
            r'scadenza[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            r'deadline[:\s]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})',
            r'entro il[\s]+([0-9]{1,2}[\s]+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)[\s]+[0-9]{4})',
            r'([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    parsed_date = date_parser.parse(date_str, dayfirst=True)
                    return parsed_date
                except:
                    continue
        
        return None
    
    except Exception as e:
        logger.error(f'Error extracting deadline: {str(e)}')
        return None


def _save_bandi_to_db(bandi_list):
    """
    Save scraped bandi to database, avoiding duplicates.
    Returns count of successfully saved records.
    """
    saved_count = 0
    
    try:
        for bando_data in bandi_list:
            try:
                # Check if bando already exists by title and fonte
                existing = Bando.query.filter_by(
                    titolo=bando_data.get('titolo'),
                    fonte=bando_data.get('fonte')
                ).first()
                
                if existing:
                    logger.info(f'Bando already exists: {bando_data.get("titolo")}')
                    continue
                
                # Create new bando
                new_bando = Bando(
                    titolo=bando_data.get('titolo'),
                    descrizione=bando_data.get('descrizione', ''),
                    url=bando_data.get('url'),
                    categoria=bando_data.get('categoria', 'General'),
                    fonte=bando_data.get('fonte', 'invitalia.it'),
                    scadenza=bando_data.get('scadenza'),
                    data_creazione=datetime.utcnow()
                )
                
                db.session.add(new_bando)
                db.session.commit()
                saved_count += 1
                logger.info(f'Saved bando: {new_bando.titolo}')
            
            except IntegrityError as e:
                db.session.rollback()
                logger.warning(f'Integrity error saving bando: {str(e)}')
            
            except Exception as e:
                db.session.rollback()
                logger.error(f'Error saving bando: {str(e)}')
        
        return saved_count
    
    except Exception as e:
        logger.error(f'Error in batch save operation: {str(e)}')
        return saved_count

import os
import logging
from typing import List, Dict, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv('RESEND_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@bandonmatch.ai')
RESEND_API_URL = 'https://api.resend.com/emails'


def _invia_email(to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
    """
    Invia un'email tramite Resend API.
    
    Args:
        to_email: Email destinatario
        subject: Oggetto dell'email
        html_content: Contenuto HTML dell'email
        
    Returns:
        Dict con risultato dell'invio
    """
    if not RESEND_API_KEY:
        logger.error('RESEND_API_KEY non configurata')
        return {'success': False, 'error': 'RESEND_API_KEY non configurata'}
    
    headers = {
        'Authorization': f'Bearer {RESEND_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'from': FROM_EMAIL,
        'to': to_email,
        'subject': subject,
        'html': html_content
    }
    
    try:
        response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f'Email inviata a {to_email}: {subject}')
        return {'success': True, 'data': response.json()}
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Errore invio email a {to_email}: {str(e)}')
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f'Errore generico invio email: {str(e)}')
        return {'success': False, 'error': str(e)}


def invia_benvenuto(utente: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invia email di benvenuto all'utente.
    
    Args:
        utente: Dict con dati utente (nome, email, cognome opzionale)
        
    Returns:
        Dict con risultato dell'invio
    """
    email = utente.get('email')
    nome = utente.get('nome', 'Utente')
    
    if not email:
        logger.warning('Email utente non fornita per benvenuto')
        return {'success': False, 'error': 'Email mancante'}
    
    subject = f'Benvenuto in BandoMatch.ai, {nome}!'
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background-color: #f3f4f6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #111827;
                color: #f3f4f6;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .content {{
                padding: 40px;
            }}
            .content p {{
                line-height: 1.6;
                margin: 16px 0;
                font-size: 16px;
            }}
            .button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 32px;
                border-radius: 6px;
                text-decoration: none;
                margin-top: 24px;
                font-weight: 600;
            }}
            .footer {{
                background-color: #1f2937;
                padding: 20px;
                text-align: center;
                font-size: 14px;
                color: #9ca3af;
            }}
            .feature-list {{
                list-style: none;
                padding: 0;
                margin: 24px 0;
            }}
            .feature-list li {{
                padding: 8px 0;
                padding-left: 24px;
                position: relative;
            }}
            .feature-list li:before {{
                content: "✓";
                position: absolute;
                left: 0;
                color: #667eea;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>BandoMatch.ai</h1>
            </div>
            <div class="content">
                <p>Ciao <strong>{nome}</strong>,</p>
                <p>Benvenuto in <strong>BandoMatch.ai</strong>! Siamo entusiasti di averti a bordo.</p>
                
                <p>Con BandoMatch.ai potrai:</p>
                <ul class="feature-list">
                    <li>Trovare bandi e finanziamenti perfetti per il tuo profilo</li>
                    <li>Ricevere notifiche personalizzate su nuove opportunità</li>
                    <li>Gestire le tue candidature in un'unica piattaforma</li>
                    <li>Aumentare le probabilità di successo dei tuoi progetti</li>
                </ul>
                
                <p>Ora che il tuo account è attivo, puoi iniziare a esplorare i bandi disponibili e trovare le migliori opportunità per te.</p>
                
                <a href="{os.getenv('APP_URL', 'https://bandonmatch.ai')}/dashboard" class="button">Accedi al Dashboard</a>
                
                <p style="margin-top: 40px; font-size: 14px; color: #9ca3af;">Se hai domande, contatta il nostro team di supporto.</p>
            </div>
            <div class="footer">
                <p>&copy; {datetime.now().year} BandoMatch.ai. Tutti i diritti riservati.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return _invia_email(email, subject, html_content)


def invia_notifica_match(utente: Dict[str, Any], bandi: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Invia email di notifica match con lista bandi compatibili.
    
    Args:
        utente: Dict con dati utente (nome, email, profilo)
        bandi: Lista di dict con dati bandi (titolo, descrizione, scadenza, url, compatibilita_score)
        
    Returns:
        Dict con risultato dell'invio
    """
    email = utente.get('email')
    nome = utente.get('nome', 'Utente')
    
    if not email:
        logger.warning('Email utente non fornita per notifica match')
        return {'success': False, 'error': 'Email mancante'}
    
    if not bandi:
        logger.warning(f'Nessun bando disponibile per {email}')
        return {'success': False, 'error': 'Nessun bando disponibile'}
    
    num_bandi = len(bandi)
    subject = f'📢 {num_bandi} nuov{"o" if num_bandi == 1 else "i"} bando{"" if num_bandi == 1 else "i"} perfetto{"" if num_bandi == 1 else "i"} per te!'
    
    # Genera HTML per il contenuto dei bandi
    bandi_html = ''
    for idx, bando in enumerate(bandi, 1):
        score = bando.get('compatibilita_score', 0)
        score_bar = '█' * int(score / 10) + '░' * (10 - int(score / 10))
        
        bandi_html += f"""
        <div style="background-color: #1f2937; border-left: 4px solid #667eea; padding: 20px; margin-bottom: 16px; border-radius: 4px;">
            <h3 style="margin: 0 0 8px 0; color: #fff; font-size: 18px;">{idx}. {bando.get('titolo', 'Bando senza titolo')}</h3>
            <p style="margin: 8px 0; color: #d1d5db; font-size: 14px;">{bando.get('descrizione', '')[:200]}...</p>
            
            <div style="margin: 12px 0;">
                <p style="margin: 4px 0; color: #9ca3af; font-size: 13px;">Compatibilità: {score}%</p>
                <div style="background-color: #374151; height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); height: 100%; width: {score}%; border-radius: 3px;"></div>
                </div>
            </div>
            
            <p style="margin: 12px 0 0 0; color: #9ca3af; font-size: 13px;">📅 Scadenza: <strong>{bando.get('scadenza', 'Data non disponibile')}</strong></p>
            
            <a href="{bando.get('url', '#')}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; margin-top: 12px; font-weight: 600; font-size: 14px;">Visualizza Bando</a>
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background-color: #f3f4f6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 700px;
                margin: 40px auto;
                background-color: #111827;
                color: #f3f4f6;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
            }}
            .content {{
                padding: 40px;
            }}
            .content p {{
                line-height: 1.6;
                margin: 16px 0;
                font-size: 16px;
            }}
            .bandi-container {{
                margin: 32px 0;
            }}
            .footer {{
                background-color: #1f2937;
                padding: 20px;
                text-align: center;
                font-size: 14px;
                color: #9ca3af;
            }}
            .cta-button {{
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 32px;
                border-radius: 6px;
                text-decoration: none;
                margin-top: 24px;
                font-weight: 600;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 Nuovi Bandi per Te!</h1>
            </div>
            <div class="content">
                <p>Ciao <strong>{nome}</strong>,</p>
                <p>Abbiamo trovato <strong>{num_bandi} nuov{"o" if num_bandi == 1 else "i"} bando{"" if num_bandi == 1 else "i"}</strong> che combaciano perfettamente con il tuo profilo e i tuoi interessi!</p>
                
                <div class="bandi-container">
                    {bandi_html}
                </div>
                
                <p>Non perdere queste opportunità! Accedi al tuo dashboard per visualizzare tutti i dettagli e candidarti.</p>
                
                <a href="{os.getenv('APP_URL', 'https://bandonmatch.ai')}/bandi" class="cta-button">Visualizza Tutti i Bandi</a>
                
                <p style="margin-top: 40px; font-size: 14px; color: #9ca3af;">Riceverai aggiornamenti regolari sui bandi più adatti a te. Puoi personalizzare le tue preferenze nelle impostazioni del profilo.</p>
            </div>
            <div class="footer">
                <p>&copy; {datetime.now().year} BandoMatch.ai. Tutti i diritti riservati.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return _invia_email(email, subject, html_content)

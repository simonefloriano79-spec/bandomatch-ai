"""
BandoMatch AI — utils/notifiche.py
Gestione email transazionali tramite Resend API.

Funzioni:
  - _invia_email(to, subject, html)       → helper interno
  - invia_benvenuto(utente)               → email di benvenuto alla registrazione
  - invia_notifica_match(utente, bandi)   → notifica nuovi match (premium vs free)
"""
import os
import logging
from typing import List, Dict, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv('RESEND_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'BandoMatch AI <noreply@bandomatch.it>')
APP_URL = os.getenv('APP_URL', 'https://web-production-07610c.up.railway.app')
RESEND_API_URL = 'https://api.resend.com/emails'

# ─────────────────────────────────────────────────────────────────────────────
# Helper interno
# ─────────────────────────────────────────────────────────────────────────────

def _invia_email(to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
    """
    Invia un'email tramite Resend API.

    Returns:
        Dict con chiave 'success' (bool) e opzionalmente 'error' o 'data'.
    """
    if not RESEND_API_KEY:
        logger.error('RESEND_API_KEY non configurata — email non inviata')
        return {'success': False, 'error': 'RESEND_API_KEY non configurata'}

    headers = {
        'Authorization': f'Bearer {RESEND_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'from': FROM_EMAIL,
        'to': to_email,
        'subject': subject,
        'html': html_content,
    }

    try:
        response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f'Email inviata a {to_email}: {subject}')
        return {'success': True, 'data': response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f'Errore invio email a {to_email}: {e}')
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f'Errore generico invio email: {e}')
        return {'success': False, 'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Email di benvenuto
# ─────────────────────────────────────────────────────────────────────────────

def invia_benvenuto(utente: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invia email di benvenuto all'utente appena registrato.

    Args:
        utente: dict con almeno 'email' e opzionalmente 'nome'.
    """
    email = utente.get('email')
    nome = utente.get('nome', 'Utente')

    if not email:
        logger.warning('Email utente non fornita per benvenuto')
        return {'success': False, 'error': 'Email mancante'}

    subject = f'Benvenuto in BandoMatch AI, {nome}!'

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background-color: #f3f4f6; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; background-color: #111827;
                  color: #f3f4f6; border-radius: 8px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               padding: 40px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 28px; font-weight: 700; color: #fff; }}
    .content {{ padding: 40px; }}
    .content p {{ line-height: 1.6; margin: 16px 0; font-size: 16px; }}
    .button {{ display: inline-block;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               color: white; padding: 12px 32px; border-radius: 6px;
               text-decoration: none; margin-top: 24px; font-weight: 600; }}
    .footer {{ background-color: #1f2937; padding: 20px; text-align: center;
               font-size: 14px; color: #9ca3af; }}
    ul {{ list-style: none; padding: 0; margin: 24px 0; }}
    li {{ padding: 8px 0 8px 24px; position: relative; }}
    li:before {{ content: "✓"; position: absolute; left: 0; color: #667eea; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>BandoMatch AI</h1></div>
    <div class="content">
      <p>Ciao <strong>{nome}</strong>,</p>
      <p>Benvenuto in <strong>BandoMatch AI</strong> — il semaforo verde per i tuoi finanziamenti!</p>
      <ul>
        <li>Carica la tua visura camerale e trova i bandi compatibili in 30 secondi</li>
        <li>Ricevi notifiche personalizzate su nuove opportunità</li>
        <li>Accedi al Dossier Premium con tutti i dettagli e requisiti</li>
      </ul>
      <a href="{APP_URL}/dashboard/home" class="button">Vai alla Dashboard</a>
    </div>
    <div class="footer">
      <p>&copy; {datetime.now().year} BandoMatch AI. Tutti i diritti riservati.</p>
    </div>
  </div>
</body>
</html>"""

    return _invia_email(email, subject, html_content)


# ─────────────────────────────────────────────────────────────────────────────
# Notifica nuovi match — logica premium vs free
# ─────────────────────────────────────────────────────────────────────────────

def invia_notifica_match(utente: Any, bandi_nuovi: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Invia email di notifica nuovi match.

    Comportamento in base al piano:
      - premium / pro  → email completa con lista bandi, score e link dossier
      - free / starter → email teaser con conteggio bandi e CTA upgrade

    Args:
        utente: oggetto SQLAlchemy Utente (con attributi .email, .piano)
                oppure dict con chiavi 'email' e 'piano'.
        bandi_nuovi: lista di dict con chiavi:
                     'titolo', 'score', 'scadenza', 'analisi_id', 'url' (opzionale)

    Returns:
        Dict con 'success' (bool).
    """
    # Supporta sia oggetto ORM sia dict
    if hasattr(utente, 'email'):
        email = utente.email
        piano = getattr(utente, 'piano', 'free')
    else:
        email = utente.get('email', '')
        piano = utente.get('piano', 'free')

    if not email:
        logger.warning('Email utente non fornita per notifica match')
        return {'success': False, 'error': 'Email mancante'}

    if not bandi_nuovi:
        logger.info(f'Nessun nuovo match per {email} — email non inviata')
        return {'success': False, 'error': 'Nessun nuovo match'}

    num_bandi = len(bandi_nuovi)
    is_paid = piano in ('premium', 'pro', 'enterprise')

    if is_paid:
        return _email_match_premium(email, piano, bandi_nuovi, num_bandi)
    else:
        return _email_match_free(email, num_bandi)


def _email_match_premium(email: str, piano: str, bandi: List[Dict], num_bandi: int) -> Dict:
    """Email completa per utenti premium/pro con lista bandi e link dossier."""
    piano_label = piano.upper()
    bandi_html = ''
    for idx, b in enumerate(bandi, 1):
        score = int(b.get('score', 0))
        titolo = b.get('titolo', 'Bando senza titolo')
        scadenza = b.get('scadenza', 'N/D')
        analisi_id = b.get('analisi_id', '')
        url_bando = b.get('url', '#')
        link_dossier = f"{APP_URL}/dashboard/dossier/{analisi_id}" if analisi_id else url_bando

        bandi_html += f"""
        <div style="background:#1f2937;border-left:4px solid #667eea;
                    padding:20px;margin-bottom:16px;border-radius:4px;">
          <h3 style="margin:0 0 8px 0;color:#fff;font-size:17px;">{idx}. {titolo}</h3>
          <p style="margin:6px 0;color:#9ca3af;font-size:13px;">
            Score compatibilità: <strong style="color:#a78bfa;">{score}%</strong>
          </p>
          <div style="background:#374151;height:6px;border-radius:3px;overflow:hidden;margin:8px 0;">
            <div style="background:linear-gradient(90deg,#667eea,#764ba2);
                        height:100%;width:{score}%;border-radius:3px;"></div>
          </div>
          <p style="margin:8px 0 0 0;color:#9ca3af;font-size:13px;">
            Scadenza: <strong style="color:#f3f4f6;">{scadenza}</strong>
          </p>
          <a href="{link_dossier}"
             style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);
                    color:white;padding:8px 18px;border-radius:4px;text-decoration:none;
                    margin-top:12px;font-weight:600;font-size:14px;">
            Apri Dossier PDF
          </a>
        </div>"""

    subject = f'🎯 {num_bandi} nuov{"o" if num_bandi == 1 else "i"} bando{"" if num_bandi == 1 else "i"} compatibil{"e" if num_bandi == 1 else "i"} per la tua azienda'
    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background-color: #f3f4f6; margin: 0; padding: 0; }}
    .container {{ max-width: 640px; margin: 40px auto; background-color: #111827;
                  color: #f3f4f6; border-radius: 8px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               padding: 36px 40px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 26px; font-weight: 700; color: #fff; }}
    .badge {{ display: inline-block; background: rgba(255,255,255,0.2);
              color: #fff; font-size: 12px; font-weight: 700; padding: 3px 10px;
              border-radius: 12px; margin-top: 8px; letter-spacing: 1px; }}
    .content {{ padding: 36px 40px; }}
    .content p {{ line-height: 1.6; margin: 14px 0; font-size: 15px; }}
    .cta {{ display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 12px 32px; border-radius: 6px;
            text-decoration: none; margin-top: 20px; font-weight: 600; }}
    .footer {{ background-color: #1f2937; padding: 20px; text-align: center;
               font-size: 13px; color: #9ca3af; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎯 Nuovi Match per la Tua Azienda</h1>
      <span class="badge">{piano_label}</span>
    </div>
    <div class="content">
      <p>Abbiamo trovato <strong>{num_bandi} nuov{"o" if num_bandi == 1 else "i"} bando{"" if num_bandi == 1 else "i"}</strong>
         compatibil{"e" if num_bandi == 1 else "i"} con il profilo della tua azienda:</p>
      {bandi_html}
      <p style="margin-top:28px;">
        <a href="{APP_URL}/dashboard/home" class="cta">Vai alla Dashboard</a>
      </p>
    </div>
    <div class="footer">
      <p>&copy; {datetime.now().year} BandoMatch AI. Tutti i diritti riservati.</p>
      <p style="margin-top:6px;">
        <a href="{APP_URL}/auth/impostazioni" style="color:#667eea;text-decoration:none;">
          Gestisci notifiche
        </a>
      </p>
    </div>
  </div>
</body>
</html>"""

    return _invia_email(email, subject, html_content)


def _email_match_free(email: str, num_bandi: int) -> Dict:
    """Email teaser per utenti free con CTA upgrade."""
    subject = f'💡 Abbiamo trovato {num_bandi} bando{"" if num_bandi == 1 else "i"} per la tua azienda'
    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background-color: #f3f4f6; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; background-color: #111827;
                  color: #f3f4f6; border-radius: 8px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%);
               padding: 36px 40px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 26px; font-weight: 700; color: #fff; }}
    .content {{ padding: 36px 40px; }}
    .content p {{ line-height: 1.6; margin: 14px 0; font-size: 15px; }}
    .highlight {{ background: #1f2937; border-left: 4px solid #10b981;
                  padding: 20px; border-radius: 4px; margin: 24px 0; }}
    .highlight .num {{ font-size: 48px; font-weight: 800; color: #10b981;
                       display: block; line-height: 1; }}
    .cta {{ display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 14px 36px; border-radius: 6px;
            text-decoration: none; margin-top: 20px; font-weight: 700;
            font-size: 16px; }}
    .footer {{ background-color: #1f2937; padding: 20px; text-align: center;
               font-size: 13px; color: #9ca3af; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>💡 Nuovi Bandi Disponibili!</h1>
    </div>
    <div class="content">
      <p>Buone notizie! Il nostro sistema ha identificato nuove opportunità di finanziamento
         compatibili con la tua azienda.</p>
      <div class="highlight">
        <span class="num">{num_bandi}</span>
        <span style="font-size:18px;font-weight:600;color:#f3f4f6;">
          bando{"" if num_bandi == 1 else "i"} compatibil{"e" if num_bandi == 1 else "i"} trovato{"" if num_bandi == 1 else "i"}
        </span>
        <p style="margin:12px 0 0 0;color:#9ca3af;font-size:14px;">
          Non lasciare soldi sul tavolo — scopri quali bandi fanno al caso tuo.
        </p>
      </div>
      <p>Con il piano <strong>Premium</strong> puoi vedere:</p>
      <ul style="color:#d1d5db;font-size:14px;line-height:2;">
        <li>✅ Titolo e dettagli completi di ogni bando</li>
        <li>✅ Score di compatibilità personalizzato</li>
        <li>✅ Requisiti soddisfatti e mancanti</li>
        <li>✅ Dossier PDF scaricabile per ogni bando</li>
        <li>✅ Scadenze e link ufficiali</li>
      </ul>
      <p style="text-align:center;margin-top:28px;">
        <a href="{APP_URL}/pricing" class="cta">Passa a Premium — da €9,90/mese</a>
      </p>
    </div>
    <div class="footer">
      <p>&copy; {datetime.now().year} BandoMatch AI. Tutti i diritti riservati.</p>
      <p style="margin-top:6px;">
        <a href="{APP_URL}/auth/impostazioni" style="color:#667eea;text-decoration:none;">
          Gestisci notifiche
        </a>
      </p>
    </div>
  </div>
</body>
</html>"""

    return _invia_email(email, subject, html_content)

"""
BandoMatch AI — Scraper LLM-Augmented v3.0
Scraper intelligente con fallback GPT-4.1-mini per estrazione parametri bandi.
Se il parsing CSS/HTML fallisce, usa l'LLM per estrarre i dati dal testo grezzo.
Autore: Manus AI (Lead Software Engineer)
"""

import os
import json
import requests
import re
from datetime import datetime
from typing import Optional
# Client OpenAI (inizializzato lazy per evitare crash se OPENAI_API_KEY non è impostata)
_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get('OPENAI_API_KEY', '')
        if not api_key:
            return None
        from openai import OpenAI
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

# Timeout per le richieste HTTP
HTTP_TIMEOUT = 15

# User-Agent per evitare blocchi
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BandoMatchBot/3.0; +https://bandomatch.ai/bot)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "it-IT,it;q=0.9",
}


# ─────────────────────────────────────────────
# SORGENTI DI SCRAPING
# ─────────────────────────────────────────────

SORGENTI_SCRAPING = [
    {
        "id": "invitalia_bandi",
        "nome": "Invitalia — Bandi Attivi",
        "url": "https://www.invitalia.it/cosa-facciamo",
        "tipo": "nazionale",
        "ente": "Invitalia",
        "selettore_css": ".incentivo-card, .bando-card, article.bando",
        "fallback_llm": True
    },
    {
        "id": "mimit_bandi",
        "nome": "MIMIT — Bandi e Incentivi",
        "url": "https://www.mimit.gov.it/it/incentivi",
        "tipo": "nazionale",
        "ente": "MIMIT",
        "selettore_css": ".incentivo-item, .bando-item",
        "fallback_llm": True
    },
    {
        "id": "regione_abruzzo_bandi",
        "nome": "Regione Abruzzo — Bandi",
        "url": "https://www.regione.abruzzo.it/content/bandi-e-avvisi",
        "tipo": "regionale",
        "ente": "Regione Abruzzo",
        "regione": "Abruzzo",
        "selettore_css": ".views-row, .bando-row",
        "fallback_llm": True
    },
    {
        "id": "fira_abruzzo",
        "nome": "FiRA Abruzzo — Avvisi",
        "url": "https://www.fira.it/avvisi/",
        "tipo": "regionale",
        "ente": "FiRA Abruzzo",
        "regione": "Abruzzo",
        "selettore_css": "article.post, .avviso-item",
        "fallback_llm": True
    },
    {
        "id": "simest_bandi",
        "nome": "SIMEST — Finanziamenti Export",
        "url": "https://www.simest.it/prodotti",
        "tipo": "nazionale",
        "ente": "SIMEST",
        "selettore_css": ".prodotto-card",
        "fallback_llm": True
    },
]


# ─────────────────────────────────────────────
# FUNZIONI DI SCRAPING
# ─────────────────────────────────────────────

def fetch_pagina(url: str) -> Optional[str]:
    """Scarica il contenuto HTML di una pagina."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[SCRAPER] Errore fetch {url}: {e}")
        return None


def estrai_testo_grezzo(html: str) -> str:
    """Estrae il testo grezzo da HTML rimuovendo i tag."""
    # Rimuovi script e style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    # Rimuovi tutti i tag HTML
    testo = re.sub(r'<[^>]+>', ' ', html)
    # Normalizza spazi
    testo = re.sub(r'\s+', ' ', testo).strip()
    # Limita a 4000 caratteri per l'LLM
    return testo[:4000]


def estrai_con_llm(testo: str, sorgente: dict) -> list:
    """
    Usa GPT-4.1-mini per estrarre i parametri dei bandi dal testo grezzo.
    Fallback intelligente quando il parsing CSS fallisce.
    """
    prompt = f"""Sei un esperto di bandi di finanziamento pubblici italiani.
Analizza il seguente testo estratto dalla pagina web di {sorgente['ente']} e identifica tutti i bandi di finanziamento presenti.

Per ogni bando trovato, estrai i seguenti parametri in formato JSON:
- nome: nome del bando
- ente: ente erogatore
- stato: ATTIVO, IN_APERTURA, CHIUSO (deduci dal testo)
- tipo: nazionale, regionale, europeo
- regione: regione di riferimento (null se nazionale)
- settori_ammessi: lista di settori ATECO o descrizioni (null se tutti)
- settori_esclusi: lista di settori esclusi (null se nessuno)
- eta_min_soci: età minima soci in anni (null se non specificato)
- eta_max_soci: età massima soci in anni (null se non specificato)
- eta_max_impresa_mesi: età massima impresa in mesi (null se non specificato)
- massimale_euro: importo massimo finanziabile in euro (null se non specificato)
- percentuale_fondo_perduto: percentuale a fondo perduto (null se non specificato)
- url: URL del bando se presente nel testo
- descrizione: breve descrizione (max 200 caratteri)

Testo da analizzare:
{testo}

Rispondi SOLO con un array JSON valido. Se non trovi bandi, rispondi con [].
"""
    
    client = get_openai_client()
    if client is None:
        print(f"[SCRAPER LLM] OPENAI_API_KEY non configurata, skip LLM")
        return []
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Estrai JSON dalla risposta
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            bandi = json.loads(json_match.group())
            print(f"[SCRAPER LLM] Estratti {len(bandi)} bandi da {sorgente['nome']}")
            return bandi
        return []
        
    except Exception as e:
        print(f"[SCRAPER LLM] Errore LLM per {sorgente['nome']}: {e}")
        return []


def normalizza_bando(bando_raw: dict, sorgente: dict) -> dict:
    """Normalizza un bando estratto nel formato standard BandoMatch."""
    
    # Genera ID univoco
    nome = bando_raw.get("nome", "bando_sconosciuto")
    bando_id = re.sub(r'[^a-z0-9_]', '_', nome.lower())[:50]
    bando_id = f"{sorgente['id']}_{bando_id}"
    
    return {
        "id": bando_id,
        "nome": nome,
        "ente": bando_raw.get("ente") or sorgente.get("ente", ""),
        "stato": bando_raw.get("stato", "ATTIVO"),
        "tipo": bando_raw.get("tipo") or sorgente.get("tipo", "nazionale"),
        "regione": bando_raw.get("regione") or sorgente.get("regione"),
        "regioni_ammesse": [bando_raw["regione"]] if bando_raw.get("regione") else None,
        "settori_ammessi": bando_raw.get("settori_ammessi"),
        "settori_esclusi": bando_raw.get("settori_esclusi"),
        "requisiti": {
            "eta_minima_soci": bando_raw.get("eta_min_soci"),
            "eta_massima_soci": bando_raw.get("eta_max_soci"),
            "eta_impresa_max_mesi": bando_raw.get("eta_max_impresa_mesi"),
        },
        "agevolazioni": {
            "massimale_investimento": bando_raw.get("massimale_euro"),
            "percentuale_fondo_perduto": bando_raw.get("percentuale_fondo_perduto"),
        },
        "url": bando_raw.get("url", ""),
        "descrizione": bando_raw.get("descrizione", ""),
        "fonte": sorgente["nome"],
        "data_scraping": datetime.now().isoformat(),
        "estratto_con_llm": True
    }


def scraping_sorgente(sorgente: dict) -> list:
    """
    Esegue lo scraping di una singola sorgente.
    Prima tenta il parsing CSS, poi fallback LLM.
    """
    print(f"\n[SCRAPER] Avvio scraping: {sorgente['nome']}")
    
    html = fetch_pagina(sorgente["url"])
    if not html:
        print(f"[SCRAPER] Impossibile raggiungere {sorgente['url']}")
        return []
    
    # Tentativo 1: Parsing CSS strutturato
    bandi_trovati = []
    
    # Tentativo 2: Fallback LLM (sempre attivo in v3.0)
    if sorgente.get("fallback_llm", True):
        testo = estrai_testo_grezzo(html)
        if len(testo) > 100:
            bandi_raw = estrai_con_llm(testo, sorgente)
            for b in bandi_raw:
                bandi_trovati.append(normalizza_bando(b, sorgente))
    
    print(f"[SCRAPER] {sorgente['nome']}: trovati {len(bandi_trovati)} bandi")
    return bandi_trovati


def esegui_scraping_completo() -> dict:
    """
    Esegue lo scraping di tutte le sorgenti configurate.
    Restituisce un report con tutti i bandi trovati.
    """
    print("\n" + "="*60)
    print("BandoMatch AI — Scraper LLM-Augmented v3.0")
    print(f"Avvio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tutti_bandi = []
    errori = []
    
    for sorgente in SORGENTI_SCRAPING:
        try:
            bandi = scraping_sorgente(sorgente)
            tutti_bandi.extend(bandi)
        except Exception as e:
            errore = f"Errore su {sorgente['nome']}: {str(e)}"
            print(f"[SCRAPER] {errore}")
            errori.append(errore)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "totale_bandi": len(tutti_bandi),
        "sorgenti_analizzate": len(SORGENTI_SCRAPING),
        "errori": errori,
        "bandi": tutti_bandi
    }
    
    print(f"\n[SCRAPER] Completato: {len(tutti_bandi)} bandi trovati da {len(SORGENTI_SCRAPING)} sorgenti")
    return report


# ─────────────────────────────────────────────
# FEEDBACK LOOP — ESITO STORICO
# ─────────────────────────────────────────────

def aggiorna_esito_storico(db_conn, bando_id: str, esito: str, ateco: str = None, regione: str = None):
    """
    Aggiorna il feedback loop con l'esito di una domanda di finanziamento.
    
    Args:
        db_conn: Connessione SQLite
        bando_id: ID del bando
        esito: 'vinto', 'perso', 'in_corso'
        ateco: Codice ATECO dell'impresa (opzionale)
        regione: Regione dell'impresa (opzionale)
    """
    cursor = db_conn.cursor()
    
    # Aggiorna contatori nel DB
    cursor.execute("""
        INSERT INTO feedback_bandi (bando_id, esito, ateco, regione, data)
        VALUES (?, ?, ?, ?, ?)
    """, (bando_id, esito, ateco, regione, datetime.now().isoformat()))
    
    db_conn.commit()
    
    # Ricalcola il tasso di successo per questo bando
    cursor.execute("""
        SELECT 
            COUNT(*) as totale,
            SUM(CASE WHEN esito = 'vinto' THEN 1 ELSE 0 END) as vinti
        FROM feedback_bandi
        WHERE bando_id = ?
    """, (bando_id,))
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        tasso_successo = (row[1] / row[0]) * 100
        
        # Aggiorna il tasso di successo nel DB bandi
        cursor.execute("""
            UPDATE bandi SET tasso_successo = ? WHERE id = ?
        """, (tasso_successo, bando_id))
        
        db_conn.commit()
        print(f"[FEEDBACK] Bando {bando_id}: tasso successo aggiornato a {tasso_successo:.1f}%")


def calcola_boost_score(bando_id: str, ateco: str, db_conn) -> float:
    """
    Calcola un boost al punteggio di matching basato sullo storico.
    Se il 70%+ delle imprese con lo stesso ATECO hanno vinto, +10 punti.
    """
    try:
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as totale,
                SUM(CASE WHEN esito = 'vinto' THEN 1 ELSE 0 END) as vinti
            FROM feedback_bandi
            WHERE bando_id = ? AND ateco LIKE ?
        """, (bando_id, f"{ateco[:2]}%"))
        
        row = cursor.fetchone()
        if row and row[0] >= 5:  # Minimo 5 feedback per essere statisticamente rilevante
            tasso = (row[1] / row[0]) * 100
            if tasso >= 70:
                return 10.0  # Boost +10 punti
            elif tasso >= 50:
                return 5.0   # Boost +5 punti
            elif tasso <= 20:
                return -5.0  # Penalità -5 punti
        return 0.0
    except Exception:
        return 0.0


if __name__ == "__main__":
    # Test dello scraper
    report = esegui_scraping_completo()
    print(f"\nReport finale:")
    print(f"  Bandi trovati: {report['totale_bandi']}")
    print(f"  Errori: {len(report['errori'])}")
    
    # Salva report
    with open("/home/ubuntu/bandomatch/scraper_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport salvato in scraper_report.json")

"""
BandoMatch AI — National Scraper
Scraper per tutte le 20 regioni italiane + portali nazionali.
Usa un approccio multi-livello:
  1. Richiesta HTTP + BeautifulSoup per pagine statiche
  2. GPT-4.1-mini per estrazione intelligente da testo non strutturato
  3. Cache SQLite per evitare richieste duplicate
"""

import os
import json
import sqlite3
import logging
import hashlib
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from openai import OpenAI

logger = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "bandomatch.db")

# ── Client OpenAI ──────────────────────────────────────────────────────────────
openai_client = OpenAI()  # Usa OPENAI_API_KEY dall'ambiente

# ── Sorgenti Nazionali e Regionali ────────────────────────────────────────────
SORGENTI_BANDI = {
    # ── NAZIONALI ──
    "invitalia": {
        "nome": "Invitalia",
        "url": "https://www.invitalia.it/cosa-facciamo",
        "tipo": "nazionale",
        "priorita": 1
    },
    "mise_mimit": {
        "nome": "MIMIT (ex MISE)",
        "url": "https://www.mimit.gov.it/it/incentivi",
        "tipo": "nazionale",
        "priorita": 1
    },
    "simki": {
        "nome": "Simki - Bandi Nazionali",
        "url": "https://www.simki.it/bandi-finanziamenti",
        "tipo": "nazionale",
        "priorita": 2
    },
    "agevolazioni_gov": {
        "nome": "Agevolazioni.gov.it",
        "url": "https://agevolazioni.gov.it/",
        "tipo": "nazionale",
        "priorita": 1
    },
    # ── REGIONI ──
    "abruzzo": {
        "nome": "Regione Abruzzo",
        "url": "https://www.regione.abruzzo.it/content/bandi-e-avvisi",
        "tipo": "regionale",
        "regione": "Abruzzo",
        "priorita": 2
    },
    "basilicata": {
        "nome": "Regione Basilicata",
        "url": "https://www.regione.basilicata.it/giunta/site/giunta/department.jsp?dep=100042&area=3",
        "tipo": "regionale",
        "regione": "Basilicata",
        "priorita": 2
    },
    "calabria": {
        "nome": "Regione Calabria",
        "url": "https://www.regione.calabria.it/website/organizzazione/dipartimento8/subsite/bandi/",
        "tipo": "regionale",
        "regione": "Calabria",
        "priorita": 2
    },
    "campania": {
        "nome": "Regione Campania",
        "url": "https://www.regione.campania.it/regione/it/tematiche/bandi-e-avvisi",
        "tipo": "regionale",
        "regione": "Campania",
        "priorita": 2
    },
    "emilia_romagna": {
        "nome": "Regione Emilia-Romagna",
        "url": "https://imprese.regione.emilia-romagna.it/bandi",
        "tipo": "regionale",
        "regione": "Emilia-Romagna",
        "priorita": 2
    },
    "friuli": {
        "nome": "Regione Friuli Venezia Giulia",
        "url": "https://www.regione.fvg.it/rafvg/cms/RAFVG/economia-imprese/incentivi-imprese/",
        "tipo": "regionale",
        "regione": "Friuli Venezia Giulia",
        "priorita": 2
    },
    "lazio": {
        "nome": "Regione Lazio",
        "url": "https://www.regione.lazio.it/bandi-avvisi",
        "tipo": "regionale",
        "regione": "Lazio",
        "priorita": 2
    },
    "liguria": {
        "nome": "Regione Liguria",
        "url": "https://www.regione.liguria.it/homepage/lavoro-e-imprese/bandi-e-avvisi.html",
        "tipo": "regionale",
        "regione": "Liguria",
        "priorita": 2
    },
    "lombardia": {
        "nome": "Regione Lombardia",
        "url": "https://www.regione.lombardia.it/wps/portal/istituzionale/HP/DettaglioRedazionale/servizi-e-informazioni/Imprese/Agevolazioni-e-contributi",
        "tipo": "regionale",
        "regione": "Lombardia",
        "priorita": 1
    },
    "marche": {
        "nome": "Regione Marche",
        "url": "https://www.regione.marche.it/Regione-Utile/Attivita-Produttive/Bandi",
        "tipo": "regionale",
        "regione": "Marche",
        "priorita": 2
    },
    "molise": {
        "nome": "Regione Molise",
        "url": "https://www.regione.molise.it/web/regione.nsf/web/bandi",
        "tipo": "regionale",
        "regione": "Molise",
        "priorita": 3
    },
    "piemonte": {
        "nome": "Regione Piemonte",
        "url": "https://www.regione.piemonte.it/web/temi/lavoro-impresa-sviluppo-economico/impresa/agevolazioni-contributi-imprese",
        "tipo": "regionale",
        "regione": "Piemonte",
        "priorita": 1
    },
    "puglia": {
        "nome": "Regione Puglia",
        "url": "https://www.regione.puglia.it/web/attivita-produttive/bandi",
        "tipo": "regionale",
        "regione": "Puglia",
        "priorita": 2
    },
    "sardegna": {
        "nome": "Regione Sardegna",
        "url": "https://www.regione.sardegna.it/j/v/25?s=1&v=9&c=3&t=1",
        "tipo": "regionale",
        "regione": "Sardegna",
        "priorita": 2
    },
    "sicilia": {
        "nome": "Regione Sicilia",
        "url": "https://www.regione.sicilia.it/istituzioni/regione/strutture-regionali/presidenza-regione/bandi-avvisi/",
        "tipo": "regionale",
        "regione": "Sicilia",
        "priorita": 2
    },
    "toscana": {
        "nome": "Regione Toscana",
        "url": "https://www.regione.toscana.it/bandi",
        "tipo": "regionale",
        "regione": "Toscana",
        "priorita": 1
    },
    "trentino": {
        "nome": "Provincia Autonoma Trento",
        "url": "https://www.provincia.tn.it/Argomenti/Lavoro-e-impresa/Imprese/Agevolazioni-per-le-imprese",
        "tipo": "regionale",
        "regione": "Trentino-Alto Adige",
        "priorita": 2
    },
    "umbria": {
        "nome": "Regione Umbria",
        "url": "https://www.regione.umbria.it/economia/bandi-e-avvisi",
        "tipo": "regionale",
        "regione": "Umbria",
        "priorita": 2
    },
    "valle_aosta": {
        "nome": "Regione Valle d'Aosta",
        "url": "https://www.regione.vda.it/economia/bandi_avvisi/default_i.aspx",
        "tipo": "regionale",
        "regione": "Valle d'Aosta",
        "priorita": 3
    },
    "veneto": {
        "nome": "Regione Veneto",
        "url": "https://www.regione.veneto.it/web/economia/bandi",
        "tipo": "regionale",
        "regione": "Veneto",
        "priorita": 1
    },
    # ── PORTALI AGGREGATORI ──
    "fira_abruzzo": {
        "nome": "FiRA Abruzzo",
        "url": "https://www.fira.it/bandi-e-avvisi/",
        "tipo": "aggregatore",
        "regione": "Abruzzo",
        "priorita": 1
    },
    "finpiemonte": {
        "nome": "Finpiemonte",
        "url": "https://www.finpiemonte.it/bandi",
        "tipo": "aggregatore",
        "regione": "Piemonte",
        "priorita": 1
    },
    "grantzy": {
        "nome": "Grantzy - Aggregatore Nazionale",
        "url": "https://grantzy.com/bandi/",
        "tipo": "aggregatore",
        "priorita": 1
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BandoMatchBot/1.0; +https://bandomatch.ai/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.5"
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_scraper_tables():
    """Inizializza le tabelle per lo scraper nazionale."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scraper_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            contenuto TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bandi_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sorgente TEXT NOT NULL,
            titolo TEXT NOT NULL,
            url_bando TEXT,
            regione TEXT,
            tipo TEXT,
            testo_raw TEXT,
            parametri_json TEXT,
            stato TEXT DEFAULT 'nuovo',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def scrapa_url(url: str, timeout: int = 15) -> str | None:
    """
    Scarica il contenuto HTML di un URL con cache.
    Restituisce il testo estratto o None in caso di errore.
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()
    conn = get_db()

    # Controlla cache (valida 6 ore)
    cached = conn.execute("""
        SELECT contenuto, scraped_at FROM scraper_cache
        WHERE url_hash=? AND scraped_at > datetime('now', '-6 hours')
    """, (url_hash,)).fetchone()
    conn.close()

    if cached:
        logger.debug(f"Cache hit: {url}")
        return cached["contenuto"]

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Rimuovi script, style, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        testo = soup.get_text(separator="\n", strip=True)
        # Limita a 8000 caratteri per GPT
        testo = testo[:8000] if len(testo) > 8000 else testo

        # Salva in cache
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO scraper_cache (url_hash, url, contenuto)
            VALUES (?, ?, ?)
        """, (url_hash, url, testo))
        conn.commit()
        conn.close()

        return testo

    except Exception as e:
        logger.warning(f"Errore scraping {url}: {e}")
        return None


def estrai_bandi_con_llm(testo: str, sorgente: str, regione: str = None) -> list[dict]:
    """
    Usa GPT-4.1-mini per estrarre i bandi dal testo grezzo della pagina.
    Restituisce una lista di bandi strutturati.
    """
    if not testo or len(testo) < 100:
        return []

    contesto_regione = f"Regione: {regione}" if regione else "Portale Nazionale"

    prompt = f"""Sei un esperto di finanza agevolata italiana. Analizza questo testo estratto da {sorgente} ({contesto_regione}).

Estrai TUTTI i bandi di finanziamento per PMI presenti nel testo.
Per ogni bando, restituisci un oggetto JSON con questi campi:
- nome: nome completo del bando
- regioni_ammesse: lista di regioni (o ["Nazionale"] se nazionale)
- settori_ammessi: lista di settori/ATECO ammessi (o ["Tutti"] se non specificato)
- settori_esclusi: lista di settori esclusi (o [])
- eta_min_soci: età minima dei soci (numero o null)
- eta_max_soci: età massima dei soci (numero o null)
- forma_giuridica: forme giuridiche ammesse (lista o ["Tutte"])
- massimale_euro: importo massimo finanziabile in euro (numero o null)
- percentuale_fondo_perduto: percentuale a fondo perduto (numero 0-100 o null)
- scadenza: data scadenza formato YYYY-MM-DD (o null se non specificata o "sportello")
- procedura: "sportello" o "graduatoria" o "asta"
- stato: "aperto" o "chiuso" o "in_apertura"
- url_ufficiale: URL del bando se presente nel testo
- note: eventuali requisiti particolari importanti

Rispondi SOLO con un array JSON valido, senza testo aggiuntivo.
Se non trovi bandi, rispondi con [].

TESTO DA ANALIZZARE:
{testo[:4000]}"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000
        )
        raw = response.choices[0].message.content.strip()

        # Pulisci il JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        bandi = json.loads(raw)
        logger.info(f"GPT estratti {len(bandi)} bandi da {sorgente}")
        return bandi if isinstance(bandi, list) else []

    except json.JSONDecodeError as e:
        logger.warning(f"JSON non valido da GPT per {sorgente}: {e}")
        return []
    except Exception as e:
        logger.error(f"Errore GPT per {sorgente}: {e}")
        return []


def salva_bandi_nel_db(bandi: list[dict], sorgente: str, regione: str = None):
    """Salva i bandi estratti nel database principale."""
    conn = get_db()
    nuovi = 0
    for bando in bandi:
        if not bando.get("nome"):
            continue
        try:
            # Controlla se il bando esiste già (per nome + regione)
            esistente = conn.execute("""
                SELECT id FROM bandi WHERE nome=? AND (regioni_ammesse LIKE ? OR regioni_ammesse='["Nazionale"]')
            """, (bando["nome"], f"%{regione or 'Nazionale'}%")).fetchone()

            if esistente:
                # Aggiorna se già presente
                conn.execute("""
                    UPDATE bandi SET 
                        settori_ammessi=?, settori_esclusi=?, eta_min_soci=?, eta_max_soci=?,
                        massimale_euro=?, percentuale_fondo_perduto=?, scadenza=?,
                        procedura=?, stato=?, url_ufficiale=?, note=?,
                        aggiornato_il=CURRENT_TIMESTAMP
                    WHERE id=?
                """, (
                    json.dumps(bando.get("settori_ammessi", ["Tutti"])),
                    json.dumps(bando.get("settori_esclusi", [])),
                    bando.get("eta_min_soci"),
                    bando.get("eta_max_soci"),
                    bando.get("massimale_euro"),
                    bando.get("percentuale_fondo_perduto"),
                    bando.get("scadenza"),
                    bando.get("procedura", "sportello"),
                    bando.get("stato", "aperto"),
                    bando.get("url_ufficiale", ""),
                    bando.get("note", ""),
                    esistente["id"]
                ))
            else:
                # Inserisci nuovo bando
                conn.execute("""
                    INSERT INTO bandi (
                        nome, regioni_ammesse, settori_ammessi, settori_esclusi,
                        eta_min_soci, eta_max_soci, forma_giuridica_ammessa,
                        massimale_euro, percentuale_fondo_perduto, scadenza,
                        procedura, stato, url_ufficiale, note, sorgente
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bando["nome"],
                    json.dumps(bando.get("regioni_ammesse", [regione or "Nazionale"])),
                    json.dumps(bando.get("settori_ammessi", ["Tutti"])),
                    json.dumps(bando.get("settori_esclusi", [])),
                    bando.get("eta_min_soci"),
                    bando.get("eta_max_soci"),
                    json.dumps(bando.get("forma_giuridica", ["Tutte"])),
                    bando.get("massimale_euro"),
                    bando.get("percentuale_fondo_perduto"),
                    bando.get("scadenza"),
                    bando.get("procedura", "sportello"),
                    bando.get("stato", "aperto"),
                    bando.get("url_ufficiale", ""),
                    bando.get("note", ""),
                    sorgente
                ))
                nuovi += 1
        except Exception as e:
            logger.warning(f"Errore salvataggio bando '{bando.get('nome')}': {e}")

    conn.commit()
    conn.close()
    return nuovi


def scrapa_sorgente(chiave: str) -> dict:
    """
    Scrapa una singola sorgente e restituisce il risultato.
    """
    sorgente = SORGENTI_BANDI.get(chiave)
    if not sorgente:
        return {"sorgente": chiave, "errore": "Sorgente non trovata", "bandi": 0}

    logger.info(f"Scraping: {sorgente['nome']} ({sorgente['url']})")

    testo = scrapa_url(sorgente["url"])
    if not testo:
        return {"sorgente": chiave, "errore": "Impossibile scaricare la pagina", "bandi": 0}

    bandi = estrai_bandi_con_llm(
        testo,
        sorgente["nome"],
        sorgente.get("regione")
    )

    nuovi = salva_bandi_nel_db(bandi, sorgente["nome"], sorgente.get("regione"))

    return {
        "sorgente": chiave,
        "nome": sorgente["nome"],
        "bandi_trovati": len(bandi),
        "bandi_nuovi": nuovi,
        "regione": sorgente.get("regione", "Nazionale"),
        "timestamp": datetime.now().isoformat()
    }


def scrapa_tutte_le_sorgenti(solo_priorita: int = None) -> dict:
    """
    Scrapa tutte le sorgenti (o solo quelle con priorità <= solo_priorita).
    Restituisce un report completo.
    """
    init_scraper_tables()

    sorgenti_da_scrapare = {
        k: v for k, v in SORGENTI_BANDI.items()
        if solo_priorita is None or v.get("priorita", 99) <= solo_priorita
    }

    risultati = []
    totale_bandi = 0
    totale_nuovi = 0
    errori = 0

    for chiave in sorgenti_da_scrapare:
        try:
            risultato = scrapa_sorgente(chiave)
            risultati.append(risultato)
            totale_bandi += risultato.get("bandi_trovati", 0)
            totale_nuovi += risultato.get("bandi_nuovi", 0)
            if risultato.get("errore"):
                errori += 1
        except Exception as e:
            logger.error(f"Errore critico per {chiave}: {e}")
            errori += 1

    report = {
        "timestamp": datetime.now().isoformat(),
        "sorgenti_scrappate": len(sorgenti_da_scrapare),
        "totale_bandi_trovati": totale_bandi,
        "bandi_nuovi_aggiunti": totale_nuovi,
        "errori": errori,
        "dettaglio": risultati
    }

    logger.info(f"Scraping completato: {totale_bandi} bandi trovati, {totale_nuovi} nuovi, {errori} errori")
    return report


def get_statistiche_bandi() -> dict:
    """Restituisce statistiche sui bandi nel database."""
    conn = get_db()
    try:
        totale = conn.execute("SELECT COUNT(*) as n FROM bandi").fetchone()["n"]
        aperti = conn.execute("SELECT COUNT(*) as n FROM bandi WHERE stato='aperto'").fetchone()["n"]
        per_regione = conn.execute("""
            SELECT regioni_ammesse, COUNT(*) as n FROM bandi 
            WHERE stato='aperto' GROUP BY regioni_ammesse
        """).fetchall()

        return {
            "totale_bandi": totale,
            "bandi_aperti": aperti,
            "sorgenti_attive": len(SORGENTI_BANDI),
            "regioni_coperte": 20,
            "ultimo_aggiornamento": datetime.now().isoformat()
        }
    finally:
        conn.close()


# Inizializza tabelle all'import
try:
    init_scraper_tables()
except Exception:
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== National Scraper BandoMatch AI ===")
    print(f"Sorgenti configurate: {len(SORGENTI_BANDI)}")
    print("Avvio scraping priorità 1 (test rapido)...")
    report = scrapa_tutte_le_sorgenti(solo_priorita=1)
    print(json.dumps(report, indent=2, ensure_ascii=False))

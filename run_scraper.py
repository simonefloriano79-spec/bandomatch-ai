#!/usr/bin/env python3
"""
BandoMatch AI — Run Scraper
Script standalone per il popolamento del database bandi.
Usa national_scraper.py per estrarre bandi da fonti reali (Invitalia, MIMIT, Regioni)
e li salva nel database PostgreSQL di Railway tramite SQLAlchemy.

Uso:
    python run_scraper.py                  # scrapa tutte le fonti
    python run_scraper.py --priorita 1     # solo fonti nazionali prioritarie
    python run_scraper.py --fonte invitalia # solo una fonte specifica
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime, date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("run_scraper")


def parse_date_flexible(date_str):
    """Converte stringhe data in oggetto datetime."""
    if not date_str:
        return None
    if isinstance(date_str, (datetime, date)):
        return date_str if isinstance(date_str, datetime) else datetime.combine(date_str, datetime.min.time())
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"]
    date_str = str(date_str).strip()
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    logger.warning(f"Impossibile parsare data: '{date_str}'")
    return None


def bando_llm_to_model(bando_dict, sorgente_nome, regione=None):
    """Converte un dict estratto da national_scraper nel modello Bando SQLAlchemy."""
    from models.bando import Bando

    titolo = (
        bando_dict.get("nome") or bando_dict.get("titolo") or
        bando_dict.get("title") or "Bando senza titolo"
    )[:500]

    url = (
        bando_dict.get("url_ufficiale") or bando_dict.get("url") or
        f"https://bandomatch.ai/bandi/auto/{abs(hash(titolo + sorgente_nome)) % 10**9}"
    )[:1000]

    stato_raw = str(bando_dict.get("stato", "aperto")).upper()
    stato_map = {
        "APERTO": "APERTO", "OPEN": "APERTO", "ATTIVO": "APERTO",
        "CHIUSO": "CHIUSO", "CLOSED": "CHIUSO", "SCADUTO": "CHIUSO",
        "SOSPESO": "SOSPESO", "RIAPERTO": "RIAPERTO",
    }
    stato = stato_map.get(stato_raw, "APERTO")

    data_scadenza = parse_date_flexible(bando_dict.get("scadenza"))
    data_apertura = parse_date_flexible(bando_dict.get("data_apertura"))

    regioni = bando_dict.get("regioni_ammesse", [])
    if not regioni and regione:
        regioni = [regione]
    if not regioni:
        regioni = ["Nazionale"]
    if isinstance(regioni, str):
        regioni = [regioni]

    ateco = bando_dict.get("settori_ammessi", [])
    if isinstance(ateco, str):
        ateco = [ateco]

    massimale = bando_dict.get("massimale_euro") or bando_dict.get("massimale_agevolazione")
    if massimale:
        try:
            massimale = float(str(massimale).replace(".", "").replace(",", ".").replace("euro", "").replace("EUR", "").strip())
        except (ValueError, TypeError):
            massimale = None

    perc_fp = bando_dict.get("percentuale_fondo_perduto")
    if perc_fp:
        try:
            perc_fp = float(str(perc_fp).replace("%", "").strip())
            if perc_fp > 100:
                perc_fp = None
        except (ValueError, TypeError):
            perc_fp = None

    descrizione = (
        bando_dict.get("descrizione") or bando_dict.get("description") or
        bando_dict.get("note") or ""
    )

    return Bando(
        titolo=titolo,
        descrizione=descrizione[:5000] if descrizione else None,
        url=url,
        fonte=sorgente_nome[:255],
        stato=stato,
        data_apertura=data_apertura,
        data_scadenza=data_scadenza,
        regioni_ammesse=regioni,
        ateco_ammessi=ateco if ateco else None,
        massimale_agevolazione=massimale,
        percentuale_fondo_perduto=perc_fp,
        data_scraping=datetime.utcnow(),
    )


def run_scraper(priorita=None, fonte_singola=None):
    """Esegue lo scraper e salva i bandi nel database PostgreSQL."""
    from app import app
    from extensions import db
    from models.bando import Bando
    import national_scraper as ns

    with app.app_context():
        db.create_all()
        logger.info("=" * 60)
        logger.info("BandoMatch AI — Scraper avviato")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 60)

        totale_nuovi = 0
        totale_aggiornati = 0
        totale_errori = 0
        risultati = []

        if fonte_singola:
            sorgenti = {fonte_singola: ns.SORGENTI_BANDI.get(fonte_singola)}
            if not sorgenti[fonte_singola]:
                logger.error(f"Fonte '{fonte_singola}' non trovata.")
                return
        else:
            sorgenti = {
                k: v for k, v in ns.SORGENTI_BANDI.items()
                if priorita is None or v.get("priorita", 99) <= priorita
            }

        logger.info(f"Sorgenti da scrapare: {len(sorgenti)}")

        for chiave, sorgente_info in sorgenti.items():
            if not sorgente_info:
                continue
            nome = sorgente_info["nome"]
            url = sorgente_info["url"]
            regione = sorgente_info.get("regione")
            logger.info(f"  Scraping: {nome}")

            try:
                testo = ns.scrapa_url(url)
                if not testo:
                    logger.warning(f"    Impossibile scaricare: {url}")
                    totale_errori += 1
                    risultati.append({"fonte": nome, "errore": "Pagina non scaricabile", "nuovi": 0})
                    continue

                bandi_estratti = ns.estrai_bandi_con_llm(testo, nome, regione)
                logger.info(f"    Bandi estratti: {len(bandi_estratti)}")

                nuovi = 0
                aggiornati = 0

                for bando_dict in bandi_estratti:
                    try:
                        titolo = (bando_dict.get("nome") or bando_dict.get("titolo") or "")[:500]
                        url_bando = (bando_dict.get("url_ufficiale") or bando_dict.get("url") or "")

                        esistente = None
                        if url_bando:
                            esistente = db.session.query(Bando).filter_by(url=url_bando).first()
                        if not esistente and titolo:
                            esistente = db.session.query(Bando).filter_by(titolo=titolo).first()

                        if esistente:
                            esistente.stato = bando_dict.get("stato", "APERTO").upper()
                            esistente.data_scadenza = parse_date_flexible(bando_dict.get("scadenza"))
                            esistente.updated_at = datetime.utcnow()
                            esistente.data_scraping = datetime.utcnow()
                            aggiornati += 1
                        else:
                            nuovo = bando_llm_to_model(bando_dict, nome, regione)
                            db.session.add(nuovo)
                            nuovi += 1

                    except Exception as e:
                        logger.warning(f"    Errore bando '{bando_dict.get('nome', '?')}': {e}")

                db.session.commit()
                totale_nuovi += nuovi
                totale_aggiornati += aggiornati
                risultati.append({
                    "fonte": nome,
                    "bandi_trovati": len(bandi_estratti),
                    "nuovi": nuovi,
                    "aggiornati": aggiornati,
                })
                logger.info(f"    Salvati: {nuovi} nuovi, {aggiornati} aggiornati")

            except Exception as e:
                logger.error(f"    Errore critico per {nome}: {e}")
                db.session.rollback()
                totale_errori += 1
                risultati.append({"fonte": nome, "errore": str(e), "nuovi": 0})

        totale_db = db.session.query(Bando).count()
        logger.info(f"COMPLETATO: {totale_nuovi} nuovi, {totale_aggiornati} aggiornati, {totale_errori} errori")
        logger.info(f"Totale bandi nel DB: {totale_db}")

        return {
            "timestamp": datetime.now().isoformat(),
            "sorgenti": len(sorgenti),
            "nuovi": totale_nuovi,
            "aggiornati": totale_aggiornati,
            "errori": totale_errori,
            "totale_db": totale_db,
            "dettaglio": risultati,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BandoMatch AI — Scraper bandi")
    parser.add_argument("--priorita", type=int, default=None,
                        help="Scrapa solo fonti con priorita <= N (1=nazionali, 2=tutte)")
    parser.add_argument("--fonte", type=str, default=None,
                        help="Scrapa solo questa fonte (es: invitalia, mise_mimit)")
    args = parser.parse_args()
    result = run_scraper(priorita=args.priorita, fonte_singola=args.fonte)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))

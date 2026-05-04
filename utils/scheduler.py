"""
BandoMatch AI - utils/scheduler.py
Scheduler APScheduler per aggiornamento automatico bandi ogni giorno alle 06:00 UTC.
Usa national_scraper.py per estrarre bandi reali e li salva nel DB PostgreSQL via SQLAlchemy.
"""
import os
import logging
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("bandomatch.scheduler")


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
    return None


def bando_dict_to_model(bando_dict, sorgente_nome, regione=None):
    """Converte un dict estratto da national_scraper nel modello Bando SQLAlchemy."""
    from models.bando import Bando

    titolo = (
        bando_dict.get("nome") or bando_dict.get("titolo") or
        bando_dict.get("title") or "Bando senza titolo"
    )[:500]

    url = (
        bando_dict.get("url_ufficiale") or bando_dict.get("url") or
        "https://bandomatch.ai/bandi/auto/{}".format(abs(hash(titolo + sorgente_nome)) % 10**9)
    )[:1000]

    stato_raw = str(bando_dict.get("stato", "aperto")).upper()
    stato_map = {
        "APERTO": "APERTO", "OPEN": "APERTO", "ATTIVO": "APERTO",
        "CHIUSO": "CHIUSO", "CLOSED": "CHIUSO", "SCADUTO": "CHIUSO",
        "SOSPESO": "SOSPESO", "RIAPERTO": "RIAPERTO",
    }
    stato = stato_map.get(stato_raw, "APERTO")

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
        data_apertura=parse_date_flexible(bando_dict.get("data_apertura")),
        data_scadenza=parse_date_flexible(bando_dict.get("scadenza")),
        regioni_ammesse=regioni,
        ateco_ammessi=ateco if ateco else None,
        massimale_agevolazione=massimale,
        percentuale_fondo_perduto=perc_fp,
        data_scraping=datetime.utcnow(),
    )


def job_scraping_bandi(app):
    """
    Job APScheduler: scrapa tutte le fonti prioritarie e salva i bandi nel DB.
    Viene eseguito ogni giorno alle 06:00 UTC.
    """
    logger.info("=" * 50)
    logger.info("Scheduler: avvio job scraping bandi - {}".format(datetime.utcnow().isoformat()))

    with app.app_context():
        try:
            import national_scraper as ns
            from models.bando import Bando
            from extensions import db

            sorgenti = {
                k: v for k, v in ns.SORGENTI_BANDI.items()
                if v.get("priorita", 99) <= 1  # Solo fonti nazionali prioritarie
            }

            totale_nuovi = 0
            totale_aggiornati = 0
            totale_errori = 0

            for chiave, sorgente_info in sorgenti.items():
                if not sorgente_info:
                    continue
                nome = sorgente_info["nome"]
                url = sorgente_info["url"]
                regione = sorgente_info.get("regione")

                logger.info("  Scraping: {}".format(nome))

                try:
                    testo = ns.scrapa_url(url)
                    if not testo:
                        logger.warning("    Impossibile scaricare: {}".format(url))
                        totale_errori += 1
                        continue

                    bandi_estratti = ns.estrai_bandi_con_llm(testo, nome, regione)
                    logger.info("    Bandi estratti: {}".format(len(bandi_estratti)))

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
                                nuovo = bando_dict_to_model(bando_dict, nome, regione)
                                db.session.add(nuovo)
                                nuovi += 1

                        except Exception as e:
                            logger.warning("    Errore bando: {}".format(e))

                    db.session.commit()
                    totale_nuovi += nuovi
                    totale_aggiornati += aggiornati
                    logger.info("    Salvati: {} nuovi, {} aggiornati".format(nuovi, aggiornati))

                except Exception as e:
                    logger.error("    Errore critico per {}: {}".format(nome, e))
                    db.session.rollback()
                    totale_errori += 1

            totale_db = db.session.query(Bando).count()
            logger.info("Scheduler: completato - {} nuovi, {} aggiornati, {} errori".format(
                totale_nuovi, totale_aggiornati, totale_errori))
            logger.info("Totale bandi nel DB: {}".format(totale_db))

            # ── Notifiche match: invia SOLO se ci sono nuovi bandi ──
            if totale_nuovi > 0:
                _invia_notifiche_nuovi_match(app, totale_nuovi)

        except Exception as e:
            logger.error("Scheduler: errore critico nel job: {}".format(e))

    logger.info("=" * 50)


def _invia_notifiche_nuovi_match(app, totale_nuovi: int):
    """
    Invia email di notifica a tutti gli utenti attivi quando vengono trovati nuovi bandi.
    Chiamata dallo scheduler SOLO quando totale_nuovi > 0.
    """
    try:
        from models.utente import Utente
        from utils.notifiche import invia_notifica_match

        utenti_attivi = Utente.query.filter_by(attivo=True).all()
        inviati = 0
        errori = 0

        for utente in utenti_attivi:
            try:
                # Costruisce un teaser generico con il conteggio dei nuovi bandi
                bandi_teaser = [{
                    'titolo': f'Nuovi bandi disponibili ({totale_nuovi} aggiunti oggi)',
                    'score': 70,
                    'scadenza': 'Vedi dashboard',
                    'analisi_id': None,
                }]
                result = invia_notifica_match(utente, bandi_teaser)
                if result.get('success'):
                    inviati += 1
                else:
                    errori += 1
            except Exception as e:
                logger.warning("Errore notifica per {}: {}".format(
                    getattr(utente, 'email', '?'), e))
                errori += 1

        logger.info("Notifiche match inviate: {} ok, {} errori".format(inviati, errori))

    except Exception as e:
        logger.error("Errore critico in _invia_notifiche_nuovi_match: {}".format(e))


def start_scheduler(scheduler, app):
    """
    Configura e avvia il job APScheduler.
    Da chiamare in app.py dopo db.create_all().

    Uso in app.py:
        from apscheduler.schedulers.background import BackgroundScheduler
        from utils.scheduler import start_scheduler
        scheduler = BackgroundScheduler()
        start_scheduler(scheduler, app)
        scheduler.start()
    """
    # Job giornaliero alle 06:00 UTC
    scheduler.add_job(
        func=job_scraping_bandi,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        args=[app],
        id="scraping_bandi_giornaliero",
        name="Scraping bandi giornaliero 06:00 UTC",
        replace_existing=True,
        misfire_grace_time=3600,  # Tolleranza 1 ora se il server era offline
    )
    logger.info("Scheduler configurato: scraping bandi ogni giorno alle 06:00 UTC")

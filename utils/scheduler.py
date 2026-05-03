from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from flask import current_app
from sqlalchemy import and_
from models.user import User
from models.bando import Bando
from models.matching import Matching
from utils.scraper import scrape_invitalia_bandi
from utils.matching import calculate_user_match_score
from utils.email import send_match_notification
from database import db

logger = logging.getLogger(__name__)

class SchedulerService:
    _scheduler = None

    @classmethod
    def init_scheduler(cls, app):
        """Inizializza lo scheduler con il contesto dell'app Flask."""
        if cls._scheduler is None:
            cls._scheduler = BackgroundScheduler()
            cls._scheduler.add_job(
                func=cls._nightly_job,
                trigger=CronTrigger(hour=2, minute=0, timezone='UTC'),
                id='nightly_bandi_sync',
                name='Nightly Bandi Sync and Matching',
                replace_existing=True,
                misfire_grace_time=3600
            )
            cls._scheduler.start()
            logger.info("Scheduler inizializzato con job giornaliero alle 02:00 UTC")

    @classmethod
    def shutdown_scheduler(cls):
        """Ferma lo scheduler."""
        if cls._scheduler and cls._scheduler.running:
            cls._scheduler.shutdown()
            logger.info("Scheduler fermato")

    @classmethod
    def _nightly_job(cls):
        """Job principale che esegue scraping, matching e notifiche."""
        logger.info(f"[{datetime.utcnow().isoformat()}] Inizio job notturno")
        try:
            # Step 1: Scraping bandi da Invitalia
            logger.info("Step 1: Scraping bandi da Invitalia")
            new_bandi_count = cls._scrape_and_store_bandi()
            logger.info(f"Scraping completato: {new_bandi_count} nuovi bandi")

            # Step 2: Ricalcola score matching per tutti gli utenti
            logger.info("Step 2: Ricalcolo score matching")
            matching_results = cls._recalculate_all_matches()
            logger.info(f"Matching completato: {matching_results['total']} match ricalcolati, "
                       f"{matching_results['high_score']} con score > 70")

            # Step 3: Invia notifiche per nuovi match
            logger.info("Step 3: Invio notifiche email")
            emails_sent = cls._send_notifications(matching_results['high_score_matches'])
            logger.info(f"Notifiche inviate: {emails_sent} email")

            logger.info(f"[{datetime.utcnow().isoformat()}] Job notturno completato con successo")
        except Exception as e:
            logger.error(f"Errore durante job notturno: {str(e)}", exc_info=True)

    @classmethod
    def _scrape_and_store_bandi(cls) -> int:
        """Scrape bandi da Invitalia e li salva nel database.
        
        Returns:
            int: Numero di nuovi bandi aggiunti
        """
        try:
            scraped_bandi = scrape_invitalia_bandi()
            new_count = 0

            for bando_data in scraped_bandi:
                existing = Bando.query.filter_by(
                    external_id=bando_data.get('external_id')
                ).first()

                if not existing:
                    bando = Bando(
                        title=bando_data.get('title'),
                        description=bando_data.get('description'),
                        external_id=bando_data.get('external_id'),
                        source='invitalia',
                        link=bando_data.get('link'),
                        deadline=bando_data.get('deadline'),
                        budget=bando_data.get('budget'),
                        keywords=','.join(bando_data.get('keywords', [])),
                        sectors=','.join(bando_data.get('sectors', []))
                    )
                    db.session.add(bando)
                    new_count += 1

            db.session.commit()
            return new_count
        except Exception as e:
            db.session.rollback()
            logger.error(f"Errore scraping Invitalia: {str(e)}")
            return 0

    @classmethod
    def _recalculate_all_matches(cls) -> dict:
        """Ricalcola i match per tutti gli utenti.
        
        Returns:
            dict: Risultati con chiavi 'total', 'high_score', 'high_score_matches'
        """
        try:
            users = User.query.filter_by(is_active=True).all()
            bandi = Bando.query.all()
            
            total_matches = 0
            high_score_matches = []

            for user in users:
                for bando in bandi:
                    # Calcola score
                    score = calculate_user_match_score(user, bando)

                    # Cerca o crea matching
                    matching = Matching.query.filter_by(
                        user_id=user.id,
                        bando_id=bando.id
                    ).first()

                    if not matching:
                        matching = Matching(
                            user_id=user.id,
                            bando_id=bando.id,
                            score=score,
                            notified=False
                        )
                        db.session.add(matching)
                    else:
                        matching.score = score
                        matching.updated_at = datetime.utcnow()

                    total_matches += 1

                    # Track high score matches non ancora notificati
                    if score > 70 and not matching.notified:
                        high_score_matches.append({
                            'user': user,
                            'bando': bando,
                            'score': score,
                            'matching': matching
                        })

            db.session.commit()
            return {
                'total': total_matches,
                'high_score': len(high_score_matches),
                'high_score_matches': high_score_matches
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Errore ricalcolo matching: {str(e)}")
            return {
                'total': 0,
                'high_score': 0,
                'high_score_matches': []
            }

    @classmethod
    def _send_notifications(cls, high_score_matches: list) -> int:
        """Invia notifiche email per nuovi match con score > 70.
        
        Args:
            high_score_matches: Lista di match con score elevato
            
        Returns:
            int: Numero di email inviate con successo
        """
        emails_sent = 0

        for match_info in high_score_matches:
            try:
                user = match_info['user']
                bando = match_info['bando']
                score = match_info['score']
                matching = match_info['matching']

                # Invia email di notifica
                send_match_notification(
                    email=user.email,
                    user_name=user.full_name,
                    bando_title=bando.title,
                    match_score=int(score),
                    bando_link=bando.link,
                    bando_deadline=bando.deadline
                )

                # Marca come notificato
                matching.notified = True
                matching.notified_at = datetime.utcnow()
                db.session.commit()
                emails_sent += 1

                logger.info(f"Email inviata a {user.email} per bando {bando.title} "
                           f"(score: {score})")
            except Exception as e:
                logger.error(f"Errore invio email per match {match_info.get('bando', {}).get('title', 'Unknown')}: "
                           f"{str(e)}")
                continue

        return emails_sent


def start_background_scheduler(app):
    """Funzione helper per avviare lo scheduler dall'app Flask."""
    SchedulerService.init_scheduler(app)


def stop_background_scheduler():
    """Funzione helper per fermare lo scheduler."""
    SchedulerService.shutdown_scheduler()

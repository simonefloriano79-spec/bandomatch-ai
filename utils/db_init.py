from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from models.user import User
from models.bando import Bando
from extensions import db


def inizializza_database():
    """
    Inizializza il database creando tutte le tabelle e inserendo dati di test.
    """
    try:
        # Crea tutte le tabelle definite in SQLAlchemy
        db.create_all()
        print("✓ Tabelle create con successo")

        # Verifica se l'admin esiste già per evitare duplicati
        admin_esistente = User.query.filter_by(email="admin@bandonatch.ai").first()
        if not admin_esistente:
            # Crea utente admin
            admin = User(
                email="admin@bandonatch.ai",
                nome="Admin",
                cognome="BandoMatch",
                password_hash="hashed_password_admin_123",
                ruolo="admin",
                azienda="BandoMatch.ai",
                verificato=True,
                data_creazione=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.flush()
            print("✓ Utente admin creato: admin@bandonatch.ai")
        else:
            admin = admin_esistente
            print("ℹ Utente admin già presente")

        # Verifica se i bandi di esempio esistono già
        bandi_esistenti = Bando.query.count()
        if bandi_esistenti == 0:
            # Bando 1: APERTO
            bando1 = Bando(
                titolo="Incentivi Ricerca e Sviluppo 2024",
                descrizione="Contributi per aziende che investono in R&D nel settore digitale e innovazione",
                ente_finanziatore="Regione Lombardia",
                stato="aperto",
                data_inizio=datetime.utcnow(),
                data_scadenza=datetime.utcnow() + timedelta(days=45),
                importo_max=500000,
                importo_min=50000,
                tasso_cofinanziamento=40,
                settori=["Tecnologia", "Digital", "Innovazione"],
                beneficiari=["PMI", "Startup", "Grandi Imprese"],
                url_bando="https://example.com/bando1",
                contatti_email="info@regione-lombardia.it",
                note="Bando aperto per nuove candidature",
                data_creazione=datetime.utcnow(),
                id_creatore=admin.id
            )
            db.session.add(bando1)
            db.session.flush()
            print("✓ Bando 1 creato (APERTO): Incentivi Ricerca e Sviluppo 2024")

            # Bando 2: IN VALUTAZIONE
            bando2 = Bando(
                titolo="Supporto Transizione Digitale PMI",
                descrizione="Agevolazioni per la digitalizzazione dei processi aziendali, e-commerce e cloud",
                ente_finanziatore="Agenzia delle Entrate",
                stato="in_valutazione",
                data_inizio=datetime.utcnow() - timedelta(days=30),
                data_scadenza=datetime.utcnow() - timedelta(days=5),
                importo_max=250000,
                importo_min=10000,
                tasso_cofinanziamento=60,
                settori=["Digitale", "E-Commerce", "Cloud Computing"],
                beneficiari=["PMI"],
                url_bando="https://example.com/bando2",
                contatti_email="digital@agenziaentrate.it",
                note="In fase di valutazione delle candidature ricevute",
                data_creazione=datetime.utcnow() - timedelta(days=35),
                id_creatore=admin.id
            )
            db.session.add(bando2)
            db.session.flush()
            print("✓ Bando 2 creato (IN VALUTAZIONE): Supporto Transizione Digitale PMI")

            # Bando 3: CHIUSO
            bando3 = Bando(
                titolo="Green Economy - Impianti Rinnovabili",
                descrizione="Contributi per l'installazione di pannelli solari e sistemi energetici rinnovabili",
                ente_finanziatore="Ministero dell'Ambiente",
                stato="chiuso",
                data_inizio=datetime.utcnow() - timedelta(days=120),
                data_scadenza=datetime.utcnow() - timedelta(days=30),
                importo_max=1000000,
                importo_min=100000,
                tasso_cofinanziamento=50,
                settori=["Energia", "Sostenibilità", "Ambiente"],
                beneficiari=["Industrie", "Grandi Imprese", "Consorzi"],
                url_bando="https://example.com/bando3",
                contatti_email="green@minambiente.it",
                note="Bando concluso, non sono più accettate candidature",
                data_creazione=datetime.utcnow() - timedelta(days=125),
                id_creatore=admin.id
            )
            db.session.add(bando3)
            db.session.flush()
            print("✓ Bando 3 creato (CHIUSO): Green Economy - Impianti Rinnovabili")

            db.session.commit()
            print("✓ Dati di test inseriti con successo")
        else:
            print(f"ℹ Database contiene già {bandi_esistenti} bandi")

        print("\n✓ Inizializzazione database completata con successo")
        return True

    except IntegrityError as e:
        db.session.rollback()
        print(f"✗ Errore di integrità: {str(e)}")
        return False
    except Exception as e:
        db.session.rollback()
        print(f"✗ Errore durante l'inizializzazione: {str(e)}")
        return False

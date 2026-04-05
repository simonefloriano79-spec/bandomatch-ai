"""
BandoMatch AI — Modulo Stripe Payments
Gestisce abbonamenti Premium (€9,90/mese) e Pro (€29,90/mese)
con Checkout Session, Webhook e gestione stato abbonamento nel DB.
"""

import os
import stripe
import sqlite3
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, redirect, url_for, session

logger = logging.getLogger(__name__)

# ── Configurazione Stripe ──────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

def get_stripe_client():
    """Inizializzazione lazy del client Stripe."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        raise ValueError("STRIPE_SECRET_KEY non configurata")
    stripe.api_key = key
    return stripe

# ── Prezzi Stripe ────────────────────────────────────────────────────────────
STRIPE_PRICES = {
    "premium": {
        "price_id": os.environ.get("STRIPE_PRICE_PREMIUM", "price_1TIoKY2doi6GhwDG3SOorEFZ"),
        "amount": 990,        # €9,90 in centesimi
        "name": "BandoMatch AI Premium",
        "interval": "month",
        "features": [
            "Analisi illimitata visure PDF",
            "Semaforo Verde/Giallo/Rosso/Grigio",
            "Dossier PDF scaricabile",
            "Alert email nuovi bandi",
            "Storico analisi 12 mesi"
        ]
    },
    "pro": {
        "price_id": os.environ.get("STRIPE_PRICE_PRO", "price_1TIoKk2doi6GhwDG4MVKK4Fq"),
        "amount": 2990,       # €29,90 in centesimi
        "name": "BandoMatch AI Pro",
        "interval": "month",
        "features": [
            "Tutto di Premium",
            "Simulatore Punteggio avanzato",
            "Post Social AI per ogni bando",
            "Reverse Matching (bandi cercano te)",
            "API access per integrazioni",
            "Supporto prioritario"
        ]
    },
    "consulenza": {
        "price_id": os.environ.get("STRIPE_PRICE_CONSULENZA", "price_1TIoKk2doi6GhwDG8MAcoeYg"),
        "amount": 4900,       # €49,00 una tantum
        "name": "Consulenza Esperto BandoMatch",
        "interval": None,     # Una tantum
        "features": [
            "Sessione 60 min con esperto",
            "Analisi approfondita bandi compatibili",
            "Piano d'azione personalizzato",
            "Follow-up via email 30 giorni"
        ]
    }
}

DB_PATH = os.path.join(os.path.dirname(__file__), "bandomatch.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_stripe_tables():
    """Crea le tabelle Stripe nel database se non esistono."""
    conn = get_db()
    # Nota: usa utenti (non users) come tabella principale
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stripe_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT UNIQUE NOT NULL,
            piano TEXT NOT NULL,
            stato TEXT DEFAULT 'pending',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pagamenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            piano TEXT NOT NULL,
            importo INTEGER NOT NULL,
            valuta TEXT DEFAULT 'eur',
            stripe_payment_intent TEXT,
            stripe_invoice_id TEXT,
            stato TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Aggiungi colonna piano_scadenza a utenti se non esiste
    try:
        conn.execute("ALTER TABLE utenti ADD COLUMN piano_scadenza TEXT")
    except Exception:
        pass  # Colonna già esistente
    conn.commit()
    conn.close()
    logger.info("Tabelle Stripe inizializzate.")


def crea_checkout_session(user_id: int, user_email: str, piano: str, base_url: str) -> dict:
    """
    Crea una Stripe Checkout Session per l'abbonamento richiesto.
    Restituisce {'checkout_url': ..., 'session_id': ...}
    """
    if piano not in STRIPE_PRICES:
        return {"error": f"Piano '{piano}' non valido."}

    prezzo = STRIPE_PRICES[piano]
    is_subscription = prezzo["interval"] is not None

    try:
        s = get_stripe_client()

        # Modalità: subscription per piani mensili, payment per una tantum
        mode = "subscription" if is_subscription else "payment"

        # Costruisci i line_items usando il Price ID reale
        price_id = prezzo["price_id"]
        if price_id.startswith("price_"):
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            # Crea price inline (fallback)
            price_data = {
                "currency": "eur",
                "unit_amount": prezzo["amount"],
                "product_data": {
                    "name": prezzo["name"],
                    "description": " | ".join(prezzo["features"][:3])
                }
            }
            if is_subscription:
                price_data["recurring"] = {"interval": prezzo["interval"]}
            line_items = [{"price_data": price_data, "quantity": 1}]

        checkout_params = {
            "payment_method_types": ["card"],
            "line_items": line_items,
            "mode": mode,
            "customer_email": user_email,
            "success_url": f"{base_url}/pagamento/successo?session_id={{CHECKOUT_SESSION_ID}}&piano={piano}",
            "cancel_url": f"{base_url}/upgrade?cancelled=1",
            "metadata": {
                "user_id": str(user_id),
                "piano": piano,
                "app": "BandoMatch AI"
            },
            "locale": "it"
        }

        # Aggiungi trial period per abbonamenti (7 giorni gratis)
        if is_subscription:
            checkout_params["subscription_data"] = {
                "trial_period_days": 7,
                "metadata": {"user_id": str(user_id), "piano": piano}
            }

        session_stripe = s.checkout.Session.create(**checkout_params)

        # Salva la sessione nel DB (tabella stripe_sessions)
        try:
            conn = get_db()
            conn.execute("""
                INSERT OR REPLACE INTO stripe_sessions 
                (user_id, session_id, piano, stato)
                VALUES (?, ?, ?, 'pending')
            """, (user_id, session_stripe.id, piano))
            conn.commit()
            conn.close()
        except Exception as db_err:
            logger.warning(f"Impossibile salvare sessione Stripe nel DB: {db_err}")

        logger.info(f"Checkout session creata: {session_stripe.id} per user {user_id} piano {piano}")
        return {
            "checkout_url": session_stripe.url,
            "session_id": session_stripe.id,
            "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
        }

    except stripe.error.AuthenticationError:
        logger.warning("Stripe non configurato — modalità demo attiva")
        return {
            "checkout_url": f"{base_url}/pagamento/demo?piano={piano}&user_id={user_id}",
            "session_id": f"demo_{user_id}_{piano}",
            "demo_mode": True
        }
    except Exception as e:
        logger.error(f"Errore Stripe: {e}")
        return {"error": str(e)}


def verifica_webhook(payload: bytes, sig_header: str) -> dict | None:
    """
    Verifica e processa il webhook Stripe.
    Restituisce l'evento se valido, None altrimenti.
    """
    try:
        s = get_stripe_client()
        event = s.Webhook.construct_event(
            payload, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        )
        return event
    except stripe.error.SignatureVerificationError:
        logger.error("Firma webhook Stripe non valida")
        return None
    except Exception as e:
        logger.error(f"Errore webhook: {e}")
        return None


def processa_evento_stripe(event: dict) -> bool:
    """
    Processa gli eventi Stripe e aggiorna il DB di conseguenza.
    Usa la tabella 'utenti' (non 'users').
    """
    event_type = event["type"]
    data = event["data"]["object"]

    conn = get_db()
    try:
        if event_type == "checkout.session.completed":
            session_id = data["id"]
            user_id = int(data["metadata"].get("user_id", 0))
            piano = data["metadata"].get("piano", "premium")
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")

            # Aggiorna sessione Stripe
            conn.execute("""
                UPDATE stripe_sessions 
                SET stato='completed', stripe_customer_id=?, stripe_subscription_id=?, updated_at=CURRENT_TIMESTAMP
                WHERE session_id=?
            """, (customer_id, subscription_id, session_id))

            # Aggiorna piano utente (tabella utenti)
            scadenza = (datetime.now() + timedelta(days=37)).isoformat()
            conn.execute("""
                UPDATE utenti SET piano=?, abbonamento_attivo=1, piano_scadenza=? WHERE id=?
            """, (piano, scadenza, user_id))

            # Registra pagamento
            conn.execute("""
                INSERT INTO pagamenti (user_id, piano, importo, stripe_payment_intent, stato)
                VALUES (?, ?, ?, ?, 'completed')
            """, (user_id, piano, STRIPE_PRICES[piano]["amount"],
                  data.get("payment_intent", "")))

            conn.commit()
            logger.info(f"Abbonamento attivato: user {user_id} → piano {piano}")
            return True

        elif event_type == "customer.subscription.deleted":
            customer_id = data.get("customer")
            # Downgrade a free
            conn.execute("""
                UPDATE utenti SET piano='free', abbonamento_attivo=0, piano_scadenza=NULL 
                WHERE id IN (SELECT user_id FROM stripe_sessions WHERE stripe_customer_id=?)
            """, (customer_id,))
            conn.commit()
            logger.info(f"Abbonamento cancellato per customer {customer_id}")
            return True

        elif event_type == "invoice.payment_failed":
            customer_id = data.get("customer")
            logger.warning(f"Pagamento fallito per customer {customer_id}")
            return True

    except Exception as e:
        logger.error(f"Errore processamento evento {event_type}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()

    return True


def attiva_piano_demo(user_id: int, piano: str) -> bool:
    """
    Attiva un piano in modalità demo (senza Stripe reale).
    """
    conn = get_db()
    try:
        scadenza = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute("""
            UPDATE utenti SET piano=?, abbonamento_attivo=1, piano_scadenza=? WHERE id=?
        """, (piano, scadenza, user_id))
        try:
            conn.execute("""
                INSERT INTO pagamenti (user_id, piano, importo, stripe_payment_intent, stato)
                VALUES (?, ?, ?, 'demo_payment', 'demo')
            """, (user_id, piano, STRIPE_PRICES.get(piano, {}).get("amount", 0)))
        except Exception:
            pass
        conn.commit()
        logger.info(f"Piano demo attivato: user {user_id} → {piano}")
        return True
    except Exception as e:
        logger.error(f"Errore attivazione demo: {e}")
        return False
    finally:
        conn.close()


def get_stato_abbonamento(user_id: int) -> dict:
    """
    Restituisce lo stato completo dell'abbonamento di un utente.
    Usa la tabella 'utenti'.
    """
    conn = get_db()
    try:
        user = conn.execute("""
            SELECT piano, piano_scadenza, abbonamento_attivo FROM utenti WHERE id=?
        """, (user_id,)).fetchone()

        if not user:
            return {"piano": "free", "attivo": False, "scadenza": None}

        piano = user["piano"] or "free"
        scadenza_str = user.get("piano_scadenza") if hasattr(user, 'get') else None
        try:
            scadenza_str = user["piano_scadenza"]
        except Exception:
            scadenza_str = None

        if piano == "free":
            return {"piano": "free", "attivo": True, "scadenza": None, "features": []}

        # Verifica scadenza
        attivo = bool(user["abbonamento_attivo"])
        if scadenza_str:
            try:
                scadenza = datetime.fromisoformat(scadenza_str)
                attivo = datetime.now() < scadenza
            except Exception:
                attivo = True

        return {
            "piano": piano,
            "attivo": attivo,
            "scadenza": scadenza_str,
            "features": STRIPE_PRICES.get(piano, {}).get("features", []),
            "importo_mensile": STRIPE_PRICES.get(piano, {}).get("amount", 0) / 100
        }
    finally:
        conn.close()


# Inizializza le tabelle all'import
try:
    init_stripe_tables()
except Exception:
    pass  # Il DB potrebbe non essere ancora pronto

import os
import json
import stripe
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models.user import User
from extensions import db

pagamenti = Blueprint('pagamenti', __name__, url_prefix='/api/v1')

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

PIANI = {
    'premium': {'price': 990, 'name': 'Premium', 'stripe_price_id': os.getenv('STRIPE_PREMIUM_PRICE_ID', 'price_premium')},
    'pro': {'price': 2990, 'name': 'Pro', 'stripe_price_id': os.getenv('STRIPE_PRO_PRICE_ID', 'price_pro')}
}


@pagamenti.route('/checkout', methods=['POST'])
def checkout():
    """Crea sessione Stripe per il pagamento di un piano"""
    try:
        data = request.get_json()
        
        if not data or 'piano' not in data or 'user_id' not in data:
            return jsonify({'error': 'Missing required fields: piano, user_id'}), 400
        
        piano = data.get('piano', '').lower()
        user_id = data.get('user_id')
        
        if piano not in PIANI:
            return jsonify({'error': f'Piano non valido. Scegli tra: {list(PIANI.keys())}'}), 400
        
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        piano_info = PIANI[piano]
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': piano_info['stripe_price_id'],
                    'quantity': 1,
                }
            ],
            mode='subscription',
            success_url=os.getenv('STRIPE_SUCCESS_URL', 'http://localhost:5000/success?session_id={CHECKOUT_SESSION_ID}'),
            cancel_url=os.getenv('STRIPE_CANCEL_URL', 'http://localhost:5000/cancel'),
            customer_email=user.email,
            metadata={
                'user_id': str(user_id),
                'piano': piano
            }
        )
        
        return jsonify({
            'session_id': session.id,
            'url': session.url
        }), 200
    
    except ValueError as ve:
        return jsonify({'error': f'Invalid request data: {str(ve)}'}), 400
    except stripe.error.StripeError as se:
        return jsonify({'error': f'Stripe error: {se.user_message}'}), 400
    except SQLAlchemyError as dbe:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@pagamenti.route('/webhook-stripe', methods=['POST'])
def webhook_stripe():
    """Gestisce gli eventi webhook di Stripe"""
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            return jsonify({'error': 'Missing Stripe-Signature header'}), 400
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({'error': 'Invalid signature'}), 403
        
        if event['type'] == 'customer.subscription.created':
            _handle_subscription_created(event['data']['object'])
        
        elif event['type'] == 'customer.subscription.updated':
            _handle_subscription_updated(event['data']['object'])
        
        elif event['type'] == 'customer.subscription.deleted':
            _handle_subscription_deleted(event['data']['object'])
        
        elif event['type'] == 'invoice.paid':
            _handle_invoice_paid(event['data']['object'])
        
        return jsonify({'status': 'success'}), 200
    
    except SQLAlchemyError as dbe:
        db.session.rollback()
        return jsonify({'error': 'Database error processing webhook'}), 500
    except Exception as e:
        return jsonify({'error': f'Webhook processing error: {str(e)}'}), 500


def _handle_subscription_created(subscription):
    """Gestisce la creazione di una nuova sottoscrizione"""
    try:
        metadata = subscription.get('metadata', {})
        user_id = metadata.get('user_id')
        piano = metadata.get('piano', 'premium')
        
        if not user_id:
            return
        
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return
        
        user.piano = piano
        user.stripe_subscription_id = subscription['id']
        user.stripe_customer_id = subscription['customer']
        user.is_active = True
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise


def _handle_subscription_updated(subscription):
    """Gestisce l'aggiornamento di una sottoscrizione"""
    try:
        customer_id = subscription['customer']
        
        user = db.session.query(User).filter_by(stripe_customer_id=customer_id).first()
        if not user:
            return
        
        if subscription['status'] == 'active':
            user.is_active = True
        elif subscription['status'] in ['canceled', 'incomplete_expired']:
            user.is_active = False
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise


def _handle_subscription_deleted(subscription):
    """Gestisce l'eliminazione di una sottoscrizione"""
    try:
        customer_id = subscription['customer']
        
        user = db.session.query(User).filter_by(stripe_customer_id=customer_id).first()
        if not user:
            return
        
        user.piano = 'free'
        user.is_active = False
        user.stripe_subscription_id = None
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise


def _handle_invoice_paid(invoice):
    """Gestisce il pagamento di una fattura"""
    try:
        customer_id = invoice['customer']
        
        user = db.session.query(User).filter_by(stripe_customer_id=customer_id).first()
        if not user:
            return
        
        user.last_payment_date = invoice['created']
        user.is_active = True
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise

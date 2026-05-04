from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Dict, Any, Optional


class Utente(UserMixin, db.Model):
    """Modello Utente con gestione autenticazione e piano"""
    __tablename__ = 'utenti'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    piano = db.Column(db.String(50), default='free', nullable=False)  # free, starter, pro, enterprise
    attivo = db.Column(db.Boolean, default=True, nullable=False)
    data_registrazione = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relazioni
    profilo_aziendale = db.relationship(
        'ProfiloAziendale',
        backref='utente',
        uselist=False,
        cascade='all, delete-orphan',
        lazy='joined'
    )

    def __repr__(self) -> str:
        return f'<Utente {self.email}>'

    @property
    def is_active(self) -> bool:
        """Flask-Login: restituisce True se l'account è attivo."""
        return self.attivo

    def set_password(self, password: str) -> None:
        """
        Genera e salva l'hash della password.

        Args:
            password (str): Password in chiaro
        """
        if not password or len(password) < 8:
            raise ValueError('La password deve essere lunga almeno 8 caratteri')
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        """
        Verifica se la password fornita corrisponde all'hash salvato.

        Args:
            password (str): Password in chiaro da verificare

        Returns:
            bool: True se la password è corretta, False altrimenti
        """
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte l'utente a dizionario.

        Returns:
            Dict[str, Any]: Rappresentazione dict dell'utente
        """
        return {
            'id': self.id,
            'email': self.email,
            'piano': self.piano,
            'attivo': self.attivo,
            'data_registrazione': self.data_registrazione.isoformat() if self.data_registrazione else None,
            'profilo_aziendale': self.profilo_aziendale.to_dict() if self.profilo_aziendale else None
        }


class ProfiloAziendale(db.Model):
    """Modello Profilo Aziendale collegato all'Utente"""
    __tablename__ = 'profili_aziendali'
    id = db.Column(db.Integer, primary_key=True)
    utente_id = db.Column(db.Integer, db.ForeignKey('utenti.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    azienda = db.Column(db.String(255), nullable=False)
    partita_iva = db.Column(db.String(11), unique=True, nullable=False, index=True)
    regione = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(2), nullable=True)
    ateco = db.Column(db.String(10), nullable=True)  # Codice ATECO attività economica
    forma_giuridica = db.Column(db.String(100), nullable=True)  # Es. S.p.A., S.r.l., etc.
    anno_costituzione = db.Column(db.Integer, nullable=True)
    fatturato_annuo = db.Column(db.Float, nullable=True)  # In euro
    numero_dipendenti = db.Column(db.Integer, nullable=True)
    data_creazione = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_aggiornamento = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f'<ProfiloAziendale {self.azienda}>'

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte il profilo aziendale a dizionario.

        Returns:
            Dict[str, Any]: Rappresentazione dict del profilo aziendale
        """
        return {
            'id': self.id,
            'utente_id': self.utente_id,
            'azienda': self.azienda,
            'partita_iva': self.partita_iva,
            'regione': self.regione,
            'provincia': self.provincia,
            'ateco': self.ateco,
            'forma_giuridica': self.forma_giuridica,
            'anno_costituzione': self.anno_costituzione,
            'fatturato_annuo': self.fatturato_annuo,
            'numero_dipendenti': self.numero_dipendenti,
            'data_creazione': self.data_creazione.isoformat() if self.data_creazione else None,
            'data_aggiornamento': self.data_aggiornamento.isoformat() if self.data_aggiornamento else None
        }

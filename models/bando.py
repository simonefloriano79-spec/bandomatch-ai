from datetime import datetime
from app import db


class Bando(db.Model):
    __tablename__ = 'bandi'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(500), nullable=False, index=True)
    descrizione = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(1000), nullable=False, unique=True, index=True)
    fonte = db.Column(db.String(255), nullable=False)  # es. "Regione Lombardia", "MISE"
    stato = db.Column(
        db.String(50),
        nullable=False,
        default='APERTO',
        index=True
    )  # APERTO, CHIUSO, SOSPESO, RIAPERTO
    data_apertura = db.Column(db.DateTime, nullable=True, index=True)
    data_scadenza = db.Column(db.DateTime, nullable=True, index=True)
    regioni_ammesse = db.Column(
        db.JSON, nullable=True
    )  # List[str] es. ["Lombardia", "Piemonte"]
    ateco_ammessi = db.Column(
        db.JSON, nullable=True
    )  # List[str] es. ["01.11", "01.12"]
    massimale_agevolazione = db.Column(
        db.Float, nullable=True
    )  # in euro, es. 50000.00
    percentuale_fondo_perduto = db.Column(
        db.Float, nullable=True
    )  # 0-100, es. 40.0
    data_scraping = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Bando(id={self.id}, titolo='{self.titolo}', fonte='{self.fonte}')>"

    def to_dict(self):
        """
        Converte il modello Bando in dizionario.
        Utile per serializzazione JSON e API responses.
        """
        return {
            'id': self.id,
            'titolo': self.titolo,
            'descrizione': self.descrizione,
            'url': self.url,
            'fonte': self.fonte,
            'stato': self.stato,
            'data_apertura': self.data_apertura.isoformat()
            if self.data_apertura
            else None,
            'data_scadenza': self.data_scadenza.isoformat()
            if self.data_scadenza
            else None,
            'regioni_ammesse': self.regioni_ammesse,
            'ateco_ammessi': self.ateco_ammessi,
            'massimale_agevolazione': self.massimale_agevolazione,
            'percentuale_fondo_perduto': self.percentuale_fondo_perduto,
            'data_scraping': self.data_scraping.isoformat()
            if self.data_scraping
            else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_open(self):
        """
        Verifica se il bando è ancora aperto.
        """
        if self.stato != 'APERTO':
            return False
        if self.data_scadenza and datetime.utcnow() > self.data_scadenza:
            return False
        return True

    def is_expired(self):
        """
        Verifica se il bando è scaduto.
        """
        if self.data_scadenza and datetime.utcnow() > self.data_scadenza:
            return True
        return False

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Bando(db.Model):
    __tablename__ = 'bandi'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(500), nullable=False, index=True)
    url = db.Column(db.String(2048), nullable=False, unique=True)
    fonte = db.Column(db.String(255), nullable=False)
    stato = db.Column(db.String(50), default='attivo', nullable=False)
    data_scraping = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Bando {self.id} - {self.titolo}>'

    def to_dict(self):
        return {
            'id': self.id,
            'titolo': self.titolo,
            'url': self.url,
            'fonte': self.fonte,
            'stato': self.stato,
            'data_scraping': self.data_scraping.isoformat() if self.data_scraping else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

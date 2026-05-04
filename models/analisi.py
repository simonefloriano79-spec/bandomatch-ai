"""
BandoMatch AI — Modello Analisi
Salva il risultato di ogni analisi visura camerale effettuata da un utente.
"""
from datetime import datetime
from extensions import db


class Analisi(db.Model):
    """Storico delle analisi visura effettuate dagli utenti."""
    __tablename__ = 'analisi'

    id = db.Column(db.Integer, primary_key=True)
    utente_id = db.Column(
        db.Integer,
        db.ForeignKey('utenti.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Dati estratti dalla visura
    ragione_sociale = db.Column(db.String(500), nullable=True)
    codice_fiscale = db.Column(db.String(16), nullable=True)
    ateco = db.Column(db.String(20), nullable=True)       # es. "62.01.00"
    regione = db.Column(db.String(100), nullable=True)
    provincia = db.Column(db.String(2), nullable=True)
    forma_giuridica = db.Column(db.String(100), nullable=True)
    eta_mesi = db.Column(db.Integer, nullable=True)
    capitale_sociale = db.Column(db.Float, nullable=True)
    numero_dipendenti = db.Column(db.Integer, nullable=True)

    # Risultati matching
    bandi_verdi = db.Column(db.Integer, default=0)
    bandi_gialli = db.Column(db.Integer, default=0)
    bandi_rossi = db.Column(db.Integer, default=0)
    bandi_grigi = db.Column(db.Integer, default=0)
    valore_potenziale = db.Column(db.Float, default=0.0)

    # JSON completo per la pagina risultati
    dati_impresa_json = db.Column(db.Text, nullable=True)    # JSON profilo impresa
    risultati_json = db.Column(db.Text, nullable=True)       # JSON lista bandi matchati
    form_integrativo_json = db.Column(db.Text, nullable=True)  # JSON dati form extra

    data_analisi = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    def __repr__(self):
        return f'<Analisi id={self.id} utente={self.utente_id} azienda={self.ragione_sociale}>'

    def to_dict(self):
        return {
            'id': self.id,
            'utente_id': self.utente_id,
            'ragione_sociale': self.ragione_sociale,
            'ateco': self.ateco,
            'regione': self.regione,
            'forma_giuridica': self.forma_giuridica,
            'eta_mesi': self.eta_mesi,
            'bandi_verdi': self.bandi_verdi,
            'bandi_gialli': self.bandi_gialli,
            'bandi_rossi': self.bandi_rossi,
            'bandi_grigi': self.bandi_grigi,
            'valore_potenziale': self.valore_potenziale,
            'data_analisi': self.data_analisi.isoformat() if self.data_analisi else None,
        }

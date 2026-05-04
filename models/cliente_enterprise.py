"""
BandoMatch AI — Modello ClienteEnterprise
Gestisce il portafoglio clienti di un utente Enterprise (CNA, CAF, commercialisti, ecc.)
"""
from datetime import datetime
from extensions import db


class ClienteEnterprise(db.Model):
    """
    Rappresenta un'azienda cliente gestita da un utente con piano Enterprise.
    Un utente Enterprise può avere N ClienteEnterprise nel proprio portafoglio.
    """
    __tablename__ = 'clienti_enterprise'

    id = db.Column(db.Integer, primary_key=True)

    # Utente Enterprise proprietario del portafoglio
    utente_id = db.Column(
        db.Integer,
        db.ForeignKey('utenti.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Dati identificativi del cliente
    ragione_sociale = db.Column(db.String(500), nullable=False)
    codice_fiscale  = db.Column(db.String(16),  nullable=True)
    partita_iva     = db.Column(db.String(11),  nullable=True)
    email_cliente   = db.Column(db.String(255), nullable=True)   # email referente cliente
    note            = db.Column(db.Text,        nullable=True)   # note interne del partner

    # Dati aziendali (estratti da visura o inseriti manualmente)
    ateco           = db.Column(db.String(20),  nullable=True)
    regione         = db.Column(db.String(100), nullable=True)
    forma_giuridica = db.Column(db.String(100), nullable=True)
    eta_mesi        = db.Column(db.Integer,     nullable=True)
    capitale_sociale= db.Column(db.Float,       nullable=True)

    # White-label: logo del partner da sovrapporre al PDF dossier
    logo_url        = db.Column(db.String(500), nullable=True)   # URL logo partner (S3/CDN)
    nome_partner    = db.Column(db.String(255), nullable=True)   # Es. "CNA Abruzzo"

    # Ultima analisi effettuata per questo cliente
    ultima_analisi_id = db.Column(
        db.Integer,
        db.ForeignKey('analisi.id', ondelete='SET NULL'),
        nullable=True
    )
    ultima_analisi_data = db.Column(db.DateTime, nullable=True)
    bandi_verdi_ultimo  = db.Column(db.Integer, default=0)
    bandi_gialli_ultimo = db.Column(db.Integer, default=0)
    valore_potenziale   = db.Column(db.Float,   default=0.0)

    # Metadati
    data_inserimento   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_aggiornamento = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow, nullable=False)
    attivo = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<ClienteEnterprise id={self.id} azienda={self.ragione_sociale}>'

    def to_dict(self):
        return {
            'id':                   self.id,
            'utente_id':            self.utente_id,
            'ragione_sociale':      self.ragione_sociale,
            'codice_fiscale':       self.codice_fiscale,
            'partita_iva':          self.partita_iva,
            'email_cliente':        self.email_cliente,
            'note':                 self.note,
            'ateco':                self.ateco,
            'regione':              self.regione,
            'forma_giuridica':      self.forma_giuridica,
            'eta_mesi':             self.eta_mesi,
            'capitale_sociale':     self.capitale_sociale,
            'logo_url':             self.logo_url,
            'nome_partner':         self.nome_partner,
            'ultima_analisi_id':    self.ultima_analisi_id,
            'ultima_analisi_data':  self.ultima_analisi_data.isoformat() if self.ultima_analisi_data else None,
            'bandi_verdi_ultimo':   self.bandi_verdi_ultimo,
            'bandi_gialli_ultimo':  self.bandi_gialli_ultimo,
            'valore_potenziale':    self.valore_potenziale,
            'data_inserimento':     self.data_inserimento.isoformat() if self.data_inserimento else None,
            'attivo':               self.attivo,
        }

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models.user import User
from models.bando import Bando
from models.applicazione import Applicazione
from sqlalchemy import and_


def genera_dossier_pdf(utente, bando):
    """
    Genera un PDF dossier con dati azienda, dettagli bando e score compatibilità.
    
    Args:
        utente: oggetto User
        bando: oggetto Bando
    
    Returns:
        str: path del file PDF generato o None in caso di errore
    """
    try:
        # Crea cartella se non esiste
        dossier_dir = os.path.join('static', 'dossier')
        os.makedirs(dossier_dir, exist_ok=True)
        
        # Genera nome file univoco
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"dossier_{utente.id}_{bando.id}_{timestamp}.pdf"
        filepath = os.path.join(dossier_dir, filename)
        
        # Crea documento PDF
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Stili
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1F2937'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            borderBottomWidth=2,
            borderBottomColor=colors.HexColor('#E5E7EB'),
            borderPadding=6
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4B5563'),
            spaceAfter=6,
            leading=14
        )
        
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6B7280'),
            fontName='Helvetica-Bold',
            spaceAfter=2
        )
        
        # Contenuto PDF
        story = []
        
        # Titolo
        story.append(Paragraph('DOSSIER DI CANDIDATURA', title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Data generazione
        data_gen = datetime.now().strftime('%d/%m/%Y %H:%M')
        story.append(Paragraph(f'<i>Generato il {data_gen}</i>', normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # SEZIONE 1: DATI AZIENDA
        story.append(Paragraph('1. DATI AZIENDA', heading_style))
        
        # Tabella dati azienda
        dati_azienda = [
            ['Campo', 'Valore'],
            ['Nome Azienda', utente.nome_azienda or 'N/D'],
            ['Ragione Sociale', utente.ragione_sociale or 'N/D'],
            ['Partita IVA', utente.partita_iva or 'N/D'],
            ['Email', utente.email or 'N/D'],
            ['Telefono', utente.telefono or 'N/D'],
            ['Indirizzo', f"{utente.indirizzo or 'N/D'}, {utente.cap or ''} {utente.citta or ''}"],
            ['Provincia', utente.provincia or 'N/D'],
            ['Dipendenti', str(utente.num_dipendenti) if utente.num_dipendenti else 'N/D'],
            ['Settore', utente.settore or 'N/D'],
            ['Data Iscrizione', utente.data_creazione.strftime('%d/%m/%Y') if utente.data_creazione else 'N/D']
        ]
        
        table_azienda = Table(dati_azienda, colWidths=[2*inch, 4.5*inch])
        table_azienda.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(table_azienda)
        story.append(Spacer(1, 0.3*inch))
        
        # SEZIONE 2: DETTAGLI BANDO
        story.append(Paragraph('2. DETTAGLI BANDO', heading_style))
        
        dati_bando = [
            ['Campo', 'Valore'],
            ['Titolo', bando.titolo or 'N/D'],
            ['Ente', bando.ente_erogatore or 'N/D'],
            ['Budget', f"€ {bando.importo_totale:,.2f}" if bando.importo_totale else 'N/D'],
            ['Data Apertura', bando.data_apertura.strftime('%d/%m/%Y') if bando.data_apertura else 'N/D'],
            ['Data Scadenza', bando.data_scadenza.strftime('%d/%m/%Y') if bando.data_scadenza else 'N/D'],
            ['Settore', bando.settore or 'N/D'],
            ['Regione', bando.regione or 'N/D'],
            ['Tipo Beneficiario', bando.tipo_beneficiario or 'N/D'],
        ]
        
        table_bando = Table(dati_bando, colWidths=[2*inch, 4.5*inch])
        table_bando.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(table_bando)
        story.append(Spacer(1, 0.3*inch))
        
        # SEZIONE 3: SCORE COMPATIBILITÀ
        story.append(Paragraph('3. ANALISI COMPATIBILITÀ', heading_style))
        
        # Recupera applicazione per score
        from models.applicazione import Applicazione as AppModel
        applicazione = AppModel.query.filter(
            and_(
                AppModel.utente_id == utente.id,
                AppModel.bando_id == bando.id
            )
        ).first()
        
        if applicazione and applicazione.score_compatibilita is not None:
            score = applicazione.score_compatibilita
            
            # Determina colore score
            if score >= 80:
                color_score = colors.HexColor('#10B981')  # Verde
                stato = 'ALTA COMPATIBILITÀ'
            elif score >= 60:
                color_score = colors.HexColor('#F59E0B')  # Arancio
                stato = 'MEDIA COMPATIBILITÀ'
            else:
                color_score = colors.HexColor('#EF4444')  # Rosso
                stato = 'BASSA COMPATIBILITÀ'
            
            # Tabella score
            dati_score = [
                ['Metrica', 'Valore'],
                ['Score Compatibilità', f'{score}%'],
                ['Stato', stato],
                ['Data Analisi', applicazione.data_creazione.strftime('%d/%m/%Y %H:%M') if applicazione.data_creazione else 'N/D'],
            ]
            
            table_score = Table(dati_score, colWidths=[2*inch, 4.5*inch])
            table_score.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (1, 1), (1, 1), color_score),
                ('TEXTCOLOR', (1, 1), (1, 1), colors.white),
                ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ]))
            
            story.append(table_score)
        else:
            story.append(Paragraph('Analisi di compatibilità non ancora disponibile.', normal_style))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_text = 'BandoMatch.ai - Piattaforma di matching tra aziende e bandi'
        story.append(Paragraph(
            f'<i>{footer_text}</i>',
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#9CA3AF'),
                alignment=TA_CENTER
            )
        ))
        
        # Costruisci PDF
        doc.build(story)
        
        # Restituisci path relativo
        return os.path.join('static', 'dossier', filename)
        
    except Exception as e:
        print(f'Errore nella generazione del dossier PDF: {str(e)}')
        return None

from datetime import datetime, date
import os
import base64
import fitz  # PyMuPDF
import streamlit as st

st.set_page_config(
    page_title="Gestione Malattia Figlio - FS", page_icon="🚆", layout="centered"
)

st.title("🚆 Compilatore e Tracciatore Malattia Figlio (TM_03_bis)")
st.write(
    "L'applicazione calcola i giorni, verifica i limiti, aggiorna lo storico, inserisce adozione/affidamento e data ingresso, mostra l'anteprima e permette il download."
)

# --- MEMORIA / STORICO LOCALE ---
LOG_FILE = "storico_malattie.txt"


def carica_storico():
    if os.path.exists(LOG_FILE):
        giorni_totali = 0
        with open(LOG_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) >= 2:
                    giorni_totali += int(parts[1])
        return giorni_totali
    return 0


def salva_storico(data_str, giorni):
    with open(LOG_FILE, "a") as f:
        f.write(f"{data_str};{giorni}\n")


giorni_gia_usati = carica_storico()

# --- FORM DI INPUT ---
with st.form("form_tm03"):
    st.subheader("1. Dati Dipendente & Struttura")
    col1, col2 = st.columns(2)
    with col1:
        cognome_nome = st.text_input(
            "Nome e Cognome", value="PASQUALE FONTANA"
        )
        cid = st.text_input("CID", value="2943518")
        figura = st.text_input("Figura Professionale", value="TECNICO MANUT ROTAB")
    with col2:
        impianto = st.text_input("Impianto / Struttura", value="IMC AV NA")

    st.subheader("2. Dati del Minore")
    col3, col4, col5 = st.columns(3)
    with col3:
        nome_figlio = st.text_input("Nome Figlio", value="GABRIELE")
        adozione_aff = st.selectbox(
            "Adozione / Affidamento (SI/NO)", ["NO", "SI"]
        )
    with col4:
        cf_figlio = st.text_input("Codice Fiscale Figlio", value="FTGS")
        data_ingresso = st.date_input(
            "Data Ingresso in Famiglia/Italia", value=None
        )
    with col5:
        data_nascita = st.date_input(
            "Data di Nascita",
            value=date(2025, 6, 21),
            min_value=date(2010, 1, 1),
        )

    st.subheader("3. Periodo di Assenza Richiesto")
    col6, col7 = st.columns(2)
    with col6:
        data_inizio = st.date_input("Data Inizio", datetime.today())
    with col7:
        data_fine = st.date_input("Data Fine", datetime.today())

    st.subheader("4. Firma e Data Richiesta")
    data_richiesta = st.date_input("Data del Richiesta (Firma)", datetime.today())

    st.subheader("5. Dichiarazioni (A TAL FINE DICHIARA)")
    # Checkbox interattivi per gestire le spunte nel modulo
    spunta_giorni_precedenti = st.checkbox(
        "Inizio rapporto in corso d'anno (I dati si aggiornano automaticamente)",
        value=True if giorni_gia_usati > 0 else False,
    )
    ferie_normali = st.checkbox(
        "Di non trovarsi nella condizione di assente per ferie previamente autorizzate nelle stesse giornate.",
        value=True,
    )
    ferie_ricovero = st.checkbox(
        "Di trovarsi nella condizione di assente per ferie previamente autorizzate in situazione di ricovero ospedaliero.",
        value=False,
    )
    altro_genitore = st.checkbox(
        "Che l'altro genitore/coniuge non è in astensione dal lavoro nello stesso periodo per il medesimo motivo.",
        value=True,
    )

    submitted = st.form_submit_button(
        "Verifica Limiti, Registra e Genera Modulo"
    )

if submitted:
    # Calcolo età ed anno di vita del minore
    oggi = date.today()
    eta_figlio = (
        oggi.year
        - data_nascita.year
        - ((oggi.month, oggi.day) < (data_nascita.month, data_nascita.day))
    )
    anno_di_vita = (
        oggi.year
        - data_nascita.year
        + (
            1
            if (oggi.month, oggi.day) >= (data_nascita.month, data_nascita.day)
            else 0
        )
    )

    # Calcolo giorni richiesti
    num_giorni_richiesti = (data_fine - data_inizio).days + 1

    if num_giorni_richiesti <= 0:
        st.error(
            "Errore: La data di fine non può essere precedente alla data di inizio."
        )
    else:
        limite_superato = False
        messaggio_limite = ""

        if 3 <= eta_figlio <= 14:
            totale_annuale = giorni_gia_usati + num_giorni_richiesti
            if totale_annuale > 10:
                limite_superato = True
                messaggio_limite = f"Attenzione! Il figlio ha {eta_figlio} anni. Il limite massimo è di 10 giorni lavorativi all'anno. Hai già usato {giorni_gia_usati} giorni, con questa richiesta saliresti a {totale_annuale} giorni."
        elif eta_figlio < 3:
            messaggio_limite = f"Figlio di età inferiore a 3 anni ({eta_figlio} anni). Malattia fruibile per l'intera durata della patologia (primi 30 giorni retribuiti da contratto aziendale)."
        else:
            messaggio_limite = f"Attenzione: il figlio ha {eta_figlio} anni. Verifica le condizioni contrattuali per minori di età superiore a 14 anni."

        st.info(messaggio_limite)

        if limite_superato:
            st.warning(
                "Impossibile procedere automaticamente: limite annuo superato."
            )
        else:
            # Registrazione nello storico locale
            periodo_str = (
                f"{data_inizio.strftime('%d/%m/%Y')} - {data_fine.strftime('%d/%m/%Y')}"
            )
            salva_storico(periodo_str, num_giorni_richiesti)

            # Compilazione PDF con le tue coordinate e il casellamento del CID
            pdf_path = "modulo_base.pdf"
            output_path = f"TM_03_bis_compilato_{data_inizio.strftime('%Y%m%d')}.pdf"

            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                page = doc[1]  # Seconda pagina per la tabella dei firmatari

                # --- FIRMATARI (In fondo alla seconda pagina) ---
                x_data_firma = 300
                x_firma = 420
                y_richiedente = 115

                page.insert_text(
                    (x_data_firma, y_richiedente),
                    data_richiesta.strftime("%d/%m/%Y"),
                    fontsize=9,
                    color=(0, 0, 0),
                )
                page.insert_text(
                    (x_firma, y_richiedente),
                    cognome_nome,
                    fontsize=8,
                    color=(0, 0, 0),
                )

                # Torneremo alla prima pagina per stampare i dati principali
                page = doc[0]

                # Formattazione data ingresso (se inserita)
                str_data_ingresso = (
                    data_ingresso.strftime("%d/%m/%Y") if data_ingresso else ""
                )

                # Campi normali con le tue coordinate esatte
                punti_stampa = [
                    (150, 153, cognome_nome),  # Nome e Cognome
                    (150, 178, figura),  # Figura Professionale
                    (415, 178, impianto),  # Impianto
                    (75, 255, nome_figlio),  # Nome Figlio
                    (155, 255, cf_figlio),  # C.F. Figlio
                    (280, 255, data_nascita.strftime("%d/%m/%Y")),  # Data Nascita
                    (380, 255, adozione_aff),  # Adozione / Affidamento (SI/NO)
                    (
                        455,
                        255,
                        str_data_ingresso,
                    ),  # Data Ingresso Famiglia/Italia
                    (
                        75,
                        340,
                        str(num_giorni_richiesti),
                    ),  # N. Giorni (Richiesta)
                    (140, 340, data_inizio.strftime("%d/%m/%Y")),  # Dal (Richiesta)
                    (220, 340, data_fine.strftime("%d/%m/%Y")),  # Al (Richiesta)
                ]

                for x, y, testo in punti_stampa:
                    if testo:
                        page.insert_text(
                            (x, y), str(testo), fontsize=9, color=(0, 0, 0)
                        )

                # --- SEZIONE DICHIARA (Spunte dinamiche basate sui checkbox) ---
                if spunta_giorni_precedenti:
                    page.insert_text(
                        (53, 435), "X", fontsize=9, color=(0, 0, 0)
                    )
                    page.insert_text(
                        (195, 435), str(giorni_gia_usati), fontsize=9, color=(0, 0, 0)
                    )
                    page.insert_text(
                        (180, 448), str(anno_di_vita), fontsize=9, color=(0, 0, 0)
                    )

                if ferie_normali:
                    page.insert_text(
                        (53, 465), "X", fontsize=9, color=(0, 0, 0)
                    )

                if ferie_ricovero:
                    page.insert_text(
                        (53, 488), "X", fontsize=9, color=(0, 0, 0)
                    )

                if altro_genitore:
                    page.insert_text(
                        (53, 522), "X", fontsize=9, color=(0, 0, 0)
                    )

                # --- CASELLAMENTO CID (Ogni cifra nella sua casella) ---
                cid_x_start = 375  # Coordinata X della prima casella del CID
                cid_y = 153  # Coordinata Y della riga del CID
                spaziatura_caselle = 28  # Distanza orizzontale tra le caselle

                for i, cifra in enumerate(str(cid)):
                    page.insert_text(
                        (cid_x_start + (i * spaziatura_caselle), cid_y),
                        cifra,
                        fontsize=9,
                        color=(0, 0, 0),
                    )

                doc.save(output_path)
                doc.close()

                st.success(
                    f"✅ Modulo compilato con successo! Aggiunti Adozione/Affidamento e Data Ingresso."
                )

                # --- 1. ANTEPRIMA DEL MODULO COMPILATO ---
                st.subheader("📄 Anteprima del Modulo Compilato")
                with open(output_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode("utf-8")

                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)

                # --- 2. PULSANTE DI DOWNLOAD / STAMPA ---
                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 Scarica e Stampa il Modulo PDF Compilato",
                        data=f,
                        file_name=output_path,
                        mime="application/pdf",
                    )
            else:
                st.error(
                    f"File '{pdf_path}' non trovato nella cartella. Inseriscilo per generare il PDF."
                )

# Riepilogo nella barra laterale
st.sidebar.header("📊 Riepilogo Anno in Corso")
st.sidebar.write(f"Giorni di malattia figlio usati: **{giorni_gia_usati}**")
if st.sidebar.button("Resetta Storico Giorni"):
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        st.sidebar.success("Storico azzerato!")
        st.rerun()
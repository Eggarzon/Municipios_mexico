import pandas as pd
import streamlit as st
from datetime import datetime
from geopy.distance import geodesic
import unicodedata
import io
from fpdf import FPDF
import tempfile
import os

CSV_FILENAME = "municipios_mexico.csv"

def limpia_texto(texto):
    # Normaliza y elimina caracteres extraños/acentos
    if pd.isna(texto):
        return ""
    txt = ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    )
    txt = txt.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    return txt.strip()

def normaliza(texto):
    if pd.isna(texto):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower().strip()

@st.cache_data
def load_municipios(filename):
    df = pd.read_csv(filename, encoding="utf-8", dtype=str)
    df['Estado'] = df['Estado'].apply(limpia_texto)
    df['Ciudad'] = df['Ciudad'].apply(limpia_texto)
    df['Longitud'] = pd.to_numeric(df['Longitud'], errors='coerce')
    df['Latitud'] = pd.to_numeric(df['Latitud'], errors='coerce')
    # FILTRA SOLO REGISTROS VÁLIDOS DE MÉXICO
    df = df[(df['Latitud'].between(14, 33)) & (df['Longitud'].between(-119, -85))]
    df = df.dropna(subset=['Latitud','Longitud'])
    return df

def calcular_distancia(lat1, lon1, lat2, lon2):
    return round(geodesic((lat1, lon1), (lat2, lon2)).km, 2)

def obtener_tarifa_por_distancia(distancia):
    if distancia <= 400:
        return 2000
    elif distancia <= 900:
        return 3500
    elif distancia <= 1300:
        return 5900
    elif distancia <= 1700:
        return 7800
    elif distancia <= 1999:
        return 8999
    else:
        return 10500

def cotizar_servicio(distancia, peso_vol, servicio, maniobras=0, volumen_m3=0):
    if servicio == "LTL":
        tarifa_m3 = obtener_tarifa_por_distancia(distancia)
        costo = round(volumen_m3 * tarifa_m3, 2)
        detalle = f"{volumen_m3:.4f} m3 x ${tarifa_m3:,.2f}/m3"
        unidad = "LTL"
    else:
        if peso_vol <= 1:
            unidad = "1 Ton"
        elif peso_vol <= 3:
            unidad = "3 Ton"
        elif peso_vol <= 5:
            unidad = "5 Ton"
        else:
            unidad = "10 Ton"

        tarifas_banderazo = {"1 Ton": 2500, "3 Ton": 3000, "5 Ton": 3500, "10 Ton": 4000}
        tarifas_km = {"1 Ton": 13, "3 Ton": 15, "5 Ton": 19, "10 Ton": 23}

        if distancia <= 50:
            costo = tarifas_banderazo[unidad]
            detalle = f"Banderazo para {unidad} ({distancia:.2f} km, <=50 km)"
        else:
            costo = tarifas_banderazo[unidad] + (distancia - 50) * tarifas_km[unidad]
            detalle = (
                f"${tarifas_banderazo[unidad]:,.2f} (banderazo hasta 50 km) + "
                f"{(distancia - 50):.2f} km x ${tarifas_km[unidad]:,.2f}/km"
            )
        if servicio == "MUDANZA":
            costo += maniobras
            detalle += f" + ${maniobras:,.2f} por maniobras"
    return unidad, round(costo, 2), detalle

def generar_pdf(cotizacion):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Cotización de Transporte", ln=True, align="C")
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Fecha de cotización: {cotizacion['Fecha cotización']}", ln=True)
    pdf.cell(200, 10, txt=f"Cliente: {cotizacion['Cliente']}", ln=True)
    pdf.cell(200, 10, txt=f"Servicio: {cotizacion['Servicio']}", ln=True)
    pdf.cell(200, 10, txt=f"Origen: {cotizacion['Origen']}", ln=True)
    pdf.cell(200, 10, txt=f"Destino: {cotizacion['Destino']}", ln=True)
    pdf.cell(200, 10, txt=f"Distancia: {cotizacion['Distancia (km)']} km", ln=True)
    pdf.cell(200, 10, txt=f"Tipo de unidad: {cotizacion['Tipo de unidad']}", ln=True)
    pdf.cell(200, 10, txt=f"Peso/Volumen: {cotizacion['Peso/Vol (Ton)']}", ln=True)
    if cotizacion['Volumen (m3)']:
        pdf.cell(200, 10, txt=f"Volumen (m3): {cotizacion['Volumen (m3)']}", ln=True)
    pdf.cell(200, 10, txt=f"Costo total: ${cotizacion['Costo Total MXN']:,.2f}", ln=True)
    pdf.multi_cell(200, 10, txt=f"Observaciones: {cotizacion['Observaciones']}")
    pdf.cell(200, 10, txt=f"Fecha de servicio: {cotizacion['Fecha de servicio']}", ln=True)
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmpfile.name)
    return tmpfile.name

def main():
    st.set_page_config(page_title="Cotizador de Fletes", layout="centered")
    st.title("Cotizador de Fletes por Municipio")

    df = load_municipios(CSV_FILENAME)
    municipios_opciones = df['Ciudad'] + " (" + df['Estado'] + ")"

    with st.form("cotizador_form"):
        col1, col2 = st.columns(2)
        with col1:
            origen = st.selectbox("Municipio de origen", municipios_opciones, key="origen")
        with col2:
            destino = st.selectbox("Municipio de destino", municipios_opciones, key="destino")
        servicio = st.selectbox("Tipo de servicio", ["FTL", "LTL", "MUDANZA"], key="servicio")
        nombre_cliente = st.text_input("Nombre del cliente")
        peso_vol = None
        volumen_m3 = ""
        maniobras = 0
        if servicio in ["FTL", "MUDANZA"]:
            peso_vol = st.number_input("Peso/Volumen estimado (Toneladas)", min_value=0.01, max_value=10.0, value=1.0, step=0.01)
        if servicio == "MUDANZA":
            maniobras = st.number_input("Costo adicional por maniobras ($)", min_value=0.0, value=0.0, step=1.0)
        if servicio == "LTL":
            col3, col4, col5 = st.columns(3)
            with col3:
                largo = st.number_input("Largo (cm)", min_value=1.0, value=100.0, step=1.0)
            with col4:
                ancho = st.number_input("Ancho (cm)", min_value=1.0, value=100.0, step=1.0)
            with col5:
                alto = st.number_input("Alto (cm)", min_value=1.0, value=100.0, step=1.0)
            volumen_cm3 = largo * ancho * alto
            volumen_m3 = volumen_cm3 / 1_000_000
        observaciones = st.text_area("Observaciones del servicio")
        fecha_servicio = st.date_input("Fecha de servicio", value=datetime.today())
        submitted = st.form_submit_button("Cotizar")

    historial = st.session_state.get("historial", [])

    if submitted:
        if origen == destino:
            st.error("El municipio de origen y destino deben ser diferentes.")
        else:
            ciudad_o, estado_o = origen.rsplit(" (", 1)
            ciudad_d, estado_d = destino.rsplit(" (", 1)
            ciudad_o = normaliza(ciudad_o)
            estado_o = normaliza(estado_o.replace(")", ""))
            ciudad_d = normaliza(ciudad_d)
            estado_d = normaliza(estado_d.replace(")", ""))

            row_o = df[(df['Ciudad'].apply(normaliza)==ciudad_o) & (df['Estado'].apply(normaliza)==estado_o)]
            row_d = df[(df['Ciudad'].apply(normaliza)==ciudad_d) & (df['Estado'].apply(normaliza)==estado_d)]

            if row_o.empty or row_d.empty:
                st.error("No se encontró alguno de los municipios en la base de datos o sus coordenadas no son válidas.")
            else:
                lat1, lon1 = row_o.iloc[0][['Latitud', 'Longitud']]
                lat2, lon2 = row_d.iloc[0][['Latitud', 'Longitud']]
                # Validar rangos antes de calcular distancia
                if not (14 <= float(lat1) <= 33 and 14 <= float(lat2) <= 33):
                    st.error(f"Latitud fuera de rango para México: Origen {lat1}, Destino {lat2}")
                    return
                if not (-119 <= float(lon1) <= -85 and -119 <= float(lon2) <= -85):
                    st.error(f"Longitud fuera de rango para México: Origen {lon1}, Destino {lon2}")
                    return

                distancia = calcular_distancia(float(lat1), float(lon1), float(lat2), float(lon2))

                unidad, costo, detalle = cotizar_servicio(
                    distancia,
                    peso_vol if peso_vol else 0,
                    servicio,
                    maniobras,
                    volumen_m3 if volumen_m3 else 0
                )

                cotizacion = {
                    "Fecha cotización": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "Cliente": nombre_cliente,
                    "Servicio": servicio,
                    "Origen": origen,
                    "Destino": destino,
                    "Distancia (km)": distancia,
                    "Tipo de unidad": unidad,
                    "Peso/Vol (Ton)": peso_vol if peso_vol else "",
                    "Volumen (m3)": round(volumen_m3, 4) if volumen_m3 else "",
                    "Costo Total MXN": costo,
                    "Detalle": detalle,
                    "Observaciones": observaciones,
                    "Fecha de servicio": fecha_servicio.strftime("%Y-%m-%d"),
                }
                if "historial" not in st.session_state:
                    st.session_state["historial"] = []
                st.session_state["historial"].append(cotizacion)
                historial = st.session_state["historial"]

                # Cotización individual (sin mostrar detalle)
                st.success(
                    f"""**Cotización**
- Cliente: {cotizacion['Cliente']}
- Servicio: {cotizacion['Servicio']}
- Origen: {cotizacion['Origen']}
- Destino: {cotizacion['Destino']}
- Distancia: {cotizacion['Distancia (km)']:.2f} km
- Tipo de unidad: {cotizacion['Tipo de unidad']}
- Peso/Volumen: {cotizacion['Peso/Vol (Ton)']}
- Volumen (m3): {cotizacion['Volumen (m3)']}
- Costo total: ${cotizacion['Costo Total MXN']:,.2f}
- Observaciones: {cotizacion['Observaciones']}
- Fecha de servicio: {cotizacion['Fecha de servicio']}
"""
                )

                cotizacion_df = pd.DataFrame([cotizacion])
                st.dataframe(cotizacion_df.drop(columns=["Detalle"]))

                # Botón para descargar PDF de la cotización individual
                pdf_path = generar_pdf(cotizacion)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="Descargar cotización en PDF",
                        data=f,
                        file_name=f"cotizacion_{cotizacion['Cliente'].replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                os.remove(pdf_path)

                # Botón para bajar el Excel de la cotización individual
                output = io.BytesIO()
                cotizacion_df.drop(columns=["Detalle"]).to_excel(output, index=False, engine='openpyxl')
                st.download_button(
                    label="Descargar cotización en Excel",
                    data=output.getvalue(),
                    file_name="cotizacion.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    st.markdown("---")
    st.subheader("Historial de cotizaciones (de esta sesión)")
    if historial:
        df_hist = pd.DataFrame(historial)
        st.dataframe(df_hist)
        output_hist = io.BytesIO()
        df_hist.to_excel(output_hist, index=False, engine='openpyxl')
        st.download_button(
            label="Descargar historial en Excel",
            data=output_hist.getvalue(),
            file_name="historial_cotizaciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Aún no hay cotizaciones en esta sesión.")

    st.markdown("---")
    st.markdown(
        """
        <small>
        Desarrollado con IA para Eggarzon. Contacto: eggarzon@gmail.com
        </small>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
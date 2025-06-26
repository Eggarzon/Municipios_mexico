
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
from math import radians, sin, cos, sqrt, atan2
import io
from datetime import datetime
from fpdf import FPDF

CSV_FILENAME = "municipios_mexico.csv"

TARIFAS_LTL = [
    (0, 400, 2000),
    (401, 900, 3500),
    (901, 1300, 5900),
    (1301, 1700, 7800),
    (1701, 1999, 8999),
    (2000, float('inf'), 10500)
]

@st.cache_data
def load_municipios(filename):
    try:
        df = pd.read_csv(filename, encoding="utf-8", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(filename, encoding="latin1", dtype=str)
    df['Longitud'] = df['Longitud'].astype(float)
    df['Latitud'] = df['Latitud'].astype(float)
    return df

def calcular_distancia(df, origen, destino):
    ciudad_o, estado_o = origen.rsplit(" (", 1)
    ciudad_d, estado_d = destino.rsplit(" (", 1)
    ciudad_o = ciudad_o.strip()
    estado_o = estado_o.replace(")", "").strip()
    ciudad_d = ciudad_d.strip()
    estado_d = estado_d.replace(")", "").strip()
    coord_o = tuple(df[(df['Ciudad'] == ciudad_o) & (df['Estado'] == estado_o)][['Latitud', 'Longitud']].iloc[0])
    coord_d = tuple(df[(df['Ciudad'] == ciudad_d) & (df['Estado'] == estado_d)][['Latitud', 'Longitud']].iloc[0])
    distancia = geodesic(coord_o, coord_d).kilometers
    return distancia, ciudad_o, estado_o, ciudad_d, estado_d

def obtener_tarifa_LTL(distancia_km):
    for min_km, max_km, tarifa in TARIFAS_LTL:
        if min_km <= distancia_km <= max_km:
            return tarifa
    return TARIFAS_LTL[-1][2]

def calcular_costo_LTL(distancia_km, largo_cm, ancho_cm, alto_cm):
    volumen_cm3 = largo_cm * ancho_cm * alto_cm
    volumen_m3 = volumen_cm3 / 1_000_000
    tarifa_m3 = obtener_tarifa_LTL(distancia_km)
    costo = volumen_m3 * tarifa_m3
    return round(costo, 2), volumen_cm3, tarifa_m3

def generar_pdf(cotizacion):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, "Cotización de Servicio de Transporte", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    for key, value in cotizacion.items():
        pdf.cell(200, 10, f"{key}: {value}", ln=True)
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

def main():
    st.set_page_config(page_title="Cotizador de Transporte México", layout="centered")
    st.title("Cotizador de Transporte México")

    df = load_municipios(CSV_FILENAME)

    with st.form("cotizador_form"):
        st.subheader("Datos del servicio")
        tipo_servicio = st.selectbox("Tipo de servicio", ["Flete completo (FTL)", "Flete consolidado (LTL)", "Mudanza"])
        col1, col2 = st.columns(2)
        with col1:
            origen = st.selectbox("Municipio de origen", df['Ciudad'] + " (" + df['Estado'] + ")", key="origen")
        with col2:
            destino = st.selectbox("Municipio de destino", df['Ciudad'] + " (" + df['Estado'] + ")", key="destino")

        detalle_servicio = st.text_area("Detalle del servicio")

        if tipo_servicio == "Flete consolidado (LTL)":
            largo = st.number_input("Largo (cm)", min_value=1)
            ancho = st.number_input("Ancho (cm)", min_value=1)
            alto = st.number_input("Alto (cm)", min_value=1)
        else:
            peso_vol = st.number_input("Peso/Volumen estimado (Toneladas)", min_value=0.01, max_value=10.0, value=1.0, step=0.01)

        fecha_servicio = st.date_input("Fecha de servicio", value=datetime.today())
        submitted = st.form_submit_button("Cotizar")

    if submitted and origen != destino:
        distancia, ciudad_o, estado_o, ciudad_d, estado_d = calcular_distancia(df, origen, destino)
        if tipo_servicio == "Flete consolidado (LTL)":
            costo, volumen_cm3, tarifa_m3 = calcular_costo_LTL(distancia, largo, ancho, alto)
            unidad = "LTL por volumen"
        elif tipo_servicio == "Mudanza":
            unidad = "Mudanza"
            costo = 3500 + distancia * 9
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
            else:
                costo = tarifas_banderazo[unidad] + (distancia - 50) * tarifas_km[unidad]

        cotizacion = {
            "Fecha cotización": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "Servicio": tipo_servicio,
            "Origen": f"{ciudad_o} ({estado_o})",
            "Destino": f"{ciudad_d} ({estado_d})",
            "Distancia (km)": round(distancia, 2),
            "Tipo de unidad": unidad,
            "Costo Total MXN": round(costo, 2),
            "Detalle": detalle_servicio,
            "Fecha de servicio": fecha_servicio.strftime("%Y-%m-%d"),
        }

        st.success("Cotización generada:")
        st.json(cotizacion)

        pdf_file = generar_pdf(cotizacion)
        st.download_button("Descargar cotización en PDF", data=pdf_file, file_name="cotizacion.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()

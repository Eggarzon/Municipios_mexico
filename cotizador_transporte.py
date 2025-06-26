import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
import os
from geopy.distance import geodesic

# Leer el archivo de municipios con codificación correcta
df_municipios = pd.read_csv("municipios.csv", encoding="utf-8")  # <- aquí se corrige el problema de caracteres

# ===================== FUNCIONES ==========================

# Calcular distancia entre dos municipios usando latitud y longitud
def obtener_distancia(origen, destino):
    lat1, lon1 = df_municipios.loc[df_municipios['municipio'] == origen, ['latitud', 'longitud']].values[0]
    lat2, lon2 = df_municipios.loc[df_municipios['municipio'] == destino, ['latitud', 'longitud']].values[0]
    return geodesic((lat1, lon1), (lat2, lon2)).km

# Calcular tarifa por distancia
rangos_precio = [
    (0, 400, 2000),
    (401, 900, 3500),
    (901, 1300, 5900),
    (1301, 1700, 7800),
    (1701, 1999, 8999),
    (2000, float('inf'), 10500)
]

def obtener_tarifa_por_mt3(distancia):
    for r in rangos_precio:
        if r[0] <= distancia <= r[1]:
            return r[2]

# Generar PDF con nombre del cliente y fecha
def generar_pdf(cotizacion):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for clave, valor in cotizacion.items():
        pdf.cell(200, 10, txt=f"{clave}: {valor}", ln=True)

    nombre_cliente = cotizacion.get("Cliente", "cliente_desconocido").replace(" ", "_")
    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"cotizacion_{nombre_cliente}_{fecha}.pdf"

    ruta_pdf = os.path.join("PDF_Cotizaciones", nombre_archivo)
    os.makedirs("PDF_Cotizaciones", exist_ok=True)

    pdf.output(ruta_pdf)
    return ruta_pdf

# Guardar cotización en Excel por día
def guardar_en_excel(cotizacion):
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    nombre_archivo = f"BaseCotizaciones/cotizaciones_{fecha_hoy}.xlsx"
    os.makedirs("BaseCotizaciones", exist_ok=True)

    df_nueva = pd.DataFrame([cotizacion])

    if os.path.exists(nombre_archivo):
        df_existente = pd.read_excel(nombre_archivo)
        df_total = pd.concat([df_existente, df_nueva], ignore_index=True)
    else:
        df_total = df_nueva

    df_total.to_excel(nombre_archivo, index=False)
    return nombre_archivo

# ===================== APP STREAMLIT ==========================

def main():
    st.title("Cotizador de Transporte")

    cliente = st.text_input("Nombre del cliente")
    origen = st.selectbox("Municipio de origen", df_municipios['municipio'].unique())
    destino = st.selectbox("Municipio de destino", df_municipios['municipio'].unique())
    tipo_flete = st.radio("Tipo de flete", ["FTL (Completo)", "LTL (Consolidado)"])

    largo = st.number_input("Largo (cm)", min_value=1)
    ancho = st.number_input("Ancho (cm)", min_value=1)
    alto = st.number_input("Alto (cm)", min_value=1)

    if st.button("Calcular cotización"):
        volumen_cm3 = largo * ancho * alto
        volumen_mt3 = volumen_cm3 / 1_000_000

        distancia_km = obtener_distancia(origen, destino)
        tarifa_mt3 = obtener_tarifa_por_mt3(distancia_km)

        if tipo_flete == "FTL (Completo)":
            costo_total = tarifa_mt3
        else:
            costo_total = volumen_mt3 * tarifa_mt3

        cotizacion = {
            "Cliente": cliente,
            "Origen": origen,
            "Destino": destino,
            "Distancia (km)": round(distancia_km, 2),
            "Tipo de Flete": tipo_flete,
            "Volumen (m3)": round(volumen_mt3, 4),
            "Tarifa x m3": tarifa_mt3,
            "Costo Total": round(costo_total, 2),
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        st.success("Cotización generada exitosamente.")
        st.write(cotizacion)

        ruta_pdf = generar_pdf(cotizacion)
        guardar_en_excel(cotizacion)

        with open(ruta_pdf, "rb") as f:
            st.download_button("Descargar PDF", data=f, file_name=os.path.basename(ruta_pdf), mime="application/pdf")

if __name__ == "__main__":
    main()

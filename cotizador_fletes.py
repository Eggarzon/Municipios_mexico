import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import os
import unicodedata
from fpdf import FPDF

# -------------------- Funciones -------------------- #
def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(R * c, 2)

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

def cotizar_servicio(distancia, peso_vol):
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
    return unidad, round(costo, 2), detalle

def generar_pdf(nombre_cliente, servicio, origen, destino, distancia, costo, detalle, observaciones):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Cotización de Transporte", ln=True, align="C")
    pdf.ln(10)

    pdf.cell(200, 10, txt=f"Cliente: {nombre_cliente}", ln=True)
    pdf.cell(200, 10, txt=f"Servicio: {servicio}", ln=True)
    pdf.cell(200, 10, txt=f"Origen: {origen}", ln=True)
    pdf.cell(200, 10, txt=f"Destino: {destino}", ln=True)
    pdf.cell(200, 10, txt=f"Distancia: {distancia} km", ln=True)
    pdf.cell(200, 10, txt=f"Costo estimado: ${costo:,.2f}", ln=True)
    pdf.multi_cell(200, 10, txt=f"Detalle: {detalle}")
    pdf.ln(5)
    pdf.multi_cell(200, 10, txt=f"Observaciones: {observaciones}")

    filename = f"cotizacion_{nombre_cliente.replace(' ', '_')}.pdf"
    pdf.output(filename)
    return filename

def guardar_excel(cotizacion, archivo='historial_cotizaciones.xlsx'):
    columnas = ["Fecha", "Cliente", "Servicio", "Origen", "Destino", "Distancia_km", "Costo", "Detalle", "Observaciones"]
    nueva_fila = pd.DataFrame([cotizacion], columns=columnas)

    if os.path.exists(archivo):
        df_existente = pd.read_excel(archivo)
        df_final = pd.concat([df_existente, nueva_fila], ignore_index=True)
    else:
        df_final = nueva_fila

    df_final.to_excel(archivo, index=False)

def normaliza(texto):
    if pd.isna(texto):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower()

# -------------------- Carga de Datos -------------------- #
df_municipios = pd.read_csv("municipios_mexico.csv", encoding='utf-8')
df_municipios.rename(columns={
    'Estado': 'estado',
    'Ciudad': 'municipio',
    'Longitud': 'longitud',
    'Latitud': 'latitud'
}, inplace=True)

# -------------------- Ejemplo de Uso -------------------- #
if __name__ == '__main__':
    nombre_cliente = input("Nombre del cliente: ")
    servicio = input("Servicio (FTL / LTL / Mudanza): ").strip().upper()
    origen = input("Municipio de origen: ").strip()
    destino = input("Municipio de destino: ").strip()

    origen_norm = normaliza(origen)
    destino_norm = normaliza(destino)

    datos_origen = df_municipios[df_municipios['municipio'].apply(normaliza) == origen_norm]
    datos_destino = df_municipios[df_municipios['municipio'].apply(normaliza) == destino_norm]

    if datos_origen.empty or datos_destino.empty:
        print("Error: municipio no encontrado.")
        exit()

    lat1, lon1 = datos_origen.iloc[0][['latitud', 'longitud']]
    lat2, lon2 = datos_destino.iloc[0][['latitud', 'longitud']]
    distancia = calcular_distancia(float(lat1), float(lon1), float(lat2), float(lon2))

    detalle = ""
    costo = 0

    if servicio == "FTL" or servicio == "MUDANZA":
        peso_vol = float(input("Ingresa el peso/volumen estimado en toneladas: "))
        unidad, costo, detalle = cotizar_servicio(distancia, peso_vol)
        if servicio == "MUDANZA":
            maniobras = float(input("Costo adicional por maniobras ($): "))
            costo += maniobras
            detalle += f" + ${maniobras:.2f} por maniobras"

    elif servicio == "LTL":
        largo = float(input("Largo (cm): "))
        ancho = float(input("Ancho (cm): "))
        alto = float(input("Alto (cm): "))
        volumen_cm3 = largo * ancho * alto
        volumen_m3 = volumen_cm3 / 1_000_000
        tarifa_m3 = obtener_tarifa_por_distancia(distancia)
        costo = round(volumen_m3 * tarifa_m3, 2)
        detalle = f"{volumen_m3:.4f} m3 x ${tarifa_m3:,.2f}/m3"

    observaciones = input("Observaciones del servicio: ")

    cotizacion = [
        datetime.today().strftime('%Y-%m-%d'),
        nombre_cliente,
        servicio,
        origen,
        destino,
        distancia,
        costo,
        detalle,
        observaciones
    ]

    guardar_excel(cotizacion)
    archivo_pdf = generar_pdf(nombre_cliente, servicio, origen, destino, distancia, costo, detalle, observaciones)
    print(f"Cotización guardada en Excel y exportada a PDF como: {archivo_pdf}")

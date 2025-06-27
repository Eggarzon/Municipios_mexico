import pandas as pd
import streamlit as st
from geopy.distance import geodesic
import io
from datetime import datetime
import unicodedata

CSV_FILENAME = "municipios_mexico.csv"  # Cambia si tu archivo tiene otro nombre

def normaliza(texto):
    # Normaliza texto para búsquedas insensibles a mayúsculas y acentos
    if pd.isna(texto):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower().strip()

@st.cache_data
def load_municipios(filename):
    try:
        df = pd.read_csv(filename, encoding="utf-8", dtype={"Estado":str, "Ciudad":str})
    except UnicodeDecodeError:
        df = pd.read_csv(filename, encoding="latin1", dtype={"Estado":str, "Ciudad":str})
    # Convierte coordenadas a float si no lo están ya
    df['Longitud'] = df['Longitud'].astype(float)
    df['Latitud'] = df['Latitud'].astype(float)
    return df

def calcular_distancia(df, origen, destino):
    ciudad_o, estado_o = origen.rsplit(" (", 1)
    ciudad_d, estado_d = destino.rsplit(" (", 1)
    ciudad_o, estado_o = normaliza(ciudad_o), normaliza(estado_o.replace(")", ""))
    ciudad_d, estado_d = normaliza(ciudad_d), normaliza(estado_d.replace(")", ""))
    # Busca municipio y estado normalizados
    row_o = df[(df['Ciudad'].apply(normaliza)==ciudad_o) & (df['Estado'].apply(normaliza)==estado_o)]
    row_d = df[(df['Ciudad'].apply(normaliza)==ciudad_d) & (df['Estado'].apply(normaliza)==estado_d)]
    if row_o.empty or row_d.empty:
        return None, None, None, None, None
    coord_o = tuple(row_o[['Latitud', 'Longitud']].iloc[0])
    coord_d = tuple(row_d[['Latitud', 'Longitud']].iloc[0])
    distancia = geodesic(coord_o, coord_d).kilometers
    return distancia, row_o.iloc[0]['Ciudad'], row_o.iloc[0]['Estado'], row_d.iloc[0]['Ciudad'], row_d.iloc[0]['Estado']

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
            f"{(distancia-50):.2f} km x ${tarifas_km[unidad]:,.2f}/km"
        )
    return unidad, round(costo, 2), detalle

def main():
    st.set_page_config(page_title="Cotizador de Fletes México", layout="centered")
    st.title("Cotizador de Fletes México por Municipio")
    st.markdown("Selecciona municipio de origen, destino y peso/volumen para cotizar tu flete.")

    df = load_municipios(CSV_FILENAME)

    with st.form("cotizador_form"):
        municipio_opciones = df['Ciudad'] + " (" + df['Estado'] + ")"
        col1, col2 = st.columns(2)
        with col1:
            origen = st.selectbox("Municipio de origen", municipio_opciones, key="origen")
        with col2:
            destino = st.selectbox("Municipio de destino", municipio_opciones, key="destino")
        peso_vol = st.number_input("Peso/Volumen estimado (Toneladas)", min_value=0.01, max_value=10.0, value=1.0, step=0.01)
        fecha_servicio = st.date_input("Fecha de servicio", value=datetime.today())
        submitted = st.form_submit_button("Cotizar")

    historial = st.session_state.get("historial", [])

    if submitted:
        if origen == destino:
            st.error("El municipio de origen y destino deben ser diferentes.")
        else:
            distancia, ciudad_o, estado_o, ciudad_d, estado_d = calcular_distancia(df, origen, destino)
            if distancia is None:
                st.error("No se encontró alguno de los municipios en la base de datos.")
            else:
                unidad, costo, detalle = cotizar_servicio(distancia, peso_vol)
                cotizacion = {
                    "Fecha cotización": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "Origen": f"{ciudad_o} ({estado_o})",
                    "Destino": f"{ciudad_d} ({estado_d})",
                    "Distancia (km)": round(distancia, 2),
                    "Tipo de unidad": unidad,
                    "Peso/Vol (Ton)": peso_vol,
                    "Costo Total MXN": round(costo, 2),
                    "Detalle": detalle,
                    "Fecha de servicio": fecha_servicio.strftime("%Y-%m-%d"),
                }
                if "historial" not in st.session_state:
                    st.session_state["historial"] = []
                st.session_state["historial"].append(cotizacion)
                historial = st.session_state["historial"]

                st.success(
                    f"""**Cotización**
- Origen: {cotizacion['Origen']}
- Destino: {cotizacion['Destino']}
- Distancia: {cotizacion['Distancia (km)']:.2f} km
- Tipo de unidad: {cotizacion['Tipo de unidad']}
- Peso/Volumen: {cotizacion['Peso/Vol (Ton)']:.2f} Ton
- Costo total: ${cotizacion['Costo Total MXN']:,.2f}
- Detalle: {cotizacion['Detalle']}
- Fecha de servicio: {cotizacion['Fecha de servicio']}
"""
                )

                cotizacion_df = pd.DataFrame([cotizacion])
                st.dataframe(cotizacion_df)

                # Botón para bajar el Excel de la cotización individual
                output = io.BytesIO()
                cotizacion_df.to_excel(output, index=False, engine='openpyxl')
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
        # Exportar historial completo
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
        Desarrollado por Eggarzon con IA. Contacto: eggarzon@gmail.com
        </small>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

import pandas as pd
import streamlit as st
from geopy.distance import geodesic
import io
from datetime import datetime

CSV_FILENAME = "municipios_mexico.csv"  # Asegúrate que este sea el nombre de tu archivo actualizado

@st.cache_data
def load_municipios(filename):
    # Lee el archivo con los nombres de columna correctos y sin geocoding
    # Asegura que las columnas se lean como texto (por si hay números con ceros a la izquierda)
    try:
        df = pd.read_csv(filename, encoding="utf-8", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(filename, encoding="latin1", dtype=str)
    # Convierte columnas de coordenadas a float
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

def cotizar_servicio(distancia, peso_vol):
    # Determinar tipo de unidad
    if peso_vol <= 1:
        unidad = "1 Ton"
    elif peso_vol <= 3:
        unidad = "3 Ton"
    elif peso_vol <= 5:
        unidad = "5 Ton"
    else:
        unidad = "10 Ton"

    # Tarifas y banderazo
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
    return unidad, costo, detalle

def main():
    st.set_page_config(page_title="Cotizador de Transporte México", layout="centered")
    st.title("Cotizador de Transporte México")
    st.markdown(
        """
        Cotiza servicio seleccionando el municipio de origen, destino y el peso/volumen estimado de la carga.
        \nEl sistema considera banderazo para viajes ≤ 50km y costo por km extra según el tipo de unidad.
        """
    )

    df = load_municipios(CSV_FILENAME)

    with st.form("cotizador_form"):
        col1, col2 = st.columns(2)
        with col1:
            origen = st.selectbox(
                "Municipio de origen",
                df['Ciudad'] + " (" + df['Estado'] + ")", key="origen"
            )
        with col2:
            destino = st.selectbox(
                "Municipio de destino",
                df['Ciudad'] + " (" + df['Estado'] + ")", key="destino"
            )
        peso_vol = st.number_input("Peso/Volumen estimado (Toneladas)", min_value=0.01, max_value=10.0, value=1.0, step=0.01)
        fecha_servicio = st.date_input("Fecha de servicio", value=datetime.today())
        submitted = st.form_submit_button("Cotizar")

    historial = st.session_state.get("historial", [])

    if submitted and origen != destino:
        distancia, ciudad_o, estado_o, ciudad_d, estado_d = calcular_distancia(df, origen, destino)
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
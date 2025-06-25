import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import os

CSV_FILENAME = "capitales_mexico.csv"
CACHE_FILENAME = "capitales_coord.csv"

def get_coordinates(city, state, geolocator, cache):
    key = f"{city},{state}"
    if key in cache:
        return cache[key]
    try:
        location = geolocator.geocode(f"{city}, {state}, Mexico", timeout=10)
        if location:
            lat, lon = location.latitude, location.longitude
            cache[key] = (lat, lon)
            return lat, lon
    except Exception:
        # Retry after brief pause
        time.sleep(1)
        location = geolocator.geocode(f"{city}, {state}, Mexico", timeout=10)
        if location:
            lat, lon = location.latitude, location.longitude
            cache[key] = (lat, lon)
            return lat, lon
    return None, None

@st.cache_data
def load_cities_with_coords(filename, cache_filename):
    df = pd.read_csv(filename)
    geolocator = Nominatim(user_agent="mexico_capitals_locator")
    cache = {}

    # If cache file exists, load it
    if os.path.exists(cache_filename):
        cachedf = pd.read_csv(cache_filename)
        for _, row in cachedf.iterrows():
            cache[f"{row['Ciudad']},{row['Estado']}"] = (row['Latitud'], row['Longitud'])

    latitudes = []
    longitudes = []
    for idx, row in df.iterrows():
        city, state = row['Ciudad'], row['Estado']
        lat, lon = get_coordinates(city, state, geolocator, cache)
        latitudes.append(lat)
        longitudes.append(lon)
        time.sleep(1)  # Para evitar bloqueo del servicio

    df['Latitud'] = latitudes
    df['Longitud'] = longitudes

    # Guardar cache actualizado
    pd.DataFrame([
        {"Estado": row['Estado'], "Ciudad": row['Ciudad'], "Latitud": lat, "Longitud": lon}
        for row, lat, lon in zip(df.itertuples(), latitudes, longitudes)
    ]).to_csv(cache_filename, index=False)

    return df

def calcular_distancias(df, ciudad_base="Guadalajara", estado_base="Jalisco"):
    base = df[(df['Ciudad'] == ciudad_base) & (df['Estado'] == estado_base)].iloc[0]
    base_coord = (base['Latitud'], base['Longitud'])
    distancias = []
    for idx, row in df.iterrows():
        coord = (row['Latitud'], row['Longitud'])
        if None in coord or None in base_coord:
            distancias.append(None)
        else:
            dist = geodesic(base_coord, coord).kilometers
            distancias.append(round(dist, 2))
    df['Distancia_desde_Guadalajara_km'] = distancias
    return df

def main():
    st.title("Distancias desde Guadalajara a Capitales de México")
    st.markdown("Esta app calcula la distancia en línea recta (geodésica) desde Guadalajara a las capitales de los 32 estados de México.")

    df = load_cities_with_coords(CSV_FILENAME, CACHE_FILENAME)
    df = calcular_distancias(df)
    df_sorted = df.sort_values("Distancia_desde_Guadalajara_km")

    st.write("Selecciona una o varias ciudades para ver la distancia desde Guadalajara:")
    ciudades_sel = st.multiselect(
        "Ciudades:", df_sorted["Ciudad"] + " (" + df_sorted["Estado"] + ")"
    )

    if ciudades_sel:
        estados_ciudades = [x.split(" (") for x in ciudades_sel]
        filtro = [
            (row['Ciudad'] == ciudad) and (row['Estado'] == estado[:-1])
            for _, row in df_sorted.iterrows()
            for ciudad, estado in estados_ciudades
        ]
        st.dataframe(df_sorted[[ 'Estado', 'Ciudad', 'Distancia_desde_Guadalajara_km']][filtro])
    else:
        st.dataframe(df_sorted[['Estado','Ciudad','Distancia_desde_Guadalajara_km']])

    st.markdown("Puedes descargar la tabla completa como Excel:")
    excel = df_sorted.to_excel(index=False, engine='openpyxl')
    st.download_button(
        label="Descargar Excel",
        data=excel,
        file_name="distancias_capitales_mexico.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    main()
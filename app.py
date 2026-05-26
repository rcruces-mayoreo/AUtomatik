import streamlit as st
import pandas as pd
import unicodedata

# Configuración de la página
st.set_page_config(page_title="Conciliador Bancario", layout="wide")

def limpiar_texto(texto):
    if pd.isna(texto):
        return ""
    # Convertir a string, quitar espacios, minúsculas y eliminar acentos
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

st.title("📑 Conciliador Automático: CB vs CG")
st.markdown("Sube los archivos para procesar la conciliación de créditos y débitos.")

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    file_cb = st.file_uploader("Subir archivo CB (Control Bancario)", type=['xlsx', 'csv'])
with col2:
    file_cg = st.file_uploader("Subir archivo CG (Contabilidad General)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    # Leer archivos (soporta Excel y CSV)
    df_cb = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
    df_cg = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

    try:
        # --- PROCESAMIENTO CB ---
        # Usamos Beneficiario (Columna E) y Créditos
        # Ajustamos los nombres de columnas a lo que Pandas suele leer
        df_cb['beneficiario_match'] = df_cb.iloc[:, 4].apply(limpiar_texto) # Columna E (índice 4)
        df_cb['monto_match'] = df_cb.iloc[:, 7] # Asumiendo Crédito está en columna H, ajustar si varía

        # --- PROCESAMIENTO CG ---
        # Buscamos en Débito Bolívar o Local (ajustado a nombres comunes)
        # Aquí buscamos el nombre en la columna que corresponda a Beneficiario en CG
        df_cg['nombre_cg_match'] = df_cg['Beneficiario'].apply(limpiar_texto) 
        df_cg['monto_cg_match'] = df_cg['Debito Local']

        # --- CONCILIACIÓN ---
        # Cruzamos donde el Crédito de CB sea igual al Débito de CG y el nombre coincida
        conciliados = pd.merge(
            df_cb, 
            df_cg, 
            left_on=['beneficiario_match', 'monto_match'],
            right_on=['nombre_cg_match', 'monto_cg

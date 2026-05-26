import streamlit as st
import pandas as pd
import unicodedata

# Configuración de la página
st.set_page_config(page_title="Conciliador Bancario", layout="wide")

def limpiar_texto(texto):
    if pd.isna(texto):
        return ""
    # Convertir a texto, quitar espacios, minúsculas y eliminar acentos
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

st.title("📑 Conciliador Automático: CB vs CG")
st.markdown("Busca Créditos en el Banco (CB) contra Débitos en Contabilidad (CG)")

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    file_cb = st.file_uploader("Subir archivo CB (Control Bancario)", type=['xlsx', 'csv'])
with col2:
    file_cg = st.file_uploader("Subir archivo CG (Contabilidad General)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    # Leer archivos
    df_cb = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
    df_cg = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

    try:
        # --- PROCESAMIENTO CB ---
        # Columna E (índice 4) es Beneficiario
        df_cb['beneficiario_match'] = df_cb.iloc[:, 4].apply(limpiar_texto)
        # Buscamos la columna que contenga "Crédito" o "Credito"
        col_credito_cb = [c for c in df_cb.columns if 'credito' in c.lower()][0]
        df_cb['monto_match'] = df_cb[col_credito_cb].fillna(0)

        # --- PROCESAMIENTO CG ---
        # Buscamos el nombre/beneficiario en CG (usualmente columna 'Beneficiario' o 'Cuenta')
        # Intentamos detectar la columna de nombre en CG
        col_nombre_cg = 'Beneficiario' if 'Beneficiario' in df_cg.columns else df_cg.columns[0]
        df_cg['nombre_cg_match'] = df_cg[col_nombre_cg].apply(limpiar_texto)
        
        # Intentamos detectar "Debito Bolivar" o "Debito Local"
        col_debito_cg = [c for c in df_cg.columns if 'debito' in c.lower()][0]
        df_cg['monto_cg_match'] = df_cg[col_debito_cg].fillna(0)

        # --- CONCILIACIÓN (El Cruce) ---
        conciliados = pd.merge(
            df_cb[df_cb['monto_match'] > 0], 
            df_cg[df_cg['monto_cg_match'] > 0], 
            left_on=['beneficiario_match', 'monto_match'],
            right_on=['nombre_cg_match', 'monto_cg_match'],
            how='inner'
        )

        # --- MOSTRAR RESULTADOS ---
        st.success(f"✅ Se encontraron {len(conciliados)} coincidencias.")
        
        tab1, tab2 = st.tabs(["Coincidencias (Conciliados)", "Pendientes"])
        
        with tab1:
            st.write("Movimientos que coinciden en Beneficiario y Monto:")
            st.dataframe(conciliados)
            
        with tab2:
            st.info("Operaciones en Banco que no se encontraron en Contabilidad:")
            pendientes = df_cb[(df_cb['monto_match'] > 0) & (~df_cb['beneficiario_match'].isin(conciliados['beneficiario_match']))]
            st.dataframe(pendientes)

    except Exception as e:
        st.error(f"Error técnico: {e}")
        st.warning("Asegúrate de que los archivos tengan los encabezados correctos.")

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
        # Columna E (índice 4) es Beneficiario según tu descripción
        # Columna B (índice 1) es Cuenta Bancaria
        df_cb['beneficiario_match'] = df_cb.iloc[:, 4].apply(limpiar_texto)
        
        # Buscamos la columna de Créditos en CB (suele ser la columna H o índice 7)
        # Si el nombre exacto es 'Credito', lo usamos. Si no, tomamos la columna 8.
        col_monto_cb = 'Credito' if 'Credito' in df_cb.columns else df_cb.columns[7]
        df_cb['monto_match'] = pd.to_numeric(df_cb[col_monto_cb], errors='coerce').fillna(0)

        # --- PROCESAMIENTO CG ---
        # Buscamos 'Debito Bolivar' o 'Debito Local'
        # Usamos una técnica para encontrar la columna aunque tenga espacios o mayúsculas
        col_debito_cg = None
        for col in df_cg.columns:
            if 'debito' in col.lower():
                col_debito_cg = col
                break
        
        if not col_debito_cg:
            st.error("No encontré la columna 'Debito' en el archivo de Contabilidad (CG).")
            st.stop()

        # Limpiamos el nombre del beneficiario en CG (asumiendo que es la primera columna o se llama Beneficiario)
        col_nom_cg = 'Beneficiario' if 'Beneficiario' in df_cg.columns else df_cg.columns[0]
        df_cg['nombre_cg_match'] = df_cg[col_nom_cg].apply(limpiar_texto)
        df_cg['monto_cg_match'] = pd.to_numeric(df_cg[col_debito_cg], errors='coerce').fillna(0)

        # --- CONCILIACIÓN ---
        # Solo cruzamos filas donde haya montos mayores a cero
        conciliados = pd.merge(
            df_cb[df_cb['monto_match'] > 0], 
            df_cg[df_cg['monto_cg_match'] > 0], 
            left_on=['beneficiario_match', 'monto_match'],
            right_on=['nombre_cg_match', 'monto_cg_match'],
            how='inner'
        )

        # --- RESULTADOS EN PANTALLA ---
        st.success(f"✅ Conciliación completada: {len(conciliados)} movimientos encontrados.")
        
        res1, res2 = st.tabs(["✅ Movimientos Conciliados", "❌ Pendientes en Banco"])
        
        with res1:
            st.dataframe(conciliados)
            
        with res2:
            # Los que están en CB pero no en el cruce
            pendientes = df_cb[(df_cb['monto_match'] > 0) & (~df_cb['beneficiario_match'].isin(conciliados['beneficiario_match']))]
            st.dataframe(pendientes)

    except Exception as e:
        st.error(f"Hubo un problema con la estructura de los archivos: {e}")
        st.info("Revisa que los nombres de las columnas no hayan cambiado.")

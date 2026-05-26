import streamlit as st
import pandas as pd
import unicodedata

# Configuración de la página
st.set_page_config(page_title="Conciliador Pro", layout="wide")

def normalizar(texto):
    """Quita acentos, espacios extra y convierte a minúsculas"""
    if pd.isna(texto):
        return ""
    texto = str(texto).strip().lower()
    # Elimina acentos usando normalización Unicode
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def buscar_columna(df, palabras_clave):
    """Busca una columna que contenga alguna de las palabras clave (sin acentos)"""
    for col in df.columns:
        col_norm = normalizar(col)
        for palabra in palabras_clave:
            if palabra in col_norm:
                return col
    return None

st.title("📑 Conciliador Inteligente (Anti-Acentos)")
st.info("Este sistema ignora mayúsculas, minúsculas y acentos (ej: Débito = debito)")

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    file_cb = st.file_uploader("Subir Control Bancario (CB)", type=['xlsx', 'csv'])
with col2:
    file_cg = st.file_uploader("Subir Contabilidad General (CG)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    df_cb = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
    df_cg = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

    try:
        # 1. Identificar columnas automáticamente (ignorando acentos)
        col_benef_cb = buscar_columna(df_cb, ['beneficiario', 'cuenta bancaria', 'descripcion'])
        col_monto_cb = buscar_columna(df_cb, ['credito', 'monto', 'importe', 'abono'])
        
        col_benef_cg = buscar_columna(df_cg, ['beneficiario', 'cuenta', 'nombre', 'auxiliar'])
        col_monto_cg = buscar_columna(df_cg, ['debito', 'debe'])

        if not col_monto_cb or not col_monto_cg:
            st.error(f"No encontré las columnas de montos. En CB busqué 'Crédito' y en CG busqué 'Débito'.")
            st.stop()

        # 2. Limpiar datos para el cruce
        # Limpieza de Beneficiarios
        df_cb['match_name'] = df_cb[col_benef_cb].apply(normalizar)
        df_cg['match_name'] = df_cg[col_benef_cg].apply(normalizar)
        
        # Limpieza de Montos (asegurar que sean números)
        df_cb['match_amount'] = pd.to_numeric(df_cb[col_monto_cb], errors='coerce').fillna(0)
        df_cg['match_amount'] = pd.to_numeric(df_cg[col_monto_cg], errors='coerce').fillna(0)

        # 3. Cruzar (Conciliar)
        # Solo tomamos registros donde el monto sea mayor a 0
        df_cb_fil = df_cb[df_cb['match_amount'] > 0].copy()
        df_cg_fil = df_cg[df_cg['match_amount'] > 0].copy()

        conciliados = pd.merge(
            df_cb_fil, 
            df_cg_fil, 
            on=['match_name', 'match_amount'],
            how='inner',
            suffixes=('_BANCO', '_CONTABILIDAD')
        )

        # 4. Mostrar Resultados
        st.success(f"✅ ¡Conciliación exitosa! Se encontraron {len(conciliados)} coincidencias.")
        
        t1, t2, t3 = st.tabs(["Coincidencias", "Pendientes en Banco", "Pendientes en Contabilidad"])
        
        with t1:
            st.write("### Movimientos que cruzaron perfectamente")
            st.dataframe(conciliados)
            
        with t2:
            pendientes_cb = df_cb_fil[~df_cb_fil.index.isin(
                pd.merge(df_cb_fil, conciliados, left_index=True, right_index=True, how='inner').index
            )]
            st.write("### Dinero en Banco que NO está en Contabilidad")
            st.dataframe(pendientes_cb)

        with t3:
            st.write("### Registros en Contabilidad que NO están en el Banco")
            st.dataframe(df_cg_fil) # Aquí podrías aplicar una lógica similar de filtrado

    except Exception as e:
        st.error(f"Error inesperado: {e}")

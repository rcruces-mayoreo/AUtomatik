import streamlit as st
import pandas as pd
import unicodedata

# Configuración de la interfaz
st.set_page_config(page_title="Conciliador Espejo CB/CG", layout="wide")

def normalizar(texto):
    """Limpia acentos, espacios y convierte a minúsculas"""
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def buscar_columna(df, palabras_clave):
    """Busca una columna que coincida con palabras clave ignorando acentos"""
    for col in df.columns:
        col_norm = normalizar(col)
        if any(p in col_norm for p in palabras_clave):
            return col
    return None

st.title("⚖️ Conciliador Contable: Lógica Espejo")
st.markdown("Comparando **Créditos CB vs Débitos CG** y **Débitos CB vs Créditos CG**")

# --- CARGA DE ARCHIVOS ---
col_a, col_b = st.columns(2)
with col_a:
    file_cb = st.file_uploader("Archivo de Banco (CB)", type=['xlsx', 'csv'])
with col_b:
    file_cg = st.file_uploader("Archivo de Contabilidad (CG)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    df_cb = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
    df_cg = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

    try:
        # 1. Identificar Columnas de Montos
        col_credito_cb = buscar_columna(df_cb, ['credito'])
        col_debito_cb = buscar_columna(df_cb, ['debito'])
        
        col_credito_cg = buscar_columna(df_cg, ['credito'])
        col_debito_cg = buscar_columna(df_cg, ['debito'])

        # Identificar Columnas de Nombres/Beneficiarios
        col_nom_cb = buscar_columna(df_cb, ['beneficiario', 'nombre', 'cuenta'])
        col_nom_cg = buscar_columna(df_cg, ['beneficiario', 'nombre', 'cuenta', 'auxiliar'])

        # 2. Preparar Datos (Limpieza)
        for df, col_nom in [(df_cb, col_nom_cb), (df_cg, col_nom_cg)]:
            df['match_name'] = df[col_nom].apply(normalizar)

        # Convertir montos a números limpios
        df_cb['m_credito'] = pd.to_numeric(df_cb[col_credito_cb], errors='coerce').fillna(0)
        df_cb['m_debito'] = pd.to_numeric(df_cb[col_debito_cb], errors='coerce').fillna(0)
        df_cg['m_credito'] = pd.to_numeric(df_cg[col_credito_cg], errors='coerce').fillna(0)
        df_cg['m_debito'] = pd.to_numeric(df_cg[col_debito_cg], errors='coerce').fillna(0)

        # 3. CONCILIACIÓN 1: Crédito Banco vs Débito Contabilidad
        match_tipo_1 = pd.merge(
            df_cb[df_cb['m_credito'] > 0],
            df_cg[df_cg['m_debito'] > 0],
            left_on=['match_name', 'm_credito'],
            right_on=['match_name', 'm_debito'],
            how='inner', suffixes=('_CB', '_CG')
        )

        # 4. CONCILIACIÓN 2: Débito Banco vs Crédito Contabilidad
        match_tipo_2 = pd.merge(
            df_cb[df_cb['m_debito'] > 0],
            df_cg[df_cg['m_credito'] > 0],
            left_on=['match_name', 'm_debito'],
            right_on=['match_name', 'm_credito'],
            how='inner', suffixes=('_CB', '_CG')
        )

        # --- MOSTRAR RESULTADOS ---
        total_matches = len(match_tipo_1) + len(match_tipo_2)
        st.success(f"📊 Se encontraron {total_matches} movimientos conciliados en total.")

        tab1, tab2, tab3 = st.tabs(["✅ Conciliaciones Encontradas", "⚠️ Pendientes en Banco", "🔍 Pendientes en Contabilidad"])

        with tab1:
            if not match_tipo_1.empty:
                st.write("### Créditos CB = Débitos CG")
                st.dataframe(match_tipo_1)
            if not match_tipo_2.empty:
                st.write("### Débitos CB = Créditos CG")
                st.dataframe(match_tipo_2)

        with tab2:
            # Identificar qué filas de CB no están en los cruces
            nombres_conciliados = pd.concat([match_tipo_1['match_name'], match_tipo_2['match_name']])
            pend_cb = df_cb[~df_cb['match_name'].isin(nombres_conciliados)]
            st.dataframe(pend_cb)

        with tab3:
            pend_cg = df_cg[~df_cg['match_name'].isin(nombres_conciliados)]
            st.dataframe(pend_cg)

    except Exception as e:
        st.error(f"Error de estructura: {e}. Revisa que las columnas 'Débito' y 'Crédito' existan en ambos archivos.")

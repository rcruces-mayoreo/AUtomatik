import streamlit as st
import pandas as pd
import unicodedata
import io
import re

st.set_page_config(page_title="Conciliador SILLACA V6", layout="wide")

def limpiar_referencia(texto):
    """Extrae solo los dígitos de una cadena para comparar números puros"""
    if pd.isna(texto): return ""
    return re.sub(r'\D', '', str(texto))

def a_numero(valor):
    if pd.isna(valor) or str(valor).strip() in ['-', '', 'None']: return 0.0
    try:
        # Convertir a string, quitar puntos de miles y ajustar coma decimal
        s = str(valor).replace(' ', '')
        if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        return round(float(pd.to_numeric(s, errors='coerce')), 2)
    except: return 0.0

def encontrar_tabla(df):
    for i in range(min(15, len(df))):
        fila = [str(x).lower() for x in df.iloc[i].values]
        if 'asiento' in fila or 'referencia' in fila:
            new_df = df.iloc[i+1:].copy()
            new_df.columns = df.iloc[i].values
            return new_df.reset_index(drop=True)
    return df

st.title("⚖️ Conciliador SILLACA - Precisión Numérica")

file_cb = st.file_uploader("📂 Archivo CB (Banco)", type=['xlsx', 'csv'])
file_cg = st.file_uploader("📂 Archivo CG (Contabilidad)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    try:
        df_cb_raw = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
        df_cg_raw = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

        df_cb = encontrar_tabla(df_cb_raw)
        df_cg = encontrar_tabla(df_cg_raw)

        # 1. Identificar columnas con nombres flexibles
        def buscar_col(cols, lista):
            for c in cols:
                if any(p in str(c).lower() for p in lista): return c
            return None

        c_num_cb = buscar_col(df_cb.columns, ['número', 'numero'])
        c_cre_cb = buscar_col(df_cb.columns, ['crédito', 'credito'])
        c_deb_cb = buscar_col(df_cb.columns, ['débito', 'debito'])
        
        c_ref_cg = buscar_col(df_cg.columns, ['referencia'])
        c_dv_cg = buscar_col(df_cg.columns, ['débito ves', 'debito local'])
        c_cv_cg = buscar_col(df_cg.columns, ['crédito ves', 'credito local'])

        # 2. Pre-procesar CG (Limpiar números de referencia)
        df_cg['ref_clean'] = df_cg[c_ref_cg].apply(limpiar_referencia)

        # 3. CRUCE
        resultados = []
        for _, f_cb in df_cb.iterrows():
            # Limpiar el número del banco (quitarle el .0 o los puntos de miles)
            num_banco_puro = limpiar_referencia(f_cb[c_num_cb])
            if not num_banco_puro: continue
            
            m_cre_cb = a_numero(f_cb[c_cre_cb])
            m_deb_cb = a_numero(f_cb[c_deb_cb])
            
            # Lógica Espejo
            if m_cre_cb > 0:
                # Buscamos en CG el número puro y el monto en Débito
                match = df_cg[(df_cg['ref_clean'].str.contains(num_banco_puro)) & 
                              (df_cg[c_dv_cg].apply(a_numero) == m_cre_cb)]
            else:
                # Buscamos en CG el número puro y el monto en Crédito
                match = df_cg[(df_cg['ref_clean'].str.contains(num_banco_puro)) & 
                              (df_cg[c_cv_cg].apply(a_numero) == m_deb_cb)]

            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**f_cb.to_dict(), 'Status': status})

        df_res = pd.DataFrame(resultados)
        st.write("### Vista Previa de Resultados")
        st.dataframe(df_res)
        
        # Exportar a Excel
        output = io.BytesIO()
        df_res.to_excel(output, index=False, engine='openpyxl')
        st.download_button("📥 Descargar Conciliación Final", output.getvalue(), "conciliacion_sillaca_v6.xlsx")

    except Exception as e:
        st.error(f"Error en el proceso: {e}")

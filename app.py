import streamlit as st
import pandas as pd
import unicodedata
import io
import re

st.set_page_config(page_title="Conciliador SILLACA V7", layout="wide")

def extraer_solo_numeros(texto):
    """Extrae el corazón numérico: de 'N/D111060' saca '111060'"""
    if pd.isna(texto): return ""
    res = re.sub(r'\D', '', str(texto))
    # Quitar ceros a la izquierda si los hay para evitar '001' vs '1'
    return res.lstrip('0')

def a_numero(valor):
    """Convierte montos a flotantes de forma ultra-segura"""
    if pd.isna(valor) or str(valor).strip() in ['-', '', 'None']: return 0.0
    try:
        s = str(valor).replace(' ', '').replace('$', '')
        if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        return round(float(pd.to_numeric(s, errors='coerce')), 2)
    except: return 0.0

def encontrar_datos(df):
    """Salta encabezados hasta encontrar la fila de títulos real"""
    for i in range(min(20, len(df))):
        fila = [str(x).lower() for x in df.iloc[i].values]
        if 'asiento' in fila or 'referencia' in fila:
            new_df = df.iloc[i+1:].copy()
            new_df.columns = df.iloc[i].values
            return new_df.reset_index(drop=True)
    return df

st.title("⚖️ Conciliador SILLACA - Versión 'ADN Numérico'")
st.markdown("---")

f_cb = st.file_uploader("📂 Archivo Banco (CB)", type=['xlsx', 'csv'])
f_cg = st.file_uploader("📂 Archivo Contabilidad (CG)", type=['xlsx', 'csv'])

if f_cb and f_cg:
    try:
        df_cb_raw = pd.read_excel(f_cb) if "xls" in f_cb.name else pd.read_csv(f_cb)
        df_cg_raw = pd.read_excel(f_cg) if "xls" in f_cg.name else pd.read_csv(f_cg)

        df_cb = encontrar_datos(df_cb_raw)
        df_cg = encontrar_datos(df_cg_raw)

        # 1. Identificar columnas con 'mucha' flexibilidad
        def find_c(cols, keys):
            for c in cols:
                if any(k in str(c).lower() for k in keys): return c
            return None

        c_num_cb = find_c(df_cb.columns, ['número', 'numero'])
        c_cre_cb, c_deb_cb = find_c(df_cb.columns, ['crédito', 'credito']), find_c(df_cb.columns, ['débito', 'debito'])
        
        c_ref_cg = find_c(df_cg.columns, ['referencia'])
        c_dv_cg, c_cv_cg = find_c(df_cg.columns, ['débito ves', 'local']), find_c(df_cg.columns, ['crédito ves', 'local'])
        c_dd_cg, c_cd_cg = find_c(df_cg.columns, ['dólar', 'dolar', 'divisa']), find_c(df_cg.columns, ['dólar', 'dolar', 'divisa'])

        # 2. PROCESO DE "ADN" EN CONTABILIDAD (CG)
        # Extraemos el número de referencia y sumamos montos
        df_cg['num_adn'] = df_cg[c_ref_cg].apply(extraer_solo_numeros)
        
        # Agrupamos (Tabla Dinámica Interna)
        cg_grouped = df_cg.groupby('num_adn').agg({
            c_dv_cg: lambda x: sum(a_numero(v) for v in x),
            c_cv_cg: lambda x: sum(a_numero(v) for v in x)
        }).reset_index()

        # 3. CRUCE CONTRA BANCO (CB)
        resultados = []
        for _, fila in df_cb.iterrows():
            adn_banco = extraer_solo_numeros(fila[c_num_cb])
            if not adn_banco: continue
            
            m_cre_cb = a_numero(fila[c_cre_cb])
            m_deb_cb = a_numero(fila[c_deb_cb])

            # Lógica Espejo: Crédito Banco (Salida) == Débito Contabilidad (Gasto)
            if m_cre_cb > 0:
                match = cg_grouped[(cg_grouped['num_adn'] == adn_banco) & (cg_grouped[c_dv_cg] == m_cre_cb)]
            else:
                match = cg_grouped[(cg_grouped['num_adn'] == adn_banco) & (cg_grouped[c_cv_cg] == m_deb_cb)]

            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**fila.to_dict(), 'Status': status})

        # Mostrar Tabla Final
        df_final = pd.DataFrame(resultados)
        st.success(f"Proceso completado. {len(df_final[df_final['Status']=='✅ Conciliado'])} coincidencias encontradas.")
        st.dataframe(df_final)

        # Excel
        buffer = io.BytesIO()
        df_final.to_excel(buffer, index=False)
        st.download_button("📥 Descargar Reporte Final", buffer.getvalue(), "conciliacion_sillaca_V7.xlsx")

    except Exception as e:
        st.error(f"Error detectado: {e}")

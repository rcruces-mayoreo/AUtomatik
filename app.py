import streamlit as st
import pandas as pd
import unicodedata
import io

st.set_page_config(page_title="Conciliador SILLACA V5", layout="wide")

def normalizar(texto):
    if pd.isna(texto): return ""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('utf-8') if c.isalnum() or c.isspace()).lower().strip()

def a_numero(valor):
    if pd.isna(valor) or str(valor).strip() in ['-', '', 'None']: return 0.0
    try:
        s = str(valor).replace('.', '').replace(',', '.')
        return float(pd.to_numeric(s, errors='coerce'))
    except: return 0.0

# --- INTERFAZ ---
st.title("⚖️ Conciliador SILLACA - Lógica de Referencia")
st.info("Nueva lógica: Buscando coincidencia de Número de Documento (Ej: 111060 en N/D111060)")

file_cb = st.file_uploader("📂 Archivo CB (Banco)", type=['xlsx', 'csv'])
file_cg = st.file_uploader("📂 Archivo CG (Contabilidad)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    try:
        # Carga y limpieza de encabezados (buscando la fila 'Asiento')
        df_cb_raw = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
        df_cg_raw = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

        # Función para saltar títulos y llegar a los datos
        def encontrar_tabla(df):
            for i in range(min(15, len(df))):
                fila = [str(x).lower() for x in df.iloc[i].values]
                if 'asiento' in fila or 'referencia' in fila:
                    new_df = df.iloc[i+1:].copy()
                    new_df.columns = df.iloc[i].values
                    return new_df.reset_index(drop=True)
            return df

        df_cb = encontrar_tabla(df_cb_raw)
        df_cg = encontrar_tabla(df_cg_raw)

        # Identificar columnas por posición o nombre (basado en tus imágenes)
        # CB: Número (Col D/E), Crédito (Col J), Débito (Col I)
        c_num_cb = [c for c in df_cb.columns if 'número' in c.lower() or 'numero' in c.lower()][0]
        c_cre_cb = [c for c in df_cb.columns if 'crédito' in c.lower() or 'credito' in c.lower()][0]
        c_deb_cb = [c for c in df_cb.columns if 'débito' in c.lower() or 'debito' in c.lower()][0]
        
        # CG: Referencia, Debito VES, Credito VES
        c_ref_cg = [c for c in df_cg.columns if 'referencia' in c.lower()][0]
        c_dv_cg = [c for c in df_cg.columns if 'débito ves' in c.lower() or 'debito local' in c.lower()][0]
        c_cv_cg = [c for c in df_cg.columns if 'crédito ves' in c.lower() or 'credito local' in c.lower()][0]

        # --- PROCESO ---
        resultados = []
        for _, f_cb in df_cb.iterrows():
            num_banco = str(f_cb[c_num_cb]).strip()
            if num_banco == 'nan' or num_banco == "": continue
            
            m_cre_cb = a_numero(f_cb[c_cre_cb])
            m_deb_cb = a_numero(f_cb[c_deb_cb])
            monto_cb = m_cre_cb if m_cre_cb > 0 else m_deb_cb

            # Buscamos en CG si la Referencia contiene el número del banco y el monto coincide (Espejo)
            # Si en CB es Crédito, en CG buscamos Débito
            if m_cre_cb > 0:
                match = df_cg[(df_cg[c_ref_cg].astype(str).str.contains(num_banco)) & (df_cg[c_dv_cg].apply(a_numero) == m_cre_cb)]
            else:
                match = df_cg[(df_cg[c_ref_cg].astype(str).str.contains(num_banco)) & (df_cg[c_cv_cg].apply(a_numero) == m_deb_cb)]

            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**f_cb.to_dict(), 'Status': status})

        df_res = pd.DataFrame(resultados)
        st.dataframe(df_res)
        
        # Exportar
        towrite = io.BytesIO()
        df_res.to_excel(towrite, index=False, engine='openpyxl')
        st.download_button("📥 Bajar Reporte", towrite.getvalue(), "conciliacion_final.xlsx")

    except Exception as e:
        st.error(f"Error: {e}")

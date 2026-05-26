import streamlit as st
import pandas as pd
import unicodedata
import io

st.set_page_config(page_title="Conciliador SILLACA V4", layout="wide")

def normalizar(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def a_numero(valor):
    if pd.isna(valor) or str(valor).strip() in ['-', '', 'None']: return 0.0
    try:
        # Limpieza profunda de formatos de moneda (puntos y comas)
        s = str(valor).replace('$', '').replace(' ', '')
        if ',' in s and '.' in s: # Formato 1.234,56
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s: # Formato 1234,56
            s = s.replace(',', '.')
        return float(pd.to_numeric(s, errors='coerce'))
    except: return 0.0

def limpiar_dataframe(df):
    for i in range(min(10, len(df))):
        fila_str = [normalizar(str(x)) for x in df.iloc[i].values]
        if 'asiento' in fila_str or 'referencia' in fila_str or 'fecha' in fila_str:
            new_df = df.iloc[i+1:].copy()
            new_df.columns = df.iloc[i].values
            return new_df.reset_index(drop=True)
    return df

def buscar_col(cols, palabras_clave):
    for c in cols:
        c_norm = normalizar(c)
        if any(p in c_norm for p in palabras_clave): return c
    return None

st.title("🤖 Conciliador SILLACA - Versión Optimizada")

file_cb = st.file_uploader("📂 Archivo CB (Banco)", type=['xlsx', 'csv'])
file_cg = st.file_uploader("📂 Archivo CG (Contabilidad)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    try:
        df_cb_raw = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
        df_cg_raw = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)
        
        df_cb = limpiar_dataframe(df_cb_raw)
        df_cg = limpiar_dataframe(df_cg_raw)

        # Identificar columnas
        c_ref_cg = buscar_col(df_cg.columns, ['referencia'])
        c_dl_cg, c_cl_cg = buscar_col(df_cg.columns, ['debito ves', 'debito local']), buscar_col(df_cg.columns, ['credito ves', 'credito local'])
        c_dd_cg, c_cd_cg = buscar_col(df_cg.columns, ['debito dolar', 'debito divisa']), buscar_col(df_cg.columns, ['credito dolar', 'credito divisa'])

        c_ref_cb = buscar_col(df_cb.columns, ['referencia', 'numero'])
        c_ben_cb = buscar_col(df_cb.columns, ['beneficiario'])
        c_con_cb = buscar_col(df_cb.columns, ['concepto'])
        c_deb_cb, c_cre_cb = buscar_col(df_cb.columns, ['debito', 'debe']), buscar_col(df_cb.columns, ['credito', 'haber'])

        # --- TABLA DINÁMICA CG ---
        for col in [c_dl_cg, c_cl_cg, c_dd_cg, c_cd_cg]:
            df_cg[col] = df_cg[col].apply(a_numero)

        cg_pivot = df_cg.groupby(c_ref_cg).agg({c_dl_cg:'sum', c_cl_cg:'sum', c_dd_cg:'sum', c_cd_cg:'sum'}).reset_index()
        cg_pivot['ref_clean'] = cg_pivot[c_ref_cg].apply(normalizar)

        # --- CRUCE ---
        resultados = []
        for _, fila in df_cb.iterrows():
            m_deb_cb, m_cre_cb = a_numero(fila[c_deb_cb]), a_numero(fila[c_cre_cb])
            if m_deb_cb == 0 and m_cre_cb == 0: continue

            # DETECCIÓN DE MONEDA MEJORADA (Busca en Beneficiario y Concepto también)
            texto_completo_cb = normalizar(f"{fila[c_ref_cb]} {fila[c_ben_cb]} {fila[c_con_cb]}")
            moneda = "VES" if "ves" in texto_completo_cb else "USD"
            
            # Buscamos si la referencia de CG está contenida en el texto de CB
            if moneda == "VES":
                match = cg_pivot[(cg_pivot.apply(lambda x: x['ref_clean'] in texto_completo_cb, axis=1)) & 
                                 ((abs(cg_pivot[c_dl_cg] - m_cre_cb) < 0.01) | (abs(cg_pivot[c_cl_cg] - m_deb_cb) < 0.01))]
            else:
                match = cg_pivot[(cg_pivot.apply(lambda x: x['ref_clean'] in texto_completo_cb, axis=1)) & 
                                 ((abs(cg_pivot[c_dd_cg] - m_cre_cb) < 0.01) | (abs(cg_pivot[c_cd_cg] - m_deb_cb) < 0.01))]
            
            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**fila.to_dict(), 'Status': status, 'Moneda Detectada': moneda})

        df_final = pd.DataFrame(resultados)
        st.dataframe(df_final)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        st.download_button("📥 Descargar Conciliación", output.getvalue(), "conciliacion_v4.xlsx")

    except Exception as e:
        st.error(f"Error: {e}")

import streamlit as st
import pandas as pd
import unicodedata

# Configuración de página
st.set_page_config(page_title="Conciliador SILLACA PRO", layout="wide")

def normalizar(texto):
    """Limpia texto: minúsculas, sin acentos, sin espacios extra"""
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def identificar_moneda(referencia):
    """Lógica 'SI' para detectar moneda"""
    ref = str(referencia).upper()
    return "VES" if "VES" in ref else "USD"

st.title("🤖 Conciliador Inteligente SILLACA")
st.markdown("---")

# 1. CARGA DE DOCUMENTOS
col_a, col_b = st.columns(2)
with col_a:
    file_cb = st.file_uploader("📂 Documento CB (Control Bancario)", type=['xlsx', 'csv'])
with col_b:
    file_cg = st.file_uploader("📂 Documento CG (Contabilidad General)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    # Lectura de datos
    df_cb = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
    df_cg = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)

    try:
        # --- PROCESAMIENTO CG (TU TABLA DINÁMICA) ---
        # Identificamos columnas de CG (buscando 'debito', 'credito', 'local', 'dolar')
        col_ref_cg = [c for c in df_cg.columns if normalizar(c) == 'referencia'][0]
        col_dl = [c for c in df_cg.columns if 'debito local' in normalizar(c)][0]
        col_cl = [c for c in df_cg.columns if 'credito local' in normalizar(c)][0]
        col_dd = [c for c in df_cg.columns if 'debito' in normalizar(c) and 'dolar' in normalizar(c)][0]
        col_cd = [c for c in df_cg.columns if 'credito' in normalizar(c) and 'dolar' in normalizar(c)][0]

        # Replicamos la Tabla Dinámica: Agrupar por Referencia y sumar
        cg_pivot = df_cg.groupby(col_ref_cg).agg({
            col_dl: 'sum', col_cl: 'sum',
            col_dd: 'sum', col_cd: 'sum'
        }).reset_index()
        cg_pivot['ref_clean'] = cg_pivot[col_ref_cg].apply(normalizar)

        # --- PROCESAMIENTO CB ---
        # Identificar moneda en CB por la columna Referencia
        col_ref_cb = [c for c in df_cb.columns if normalizar(c) == 'referencia'][0]
        col_benef_cb = df_cb.columns[4] # Columna E
        col_concep_cb = df_cb.columns[5] # Columna F
        col_deb_cb = [c for c in df_cb.columns if 'debito' in normalizar(c)][0]
        col_cre_cb = [c for c in df_cb.columns if 'credito' in normalizar(c)][0]

        df_cb['moneda'] = df_cb[col_ref_cb].apply(identificar_moneda)
        # Combinamos Beneficiario + Concepto para hacer match con la Referencia de CG
        df_cb['match_text'] = (df_cb[col_benef_cb].astype(str) + " " + df_cb[col_concep_cb].astype(str)).apply(normalizar)
        
        # --- EL CRUCE (MATCHING) ---
        conciliados = []
        
        for idx, fila in df_cb.iterrows():
            moneda = fila['moneda']
            monto_deb = fila[col_deb_cb]
            monto_cre = fila[col_cre_cb]
            texto_cb = fila['match_text']

            # Buscamos en la 'Tabla Dinámica' de CG
            # Si es crédito en CB, buscamos débito en CG y viceversa
            if moneda == "VES":
                match = cg_pivot[
                    (cg_pivot['ref_clean'].str.contains(texto_cb) | (texto_cb in cg_pivot['ref_clean'].values)) &
                    ((cg_pivot[col_dl] == monto_cre) | (cg_pivot[col_cl] == monto_deb))
                ]
            else: # USD
                match = cg_pivot[
                    (cg_pivot['ref_clean'].str.contains(texto_cb) | (texto_cb in cg_pivot['ref_clean'].values)) &
                    ((cg_pivot[col_dd] == monto_cre) | (cg_pivot[col_cd] == monto_deb))
                ]
            
            if not match.empty:
                conciliados.append({**fila.to_dict(), 'Status': '✅ Conciliado'})
            else:
                conciliados.append({**fila.to_dict(), 'Status': '❌ Pendiente'})

        # --- RESULTADOS ---
        df_final = pd.DataFrame(conciliados)
        
        st.header("📊 Resultado de la Conciliación")
        met1, met2 = st.columns(2)
        met1.metric("Conciliados", len(df_final[df_final['Status'] == '✅ Conciliado']))
        met2.metric("Pendientes", len(df_final[df_final['Status'] == '❌ Pendiente']))

        st.dataframe(df_final.drop(columns=['match_text']))

        # Botón para descargar a Excel
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte Conciliado", csv, "conciliacion_final.csv", "text/csv")

    except Exception as e:
        st.error(f"Error en el proceso: {e}. Revisa que las columnas tengan los nombres indicados.")

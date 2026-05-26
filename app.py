import streamlit as st
import pandas as pd
import unicodedata
import io

# Configuración de página
st.set_page_config(page_title="Conciliador SILLACA PRO", layout="wide")

def normalizar(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def limpiar_dataframe(df):
    """Detecta la fila de encabezados real buscando la palabra 'Asiento'"""
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).apply(normalizar).tolist()
        if 'asiento' in fila or 'fecha' in fila:
            new_df = df.iloc[i+1:].copy()
            new_df.columns = df.iloc[i].tolist()
            return new_df.reset_index(drop=True)
    return df

def buscar_col(cols, posibles_nombres):
    """Busca una columna por aproximación de nombre"""
    for c in cols:
        c_norm = normalizar(c)
        if any(p in c_norm for p in posibles_nombres):
            return c
    return None

st.title("🤖 Conciliador Inteligente SILLACA")
st.info("Detectando automáticamente encabezados y moneda...")

col_a, col_b = st.columns(2)
with col_a:
    file_cb = st.file_uploader("📂 Archivo CB (Banco)", type=['xlsx', 'csv'])
with col_b:
    file_cg = st.file_uploader("📂 Archivo CG (Contabilidad)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    # Leer archivos saltando posibles errores de formato
    try:
        df_cb_raw = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
        df_cg_raw = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)
        
        # Limpiar filas de título/basura
        df_cb = limpiar_dataframe(df_cb_raw)
        df_cg = limpiar_dataframe(df_cg_raw)

        # 1. Identificar columnas clave (ahora más flexible)
        c_ref_cg = buscar_col(df_cg.columns, ['referencia'])
        c_dl_cg = buscar_col(df_cg.columns, ['debito ves', 'debito local'])
        c_cl_cg = buscar_col(df_cg.columns, ['credito ves', 'credito local'])
        c_dd_cg = buscar_col(df_cg.columns, ['debito dolar', 'debito divisa'])
        c_cd_cg = buscar_col(df_cg.columns, ['credito dolar', 'credito divisa'])

        c_ref_cb = buscar_col(df_cb.columns, ['referencia', 'numero'])
        c_ben_cb = buscar_col(df_cb.columns, ['beneficiario'])
        c_con_cb = buscar_col(df_cb.columns, ['concepto'])
        c_deb_cb = buscar_col(df_cb.columns, ['debito', 'debe'])
        c_cre_cb = buscar_col(df_cb.columns, ['credito', 'haber'])

        # Validar que encontramos lo básico
        if not c_ref_cg or not c_ben_cb:
            st.error("No pude encontrar las columnas necesarias. Revisa los nombres en tus archivos.")
            st.stop()

        # 2. PROCESO DE TABLA DINÁMICA (Agrupar CG)
        cg_pivot = df_cg.groupby(c_ref_cg).agg({
            c_dl_cg: 'sum', c_cl_cg: 'sum',
            c_dd_cg: 'sum', c_cd_cg: 'sum'
        }).reset_index()
        cg_pivot['ref_clean'] = cg_pivot[c_ref_cg].apply(normalizar)

        # 3. CRUCE (Siguiendo tu lógica espejo)
        resultados = []
        for _, fila in df_cb.iterrows():
            # Identificar moneda (si dice VES en la referencia de CB)
            ref_texto = str(fila[c_ref_cb]).upper()
            moneda = "VES" if "VES" in ref_texto else "USD"
            
            # Montos en CB
            m_deb_cb = float(str(fila[c_deb_cb]).replace(',','')) if pd.notna(fila[c_deb_cb]) and fila[c_deb_cb] != '-' else 0
            m_cre_cb = float(str(fila[c_cre_cb]).replace(',','')) if pd.notna(fila[c_cre_cb]) and fila[c_cre_cb] != '-' else 0
            
            # Texto para buscar (Beneficiario + Concepto)
            busqueda = normalizar(f"{fila[c_ben_cb]} {fila[c_con_cb]}")
            
            # Buscar en el pivote de CG
            if moneda == "VES":
                # CB Credito vs CG Debito (o viceversa)
                match = cg_pivot[(cg_pivot['ref_clean'].str.contains(busqueda)) & 
                                 ((cg_pivot[c_dl_cg] == m_cre_cb) | (cg_pivot[c_cl_cg] == m_deb_cb))]
            else:
                match = cg_pivot[(cg_pivot['ref_clean'].str.contains(busqueda)) & 
                                 ((cg_pivot[c_dd_cg] == m_cre_cb) | (cg_pivot[c_cd_cg] == m_deb_cb))]
            
            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**fila.to_dict(), 'Status': status, 'Moneda Detectada': moneda})

        # 4. MOSTRAR TABLAS
        df_final = pd.DataFrame(resultados)
        st.subheader("Resultados de la comparación")
        st.dataframe(df_final)
        
        # Descarga
        output = io.BytesIO()
        df_final.to_excel(output, index=False)
        st.download_button("📥 Descargar Excel", output.getvalue(), "conciliacion.xlsx")

    except Exception as e:
        st.error(f"Error técnico: {e}")

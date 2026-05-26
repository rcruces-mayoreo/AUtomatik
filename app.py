import streamlit as st
import pandas as pd
import unicodedata
import io

# Configuración de página
st.set_page_config(page_title="Conciliador SILLACA PRO", layout="wide")

def normalizar(texto):
    """Limpia texto: minúsculas, sin acentos, sin espacios extra"""
    if pd.isna(texto): return ""
    texto = str(texto).strip().lower()
    # Elimina acentos usando normalización Unicode
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')

def a_numero(valor):
    """Convierte texto a número de forma segura. Si es texto, devuelve 0.0"""
    if pd.isna(valor) or str(valor).strip() in ['-', '', 'None']:
        return 0.0
    try:
        # Elimina puntos de miles y cambia coma decimal si existe
        s = str(valor).replace('.', '').replace(',', '.')
        return float(pd.to_numeric(s, errors='coerce'))
    except:
        return 0.0

def limpiar_dataframe(df):
    """Busca la fila donde empiezan los datos reales"""
    for i in range(len(df)):
        # Buscamos una fila que contenga palabras clave de encabezado
        fila_str = [normalizar(str(x)) for x in df.iloc[i].values]
        if 'asiento' in fila_str or 'referencia' in fila_str or 'fecha' in fila_str:
            new_df = df.iloc[i+1:].copy()
            new_df.columns = df.iloc[i].values
            return new_df.reset_index(drop=True)
    return df

def buscar_col(cols, palabras_clave):
    """Busca una columna que contenga alguna de las palabras clave (sin acentos)"""
    for c in cols:
        c_norm = normalizar(c)
        if any(p in c_norm for p in palabras_clave):
            return c
    return None

st.title("🤖 Conciliador Inteligente SILLACA")
st.info("Nueva versión: Tolerancia a errores de texto en columnas de montos y detección de acentos.")

# --- CARGA DE ARCHIVOS ---
col_a, col_b = st.columns(2)
with col_a:
    file_cb = st.file_uploader("📂 Archivo CB (Banco)", type=['xlsx', 'csv'])
with col_b:
    file_cg = st.file_uploader("📂 Archivo CG (Contabilidad)", type=['xlsx', 'csv'])

if file_cb and file_cg:
    try:
        # Lectura inicial
        df_cb_raw = pd.read_excel(file_cb) if "xls" in file_cb.name else pd.read_csv(file_cb)
        df_cg_raw = pd.read_excel(file_cg) if "xls" in file_cg.name else pd.read_csv(file_cg)
        
        # Limpieza de encabezados
        df_cb = limpiar_dataframe(df_cb_raw)
        df_cg = limpiar_dataframe(df_cg_raw)

        # Identificación de columnas (ignorando acentos)
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

        # --- PROCESO DE TABLA DINÁMICA (CG) ---
        # Convertimos montos de CG a números antes de agrupar
        for col in [c_dl_cg, c_cl_cg, c_dd_cg, c_cd_cg]:
            df_cg[col] = df_cg[col].apply(a_numero)

        cg_pivot = df_cg.groupby(c_ref_cg).agg({
            c_dl_cg: 'sum', c_cl_cg: 'sum',
            c_dd_cg: 'sum', c_cd_cg: 'sum'
        }).reset_index()
        cg_pivot['ref_clean'] = cg_pivot[c_ref_cg].apply(normalizar)

        # --- CRUCE (Matching) ---
        resultados = []
        for _, fila in df_cb.iterrows():
            # Convertir montos de CB de forma segura
            m_deb_cb = a_numero(fila[c_deb_cb])
            m_cre_cb = a_numero(fila[c_cre_cb])
            
            # Si ambos son 0 (es una fila de encabezado que se coló), la saltamos
            if m_deb_cb == 0 and m_cre_cb == 0:
                continue

            # Detectar moneda por referencia
            ref_cb_texto = str(fila[c_ref_cb]).upper()
            moneda = "VES" if "VES" in ref_cb_texto else "USD"
            
            # Texto de búsqueda (Beneficiario + Concepto)
            busqueda = normalizar(f"{fila[c_ben_cb]} {fila[c_con_cb]}")
            
            # Búsqueda en CG Pivot
            if moneda == "VES":
                match = cg_pivot[(cg_pivot['ref_clean'].str.contains(busqueda)) & 
                                 ((cg_pivot[c_dl_cg] == m_cre_cb) | (cg_pivot[c_cl_cg] == m_deb_cb))]
            else:
                match = cg_pivot[(cg_pivot['ref_clean'].str.contains(busqueda)) & 
                                 ((cg_pivot[c_dd_cg] == m_cre_cb) | (cg_pivot[c_cd_cg] == m_deb_cb))]
            
            status = "✅ Conciliado" if not match.empty else "❌ Pendiente"
            resultados.append({**fila.to_dict(), 'Status': status, 'Moneda': moneda})

        # --- MOSTRAR RESULTADOS ---
        df_final = pd.DataFrame(resultados)
        st.success(f"Procesadas {len(df_final)} transacciones.")
        st.dataframe(df_final)
        
        # Botón de descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        st.download_button("📥 Descargar Conciliación en Excel", output.getvalue(), "conciliacion_sillaca.xlsx")

    except Exception as e:
        st.error(f"Se produjo un error: {e}")
        st.info("Asegúrate de que los archivos tengan las columnas de Débitos y Créditos.")

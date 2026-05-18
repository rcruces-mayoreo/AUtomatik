import streamlit as st
import pandas as pd
import re
import unicodedata

st.set_page_config(page_title="Auditoría Beval - Resiliente", layout="wide")

# --- FUNCIONES DE HOLGURA Y NORMALIZACIÓN ---

def eliminar_acentos(texto):
    """Transforma 'Crédito Bolívar' en 'credito bolivar'"""
    if not isinstance(texto, str): return str(texto)
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode("utf-8")
    return texto.lower().strip()

def encontrar_columna(lista_columnas, palabras_clave):
    """Busca una columna que coincida con alguna palabra clave, ignorando acentos"""
    for col in lista_columnas:
        col_normalizada = eliminar_acentos(col)
        for palabra in palabras_clave:
            if palabra in col_normalizada:
                return col
    return None

def extraer_14_digitos(texto):
    match = re.search(r'\d{14}', str(texto))
    return match.group(0) if match else None

def limpiar_factura(texto):
    numeros = re.sub(r'\D', '', str(texto))
    return numeros.lstrip('0')

def normalizar_fecha(fecha):
    try:
        return pd.to_datetime(fecha).date()
    except:
        return None

# --- INTERFAZ ---

st.title("🛡️ Sistema de Auditoría Beval (Versión Inteligente)")
st.info("Este sistema ahora tolera cambios en acentos y nombres de columnas (Ej: Crédito Bolívar / Credito local).")

col1, col2 = st.columns(2)
with col1:
    f_softland = st.file_uploader("Subir Libro Diario (Softland)", type=['xlsx', 'xls'])
with col2:
    f_tax = st.file_uploader("Subir Informe de Retenciones (Impuestos)", type=['xlsx', 'xls'])

if f_softland and f_tax:
    try:
        # 1. PROCESAR SOFTLAND (CP)
        engine_soft = 'openpyxl' if f_softland.name.endswith('xlsx') else 'xlrd'
        df_soft = pd.read_excel(f_softland, engine=engine_soft)
        cols_soft = df_soft.columns.tolist()

        # Buscamos las columnas necesarias con "holgura"
        col_cta = encontrar_columna(cols_soft, ["cuenta contable", "codigo cuenta"])
        col_monto = encontrar_columna(cols_soft, ["credito bolivar", "credito local", "haber", "monto local"])
        col_fecha = encontrar_columna(cols_soft, ["fecha"])
        col_fuente = encontrar_columna(cols_soft, ["fuente"])
        col_ref = encontrar_columna(cols_soft, ["referencia", "glosa"])

        if not col_monto or not col_cta:
            st.error(f"No logré encontrar la columna de Monto o Cuenta. Columnas detectadas: {cols_soft}")
        else:
            # Filtramos cuenta de retención
            soft_ret = df_soft[df_soft[col_cta].astype(str) == "2.1.3.05.1.001"].copy()
            
            soft_ret['COMP_KEY'] = soft_ret[col_fuente].apply(extraer_14_digitos)
            soft_ret['FECHA_KEY'] = soft_ret[col_fecha].apply(normalizar_fecha)
            soft_ret['FACT_KEY'] = soft_ret[col_ref].apply(limpiar_factura)
            soft_ret['MONTO_KEY'] = pd.to_numeric(soft_ret[col_monto], errors='coerce').fillna(0).round(2)

            # 2. PROCESAR INFORME DE IMPUESTOS
            engine_tax = 'openpyxl' if f_tax.name.endswith('xlsx') else 'xlrd'
            df_tax_raw = pd.read_excel(f_tax, header=None, engine=engine_tax)

            datos_tax = []
            for i, row in df_tax_raw.iterrows():
                comprobante = extraer_14_digitos(row[0])
                if comprobante:
                    datos_tax.append({
                        'COMP_KEY': comprobante,
                        'FECHA_TAX': normalizar_fecha(row[1]), # Columna B
                        'FACT_KEY': limpiar_factura(row[3]),   # Columna D
                        'MONTO_KEY': pd.to_numeric(row[8], errors='coerce'), # Columna I
                    })
            
            df_tax_clean = pd.DataFrame(datos_tax)

            if st.button("🚀 Iniciar Validación"):
                if df_tax_clean.empty:
                    st.error("No se detectaron comprobantes de 14 dígitos en el archivo de Impuestos.")
                else:
                    # 3. CRUCE
                    conciliacion = pd.merge(
                        df_tax_clean,
                        soft_ret[['COMP_KEY', 'FECHA_KEY', 'FACT_KEY', 'MONTO_KEY', col_ref]],
                        on='COMP_KEY',
                        how='outer',
                        suffixes=('_TAX', '_SOFT'),
                        indicator=True
                    )

                    # 4. VALIDACIÓN
                    def validar(r):
                        if r['_merge'] == 'left_only': return "Falta en Contabilidad"
                        if r['_merge'] == 'right_only': return "Falta en Impuestos"
                        
                        alertas = []
                        if r['FECHA_TAX'] != r['FECHA_KEY']: alertas.append("Fecha Diferente")
                        if r['FACT_KEY_TAX'] != r['FACT_KEY_SOFT']: alertas.append("Factura Diferente")
                        if abs(r['MONTO_KEY_TAX'] - r['MONTO_KEY_SOFT']) > 0.1: alertas.append("Monto Diferente")
                        
                        return "✅ Correcto" if not alertas else "⚠️ " + " | ".join(alertas)

                    conciliacion['Estado'] = conciliacion.apply(validar, axis=1)

                    # 5. RESULTADOS
                    st.dataframe(conciliacion[[
                        'COMP_KEY', 'Estado', 'FECHA_TAX', 'FECHA_KEY', 
                        'MONTO_KEY_TAX', 'MONTO_KEY_SOFT'
                    ]])

    except Exception as e:
        st.error(f"Error en el proceso: {e}")

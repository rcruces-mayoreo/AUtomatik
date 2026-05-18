import streamlit as st
import pandas as pd
import re
import unicodedata
import io

st.set_page_config(page_title="Auditoría Beval - Exportar a Excel", layout="wide")

# --- FUNCIONES DE NORMALIZACIÓN ---

def eliminar_acentos(texto):
    if not isinstance(texto, str): return str(texto)
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode("utf-8")
    return texto.lower().strip()

def encontrar_columna(lista_columnas, palabras_clave):
    for col in lista_columnas:
        col_normalizada = eliminar_acentos(col)
        for palabra in palabras_clave:
            if palabra in col_normalizada:
                return col
    return None

def extraer_14_digitos(texto):
    # Buscamos 14 números. Si hay ceros a la izquierda, los mantenemos
    match = re.search(r'\d{12,14}', str(texto))
    return match.group(0).zfill(14) if match else None

def limpiar_factura(texto):
    if pd.isna(texto): return ""
    numeros = re.sub(r'\D', '', str(texto))
    return numeros.lstrip('0')

def limpiar_monto(valor):
    """Convierte montos de Excel (incluso con comas) a números decimales"""
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    # Si viene como string, quitamos puntos de miles y cambiamos coma por punto
    s = str(valor).replace('.', '').replace(',', '.')
    try:
        return float(re.findall(r"[-+]?\d*\.\d+|\d+", s)[0])
    except:
        return 0.0

def normalizar_fecha(fecha):
    try:
        return pd.to_datetime(fecha).date()
    except:
        return None

# --- INTERFAZ ---

st.title("📊 Generador de Conciliación - Mayor Beval")
st.markdown("Sube los archivos y descarga el reporte de discrepancias en Excel.")

col1, col2 = st.columns(2)
with col1:
    f_softland = st.file_uploader("Libro Diario (Softland)", type=['xlsx', 'xls'])
with col2:
    f_tax = st.file_uploader("Informe de Retenciones (Impuestos)", type=['xlsx', 'xls'])

if f_softland and f_tax:
    try:
        # 1. PROCESAR SOFTLAND
        engine_soft = 'openpyxl' if f_softland.name.endswith('xlsx') else 'xlrd'
        df_soft = pd.read_excel(f_softland, engine=engine_soft)
        cols_soft = df_soft.columns.tolist()

        col_cta = encontrar_columna(cols_soft, ["cuenta contable"])
        col_monto = encontrar_columna(cols_soft, ["credito bolivar", "credito local", "haber"])
        col_fecha = encontrar_columna(cols_soft, ["fecha"])
        col_fuente = encontrar_columna(cols_soft, ["fuente"])
        col_ref = encontrar_columna(cols_soft, ["referencia", "glosa"])

        soft_ret = df_soft[df_soft[col_cta].astype(str) == "2.1.3.05.1.001"].copy()
        soft_ret['COMP_KEY'] = soft_ret[col_fuente].apply(extraer_14_digitos)
        soft_ret['FECHA_KEY'] = soft_ret[col_fecha].apply(normalizar_fecha)
        soft_ret['FACT_KEY'] = soft_ret[col_ref].apply(limpiar_factura)
        soft_ret['MONTO_SOFT'] = soft_ret[col_monto].apply(limpiar_monto)

        # 2. PROCESAR IMPUESTOS (DINÁMICO)
        engine_tax = 'openpyxl' if f_tax.name.endswith('xlsx') else 'xlrd'
        df_tax_raw = pd.read_excel(f_tax, header=None, engine=engine_tax)

        datos_tax = []
        for i, row in df_tax_raw.iterrows():
            comprobante = extraer_14_digitos(row[0])
            if comprobante:
                datos_tax.append({
                    'COMP_KEY': comprobante,
                    'FECHA_TAX': normalizar_fecha(row[1]),
                    'FACT_TAX_RAW': str(row[3]),
                    'FACT_KEY': limpiar_factura(row[3]),
                    'MONTO_TAX': limpiar_monto(row[8]) # Columna I
                })
        
        df_tax_clean = pd.DataFrame(datos_tax)

        if st.button("🚀 Procesar y Generar Excel"):
            # 3. CRUCE
            conciliacion = pd.merge(
                df_tax_clean,
                soft_ret[['COMP_KEY', 'FECHA_KEY', 'FACT_KEY', 'MONTO_SOFT', col_ref]],
                on='COMP_KEY',
                how='outer',
                suffixes=('_TAX', '_SOFT'),
                indicator=True
            )

            # 4. VALIDACIÓN
            def validar(r):
                if r['_merge'] == 'left_only': return "Falta en Contabilidad"
                if r['_merge'] == 'right_only': return "Falta en Reporte Impuestos"
                alertas = []
                if r['FECHA_TAX'] != r['FECHA_KEY']: alertas.append("Fecha Diferente")
                if r['FACT_KEY_TAX'] != r['FACT_KEY_SOFT']: alertas.append("Factura Diferente")
                if abs(r['MONTO_TAX'] - r['MONTO_SOFT']) > 0.5: alertas.append("Monto Diferente")
                return "Correcto" if not alertas else "Revisar: " + ", ".join(alertas)

            conciliacion['Resultado'] = conciliacion.apply(validar, axis=1)
            conciliacion['Diferencia_Monto'] = conciliacion['MONTO_TAX'] - conciliacion['MONTO_SOFT']

            # 5. CREAR EXCEL EN MEMORIA
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                conciliacion.to_excel(writer, index=False, sheet_name='Resultado_Conciliacion')
                
                # Formatear el Excel (Opcional: ajustar anchos de columna)
                workbook = writer.book
                worksheet = writer.sheets['Resultado_Conciliacion']
                header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
                for col_num, value in enumerate(conciliacion.columns.values):
                    worksheet.write(0, col_num, value, header_format)

            excel_data = output.getvalue()

            st.success("✅ Conciliación generada con éxito.")
            
            # BOTÓN DE DESCARGA
            st.download_button(
                label="📥 Descargar Resultado en Excel",
                data=excel_data,
                file_name=f"Conciliacion_Beval_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Vista previa corta
            st.dataframe(conciliacion[['COMP_KEY', 'Resultado', 'MONTO_TAX', 'MONTO_SOFT']].head(10))

    except Exception as e:
        st.error(f"Error: {e}")

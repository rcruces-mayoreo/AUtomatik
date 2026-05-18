import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="Sistema de Validación Beval", layout="wide")

# --- FUNCIONES DE LIMPIEZA INTELIGENTE ---

def extraer_14_digitos(texto):
    """Busca exactamente una secuencia de 14 números seguidos"""
    match = re.search(r'\d{14}', str(texto))
    return match.group(0) if match else None

def limpiar_factura(texto):
    """Extrae números de la factura y quita ceros a la izquierda"""
    numeros = re.sub(r'\D', '', str(texto)) # Solo números
    return numeros.lstrip('0') # Quitar ceros a la izquierda (000123 -> 123)

def normalizar_fecha(fecha):
    """Convierte diferentes formatos de fecha a date estándar"""
    try:
        return pd.to_datetime(fecha).date()
    except:
        return None

# --- INTERFAZ ---

st.title("🛡️ Sistema de Auditoría: Impuestos vs Contabilidad")
st.subheader("Compañía Mayor Beval - Validación de Retenciones")

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
        
        # Filtramos solo la cuenta de retención
        soft_ret = df_soft[df_soft['Cuenta Contable'] == "2.1.3.05.1.001"].copy()
        
        # Procesamos columnas de Softland para comparación
        soft_ret['COMP_KEY'] = soft_ret['Fuente'].apply(extraer_14_digitos)
        soft_ret['FECHA_KEY'] = soft_ret['Fecha'].apply(normalizar_fecha)
        soft_ret['FACT_KEY'] = soft_ret['Referencia'].apply(limpiar_factura)
        soft_ret['MONTO_KEY'] = pd.to_numeric(soft_ret['Crédito Bolívar'], errors='coerce').fillna(0).round(2)

        # 2. PROCESAR INFORME DE IMPUESTOS (DINÁMICO)
        engine_tax = 'openpyxl' if f_tax.name.endswith('xlsx') else 'xlrd'
        df_tax_raw = pd.read_excel(f_tax, header=None, engine=engine_tax)

        datos_tax = []
        # Recorremos el archivo de impuestos buscando los 14 dígitos en cualquier fila de la columna A
        for i, row in df_tax_raw.iterrows():
            comprobante = extraer_14_digitos(row[0])
            
            if comprobante: # Si encontramos los 14 dígitos, es una fila de datos
                datos_tax.append({
                    'COMP_KEY': comprobante,
                    'FECHA_TAX': normalizar_fecha(row[1]), # Columna B
                    'FACT_TAX_RAW': str(row[3]),           # Columna D
                    'FACT_KEY': limpiar_factura(row[3]),   # Columna D (Limpia)
                    'MONTO_KEY': pd.to_numeric(row[8], errors='coerce'), # Columna I
                })
        
        df_tax_clean = pd.DataFrame(datos_tax)

        if st.button("🚀 Iniciar Validación Cruzada"):
            if df_tax_clean.empty:
                st.error("No se detectaron comprobantes de 14 dígitos en el archivo de Impuestos.")
            else:
                # 3. CRUCE MAESTRO (JOIN por Comprobante)
                conciliacion = pd.merge(
                    df_tax_clean,
                    soft_ret[['COMP_KEY', 'FECHA_KEY', 'FACT_KEY', 'MONTO_KEY', 'Asiento', 'Referencia']],
                    on='COMP_KEY',
                    how='outer',
                    suffixes=('_TAX', '_SOFT'),
                    indicator=True
                )

                # 4. LÓGICA DE APRENDIZAJE / VALIDACIÓN
                def validar_fila(r):
                    if r['_merge'] == 'left_only': return "Falta en Contabilidad"
                    if r['_merge'] == 'right_only': return "Falta en Reporte Impuestos"
                    
                    alertas = []
                    if r['FECHA_TAX'] != r['FECHA_KEY']: alertas.append("Fecha Diferente")
                    if r['FACT_KEY_TAX'] != r['FACT_KEY_SOFT']: alertas.append("Factura no coincide")
                    if abs(r['MONTO_KEY_TAX'] - r['MONTO_KEY_SOFT']) > 0.1: alertas.append("Monto Descuadrado")
                    
                    return "✅ Correcto" if not alertas else "⚠️ " + " | ".join(alertas)

                conciliacion['Resultado_Validacion'] = conciliacion.apply(validar_fila, axis=1)

                # 5. MOSTRAR RESULTADOS ORGANIZADOS
                st.success(f"Análisis finalizado. {len(conciliacion)} registros evaluados.")
                
                # Resumen de métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Correctos", len(conciliacion[conciliacion['Resultado_Validacion'] == "✅ Correcto"]))
                m2.metric("Con Errores", len(conciliacion[conciliacion['Resultado_Validacion'].str.contains("⚠️")]))
                m3.metric("Faltantes", len(conciliacion[conciliacion['Resultado_Validacion'].str.contains("Falta")]))

                # Filtro de visualización
                opcion = st.selectbox("Filtrar resultados por:", ["Todos", "Solo Errores y Faltantes", "Correctos"])
                
                df_mostrar = conciliacion
                if opcion == "Solo Errores y Faltantes":
                    df_mostrar = conciliacion[conciliacion['Resultado_Validacion'] != "✅ Correcto"]
                elif opcion == "Correctos":
                    df_mostrar = conciliacion[conciliacion['Resultado_Validacion'] == "✅ Correcto"]

                st.dataframe(df_mostrar[[
                    'COMP_KEY', 'Resultado_Validacion', 
                    'FECHA_TAX', 'FECHA_KEY', 
                    'FACT_TAX_RAW', 'Referencia', 
                    'MONTO_KEY_TAX', 'MONTO_KEY_SOFT', 'Asiento'
                ]])

    except Exception as e:
        st.error(f"Error en el proceso: {e}")

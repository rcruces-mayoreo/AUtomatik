import streamlit as st
import pandas as pd
import re

# Configuración visual
st.set_page_config(page_title="Beval - Validación IVA", layout="wide")

def extraer_factura(referencia):
    """Extrae el número de factura de glosas como '75% RET IVA FACT 033955'"""
    ref_str = str(referencia).upper()
    match = re.search(r'(?:FACT|FAC|NRO|N/D|N/C)\s*([A-Za-z0-9-]+)', ref_str)
    return match.group(1).strip() if match else ref_str.strip()

def limpiar_rif(rif):
    if pd.isna(rif): return ""
    return str(rif).replace("-", "").replace(" ", "").upper()

st.title("🚀 Sistema de Validación Contable - Mayor Beval")
st.subheader("Conciliación: Libro de Compras vs Softland")

# --- CARGA DE DATOS ---
col1, col2 = st.columns(2)
with col1:
    f_softland = st.file_uploader("Subir Libro Diario (Softland)", type=['xlsx', 'xls'])
with col2:
    f_libro = st.file_uploader("Subir Libro de Compras", type=['xlsx', 'xls'])

if f_softland and f_libro:
    try:
        # Cargar Softland (Probamos motores para .xlsx o .xls)
        engine_soft = 'openpyxl' if f_softland.name.endswith('xlsx') else 'xlrd'
        df_soft = pd.read_excel(f_softland, engine=engine_soft)
        
        # Cargar Libro (Probamos motores)
        engine_lib = 'openpyxl' if f_libro.name.endswith('xlsx') else 'xlrd'
        fila_encabezado = st.number_input("¿En qué fila están los títulos en el Libro de Compras?", value=7)
        df_lcf = pd.read_excel(f_libro, skiprows=fila_encabezado-1, engine=engine_lib)

        if st.button("Ejecutar Validación"):
            # 1. Procesar Softland (Cuenta de Retenciones IVA)
            cta = "2.1.3.05.1.001"
            soft_filtrado = df_soft[df_soft['Cuenta Contable'] == cta].copy()
            
            if soft_filtrado.empty:
                st.error(f"No se encontraron movimientos en la cuenta {cta}. Revisa el archivo de Softland.")
            else:
                soft_filtrado['RIF_ID'] = soft_filtrado['Nit'].apply(limpiar_rif)
                soft_filtrado['FACT_ID'] = soft_filtrado['Referencia'].apply(extraer_factura)

                # 2. Procesar Libro de Compras
                df_lcf.columns = [str(c).strip() for c in df_lcf.columns] # Limpiar nombres de columnas
                df_lcf['RIF_ID'] = df_lcf['RIF'].apply(limpiar_rif)
                
                # Buscar columna de factura (columna 8 típicamente)
                col_fact_lcf = 'Nro. Factura' if 'Nro. Factura' in df_lcf.columns else df_lcf.columns[7]
                df_lcf['FACT_ID'] = df_lcf[col_fact_lcf].astype(str).str.strip()

                # 3. Cruzar información
                cruce = pd.merge(
                    df_lcf,
                    soft_filtrado[['RIF_ID', 'FACT_ID', 'Crédito Bolívar', 'Asiento', 'Referencia']],
                    on=['RIF_ID', 'FACT_ID'],
                    how='outer',
                    indicator=True
                )

                # 4. Mostrar Resultados
                st.success("✅ Análisis Completado")
                
                col_monto_lcf = 'IVA Retenido' if 'IVA Retenido' in cruce.columns else cruce.columns[-1]
                cruce['Diferencia'] = cruce[col_monto_lcf].fillna(0) - cruce['Crédito Bolívar'].fillna(0)

                # Tabs para organizar resultados
                tab1, tab2, tab3 = st.tabs(["Diferencias de Monto", "Faltantes en Softland", "Todo el Cruce"])
                
                with tab1:
                    descuadres = cruce[(cruce['_merge'] == 'both') & (cruce['Diferencia'].abs() > 0.05)]
                    if not descuadres.empty:
                        st.warning("⚠️ Montos que no coinciden:")
                        st.dataframe(descuadres[['RIF_ID', 'FACT_ID', col_monto_lcf, 'Crédito Bolívar', 'Diferencia', 'Asiento']])
                    else:
                        st.write("No hay diferencias de montos.")

                with tab2:
                    faltantes = cruce[cruce['_merge'] == 'left_only']
                    if not faltantes.empty:
                        st.error(f"Se encontraron {len(faltantes)} facturas sin asiento contable.")
                        st.dataframe(faltantes[['RIF_ID', 'FACT_ID', col_monto_lcf]])
                    else:
                        st.write("Todas las facturas del libro tienen su asiento.")
                
                with tab3:
                    st.write("Data completa del proceso:")
                    st.dataframe(cruce)

    except Exception as e:
        st.error(f"Error técnico: {e}")
        st.info("Asegúrate de que los archivos no estén protegidos por contraseña y tengan el formato correcto.")
else:
    st.info("Carga los archivos para iniciar.")

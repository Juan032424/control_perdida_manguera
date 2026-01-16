import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(
    page_title="Control y Pérdida de Mangueras",
    layout="wide"
)

st.title("🚨 Análisis de Pérdida de Mangueras")
st.markdown("""
Este análisis permite **identificar responsables**, **antigüedad del material** 
y **niveles de riesgo**, para sustentar decisiones y acciones correctivas.
""")

# =========================
# CARGA ARCHIVO ORIGINAL
# =========================
archivo = st.file_uploader(
    "📂 Suba el archivo ORIGINAL de inventario",
    type=["xlsx"]
)

if archivo:
    xls = pd.ExcelFile(archivo)
    data = []

    for hoja in xls.sheet_names:
        df_sheet = pd.read_excel(xls, sheet_name=hoja, header=1)
        
        # Lógica para detectar secciones (TABLET, NORMAL, DEVOLUCION)
        current_origin = "NORMAL"
        orig_column = []
        for val in df_sheet.iloc[:, 0]:
            str_val = str(val).upper()
            if "TABLET" in str_val:
                current_origin = "TABLET"
            elif "DEVOLUCION" in str_val:
                current_origin = "NORMAL" # Las devoluciones vuelven al flujo normal o se marcan aparte
            orig_column.append(current_origin)
        
        df_sheet["Origen"] = orig_column
        df_sheet["Hoja"] = hoja
        data.append(df_sheet)

    df_all = pd.concat(data, ignore_index=True)

    # Eliminar filas decorativas (donde el ID no es numérico)
    df_all = df_all[pd.to_numeric(df_all["Id"], errors="coerce").notnull()].copy()

    # =========================
    # LIMPIEZA
    # =========================
    df_all["Salida"] = pd.to_numeric(df_all["Salida"], errors="coerce").fillna(0)
    df_all["Entrada"] = pd.to_numeric(df_all["Entrada"], errors="coerce").fillna(0)
    df_all["Fecha"] = pd.to_datetime(df_all["Fecha"], errors="coerce")

    # Filtrar solo mangueras (base)
    df_m_raw = df_all[
        df_all["Items"].str.contains("MANGUERA", na=False, case=False)
    ].copy()

    # =========================
    # FILTROS LATERALES
    # =========================
    st.sidebar.header("🔍 Filtros de Material")
    tipos_manguera = sorted(df_m_raw["Items"].unique())
    sel_tipos = st.sidebar.multiselect(
        "Seleccione tipo(s) de manguera:",
        tipos_manguera,
        default=tipos_manguera
    )

    if not sel_tipos:
        st.warning("⚠️ Seleccione al menos un tipo de manguera en el menú lateral.")
        st.stop()

    df_m = df_m_raw[df_m_raw["Items"].isin(sel_tipos)].copy()

    # =========================
    # CONSOLIDADO POR GESTOR (BASADO EN HOJAS)
    # =========================
    # El usuario indica que cada hoja es un gestor diferente
    df_m["Gestor"] = df_m["Hoja"].str.upper()

    resumen = (
        df_m.groupby(["Gestor"])
        .agg(
            Entregas_Salida=("Salida", "sum"),
            Devoluciones_Entrada=("Entrada", "sum"),
            Ultima_Actividad=("Fecha", "max"),
            Num_Movimientos=("Id", "count")
        )
        .reset_index()
    )

    # Cálculo de Stock Real (Neto)
    resumen["Stock_Actual"] = resumen["Entregas_Salida"] - resumen["Devoluciones_Entrada"]

    # Calculamos días desde la última actividad para riesgo de inactividad
    resumen["Dias_Inactivo"] = (
        datetime.now() - resumen["Ultima_Actividad"]
    ).dt.days.fillna(0)

    # =========================
    # SEMÁFORO DE RIESGO (Basado en Stock Actual)
    # =========================
    def riesgo(row):
        if row["Stock_Actual"] >= 150 or row["Dias_Inactivo"] > 60:
            return "🔴 ALTO"
        elif row["Stock_Actual"] >= 80 or row["Dias_Inactivo"] > 30:
            return "🟠 MEDIO"
        else:
            return "🟢 BAJO"

    resumen["Riesgo"] = resumen.apply(riesgo, axis=1)

    # =========================
    # TABLA DE ARGUMENTOS
    # =========================
    st.dataframe(
        resumen.sort_values(["Stock_Actual"], ascending=False)[[
            "Gestor", "Stock_Actual", "Entregas_Salida", 
            "Devoluciones_Entrada", "Riesgo", "Dias_Inactivo"
        ]],
        use_container_width=True,
        hide_index=True
    )

    # =========================
    # KPIs PERSONALIZADOS
    # =========================
    total_e = int(resumen['Entregas_Salida'].sum())
    total_d = int(resumen['Devoluciones_Entrada'].sum())
    total_p = int(resumen['Stock_Actual'].sum())

    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        st.markdown(f"""
            <div style="background-color:#d4edda; padding:20px; border-radius:10px; border-left: 8px solid #28a745;">
                <h4 style="color:#155724; margin:0;">✅ Material Entregado</h4>
                <p style="color:#155724; font-size:35px; font-weight:bold; margin:0;">{total_e} m</p>
            </div>
        """, unsafe_allow_html=True)

    with kpi2:
        st.markdown(f"""
            <div style="background-color:#fff3cd; padding:20px; border-radius:10px; border-left: 8px solid #ffc107;">
                <h4 style="color:#856404; margin:0;">🔄 Material Devuelto</h4>
                <p style="color:#856404; font-size:35px; font-weight:bold; margin:0;">{total_d} m</p>
            </div>
        """, unsafe_allow_html=True)

    with kpi3:
        st.markdown(f"""
            <div style="background-color:#f8d7da; padding:20px; border-radius:10px; border-left: 8px solid #dc3545;">
                <h4 style="color:#721c24; margin:0;">🚨 Por Devolver / Legalizar</h4>
                <p style="color:#721c24; font-size:35px; font-weight:bold; margin:0;">{total_p} m</p>
            </div>
        """, unsafe_allow_html=True)

    # =========================
    # PANEL DE TOMA DE DECISIONES
    # =========================
    st.divider()
    st.header("🎯 Análisis para Toma de Decisiones")
    
    gestor_sel = st.selectbox("Seleccione un Gestor para profundizar:", sorted(resumen["Gestor"].unique()))
    
    if gestor_sel:
        row_g = resumen[resumen["Gestor"] == gestor_sel].iloc[0]
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.metric("Stock Actual", f"{int(row_g['Stock_Actual'])} m")
        with col_b:
            st.metric("Total Devuelto", f"{int(row_g['Devoluciones_Entrada'])} m")
        with col_c:
            st.metric("Días desde última actividad", f"{int(row_g['Dias_Inactivo'])} días")

        # Alertas Personalizadas
        if row_g["Stock_Actual"] > 100:
            st.warning(f"⚠️ **Atención**: {gestor_sel} tiene un stock superior a 100m. Se recomienda solicitar devolución parcial.")
        if row_g["Dias_Inactivo"] > 30:
            st.error(f"🚨 **Crítico**: El gestor no ha reportado movimientos en más de 30 días. Posible material estancado.")
        
        # Detalle de movimientos del gestor
        st.subheader(f"📜 Últimos Movimientos - {gestor_sel}")
        det_gestor = df_m[df_m["Gestor"] == gestor_sel].sort_values("Fecha", ascending=False)
        st.dataframe(
            det_gestor[["Fecha", "Origen", "Proceso", "Salida", "Entrada", "Id"]],
            use_container_width=True,
            hide_index=True
        )

        # Resumen Tablet vs Normal
        st.markdown("**Desglose por Origen:**")
        tablet_stats = det_gestor.groupby("Origen")["Salida"].sum()
        st.write(tablet_stats)

    # =========================
    # PARETO 80/20
    # =========================
    st.divider()
    st.subheader("📈 Concentración del Stock (Pareto)")

    pareto = (
        resumen.groupby("Gestor")["Stock_Actual"]
        .sum()
        .sort_values(ascending=False)
    )

    fig, ax = plt.subplots()
    pareto.plot(kind="bar", ax=ax)
    ax.set_ylabel("Cantidad")
    ax.set_title("Gestores que concentran la manguera")

    st.pyplot(fig)

    # =========================
    # MENSAJE GERENCIAL
    # =========================
    st.success("""
    📌 **Interpretación clave**:
    - La manguera entregada queda bajo responsabilidad del gestor.
    - La antigüedad sin devolución incrementa el riesgo de pérdida.
    - La concentración en pocos gestores evidencia fallas de control.
    """)

    st.success("""
    📌 **Interpretación clave**:
    - SEGUN REPORTES DE ALMACEN HAY VECES QUE EN LA LIMPIEZA DE LOS CARROS DE TRANSPORTE DE MATERIALES SUELEN QUEDARSE
    RETAZOS DE MANGUERA QUE SE ENCUENTRAN EN YA USADOS PERO COMO ALMACEN NO PUEDE RECIBIR MENOS DE 2M DE MANGUERA EN DEVOLUCION
    LO DEJAN EN EL CARRO DE TRANSPORTEN Y NO SOPORTAN QUE PASO CON ESOS RECORTES QUE QUEDARON Y QUE NO SE PUDIERON DEVOLVER
    """)
else:
    st.info("⬆️ Cargue el archivo para iniciar el análisis.")

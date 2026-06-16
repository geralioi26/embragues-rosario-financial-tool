import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from PIL import Image

# 1. IDENTIDAD
st.set_page_config(page_title="Embragues Rosario", page_icon="logo.png")
try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Embragues Rosario")
st.markdown("Crespo 4117, Rosario | **IIBB: EXENTO**")

# ==========================================
# 🚨 PEGA TU LINK ACÁ ABAJO ENTRE LAS COMILLAS
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YJHJ006kr-izLHG9Ib5CRUX5VUdu6INRDsKn4u0x32Y/edit"
# ==========================================

# --- CONEXIÓN SEGURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# ==============================================================
# SOLUCIÓN RATE LIMIT: funciones cacheadas con @st.cache_data
# ==============================================================

@st.cache_data(ttl=600, show_spinner=False)
def leer_hoja(url, hoja):
    return conn.read(spreadsheet=url, worksheet=hoja)

def leer_hoja_fresca(url, hoja):
    return conn.read(spreadsheet=url, worksheet=hoja, ttl=0)

# --- CARGA DE COEFICIENTES DESDE SHEETS (cacheada) ---
try:
    df_config = leer_hoja(SHEET_URL, "Configuracion")
    config = dict(zip(df_config["Parametro"], df_config["Valor"]))
    GETNET_1    = float(config.get("GETNET_1_PAGO",    1.0223))
    GETNET_3    = float(config.get("GETNET_3_CUOTAS",  1.1247))
    GETNET_6    = float(config.get("GETNET_6_CUOTAS",  1.2330))
    MASPAGOS_1  = float(config.get("MASPAGOS_1_PAGO",  1.0286))
    MASPAGOS_3  = float(config.get("MASPAGOS_3_CUOTAS",1.1450))
    MASPAGOS_6  = float(config.get("MASPAGOS_6_CUOTAS",1.2898))
except Exception as e:
    st.warning(f"⚠️ No se pudo leer 'Configuracion'. Usando valores de respaldo. ({e})")
    GETNET_1, GETNET_3, GETNET_6        = 1.0223, 1.1247, 1.2330
    MASPAGOS_1, MASPAGOS_3, MASPAGOS_6 = 1.0286, 1.1450, 1.2898

# --- CARGA DE CATÁLOGOS (cacheada) ---
try:
    df_kits   = leer_hoja(SHEET_URL, "Catalogo_Kits")
    df_crapo  = leer_hoja(SHEET_URL, "Catalogo_Crapodinas")
    df_distri = leer_hoja(SHEET_URL, "Catalogo_Distribucion")
    df_ventas = leer_hoja(SHEET_URL, "Ventas")
except Exception as e:
    st.warning(f"⚠️ Error al leer los catálogos: {e}")
    df_kits = df_crapo = df_distri = df_ventas = pd.DataFrame()

# --- FUNCIÓN AUXILIAR: GUARDAR EN CATÁLOGO DE KITS ---
def actualizar_catalogo_kits(vehiculo, descripcion, codigo, precio, marca):
    try:
        df = leer_hoja_fresca(SHEET_URL, "Catalogo_Kits")
        marca_limpia = str(marca).upper()
        col_cod = f"Codigo_{marca_limpia}"
        col_pre = f"Precio_{marca_limpia}"
        if col_cod not in df.columns:
            st.warning(f"⚠️ La marca {marca_limpia} no tiene columnas en Kits.")
            return
        vehiculo_limpio = str(vehiculo).strip().lower()
        desc_limpia     = str(descripcion).strip().lower()
        cod_buscado     = str(codigo).split('.')[0].strip()
        filtro_exacto = (
            (df['Vehiculo'].astype(str).str.strip().str.lower() == vehiculo_limpio) &
            (df['Descripcion'].astype(str).str.strip().str.lower() == desc_limpia)
        )
        codigos_col   = df[col_cod].astype(str).str.split('.').str[0].str.strip()
        filtro_codigo = codigos_col == cod_buscado
        if filtro_exacto.any():
            idx = df.index[filtro_exacto][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
            msg = f"✅ Kit {marca_limpia} actualizado para {vehiculo}"
        elif filtro_codigo.any():
            idx = df.index[filtro_codigo][0]
            v_actual = str(df.at[idx, 'Vehiculo'])
            if vehiculo_limpio not in v_actual.lower():
                df.at[idx, 'Vehiculo'] = f"{v_actual} / {vehiculo}"
            df.at[idx, col_pre] = precio
            msg = f"🔗 Kit equivalente detectado: {vehiculo}"
        else:
            nueva_fila = {col: "" for col in df.columns}
            nueva_fila["Vehiculo"]    = vehiculo
            nueva_fila["Descripcion"] = descripcion
            nueva_fila[col_cod]       = codigo
            nueva_fila[col_pre]       = precio
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            msg = f"✨ Nuevo Kit en catálogo: {vehiculo}"
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        leer_hoja.clear()
        st.toast(msg, icon="📦")
    except Exception as e:
        st.error(f"Error en catálogo de kits: {e}")

# --- FUNCIÓN PARA GUARDAR CRAPODINAS NUEVAS ---
def actualizar_catalogo_crapodinas(vehiculo, descripcion, codigo, precio, marca):
    try:
        df = leer_hoja_fresca(SHEET_URL, "Catalogo_Crapodinas")
        marca_limpia = str(marca).upper()
        col_cod = f"Codigo_{marca_limpia}"
        col_pre = f"Precio_{marca_limpia}"
        if col_cod not in df.columns:
            st.warning(f"⚠️ La marca {marca_limpia} no tiene columnas.")
            return
        vehiculo_limpio = str(vehiculo).strip().lower()
        desc_limpia     = str(descripcion).strip().lower()
        cod_buscado     = str(codigo).split('.')[0].strip()
        filtro_exacto = (
            (df['Vehiculo'].astype(str).str.strip().str.lower() == vehiculo_limpio) &
            (df['Descripcion'].astype(str).str.strip().str.lower() == desc_limpia)
        )
        codigos_col   = df[col_cod].astype(str).str.split('.').str[0].str.strip()
        filtro_codigo = codigos_col == cod_buscado
        if filtro_exacto.any():
            idx = df.index[filtro_exacto][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
            msg = f"✅ Datos actualizados: {vehiculo} ({marca_limpia})"
        elif filtro_codigo.any():
            idx = df.index[filtro_codigo][0]
            v_actual = str(df.at[idx, 'Vehiculo'])
            if vehiculo_limpio not in v_actual.lower():
                df.at[idx, 'Vehiculo'] = f"{v_actual} / {vehiculo}"
            df.at[idx, col_pre] = precio
            msg = f"🔗 Equivalencia: {codigo} ahora también en {vehiculo}"
        else:
            nueva_fila = {col: "" for col in df.columns}
            nueva_fila["Vehiculo"]    = vehiculo
            nueva_fila["Descripcion"] = descripcion
            nueva_fila[col_cod]       = codigo
            nueva_fila[col_pre]       = precio
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            msg = f"✨ Nuevo en catálogo: {vehiculo}"
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", data=df)
        leer_hoja.clear()
        st.toast(msg, icon="⚙️")
    except Exception as e:
        st.error(f"Error al actualizar catálogo de crapodinas: {e}")

# --- FUNCIÓN PRINCIPAL DE GUARDADO ---
def guardar_en_google(categoria, cliente, vehiculo, detalle, monto, costo, proveedor,
                      cod_kit, cod_crap, f_pago, e_cliente, e_prov,
                      m_forros, c_forros, costo_f, ganancia):
    fecha_hoy = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    columnas = [
        "Fecha", "Categoría", "Cliente", "Vehículo", "Detalle",
        "Venta $", "Compra $", "Proveedor", "Código", "Cod_Crapodina",
        "Forma_de_pago", "Estado_Cobro", "Estado_Pago_Prov",
        "Marca_Forros", "Cod_Forros", "Costo_Forros", "Ganancia"
    ]
    try:
        df_existente = leer_hoja_fresca(SHEET_URL, "Ventas")
    except Exception as e:
        st.error(f"Error al leer hoja Ventas: {e}")
        st.stop()
    nuevo_reg    = pd.DataFrame([[fecha_hoy, categoria, cliente, vehiculo, detalle,
                                  monto, costo, proveedor, cod_kit, cod_crap,
                                  f_pago, e_cliente, e_prov,
                                  m_forros, c_forros, costo_f, ganancia]],
                                columns=columnas)
    df_actualizado = pd.concat([df_existente, nuevo_reg], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_actualizado)
    leer_hoja.clear()

# --- FUNCIÓN PARA MARCAR COBRO ---
def marcar_como_pagado(idx_fila, forma_pago):
    try:
        df = leer_hoja_fresca(SHEET_URL, "Ventas")
        df.at[idx_fila, "Estado_Cobro"]  = "Pagado"
        df.at[idx_fila, "Forma_de_pago"] = forma_pago
        conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df)
        leer_hoja.clear()
        st.toast("✅ Cobro registrado", icon="💰")
    except Exception as e:
        st.error(f"Error al actualizar cobro: {e}")

# 2. PANEL DE CARGA
st.sidebar.header("⚙️ Configuración")

# Inicialización defensiva
m_kit         = ""
m_forros      = ""
forros_codigo = ""
forros_costo  = 0
crap_codigo   = ""
crap_costo    = 0
tipo_crap     = ""
m_crap        = []

tipo_item = st.sidebar.selectbox("Tipo de Trabajo:",
                                 ["Embrague Nuevo (Venta)",
                                  "Reparación de Embrague",
                                  "Kit de Distribución",
                                  "Otro"])

if "Nuevo" in tipo_item:
    cat_f, icono, incl_rectif = "Venta", "⚙️", True
    lista_marcas = ["LUK", "SACHS", "VALEO", "PHC_VALEO", "ORIGINAL", "OTRA"]
    m_kit = st.sidebar.selectbox("Marca del Kit:", lista_marcas)
    sugerencia = f"KIT nuevo marca *{m_kit}*"
elif "Reparación" in tipo_item:
    cat_f, icono, incl_rectif = "Reparación", "🔧", False
    m_crap = st.sidebar.multiselect("Marcas de Crapodina:",
                                    ["Luk", "Skf", "Ina", "Dbh", "The"],
                                    default=["Luk", "Skf"])
    crap_codigo   = st.sidebar.text_input("Código de Crapodina:", "")
    crap_costo    = st.sidebar.number_input("Costo de Crapodina ($):", min_value=0, value=0)
    tipo_crap     = st.sidebar.selectbox("⚙️ Tipo de Crapodina:", ["Hidráulica", "Mecánica"])
    m_forros      = st.sidebar.selectbox("Marca de Forros:", ["IAR", "Fras-le", "Termolite", "Otro"])
    forros_codigo = st.sidebar.text_input("Código de Forros:", "")
    forros_costo  = st.sidebar.number_input("Costo de Forros ($):", min_value=0, value=0)
    m_neg = [f"*{m}*" for m in m_crap]
    if len(m_neg) > 1:
        t_m = ", ".join(m_neg[:-1]) + " o " + m_neg[-1]
    elif m_neg:
        t_m = m_neg[0]
    else:
        t_m = "*primera marca*"
    sugerencia = f"reparado completo placa disco con forros originales volante rectificado y balanceado con crapodina {t_m}"
else:
    cat_f, icono, incl_rectif = "Venta", "🛠️", False
    sugerencia = "KIT de distribución"

monto_limpio   = st.sidebar.number_input("Precio de VENTA ($):", min_value=0, value=0)
vehiculo_input = st.sidebar.text_input("Vehículo:", "citroen c4 1.6")
cliente_input  = st.sidebar.text_input("Nombre del Cliente:", "Consumidor Final")
detalle_excel  = st.sidebar.text_input("📝 Detalle para Excel:", value="Reparación completa")
detalle_final  = st.sidebar.text_area("💬 Detalle en WhatsApp:", value=sugerencia)

st.sidebar.divider()
st.sidebar.write("📸 **Uso Interno**")

if cat_f == "Reparación":
    codigo_manual = crap_codigo
    precio_compra = crap_costo + forros_costo
    st.sidebar.info(f"💰 Costo Materiales: ${precio_compra:,.0f}")
else:
    codigo_manual = st.sidebar.text_input("Código de repuesto:", "")
    precio_compra = st.sidebar.number_input("Precio de COMPRA ($):", min_value=0, value=0)

foto_repuesto = st.sidebar.file_uploader("📷 Sacar foto a la caja/repuesto", type=["jpg", "png", "jpeg"])
if foto_repuesto:
    st.sidebar.image(foto_repuesto, caption="Vista previa", use_container_width=True)

ganancia = monto_limpio - precio_compra
if monto_limpio > 0:
    st.sidebar.metric("Ganancia Estimada", f"$ {ganancia:,.0f}")

proveedor_input = st.sidebar.text_input("Proveedor:", "icepar")

st.sidebar.divider()
st.sidebar.subheader("💰 Estado de la Operación")

estado_cliente = st.sidebar.selectbox("Estado del Cliente:", ["Pagado", "Debe", "Seña"], index=0)

f_pago_input = "N/A"
if estado_cliente == "Pagado":
    lista_pagos = [
        "Efectivo", "Transferencia", "Débito",
        "BNA - 1 Pago", "BNA - 3 Cuotas", "BNA - 6 Cuotas",
        "Getnet - 1 Pago", "Getnet - 3 Cuotas", "Getnet - 6 Cuotas",
        "Combinado", "Otro"
    ]
    f_pago_input = st.sidebar.selectbox("¿Cómo pagó el cliente?:", lista_pagos)

estado_p_prov = st.sidebar.selectbox("Estado al Proveedor:", ["Pagado", "Cuenta Corriente", "N/A"], index=0)

if cat_f == "Reparación":
    cod_kit_final  = ""
    cod_crap_final = crap_codigo
else:
    cod_kit_final  = codigo_manual
    cod_crap_final = ""

# =============================================
# MEJORA 1: CONFIRMACIÓN ANTES DE GUARDAR
# =============================================
if st.sidebar.button("💾 GUARDAR VENTA"):
    st.session_state["confirmar_venta"] = True

if st.session_state.get("confirmar_venta"):
    st.sidebar.warning(
        f"⚠️ **¿Confirmar esta venta?**\n\n"
        f"🚗 **Vehículo:** {vehiculo_input}\n\n"
        f"👤 **Cliente:** {cliente_input}\n\n"
        f"💰 **Monto:** ${monto_limpio:,.0f}"
    )
    col_si, col_no = st.sidebar.columns(2)
    if col_si.button("✅ Confirmar", use_container_width=True):
        st.session_state["confirmar_venta"] = False
        guardar_en_google(cat_f, cliente_input, vehiculo_input, detalle_excel,
                          monto_limpio, precio_compra, proveedor_input,
                          cod_kit_final, cod_crap_final, f_pago_input,
                          estado_cliente, estado_p_prov,
                          m_forros, forros_codigo, forros_costo, ganancia)
        if cod_kit_final:
            marca_kit_final = m_kit[0] if isinstance(m_kit, list) and m_kit else (m_kit or "OTRA")
            actualizar_catalogo_kits(vehiculo_input, "Kit de Embrague", cod_kit_final, monto_limpio, marca_kit_final)
        if cod_crap_final:
            marca_elegida = m_crap[0] if m_crap else "OTRA"
            actualizar_catalogo_crapodinas(vehiculo_input, f"Crapodina {tipo_crap}", cod_crap_final, crap_costo, marca_elegida)
        st.sidebar.success(f"✅ ¡Venta de ${monto_limpio:,.0f} guardada!")
    if col_no.button("❌ Cancelar", use_container_width=True):
        st.session_state["confirmar_venta"] = False
        st.sidebar.info("Venta cancelada.")

# 3. CALCULADORA MULTI-POS
st.markdown("### 💳 Calculadora de Cuotas")
tipo_pos = st.radio("¿Qué POS vas a usar?", ["GETNET (18 días)", "MÁS PAGOS (18 días)"], horizontal=True)

if "GETNET" in tipo_pos:
    c1, c3, c6 = GETNET_1, GETNET_3, GETNET_6
    nombre_pos  = "GETNET"
else:
    c1, c3, c6 = MASPAGOS_1, MASPAGOS_3, MASPAGOS_6
    nombre_pos  = "MÁS PAGOS"

t1 = monto_limpio * c1
t3 = monto_limpio * c3
t6 = monto_limpio * c6

p_1, p_3, p_6 = [(x - 1) * 100 for x in [c1, c3, c6]]
st.info(f"📊 **Recargos Reales:** 1 Pago: {p_1:.1f}% | 3 Cuotas: {p_3:.1f}% | 6 Cuotas: {p_6:.1f}%")

st.divider()
st.markdown(f"""
    <div style='background-color: #d4edda; padding: 10px; border-radius: 5px;
                text-align: center; border: 2px solid #28a745;'>
        <h2 style='color: #155724; margin:0;'>💰 CONTADO / TRANSF: $ {monto_limpio:,.0f}</h2>
        <p style='margin:0; font-size: 0.9em;'>(Este monto te queda limpio)</p>
    </div>
    """, unsafe_allow_html=True)

st.write(f"**Precios de Lista con {nombre_pos}:**")
col_a, col_b, col_c = st.columns(3)
with col_a: st.metric("1 PAGO",   f"$ {t1:,.0f}")
with col_b: st.metric("3 CUOTAS", f"$ {t3/3:,.2f}", f"Total: ${t3:,.0f}")
with col_c: st.metric("6 CUOTAS", f"$ {t6/6:,.2f}", f"Total: ${t6:,.0f}")

# 4. WHATSAPP
txt_rectif = "\n✅ *Incluye rectificación y balanceo de volante*" if incl_rectif else ""
maps_link  = "https://www.google.com/maps?q=Crespo+4117+Rosario"

mensaje = (
    f"🚗 *EMBRAGUES ROSARIO*\n"
    f"¡Hola! Gracias por tu consulta. Te paso el presupuesto:\n\n"
    f"🚗 *Vehículo:* {vehiculo_input}\n"
    f"{icono} *Trabajo:* {detalle_final}"
    f"{txt_rectif}\n\n"
    f"💰 *EFECTIVO / TRANSF:* ${monto_limpio:,.0f}\n\n"
    f"💳 *TARJETA BANCARIA ({nombre_pos}):*\n"
    f"✅ *1 pago:* ${t1:,.0f}\n\n"
    f"✅ *3 cuotas de:* ${t3/3:,.2f}\n"
    f"      (Total: ${t3:,.0f})\n\n"
    f"✅ *6 cuotas de:* ${t6/6:,.2f}\n"
    f"      (Total: ${t6:,.0f})\n\n"
    f"📍 *Dirección:* Crespo 4117, Rosario\n"
    f"📍 *Ubicación:* {maps_link}\n"
    f"📸 *Instagram:* @embraguesrosario\n"
    f"⏰ *Horario:* 8:30 a 17:00 hs\n\n"
    f"¡Te esperamos pronto! 🙋🏻"
)

link_wa = f"https://wa.me/?text={urllib.parse.quote(mensaje)}"
st.link_button("🟢 ENVIAR PRESUPUESTO POR WHATSAPP", link_wa)

# 5. HISTORIAL
st.divider()
st.subheader("📋 Últimos Movimientos")
try:
    df_ver = leer_hoja(SHEET_URL, "Ventas")
    if not df_ver.empty:
        st.dataframe(df_ver.tail(5)[::-1], use_container_width=True)
    else:
        st.info("La planilla está vacía todavía.")
except Exception as e:
    st.warning("⚠️ No se pudo cargar el historial.")

# =============================================
# MEJORA 2: RESUMEN DE VENTAS
# =============================================
st.divider()
st.header("📊 Resumen de Ventas")

try:
    df_res = leer_hoja(SHEET_URL, "Ventas").copy()
    if not df_res.empty and "Fecha" in df_res.columns:
        df_res["Fecha_dt"] = pd.to_datetime(df_res["Fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
        df_res["Venta $"]  = pd.to_numeric(df_res["Venta $"],  errors="coerce").fillna(0)
        df_res["Ganancia"] = pd.to_numeric(df_res["Ganancia"], errors="coerce").fillna(0)

        ahora    = datetime.now() - timedelta(hours=3)
        hoy      = ahora.date()
        lun      = hoy - timedelta(days=hoy.weekday())
        primer_d = hoy.replace(day=1)

        mask_hoy  = df_res["Fecha_dt"].dt.date == hoy
        mask_sem  = df_res["Fecha_dt"].dt.date >= lun
        mask_mes  = df_res["Fecha_dt"].dt.date >= primer_d

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📅 Hoy",
                      f"${df_res[mask_hoy]['Venta $'].sum():,.0f}",
                      f"{mask_hoy.sum()} trabajo(s)")
        with col2:
            st.metric("📆 Esta semana",
                      f"${df_res[mask_sem]['Venta $'].sum():,.0f}",
                      f"{mask_sem.sum()} trabajo(s)")
        with col3:
            st.metric("🗓️ Este mes",
                      f"${df_res[mask_mes]['Venta $'].sum():,.0f}",
                      f"{mask_mes.sum()} trabajo(s)")

        st.divider()
        col4, col5 = st.columns(2)
        with col4:
            st.metric("💰 Ganancia del mes",
                      f"${df_res[mask_mes]['Ganancia'].sum():,.0f}")
        with col5:
            if "Categoría" in df_res.columns:
                tipos = df_res[mask_mes]["Categoría"].value_counts()
                resumen_tipos = " | ".join([f"{k}: {v}" for k, v in tipos.items()])
                st.metric("🔧 Trabajos del mes por tipo", resumen_tipos if resumen_tipos else "—")

    else:
        st.info("Todavía no hay ventas registradas para mostrar.")
except Exception as e:
    st.warning(f"⚠️ No se pudo cargar el resumen: {e}")

# =============================================
# MEJORA 3: COBROS PENDIENTES
# =============================================
st.divider()
st.header("💸 Cobros Pendientes")

try:
    df_pend = leer_hoja(SHEET_URL, "Ventas").copy()
    if not df_pend.empty and "Estado_Cobro" in df_pend.columns:
        pendientes = df_pend[df_pend["Estado_Cobro"].isin(["Debe", "Seña"])].copy()
        if pendientes.empty:
            st.success("✅ No hay cobros pendientes.")
        else:
            st.warning(f"Hay **{len(pendientes)}** cobro(s) pendiente(s):")
            lista_pagos_cobro = [
                "Efectivo", "Transferencia", "Débito",
                "BNA - 1 Pago", "BNA - 3 Cuotas", "BNA - 6 Cuotas",
                "Getnet - 1 Pago", "Getnet - 3 Cuotas", "Getnet - 6 Cuotas",
                "Combinado", "Otro"
            ]
            for pos, (idx, fila) in enumerate(pendientes.iterrows()):
                with st.expander(
                    f"{'🔴' if fila.get('Estado_Cobro') == 'Debe' else '🟡'} "
                    f"{fila.get('Fecha','—')} | {fila.get('Vehículo','—')} | "
                    f"{fila.get('Cliente','—')} | ${float(fila.get('Venta $', 0)):,.0f} "
                    f"({fila.get('Estado_Cobro','—')})"
                ):
                    fp_key = f"fp_cobro_{pos}_{idx}"
                    forma_cobro = st.selectbox("Forma de pago:", lista_pagos_cobro, key=fp_key)
                    if st.button("✅ Marcar como Pagado", key=f"pagar_{pos}_{idx}"):
                        marcar_como_pagado(idx, forma_cobro)
                        st.rerun()
    else:
        st.info("No hay datos de ventas todavía.")
except Exception as e:
    st.warning(f"⚠️ No se pudo cargar los pendientes: {e}")

# 6. BUSCADOR DE CATÁLOGO
st.divider()
st.header("🔍 Consultar Catálogo")

tipo_busqueda = st.radio("¿Qué estás buscando?",
                         ["Embragues (Kits)", "Crapodinas", "Distribución"],
                         horizontal=True)
busqueda = st.text_input("✍️ Escribí Modelo de Auto o Código (Ej: 'Gol', '620 3000', 'Ranger'):")

if busqueda:
    st.caption(f"Resultados para: '{busqueda}'")
    if tipo_busqueda == "Embragues (Kits)":
        mask = df_kits.astype(str).apply(lambda x: x.str.contains(busqueda, case=False, na=False)).any(axis=1)
        resultados = df_kits[mask]
        st.dataframe(resultados, hide_index=True) if not resultados.empty else st.info("No encontré kits con ese dato. ¿Probaste otra palabra?")
    elif tipo_busqueda == "Crapodinas":
        mask = df_crapo.astype(str).apply(lambda x: x.str.contains(busqueda, case=False, na=False)).any(axis=1)
        resultados = df_crapo[mask]
        st.dataframe(resultados, hide_index=True) if not resultados.empty else st.info("No encontré crapodinas así.")
    elif tipo_busqueda == "Distribución":
        mask = df_distri.astype(str).apply(lambda x: x.str.contains(busqueda, case=False, na=False)).any(axis=1)
        resultados = df_distri[mask]
        st.dataframe(resultados, hide_index=True) if not resultados.empty else st.info("Nada en Distribución todavía.")

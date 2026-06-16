import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# ============================================================
# 1. IDENTIDAD
# ============================================================
st.set_page_config(page_title="Embragues Rosario", page_icon="🔧")
try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Embragues Rosario")
st.markdown("Crespo 4117, Rosario | **IIBB: EXENTO**")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YJHJ006kr-izLHG9Ib5CRUX5VUdu6INRDsKn4u0x32Y/edit"

# ============================================================
# 2. CONEXIÓN
# ============================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# ============================================================
# 3. CARGA DE DATOS EN SESSION_STATE
# Solo lee de Google Sheets UNA VEZ por sesión.
# Mientras el usuario llena el formulario, NO hace ninguna
# petición a la API. Solo se reconecta al guardar.
# ============================================================
def cargar_datos():
    """Lee todas las hojas y las guarda en session_state."""
    try:
        st.session_state["df_config"]  = conn.read(spreadsheet=SHEET_URL, worksheet="Configuracion", ttl=0)
    except:
        st.session_state["df_config"]  = pd.DataFrame()
    try:
        st.session_state["df_kits"]    = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", ttl=0)
    except:
        st.session_state["df_kits"]    = pd.DataFrame()
    try:
        st.session_state["df_crapo"]   = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", ttl=0)
    except:
        st.session_state["df_crapo"]   = pd.DataFrame()
    try:
        st.session_state["df_distri"]  = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Distribucion", ttl=0)
    except:
        st.session_state["df_distri"]  = pd.DataFrame()
    try:
        st.session_state["df_ventas"]  = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
    except:
        st.session_state["df_ventas"]  = pd.DataFrame()
    st.session_state["datos_cargados"] = True

# Carga solo si es la primera vez en esta sesión
if not st.session_state.get("datos_cargados"):
    with st.spinner("Conectando con Google Sheets..."):
        cargar_datos()

# Shortcut a los datos en memoria
df_config  = st.session_state.get("df_config",  pd.DataFrame())
df_kits    = st.session_state.get("df_kits",    pd.DataFrame())
df_crapo   = st.session_state.get("df_crapo",   pd.DataFrame())
df_distri  = st.session_state.get("df_distri",  pd.DataFrame())
df_ventas  = st.session_state.get("df_ventas",  pd.DataFrame())

# ============================================================
# 4. COEFICIENTES DESDE SHEETS
# ============================================================
try:
    config    = dict(zip(df_config["Parametro"], df_config["Valor"]))
    GETNET_1  = float(config.get("GETNET_1_PAGO",    1.0223))
    GETNET_3  = float(config.get("GETNET_3_CUOTAS",  1.1247))
    GETNET_6  = float(config.get("GETNET_6_CUOTAS",  1.2330))
    MPAGOS_1  = float(config.get("MASPAGOS_1_PAGO",  1.0286))
    MPAGOS_3  = float(config.get("MASPAGOS_3_CUOTAS",1.1450))
    MPAGOS_6  = float(config.get("MASPAGOS_6_CUOTAS",1.2898))
except:
    GETNET_1, GETNET_3, GETNET_6 = 1.0223, 1.1247, 1.2330
    MPAGOS_1, MPAGOS_3, MPAGOS_6 = 1.0286, 1.1450, 1.2898

# ============================================================
# 5. FUNCIONES DE ESCRITURA
# ============================================================
def guardar_venta(categoria, cliente, vehiculo, detalle, monto, costo, proveedor,
                  cod_kit, cod_crap, f_pago, e_cliente, e_prov,
                  m_forros, c_forros, costo_f, ganancia):
    fecha_hoy = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    columnas  = ["Fecha","Categoría","Cliente","Vehículo","Detalle",
                 "Venta $","Compra $","Proveedor","Código","Cod_Crapodina",
                 "Forma_de_pago","Estado_Cobro","Estado_Pago_Prov",
                 "Marca_Forros","Cod_Forros","Costo_Forros","Ganancia"]
    df_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
    nueva     = pd.DataFrame([[fecha_hoy, categoria, cliente, vehiculo, detalle,
                               monto, costo, proveedor, cod_kit, cod_crap,
                               f_pago, e_cliente, e_prov,
                               m_forros, c_forros, costo_f, ganancia]],
                             columns=columnas)
    df_nuevo  = pd.concat([df_actual, nueva], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_nuevo)
    # Actualizar copia en memoria
    st.session_state["df_ventas"] = df_nuevo

def guardar_kit(vehiculo, codigo, precio, marca):
    if not codigo:
        return
    try:
        df        = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", ttl=0)
        marca_up  = str(marca).upper()
        col_cod   = f"Codigo_{marca_up}"
        col_pre   = f"Precio_{marca_up}"
        if col_cod not in df.columns:
            st.warning(f"⚠️ Marca {marca_up} no tiene columnas en Kits.")
            return
        veh_l     = vehiculo.strip().lower()
        cod_l     = str(codigo).split('.')[0].strip()
        mask_veh  = df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l
        mask_cod  = df[col_cod].astype(str).str.split('.').str[0].str.strip() == cod_l
        if mask_veh.any():
            idx = df.index[mask_veh][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
            msg = f"✅ Kit actualizado: {vehiculo}"
        elif mask_cod.any():
            idx = df.index[mask_cod][0]
            v_actual = str(df.at[idx,'Vehiculo'])
            if veh_l not in v_actual.lower():
                df.at[idx,'Vehiculo'] = f"{v_actual} / {vehiculo}"
            df.at[idx, col_pre] = precio
            msg = f"🔗 Equivalente: {vehiculo}"
        else:
            fila = {c: "" for c in df.columns}
            fila["Vehiculo"] = vehiculo
            fila["Descripcion"] = "Kit de Embrague"
            fila[col_cod] = codigo
            fila[col_pre] = precio
            df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
            msg = f"✨ Nuevo kit: {vehiculo}"
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        st.session_state["df_kits"] = df
        st.toast(msg, icon="📦")
    except Exception as e:
        st.error(f"Error kits: {e}")

def guardar_crapodina(vehiculo, tipo_c, codigo, precio, marca):
    if not codigo:
        return
    try:
        df        = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", ttl=0)
        marca_up  = str(marca).upper()
        col_cod   = f"Codigo_{marca_up}"
        col_pre   = f"Precio_{marca_up}"
        if col_cod not in df.columns:
            st.warning(f"⚠️ Marca {marca_up} no tiene columnas en Crapodinas.")
            return
        veh_l    = vehiculo.strip().lower()
        desc_l   = f"Crapodina {tipo_c}".strip().lower()
        cod_l    = str(codigo).split('.')[0].strip()
        mask_veh = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                   (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
        mask_cod = df[col_cod].astype(str).str.split('.').str[0].str.strip() == cod_l
        if mask_veh.any():
            idx = df.index[mask_veh][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
            msg = f"✅ Crapodina actualizada: {vehiculo}"
        elif mask_cod.any():
            idx = df.index[mask_cod][0]
            v_actual = str(df.at[idx,'Vehiculo'])
            if veh_l not in v_actual.lower():
                df.at[idx,'Vehiculo'] = f"{v_actual} / {vehiculo}"
            df.at[idx, col_pre] = precio
            msg = f"🔗 Equivalente: {vehiculo}"
        else:
            fila = {c: "" for c in df.columns}
            fila["Vehiculo"]    = vehiculo
            fila["Descripcion"] = f"Crapodina {tipo_c}"
            fila[col_cod]       = codigo
            fila[col_pre]       = precio
            df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
            msg = f"✨ Nueva crapodina: {vehiculo}"
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", data=df)
        st.session_state["df_crapo"] = df
        st.toast(msg, icon="⚙️")
    except Exception as e:
        st.error(f"Error crapodinas: {e}")

def marcar_cobrado(idx_fila, forma_pago):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
        df.at[idx_fila, "Estado_Cobro"]  = "Pagado"
        df.at[idx_fila, "Forma_de_pago"] = forma_pago
        conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df)
        st.session_state["df_ventas"] = df
        st.toast("✅ Cobro registrado", icon="💰")
    except Exception as e:
        st.error(f"Error al registrar cobro: {e}")

# ============================================================
# 6. SIDEBAR — FORMULARIO DE CARGA
# ============================================================
st.sidebar.header("⚙️ Configuración")

# Inicialización defensiva
m_kit = m_forros = forros_codigo = crap_codigo = tipo_crap = ""
forros_costo = crap_costo = 0
m_crap = []

tipo_item = st.sidebar.selectbox("Tipo de Trabajo:",
    ["Embrague Nuevo (Venta)", "Reparación de Embrague", "Kit de Distribución", "Otro"])

if "Nuevo" in tipo_item:
    cat_f, icono, incl_rectif = "Venta", "⚙️", True
    m_kit      = st.sidebar.selectbox("Marca del Kit:", ["LUK","SACHS","VALEO","PHC_VALEO","ORIGINAL","OTRA"])
    sugerencia = f"KIT nuevo marca *{m_kit}*"

elif "Reparación" in tipo_item:
    cat_f, icono, incl_rectif = "Reparación", "🔧", False
    m_crap        = st.sidebar.multiselect("Marcas de Crapodina:", ["Luk","Skf","Ina","Dbh","The"], default=["Luk","Skf"])
    crap_codigo   = st.sidebar.text_input("Código de Crapodina:", "")
    crap_costo    = st.sidebar.number_input("Costo de Crapodina ($):", min_value=0, value=0)
    tipo_crap     = st.sidebar.selectbox("⚙️ Tipo de Crapodina:", ["Hidráulica","Mecánica"])
    m_forros      = st.sidebar.selectbox("Marca de Forros:", ["IAR","Fras-le","Termolite","Otro"])
    forros_codigo = st.sidebar.text_input("Código de Forros:", "")
    forros_costo  = st.sidebar.number_input("Costo de Forros ($):", min_value=0, value=0)
    m_neg = [f"*{m}*" for m in m_crap]
    t_m   = (", ".join(m_neg[:-1]) + " o " + m_neg[-1]) if len(m_neg) > 1 else (m_neg[0] if m_neg else "*primera marca*")
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

foto_repuesto = st.sidebar.file_uploader("📷 Foto del repuesto", type=["jpg","png","jpeg"])
if foto_repuesto:
    st.sidebar.image(foto_repuesto, caption="Vista previa", use_container_width=True)

ganancia = monto_limpio - precio_compra
if monto_limpio > 0:
    st.sidebar.metric("Ganancia Estimada", f"$ {ganancia:,.0f}")

proveedor_input = st.sidebar.text_input("Proveedor:", "icepar")

st.sidebar.divider()
st.sidebar.subheader("💰 Estado de la Operación")

estado_cliente = st.sidebar.selectbox("Estado del Cliente:", ["Pagado","Debe","Seña"], index=0)
f_pago_input   = "N/A"
if estado_cliente == "Pagado":
    f_pago_input = st.sidebar.selectbox("¿Cómo pagó?:", [
        "Efectivo","Transferencia","Débito",
        "BNA - 1 Pago","BNA - 3 Cuotas","BNA - 6 Cuotas",
        "Getnet - 1 Pago","Getnet - 3 Cuotas","Getnet - 6 Cuotas",
        "Combinado","Otro"])

estado_p_prov = st.sidebar.selectbox("Estado al Proveedor:", ["Pagado","Cuenta Corriente","N/A"], index=0)

cod_kit_final  = "" if cat_f == "Reparación" else codigo_manual
cod_crap_final = crap_codigo if cat_f == "Reparación" else ""

# ============================================================
# BOTÓN GUARDAR CON CONFIRMACIÓN
# ============================================================
if st.sidebar.button("💾 GUARDAR VENTA", use_container_width=True):
    st.session_state["pedir_confirmacion"] = True

if st.session_state.get("pedir_confirmacion"):
    st.sidebar.warning(
        f"⚠️ **¿Confirmar esta venta?**\n\n"
        f"🚗 **Vehículo:** {vehiculo_input}\n\n"
        f"👤 **Cliente:** {cliente_input}\n\n"
        f"💰 **Monto:** ${monto_limpio:,.0f}"
    )
    col_si, col_no = st.sidebar.columns(2)
    confirmar = col_si.button("✅ Sí, guardar", use_container_width=True)
    cancelar  = col_no.button("❌ Cancelar",    use_container_width=True)

    if confirmar:
        st.session_state["pedir_confirmacion"] = False
        try:
            guardar_venta(cat_f, cliente_input, vehiculo_input, detalle_excel,
                          monto_limpio, precio_compra, proveedor_input,
                          cod_kit_final, cod_crap_final, f_pago_input,
                          estado_cliente, estado_p_prov,
                          m_forros, forros_codigo, forros_costo, ganancia)
            if cod_kit_final:
                marca_k = m_kit[0] if isinstance(m_kit, list) and m_kit else (m_kit or "OTRA")
                guardar_kit(vehiculo_input, cod_kit_final, monto_limpio, marca_k)
            if cod_crap_final:
                guardar_crapodina(vehiculo_input, tipo_crap, cod_crap_final, crap_costo, m_crap[0] if m_crap else "OTRA")
            st.sidebar.success(f"✅ Venta de ${monto_limpio:,.0f} guardada!")
        except Exception as e:
            st.sidebar.error(f"Error al guardar: {e}")

    if cancelar:
        st.session_state["pedir_confirmacion"] = False
        st.sidebar.info("Venta cancelada.")

# ============================================================
# 7. CALCULADORA DE CUOTAS
# ============================================================
st.markdown("### 💳 Calculadora de Cuotas")
tipo_pos = st.radio("¿Qué POS vas a usar?", ["GETNET (18 días)", "MÁS PAGOS (18 días)"], horizontal=True)

if "GETNET" in tipo_pos:
    c1, c3, c6 = GETNET_1, GETNET_3, GETNET_6
    nombre_pos  = "GETNET"
else:
    c1, c3, c6 = MPAGOS_1, MPAGOS_3, MPAGOS_6
    nombre_pos  = "MÁS PAGOS"

t1 = monto_limpio * c1
t3 = monto_limpio * c3
t6 = monto_limpio * c6

p_1, p_3, p_6 = [(x-1)*100 for x in [c1,c3,c6]]
st.info(f"📊 **Recargos:** 1 Pago: {p_1:.1f}% | 3 Cuotas: {p_3:.1f}% | 6 Cuotas: {p_6:.1f}%")

st.divider()
st.markdown(f"""
<div style='background:#d4edda;padding:10px;border-radius:5px;text-align:center;border:2px solid #28a745;'>
  <h2 style='color:#155724;margin:0;'>💰 CONTADO / TRANSF: ${monto_limpio:,.0f}</h2>
  <p style='margin:0;font-size:0.9em;'>(Este monto te queda limpio)</p>
</div>""", unsafe_allow_html=True)

st.write(f"**Precios con {nombre_pos}:**")
ca, cb, cc = st.columns(3)
with ca: st.metric("1 PAGO",   f"${t1:,.0f}")
with cb: st.metric("3 CUOTAS", f"${t3/3:,.2f}", f"Total: ${t3:,.0f}")
with cc: st.metric("6 CUOTAS", f"${t6/6:,.2f}", f"Total: ${t6:,.0f}")

# ============================================================
# 8. WHATSAPP
# ============================================================
txt_rectif = "\n✅ *Incluye rectificación y balanceo de volante*" if incl_rectif else ""
maps_link  = "https://www.google.com/maps?q=Crespo+4117+Rosario"

mensaje = (
    f"🚗 *EMBRAGUES ROSARIO*\n"
    f"¡Hola! Gracias por tu consulta. Te paso el presupuesto:\n\n"
    f"🚗 *Vehículo:* {vehiculo_input}\n"
    f"{icono} *Trabajo:* {detalle_final}{txt_rectif}\n\n"
    f"💰 *EFECTIVO / TRANSF:* ${monto_limpio:,.0f}\n\n"
    f"💳 *TARJETA BANCARIA ({nombre_pos}):*\n"
    f"✅ *1 pago:* ${t1:,.0f}\n\n"
    f"✅ *3 cuotas de:* ${t3/3:,.2f}\n      (Total: ${t3:,.0f})\n\n"
    f"✅ *6 cuotas de:* ${t6/6:,.2f}\n      (Total: ${t6:,.0f})\n\n"
    f"📍 *Dirección:* Crespo 4117, Rosario\n"
    f"📍 *Ubicación:* {maps_link}\n"
    f"📸 *Instagram:* @embraguesrosario\n"
    f"⏰ *Horario:* 8:30 a 17:00 hs\n\n"
    f"¡Te esperamos pronto! 🙋🏻"
)
st.link_button("🟢 ENVIAR PRESUPUESTO POR WHATSAPP", f"https://wa.me/?text={urllib.parse.quote(mensaje)}")

# ============================================================
# 9. ÚLTIMOS MOVIMIENTOS
# ============================================================
st.divider()
st.subheader("📋 Últimos Movimientos")
df_v = st.session_state.get("df_ventas", pd.DataFrame())
if not df_v.empty:
    st.dataframe(df_v.tail(5)[::-1], use_container_width=True)
else:
    st.info("La planilla está vacía todavía.")

# ============================================================
# 10. RESUMEN DE VENTAS
# ============================================================
st.divider()
st.header("📊 Resumen de Ventas")

df_res = st.session_state.get("df_ventas", pd.DataFrame()).copy()
if not df_res.empty and "Fecha" in df_res.columns:
    df_res["Fecha_dt"] = pd.to_datetime(df_res["Fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
    df_res["Venta $"]  = pd.to_numeric(df_res["Venta $"],  errors="coerce").fillna(0)
    df_res["Ganancia"] = pd.to_numeric(df_res["Ganancia"], errors="coerce").fillna(0)

    ahora    = datetime.now() - timedelta(hours=3)
    hoy      = ahora.date()
    lun      = hoy - timedelta(days=hoy.weekday())
    primer_d = hoy.replace(day=1)

    m_hoy = df_res["Fecha_dt"].dt.date == hoy
    m_sem = df_res["Fecha_dt"].dt.date >= lun
    m_mes = df_res["Fecha_dt"].dt.date >= primer_d

    c1r, c2r, c3r = st.columns(3)
    with c1r: st.metric("📅 Hoy",         f"${df_res[m_hoy]['Venta $'].sum():,.0f}", f"{m_hoy.sum()} trabajo(s)")
    with c2r: st.metric("📆 Esta semana", f"${df_res[m_sem]['Venta $'].sum():,.0f}", f"{m_sem.sum()} trabajo(s)")
    with c3r: st.metric("🗓️ Este mes",    f"${df_res[m_mes]['Venta $'].sum():,.0f}", f"{m_mes.sum()} trabajo(s)")

    st.divider()
    c4r, c5r = st.columns(2)
    with c4r:
        st.metric("💰 Ganancia del mes", f"${df_res[m_mes]['Ganancia'].sum():,.0f}")
    with c5r:
        if "Categoría" in df_res.columns:
            tipos = df_res[m_mes]["Categoría"].value_counts()
            st.metric("🔧 Por tipo", " | ".join([f"{k}: {v}" for k, v in tipos.items()]) or "—")
else:
    st.info("Todavía no hay ventas registradas.")

# ============================================================
# 11. COBROS PENDIENTES
# ============================================================
st.divider()
st.header("💸 Cobros Pendientes")

df_pend = st.session_state.get("df_ventas", pd.DataFrame()).copy()
if not df_pend.empty and "Estado_Cobro" in df_pend.columns:
    pendientes = df_pend[df_pend["Estado_Cobro"].isin(["Debe", "Seña"])].copy()
    if pendientes.empty:
        st.success("✅ No hay cobros pendientes.")
    else:
        st.warning(f"Hay **{len(pendientes)}** cobro(s) pendiente(s):")
        lista_fp = ["Efectivo","Transferencia","Débito",
                    "BNA - 1 Pago","BNA - 3 Cuotas","BNA - 6 Cuotas",
                    "Getnet - 1 Pago","Getnet - 3 Cuotas","Getnet - 6 Cuotas",
                    "Combinado","Otro"]
        for pos, (idx, fila) in enumerate(pendientes.iterrows()):
            emoji = "🔴" if fila.get("Estado_Cobro") == "Debe" else "🟡"
            monto_fila = 0.0
            try:
                monto_fila = float(fila.get("Venta $", 0))
            except:
                pass
            titulo = (f"{emoji} {fila.get('Fecha','—')} | "
                      f"{fila.get('Vehículo','—')} | "
                      f"{fila.get('Cliente','—')} | "
                      f"${monto_fila:,.0f} ({fila.get('Estado_Cobro','—')})")
            with st.expander(titulo):
                fp_sel = st.selectbox("Forma de pago al cobrar:", lista_fp, key=f"fp_{pos}_{idx}")
                if st.button("✅ Marcar como Pagado", key=f"pagar_{pos}_{idx}"):
                    marcar_cobrado(idx, fp_sel)
                    st.rerun()
else:
    st.info("No hay datos de ventas todavía.")

# ============================================================
# 12. BUSCADOR DE CATÁLOGO
# ============================================================
st.divider()
st.header("🔍 Consultar Catálogo")

tipo_busqueda = st.radio("¿Qué estás buscando?",
                         ["Embragues (Kits)","Crapodinas","Distribución"], horizontal=True)
busqueda = st.text_input("✍️ Modelo de Auto o Código (Ej: 'Gol', '620 3000', 'Ranger'):")

if busqueda:
    st.caption(f"Resultados para: '{busqueda}'")
    if tipo_busqueda == "Embragues (Kits)":
        df_b = st.session_state.get("df_kits", pd.DataFrame())
    elif tipo_busqueda == "Crapodinas":
        df_b = st.session_state.get("df_crapo", pd.DataFrame())
    else:
        df_b = st.session_state.get("df_distri", pd.DataFrame())

    if not df_b.empty:
        mask = df_b.astype(str).apply(lambda x: x.str.contains(busqueda, case=False, na=False)).any(axis=1)
        res  = df_b[mask]
        if not res.empty:
            st.dataframe(res, hide_index=True)
        else:
            st.info("No encontré nada con ese dato.")
    else:
        st.info("Catálogo vacío todavía.")

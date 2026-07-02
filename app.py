import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# 1. IDENTIDAD
st.set_page_config(page_title="Embragues Rosario", page_icon="🔧")
try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Embragues Rosario")
st.markdown("Crespo 4117, Rosario | **IIBB: EXENTO**")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YJHJ006kr-izLHG9Ib5CRUX5VUdu6INRDsKn4u0x32Y/edit"

# 2. CONEXIÓN
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# 3. CACHÉ
@st.cache_data(ttl=600, show_spinner=False)
def leer_hoja(url, hoja):
    return conn.read(spreadsheet=url, worksheet=hoja)

def leer_fresca(url, hoja):
    return conn.read(spreadsheet=url, worksheet=hoja, ttl=0)

# 4. COEFICIENTES DESDE SHEETS
try:
    df_cfg = leer_hoja(SHEET_URL, "Configuracion")
    cfg = dict(zip(df_cfg["Parametro"], df_cfg["Valor"]))
    
    GETNET_1 = float(cfg["GETNET_1_PAGO"])
    GETNET_3 = float(cfg["GETNET_3_CUOTAS"])
    GETNET_6 = float(cfg["GETNET_6_CUOTAS"])
    MPAGOS_1 = float(cfg["MASPAGOS_1_PAGO"])
    MPAGOS_3 = float(cfg["MASPAGOS_3_CUOTAS"])
    MPAGOS_6 = float(cfg["MASPAGOS_6_CUOTAS"])
except Exception as e:
    st.error("🚨 ERROR CRÍTICO: No se pudieron leer las tasas de financiación.")
    st.stop()

# 5. CATÁLOGOS
try:
    df_kits = leer_hoja(SHEET_URL, "Catalogo_Kits")
    df_crapo = leer_hoja(SHEET_URL, "Catalogo_Crapodinas")
    df_distri = leer_hoja(SHEET_URL, "Catalogo_Distribucion")
except Exception as e:
    df_kits = df_crapo = df_distri = pd.DataFrame()

# 6. FUNCIONES DE ESCRITURA
def actualizar_catalogo_kits(vehiculo, descripcion, codigo, precio, marca):
    try:
        df = leer_fresca(SHEET_URL, "Catalogo_Kits")
        
        # BLINDAJE
        if 'Vehiculo' not in df.columns: df['Vehiculo'] = ""
        if 'Descripcion' not in df.columns: df['Descripcion'] = ""
        
        marca_up = str(marca).upper()
        col_cod = f"Codigo_{marca_up}"
        col_pre = f"Precio_{marca_up}"
        
        if col_cod not in df.columns:
            df[col_cod] = ""
            df[col_pre] = ""

        veh_l = str(vehiculo).strip().lower()
        desc_l = str(descripcion).strip().lower()
        cod_l = str(codigo).split('.')[0].strip()
        
        m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                   (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
        
        m_cod = df[col_cod].astype(str).str.split('.').str[0].str.strip() == cod_l if not df[col_cod].isna().all() else pd.Series([False]*len(df))
        
        if m_exacto.any():
            idx = df.index[m_exacto][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
        elif m_cod.any():
            idx = df.index[m_cod][0]
            v_a = str(df.at[idx,'Vehiculo'])
            if veh_l not in v_a.lower():
                df.at[idx,'Vehiculo'] = f"{v_a} / {vehiculo}"
            df.at[idx, col_pre] = precio
        else:
            fila = {c: "" for c in df.columns}
            fila["Vehiculo"] = vehiculo
            fila["Descripcion"] = descripcion
            fila[col_cod] = codigo
            fila[col_pre] = precio
            df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
            
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        leer_hoja.clear()
    except Exception as e:
        st.error(f"Error real en kits: {e}") # <-- CAMBIAR EL 'pass' POR ESTO

def actualizar_catalogo_crapodinas(vehiculo, descripcion, codigo, precio, marca):
    try:
        df = leer_fresca(SHEET_URL, "Catalogo_Crapodinas")
        
        if 'Vehiculo' not in df.columns: df['Vehiculo'] = ""
        if 'Descripcion' not in df.columns: df['Descripcion'] = ""
        
        marca_up = str(marca).upper()
        col_cod = f"Codigo_{marca_up}"
        col_pre = f"Precio_{marca_up}"
        
        if col_cod not in df.columns:
            df[col_cod] = ""
            df[col_pre] = ""

        veh_l = str(vehiculo).strip().lower()
        desc_l = str(descripcion).strip().lower()
        cod_l = str(codigo).split('.')[0].strip()
        
        m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                   (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
                   
        m_cod = df[col_cod].astype(str).str.split('.').str[0].str.strip() == cod_l if not df[col_cod].isna().all() else pd.Series([False]*len(df))
        
        if m_exacto.any():
            idx = df.index[m_exacto][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
        elif m_cod.any():
            idx = df.index[m_cod][0]
            v_a = str(df.at[idx,'Vehiculo'])
            if veh_l not in v_a.lower():
                df.at[idx,'Vehiculo'] = f"{v_a} / {vehiculo}"
            df.at[idx, col_pre] = precio
        else:
            fila = {c: "" for c in df.columns}
            fila["Vehiculo"] = vehiculo
            fila["Descripcion"] = descripcion
            fila[col_cod] = codigo
            fila[col_pre] = precio
            df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
            
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", data=df)
        leer_hoja.clear()
    except Exception as e:
        st.error(f"Error real en crapodinas: {e}")

def guardar_en_google(categoria, cliente, vehiculo, detalle, monto_bruto, monto_neto, costo, proveedor,
                      cod_kit, cod_crap, f_pago, e_cliente, e_prov,
                      m_forros, c_forros, costo_f, ganancia):
    fecha_hoy = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    
    columnas = ["Fecha", "Categoría", "Cliente", "Vehículo", "Detalle",
                "Venta $", "Compra $", "Proveedor", "Código", "Cod_Crapodina",
                "Forma_de_pago", "Estado_Cobro", "Estado_Pago_Prov",
                "Marca_Forros", "Cod_Forros", "Costo_Forros", "Ganancia", "Monto Neto Esperado"]
    try:
        df_existente = leer_fresca(SHEET_URL, "Ventas")
    except Exception as e:
        st.error(f"Error al leer Ventas: {e}")
        st.stop()
        
    nueva = pd.DataFrame([[fecha_hoy, categoria, cliente, vehiculo, detalle,
                           monto_bruto, costo, proveedor, cod_kit, cod_crap,
                           f_pago, e_cliente, e_prov,
                           m_forros, c_forros, costo_f, ganancia, monto_neto]],
                         columns=columnas)
    df_nuevo = pd.concat([df_existente, nueva], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_nuevo)
    leer_hoja.clear()

# -------------------------------------------------------------
# SISTEMA DE LIMPIEZA BLINDADA (LLAVES DINÁMICAS)
if "form_key" not in st.session_state:
    st.session_state.form_key = 0
fk = st.session_state.form_key
# -------------------------------------------------------------

# 7. SIDEBAR — FORMULARIO
st.sidebar.header("⚙️ Configuración")

if "venta_exitosa" in st.session_state:
    st.sidebar.success(st.session_state["venta_exitosa"])
    del st.session_state["venta_exitosa"]

m_kit = m_forros = forros_codigo = crap_codigo = tipo_crap = ""
forros_costo = crap_costo = 0
m_crap = []

tipo_item = st.sidebar.selectbox("Tipo de Trabajo:",
    ["Embrague Nuevo (Venta)", "Reparación de Embrague", "Kit de Distribución", "Otro"], key=f"tipo_{fk}")

if "Nuevo" in tipo_item:
    cat_f, icono, incl_rectif = "Venta", "⚙️", False
    m_kit = st.sidebar.selectbox("Marca del Kit:", ["LUK","SACHS","VALEO","PHC_VALEO","ORIGINAL","OTRA"], key=f"mkit_{fk}")
    sugerencia = f"KIT nuevo marca *{m_kit}*"
elif "Reparación" in tipo_item:
    cat_f, icono, incl_rectif = "Reparación", "🔧", True
    m_crap = st.sidebar.multiselect("Marcas de Crapodina:", ["Luk","Skf","Ina","Dbh","The"], default=["Luk","Skf"], key=f"mcrap_{fk}")
    crap_codigo = st.sidebar.text_input("Código de Crapodina:", "", key=f"crapcod_{fk}")
    crap_costo = st.sidebar.number_input("Costo de Crapodina ($):", min_value=0, value=0, key=f"crapcost_{fk}")
    tipo_crap = st.sidebar.selectbox("⚙️ Tipo de Crapodina:", ["Hidráulica","Mecánica"], key=f"tipocrap_{fk}")
    m_forros = st.sidebar.selectbox("Marca de Forros:", ["IAR Metal","Fras-le","Termolite","Otro"], key=f"mforro_{fk}")
    forros_codigo = st.sidebar.text_input("Código de Forros:", "", key=f"forrocod_{fk}")
    forros_costo = st.sidebar.number_input("Costo de Forros ($):", min_value=0, value=0, key=f"forrocost_{fk}")
    m_neg = [f"*{m}*" for m in m_crap]
    t_m = (", ".join(m_neg[:-1]) + " o " + m_neg[-1]) if len(m_neg) > 1 else (m_neg[0] if m_neg else "*primera marca*")
    sugerencia = f"reparado completo placa disco con forros originales volante rectificado y balanceado con crapodina {t_m}"
else:
    cat_f, icono, incl_rectif = "Venta", "🛠️", False
    sugerencia = "KIT de distribución"

monto_limpio = st.sidebar.number_input("Precio de VENTA ($):", min_value=0, value=0, key=f"montolimpio_{fk}")
vehiculo_input = st.sidebar.text_input("Vehículo:", value="", key=f"vehiculo_{fk}")
cliente_input = st.sidebar.text_input("Nombre del Cliente:", value="", key=f"cliente_{fk}")
detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Venta / Reparación", key=f"detalle_{fk}")
detalle_final = st.sidebar.text_area("💬 Detalle en WhatsApp:", value=sugerencia, key=f"detwhats_{fk}")

st.sidebar.divider()
st.sidebar.write("📸 **Uso Interno**")

if cat_f == "Reparación":
    codigo_manual = crap_codigo
    precio_compra = crap_costo + forros_costo
    st.sidebar.info(f"💰 Costo Materiales: ${precio_compra:,.0f}")
else:
    codigo_manual = st.sidebar.text_input("Código de repuesto:", "", key=f"codrep_{fk}")
    precio_compra = st.sidebar.number_input("Precio de COMPRA ($):", min_value=0, value=0, key=f"precomp_{fk}")

foto_repuesto = st.sidebar.file_uploader("📷 Foto del repuesto", type=["jpg","png","jpeg"], key=f"foto_{fk}")
if foto_repuesto:
    st.sidebar.image(foto_repuesto, caption="Vista previa", use_container_width=True)

ganancia = monto_limpio - precio_compra
if monto_limpio > 0:
    st.sidebar.metric("Ganancia Estimada", f"$ {ganancia:,.0f}")

proveedor_input = st.sidebar.text_input("Proveedor:", value="", key=f"prov_{fk}")

st.sidebar.divider()
st.sidebar.subheader("💰 Estado de la Operación")

estado_cliente = st.sidebar.selectbox("Estado del Cliente:", ["Pagado","Debe","Seña"], index=0, key=f"estcli_{fk}")
f_pago_input = "N/A"
if estado_cliente == "Pagado":
    f_pago_input = st.sidebar.selectbox("¿Cómo pagó?:", [
        "Efectivo","Transferencia","Débito",
        "BNA - 1 Pago","BNA - 3 Cuotas","BNA - 6 Cuotas",
        "Getnet - 1 Pago","Getnet - 3 Cuotas","Getnet - 6 Cuotas",
        "Más Pagos - 1 Pago","Más Pagos - 3 Cuotas","Más Pagos - 6 Cuotas",
        "Combinado","Otro"], key=f"fpago_{fk}")

estado_p_prov = st.sidebar.selectbox("Estado al Proveedor:", ["Pagado","Cuenta Corriente","N/A"], index=0, key=f"estprov_{fk}")

cod_kit_final = "" if cat_f == "Reparación" else codigo_manual
cod_crap_final = crap_codigo if cat_f == "Reparación" else ""

if st.sidebar.button("💾 GUARDAR VENTA", key=f"btn_guardar_{fk}"):
    
    # MOTOR DE CÁLCULO FINANCIERO CRÍTICO Y LÓGICA DE AUDITORÍA
    monto_bruto = monto_limpio
    monto_neto_guardar = monto_limpio
    
    if f_pago_input in ["Efectivo", "Transferencia"]:
        monto_neto_guardar = "-"
    elif f_pago_input == "Getnet - 1 Pago": monto_bruto = monto_limpio * GETNET_1
    elif f_pago_input == "Getnet - 3 Cuotas": monto_bruto = monto_limpio * GETNET_3
    elif f_pago_input == "Getnet - 6 Cuotas": monto_bruto = monto_limpio * GETNET_6
    elif f_pago_input == "Más Pagos - 1 Pago": monto_bruto = monto_limpio * MPAGOS_1
    elif f_pago_input == "Más Pagos - 3 Cuotas": monto_bruto = monto_limpio * MPAGOS_3
    elif f_pago_input == "Más Pagos - 6 Cuotas": monto_bruto = monto_limpio * MPAGOS_6
    
    guardar_en_google(cat_f, cliente_input, vehiculo_input, detalle_excel,
                      monto_bruto, monto_neto_guardar, precio_compra, proveedor_input,
                      cod_kit_final, cod_crap_final, f_pago_input,
                      estado_cliente, estado_p_prov,
                      m_forros, forros_codigo, forros_costo, ganancia)
                      
    if cod_kit_final:
        marca_k = m_kit[0] if isinstance(m_kit, list) and m_kit else (m_kit or "OTRA")
        actualizar_catalogo_kits(vehiculo_input, "Kit de Embrague", cod_kit_final, monto_limpio, marca_k)
    if cod_crap_final:
        actualizar_catalogo_crapodinas(vehiculo_input, f"Crapodina {tipo_crap}",
                                       cod_crap_final, crap_costo,
                                       m_crap[0] if m_crap else "OTRA")
                                       
    st.session_state.form_key += 1
    st.session_state["venta_exitosa"] = f"✅ Venta registrada correctamente."
    st.rerun()

# 8. CALCULADORA DE CUOTAS
st.markdown("### 💳 Calculadora de Cuotas")
tipo_pos = st.radio("¿Qué POS vas a usar?", ["GETNET", "MÁS PAGOS"], horizontal=True)

if "GETNET" in tipo_pos:
    c1, c3, c6 = GETNET_1, GETNET_3, GETNET_6
    nombre_pos = "GETNET"
else:
    c1, c3, c6 = MPAGOS_1, MPAGOS_3, MPAGOS_6
    nombre_pos = "MÁS PAGOS"

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

# 9. WHATSAPP
txt_rectif = "\n✅ *Incluye rectificación y balanceo de volante*" if incl_rectif else ""
maps_link = "https://www.google.com/maps?q=Crespo+4117+Rosario"
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

# 10. HISTORIAL
st.divider()
st.subheader("📋 Últimos Movimientos")
try:
    df_ver = leer_hoja(SHEET_URL, "Ventas")
    if not df_ver.empty:
        st.dataframe(df_ver.tail(5)[::-1], use_container_width=True)
    else:
        st.info("La planilla está vacía todavía.")
except Exception:
    st.warning("⚠️ No se pudo cargar el historial.")

# 11. BUSCADOR DE CATÁLOGO
st.divider()
st.header("🔍 Consultar Catálogo")
tipo_busqueda = st.radio("¿Qué estás buscando?",
                         ["Embragues (Kits)","Crapodinas","Distribución"], horizontal=True)
busqueda = st.text_input("✍️ Modelo de Auto o Código (Ej: 'Gol', '620 3000', 'Ranger'):")

if busqueda:
    st.caption(f"Resultados para: '{busqueda}'")
    if tipo_busqueda == "Embragues (Kits)":
        df_b = df_kits
    elif tipo_busqueda == "Crapodinas":
        df_b = df_crapo
    else:
        df_b = df_distri
    if not df_b.empty:
        mask = df_b.astype(str).apply(lambda x: x.str.contains(busqueda, case=False, na=False)).any(axis=1)
        res = df_b[mask]
        st.dataframe(res, hide_index=True) if not res.empty else st.info("No encontré nada con ese dato.")
    else:
        st.info("Catálogo vacío todavía.")

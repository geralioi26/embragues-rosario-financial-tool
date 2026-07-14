import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# 1. IDENTIDAD
st.set_page_config(page_title="Embragues Rosario", page_icon="logo.png")
try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Embragues Rosario")
st.markdown("Crespo 4117, Rosario | **IIBB: EXENTO**")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YJHJ006kr-izLHG9Ib5CRUX5VUdu6INRDsKn4u0x32Y/edit"

# 2. CONEXIÓN (Estructura a prueba de errores)
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_conn()

# 3. CACHÉ
@st.cache_data(ttl=600, show_spinner=False)
def leer_hoja(url, hoja):
    return conn.read(spreadsheet=url, worksheet=hoja)

def leer_fresca(url, hoja):
    # 1. Leemos el Excel y hacemos una copia segura en la RAM
    df = conn.read(spreadsheet=url, worksheet=hoja, ttl=900).copy()
    
    # 2. Forzamos a que las celdas vacías falsas de Excel sean verdaderos nulos
    df = df.replace(["", " ", "None"], None)
    
    # 3. Ahora sí, volamos la grasa y dejamos solo los repuestos reales
    df = df.dropna(how='all')
    
    return df
# 4. COEFICIENTES DESDE SHEETS (SEGURIDAD FINANCIERA ESTRICTA)
try:
    df_cfg = leer_hoja(SHEET_URL, "Configuracion")
    
    # BLINDAJE 1: Limpiamos espacios invisibles al principio o final de las palabras
    df_cfg["Parametro"] = df_cfg["Parametro"].astype(str).str.strip()
    cfg = dict(zip(df_cfg["Parametro"], df_cfg["Valor"]))
    
    # BLINDAJE 2: Convertimos a la fuerza cualquier coma en punto para que la matemática no falle
    def a_numero(valor):
        return float(str(valor).replace(",", ".").strip())
    
    # Exigimos la lectura directa y limpia
    GETNET_1 = a_numero(cfg["GETNET_1_PAGO"])
    GETNET_3 = a_numero(cfg["GETNET_3_CUOTAS"])
    GETNET_6 = a_numero(cfg["GETNET_6_CUOTAS"])
    MPAGOS_1 = a_numero(cfg["MASPAGOS_1_PAGO"])
    MPAGOS_3 = a_numero(cfg["MASPAGOS_3_CUOTAS"])
    MPAGOS_6 = a_numero(cfg["MASPAGOS_6_CUOTAS"])

except Exception as e:
    st.error(f"🚨 ERROR TÉCNICO DETALLADO: {e}")
    st.error("Verificá la tabla de abajo. Así es exactamente como la aplicación está leyendo tu Excel. Si falta algún dato, ahí está la fuga.")
    try:
        st.dataframe(df_cfg) # Le pedimos que nos muestre en pantalla qué fue lo que leyó
    except:
        pass
    st.stop()

# 5. CATÁLOGOS
try:
    df_kits = leer_hoja(SHEET_URL, "Catalogo_Kits")
    df_crapo = leer_hoja(SHEET_URL, "Catalogo_Crapodinas")
    df_distri = leer_hoja(SHEET_URL, "Catalogo_Distribucion")
except Exception as e:
    df_kits = df_crapo = df_distri = pd.DataFrame()

# 6. FUNCIONES DE ESCRITURA

def saldar_deuda(fecha, nombre, tipo_actor):
    try:
        df = leer_fresca(SHEET_URL, "Ventas")
        
        # Filtramos para asegurarnos de no agarrar filas vacías
        if tipo_actor == "Cliente":
            mask = (df['Fecha'].astype(str).str.strip() == str(fecha).strip()) & (df['Cliente'].astype(str).str.strip() == str(nombre).strip())
            if mask.any():
                idx = df.index[mask][0]
                df.at[idx, 'Estado_Cobro'] = "Pagado"
                
        elif tipo_actor == "Proveedor":
            mask = (df['Fecha'].astype(str).str.strip() == str(fecha).strip()) & (df['Proveedor'].astype(str).str.strip() == str(nombre).strip())
            if mask.any():
                idx = df.index[mask][0]
                df.at[idx, 'Estado_Pago_Prov'] = "Pagado"
                
        # Guardamos en el Excel y limpiamos la memoria
        conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df)
        st.cache_data.clear()
        return True
        
    except Exception as e:
        st.error(f"Falla al saldar deuda: {e}")
        return False

def actualizar_catalogo_kits(vehiculo, descripcion, codigo, precio, marca, motor, proveedor):
    try:
        df = leer_fresca(SHEET_URL, "Catalogo_Kits")
        
        # BLINDAJE: Adaptado exactamente a las columnas de tu Excel
        if 'Vehiculo' not in df.columns: df['Vehiculo'] = ""
        
        marca_up = str(marca).upper()
        col_cod = f"Codigo_{marca_up}"
        col_pre = f"Precio_{marca_up}"
        
        if col_cod not in df.columns:
            df[col_cod] = ""
            df[col_pre] = ""

        veh_l = str(vehiculo).strip().lower()
        cod_l = str(codigo).split('.')[0].strip()
        
        m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l)
        
        if m_exacto.any():
            idx = df.index[m_exacto][0]
            df.at[idx, col_cod] = codigo
            df.at[idx, col_pre] = precio
            if motor: df.at[idx, "Motor"] = motor
            if proveedor: df.at[idx, "Proveedor"] = proveedor
        else:
            fila = {c: "" for c in df.columns}
            fila["Vehiculo"] = vehiculo
            fila["Motor"] = motor
            fila["Proveedor"] = proveedor
            fila[col_cod] = codigo
            fila[col_pre] = precio
            df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
            
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        leer_hoja.clear()
    except Exception as e:
        st.error(f"Falla al guardar en Kits: {e}")

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
        
        m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                   (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
                   
        if m_exacto.any():
            idx = df.index[m_exacto][0]
            df.at[idx, col_cod] = codigo
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
        st.error(f"Falla al guardar en Crapodinas: {e}")

def guardar_en_google(nro_trabajo, categoria, cliente, vehiculo, detalle, monto_bruto, monto_neto, costo, proveedor,
                      cod_kit, cod_crap, f_pago, e_cliente, e_prov,
                      m_forros, c_forros, costo_f, ganancia):
    fecha_hoy = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    
    # Agregamos "Nro_Trabajo" exactamente en la segunda posición
    columnas = ["Fecha", "Nro_Trabajo", "Categoría", "Cliente", "Vehículo", "Detalle",
                "Venta $", "Compra $", "Proveedor", "Código", "Cod_Crapodina",
                "Forma_de_pago", "Estado_Cobro", "Estado_Pago_Prov",
                "Marca_Forros", "Cod_Forros", "Costo_Forros", "Ganancia", "Monto Neto Esperado"]
    try:
        df_existente = leer_fresca(SHEET_URL, "Ventas")
    except Exception as e:
        st.error(f"Error al leer Ventas: {e}")
        st.stop()
        
    # Inyectamos la variable nro_trabajo después de fecha_hoy
    nueva = pd.DataFrame([[fecha_hoy, nro_trabajo, categoria, cliente, vehiculo, detalle,
                           monto_bruto, costo, proveedor, cod_kit, cod_crap,
                           f_pago, e_cliente, e_prov,
                           m_forros, c_forros, costo_f, ganancia, monto_neto]],
                         columns=columnas)
    df_nuevo = pd.concat([df_existente, nueva], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_nuevo)
    leer_hoja.clear()

# -------------------------------------------------------------
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
    ["Embrague Nuevo (Venta)", "Reparación de Embrague", "Rectificación de Volante", "Kit de Distribución", "Otro"], key=f"tipo_{fk}")

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
elif "Rectificación" in tipo_item:
    cat_f, icono, incl_rectif = "Rectificación", "⚙️", True
    sugerencia = "Rectificación de volante"
else:
    cat_f, icono, incl_rectif = "Venta", "🛠️", False
    sugerencia = "KIT de distribución"

# CONDICIÓN: Ocultar Nro de Trabajo si es Rectificación
if tipo_item != "Rectificación de Volante":
    nro_trabajo_input = st.sidebar.text_input("Nro. de Trabajo (Ej: 168):", value="", key=f"nrotrabajo_{fk}")
else:
    nro_trabajo_input = ""

monto_limpio = st.sidebar.number_input("Precio de VENTA ($):", min_value=0, value=0, key=f"montolimpio_{fk}")
vehiculo_input = st.sidebar.text_input("Vehículo:", value="", key=f"vehiculo_{fk}")
motor_input = st.sidebar.text_input("Motor:", value="", key=f"motor_{fk}")

# CONDICIÓN: Ocultar Proveedor si es Rectificación
if tipo_item != "Rectificación de Volante":
    proveedor_input = st.sidebar.text_input("Proveedor:", value="", key=f"proveedor_{fk}")
else:
    proveedor_input = "Taller Propio"

# Ajuste del Detalle
if tipo_item == "Rectificación de Volante":
    detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Rectificación volante", key=f"detalle_{fk}")
else:
    detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Venta / Reparación", key=f"detalle_{fk}")
    
cliente_input = st.sidebar.text_input("Nombre del Cliente:", value="", key=f"cliente_{fk}")
detalle_final = st.sidebar.text_area("💬 Detalle en WhatsApp:", value=sugerencia, key=f"detwhats_{fk}")

st.sidebar.divider()
st.sidebar.write("📸 **Uso Interno**")

# Lógica de costos según tipo
if cat_f == "Reparación":
    codigo_manual = crap_codigo
    precio_compra = crap_costo + forros_costo
    st.sidebar.info(f"💰 Costo Materiales: ${precio_compra:,.0f}")
elif cat_f == "Rectificación":
    codigo_manual = ""
    precio_compra = 0
    st.sidebar.info("💰 Costo Materiales: $0 (Servicio Propio)")
else:
    codigo_manual = st.sidebar.text_input("Código de repuesto:", "", key=f"codrep_{fk}")
    precio_compra = st.sidebar.number_input("Precio de COMPRA ($):", min_value=0, value=0, key=f"precomp_{fk}")

foto_repuesto = st.sidebar.file_uploader("📷 Foto del repuesto", type=["jpg","png","jpeg"], key=f"foto_{fk}")
if foto_repuesto:
    st.sidebar.image(foto_repuesto, caption="Vista previa", use_container_width=True)

ganancia = monto_limpio - precio_compra
if monto_limpio > 0:
    st.sidebar.metric("Ganancia Estimada", f"$ {ganancia:,.0f}")

st.sidebar.divider()
st.sidebar.subheader("💰 Estado de la Operación")

estado_cliente = st.sidebar.selectbox("Estado del Cliente:", ["Pagado","Cuenta Corriente","Seña"], index=0, key=f"estcli_{fk}")
f_pago_input = "N/A"
if estado_cliente == "Pagado":
    f_pago_input = st.sidebar.selectbox("¿Cómo pagó?:", [
        "Efectivo","Transferencia","Débito",
        "BNA - 1 Pago","BNA - 3 Cuotas","BNA - 6 Cuotas",
        "Link de Pago Getnet",
        "Getnet - 1 Pago","Getnet - 3 Cuotas","Getnet - 6 Cuotas",
        "Más Pagos - 1 Pago","Más Pagos - 3 Cuotas","Más Pagos - 6 Cuotas",
        "Combinado","Otro"], key=f"fpago_{fk}")
# CONDICIÓN: Ocultar pago a proveedor si es rectificación
if tipo_item != "Rectificación de Volante":
    estado_p_prov = st.sidebar.selectbox("Estado al Proveedor:", ["Pagado","Cuenta Corriente","N/A"], index=0, key=f"estprov_{fk}")
else:
    estado_p_prov = "N/A"

cod_kit_final = "" if cat_f in ["Reparación", "Rectificación"] else codigo_manual
cod_crap_final = crap_codigo if cat_f == "Reparación" else ""

if st.sidebar.button("💾 GUARDAR VENTA", key=f"btn_guardar_{fk}"):
        
        monto_bruto = monto_limpio
        monto_neto_guardar = monto_limpio
        
        # Matemática quirúrgica para Links y POS
        if f_pago_input in ["Efectivo", "Transferencia"]:
            monto_neto_guardar = "-"
        elif "Link" in f_pago_input: 
            monto_bruto = int(round(monto_limpio / 0.9758))  # Descuento Getnet Plazo Estándar (2.42%)
        elif f_pago_input == "Getnet - 1 Pago": monto_bruto = int(round(monto_limpio * GETNET_1))
        elif f_pago_input == "Getnet - 3 Cuotas": monto_bruto = int(round(monto_limpio * GETNET_3))
        elif f_pago_input == "Getnet - 6 Cuotas": monto_bruto = int(round(monto_limpio * GETNET_6))
        elif f_pago_input == "Más Pagos - 1 Pago": monto_bruto = int(round(monto_limpio * MPAGOS_1))
        elif f_pago_input == "Más Pagos - 3 Cuotas": monto_bruto = int(round(monto_limpio * MPAGOS_3))
        elif f_pago_input == "Más Pagos - 6 Cuotas": monto_bruto = int(round(monto_limpio * MPAGOS_6))
        
        # Inyectamos nro_trabajo_input en la función (La rectificación ya va limpia acá)
        guardar_en_google(nro_trabajo_input, cat_f, cliente_input, vehiculo_input, detalle_excel,
                          monto_bruto, monto_neto_guardar, precio_compra, proveedor_input,
                          cod_kit_final, cod_crap_final, f_pago_input,
                          estado_cliente, estado_p_prov,
                          m_forros, forros_codigo, forros_costo, ganancia)
                          
        if cod_kit_final and cat_f == "Venta":
            marca_k = m_kit[0] if isinstance(m_kit, list) and m_kit else (m_kit or "OTRA")
            actualizar_catalogo_kits(vehiculo_input, "Kit de Embrague", cod_kit_final, precio_compra, marca_k, motor_input, proveedor_input)
        if cod_crap_final and cat_f == "Reparación":
            actualizar_catalogo_crapodinas(vehiculo_input, f"Crapodina {tipo_crap}",
                                           cod_crap_final, crap_costo,
                                           m_crap[0] if m_crap else "OTRA")
                                           
        st.session_state.form_key += 1
        st.session_state["venta_exitosa"] = "✅ Venta registrada correctamente."
        st.cache_data.clear()
        st.rerun()

# 8. CALCULADORA DE CUOTAS
st.markdown("### 💳 Calculadora de Cuotas / Links")
tipo_pos = st.radio("¿Qué vas a usar?", ["GETNET (Posnet)", "MÁS PAGOS (Posnet)", "LINK DE PAGO (Getnet)"], horizontal=True)

if tipo_pos == "LINK DE PAGO (Getnet)":
    nombre_pos = "LINK GETNET"
    plan_link = st.selectbox("Plan de Cuotas para el Cliente:", ["Estándar Bancario", "Cuota Simple (MiPyME)"])
    
    # Matemática quirúrgica: Descuento Getnet Plazo Estándar (2% arancel + 21% IVA = 2.42%) -> factor divisor 0.9758
    monto_link = monto_limpio / 0.9758
    
    # Coeficientes según el plan que elija para el cliente
    if "Estándar" in plan_link:
        c3, c6 = 1.0913, 1.1666
    else:
        c3, c6 = 1.0810, 1.1638
        
    t1 = monto_link 
    t3 = monto_link * c3
    t6 = monto_link * c6
    
    st.info(f"🔗 **MONTO DEL LINK A GENERAR:** $ {monto_link:,.0f} (Copiá este valor exacto en la App de Getnet)")

elif "GETNET" in tipo_pos:
    c1, c3, c6 = GETNET_1, GETNET_3, GETNET_6
    nombre_pos = "GETNET"
    t1, t3, t6 = monto_limpio * c1, monto_limpio * c3, monto_limpio * c6
    p_1, p_3, p_6 = [(x-1)*100 for x in [c1,c3,c6]]
    st.info(f"📊 **Recargos:** 1 Pago: {p_1:.1f}% | 3 Cuotas: {p_3:.1f}% | 6 Cuotas: {p_6:.1f}%")
else:
    c1, c3, c6 = MPAGOS_1, MPAGOS_3, MPAGOS_6
    nombre_pos = "MÁS PAGOS"
    t1, t3, t6 = monto_limpio * c1, monto_limpio * c3, monto_limpio * c6
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
if "LINK" in tipo_pos:
    with ca: st.metric("LINK A GENERAR",   f"${t1:,.0f}")
    with cb: st.metric("Cliente en 3 (Aprox)", f"${t3/3:,.2f}", f"Total: ${t3:,.0f}")
    with cc: st.metric("Cliente en 6 (Aprox)", f"${t6/6:,.2f}", f"Total: ${t6:,.0f}")
else:
    with ca: st.metric("1 PAGO",   f"${t1:,.0f}")
    with cb: st.metric("3 CUOTAS", f"${t3/3:,.2f}", f"Total: ${t3:,.0f}")
    with cc: st.metric("6 CUOTAS", f"${t6/6:,.2f}", f"Total: ${t6:,.0f}")

# 9. WHATSAPP
txt_rectif = "\n✅ *Incluye rectificación y balanceo de volante*" if incl_rectif else ""
maps_link = "https://www.google.com/maps?q=Crespo+4117+Rosario"

# Texto condicional para no confundir al cliente con el Link vs Posnet
if "LINK" in tipo_pos:
    txt_tarjeta = (
        f"💳 *LINK DE PAGO GETNET:*\n"
        f"El monto exacto del link es de ${t1:,.0f}.\n"
        f"*(Si elegís financiar con tu banco, estos son los valores aproximados:)*\n"
        f"✅ *3 cuotas de:* ${t3/3:,.2f} (Total: ${t3:,.0f})\n"
        f"✅ *6 cuotas de:* ${t6/6:,.2f} (Total: ${t6:,.0f})\n\n"
    )
else:
    txt_tarjeta = (
        f"💳 *TARJETA BANCARIA ({nombre_pos}):*\n"
        f"✅ *1 pago:* ${t1:,.0f}\n\n"
        f"✅ *3 cuotas de:* ${t3/3:,.2f}\n      (Total: ${t3:,.0f})\n\n"
        f"✅ *6 cuotas de:* ${t6/6:,.2f}\n      (Total: ${t6:,.0f})\n\n"
    )

mensaje = (
    f"🚗 *EMBRAGUES ROSARIO*\n"
    f"¡Hola! Gracias por tu consulta. Te paso el presupuesto:\n\n"
    f"🚗 *Vehículo:* {vehiculo_input}\n"
    f"{icono} *Trabajo:* {detalle_final}{txt_rectif}\n\n"
    f"💰 *EFECTIVO / TRANSF:* ${monto_limpio:,.0f}\n\n"
    f"{txt_tarjeta}"
    f"📍 *Dirección:* Crespo 4117, Rosario\n"
    f"📍 *Ubicación:* {maps_link}\n"
    f"📸 *Instagram:* @embraguesrosario\n"
    f"⏰ *Horario:* 8:30 a 17:00 hs\n\n"
    f"¡Te esperamos pronto! 🙋🏻"
)
st.link_button("🟢 ENVIAR PRESUPUESTO POR WHATSAPP", f"https://wa.me/?text={urllib.parse.quote(mensaje)}")

# 10. HISTORIAL Y DASHBOARD FINANCIERO
st.divider()

try:
    # Leemos la hoja de Excel una sola vez
    df_ver = leer_hoja(SHEET_URL, "Ventas")
    
    if not df_ver.empty:
        # --- DASHBOARD DE GANANCIAS ---
        with st.expander("📊 Tablero de Finanzas (Mes a Mes)"):
            import pandas as pd
            import datetime
            
            # Hacemos una copia para trabajar los números sin romper la tabla
            df_dash = df_ver.copy()
            
            # Limpiamos las columnas para que el sistema pueda sumar matemáticamente
            df_dash['Fecha'] = pd.to_datetime(df_dash['Fecha'], dayfirst=True, errors='coerce')
            df_dash['Ganancia'] = pd.to_numeric(df_dash['Ganancia'], errors='coerce').fillna(0)
            df_dash['Venta $'] = pd.to_numeric(df_dash['Venta $'], errors='coerce').fillna(0)
            df_dash['Compra $'] = pd.to_numeric(df_dash['Compra $'], errors='coerce').fillna(0)
            
            # Calculamos las fechas de hoy
            hoy = datetime.date.today()
            mes_actual = hoy.month
            anio_actual = hoy.year
            
            # Calculamos cuál fue el mes pasado
            if mes_actual == 1:
                mes_pasado = 12
                anio_pasado = anio_actual - 1
            else:
                mes_pasado = mes_actual - 1
                anio_pasado = anio_actual
                
            # Filtramos la tabla separando la plata de cada mes
            df_mes_actual = df_dash[(df_dash['Fecha'].dt.month == mes_actual) & (df_dash['Fecha'].dt.year == anio_actual)]
            df_mes_pasado = df_dash[(df_dash['Fecha'].dt.month == mes_pasado) & (df_dash['Fecha'].dt.year == anio_pasado)]
            
            # --- INDICADORES FINANCIEROS ---
            ganancia_actual = df_mes_actual['Ganancia'].sum()
            ganancia_pasada = df_mes_pasado['Ganancia'].sum()
            diferencia = ganancia_actual - ganancia_pasada
            
            # Plata en la calle (Ventas totales en Cuenta Corriente)
            df_cobrar = df_mes_actual[df_mes_actual['Estado_Cobro'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            plata_en_calle = df_cobrar['Venta $'].sum()
            
            # Deuda a proveedores (Compras totales en Cuenta Corriente)
            df_pagar = df_mes_actual[df_mes_actual['Estado_Pago_Prov'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            deuda_prov = df_pagar['Compra $'].sum()
            
            # Mostramos los 3 bloques principales
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(label="📈 Ganancia Este Mes", value=f"${ganancia_actual:,.0f}", delta=f"${diferencia:,.0f} vs Mes Pasado")
            with c2:
                st.metric(label="⏳ A Cobrar (En la Calle)", value=f"${plata_en_calle:,.0f}", delta="Fiado a Clientes", delta_color="off")
            with c3:
                st.metric(label="⚠️ A Pagar (Deuda Prov.)", value=f"${deuda_prov:,.0f}", delta="Fiado de Proveedores", delta_color="off")
                
            # --- DETALLE DE DEUDORES Y ACREEDORES ---
            st.markdown("---")
            col_det_1, col_det_2 = st.columns(2)
            
            with col_det_1:
                st.markdown("**🎯 ¿Quién me debe?**")
                if not df_cobrar.empty:
                    detalle_clientes = df_cobrar.groupby('Cliente')['Venta $'].sum().reset_index()
                    detalle_clientes = detalle_clientes[detalle_clientes['Venta $'] > 0]
                    # Formato limpio para la tabla
                    st.dataframe(detalle_clientes.style.format({'Venta $': '${:,.0f}'}), hide_index=True, use_container_width=True)
                else:
                    st.success("Nadie te debe plata este mes. ¡Excelente!")
                    
            with col_det_2:
                st.markdown("**🏭 ¿A quién le debo?**")
                if not df_pagar.empty:
                    detalle_prov = df_pagar.groupby('Proveedor')['Compra $'].sum().reset_index()
                    detalle_prov = detalle_prov[detalle_prov['Compra $'] > 0]
                    # Formato limpio para la tabla
                    st.dataframe(detalle_prov.style.format({'Compra $': '${:,.0f}'}), hide_index=True, use_container_width=True)
                else:
                    st.success("No le debés a ningún proveedor este mes.")

            st.markdown("---")
                
            # --- GRÁFICO DE EVOLUCIÓN (MEJORADO Y ORDENADO) ---
            st.markdown("**Evolución Diaria de Ganancias (Mes Actual)**")
            if not df_mes_actual.empty:
                # Agrupamos la ganancia por la FECHA EXACTA (no solo el número del día)
                grafico_datos = df_mes_actual.groupby(df_mes_actual['Fecha'].dt.date)['Ganancia'].sum()
                
                # Armamos el calendario completo desde el día 1 hasta hoy para que no queden huecos
                rango_fechas = pd.date_range(start=datetime.date(anio_actual, mes_actual, 1), end=hoy).date
                grafico_datos = grafico_datos.reindex(rango_fechas, fill_value=0)
                
                # Le damos el formato exacto de fecha "Día/Mes" (Ej: 01/07, 02/07) para el gráfico
                grafico_datos.index = [f"{d.day:02d}/{d.month:02d}" for d in grafico_datos.index]
                
                # Usamos gráfico de barras con el eje X ordenado cronológicamente
                st.bar_chart(grafico_datos)
            else:
                st.info("No hay ventas registradas todavía este mes para graficar.")
                
        # --- HISTORIAL (Tabla original) ---
        st.subheader("📋 Últimos Movimientos")
        st.dataframe(df_ver.tail(5)[::-1], use_container_width=True)
        
    else:
        st.subheader("📋 Últimos Movimientos")
        st.info("La planilla está vacía todavía.")
        
except Exception as e:
    st.warning(f"⚠️ No se pudo cargar el historial o el tablero. Error: {e}")

# 9. GESTIÓN DE SALDOS (CUENTAS CORRIENTES)
st.markdown("---")
st.markdown("### 📒 Gestión de Cuentas Corrientes")

if st.checkbox("Abrir panel de Cuentas Corrientes"):
    tipo_saldo = st.radio("¿Qué querés saldar?", ["Cobro a Cliente", "Pago a Proveedor"], horizontal=True)

    try:
        df_ventas = leer_fresca(SHEET_URL, "Ventas")
        
        # ==========================================
        # OPCIÓN 1: COBRO A CLIENTES
        # ==========================================
        if tipo_saldo == "Cobro a Cliente":
            df_deudas = df_ventas[df_ventas['Estado_Cobro'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            
            if not df_deudas.empty:
                col_monto = 'Venta $'
                
                st.write("📊 **Resumen: ¿Cuánto nos debe cada cliente en total?**")
                resumen_totales = df_deudas.groupby('Cliente')[col_monto].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                resumen_totales.columns = ['Cliente', 'Deuda Total ($)']
                st.dataframe(resumen_totales.style.format({'Deuda Total ($)': '${:,.0f}'}), hide_index=True)
                
                st.write("📝 **Desglose exacto de los trabajos pendientes:**")
                cols_mostrar = ['Fecha', 'Cliente', 'Vehículo', 'Detalle', col_monto]
                cols_finales = [c for c in cols_mostrar if c in df_deudas.columns]
                
                df_detalle = df_deudas[cols_finales].copy()
                df_detalle[col_monto] = pd.to_numeric(df_detalle[col_monto], errors='coerce').fillna(0)
                st.dataframe(df_detalle.style.format({col_monto: '${:,.0f}'}), hide_index=True, use_container_width=True)
                
                st.divider()
                
                opciones = df_deudas['Fecha'].astype(str) + " | " + df_deudas['Cliente'].astype(str) + " | " + df_deudas['Vehículo'].astype(str)
                seleccion = st.multiselect("Seleccioná la o las deudas a cobrar (podés elegir varias):", opciones.tolist())
                
                if st.button("💰 Registrar Cobro(s)"):
                    if seleccion:
                        for sel in seleccion:
                            fecha_sel = sel.split(" | ")[0]
                            cliente_sel = sel.split(" | ")[1]
                            saldar_deuda(fecha_sel, cliente_sel, "Cliente")
                        st.success(f"✅ {len(seleccion)} cobro(s) registrado(s). El Excel se actualizó a 'Pagado'.")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para cobrar.")
            else:
                st.success("✅ No hay deudas de clientes registradas. ¡Están todos al día!")
                st.divider()

        # ==========================================
        # OPCIÓN 2: PAGO A PROVEEDORES
        # ==========================================
        elif tipo_saldo == "Pago a Proveedor":
            df_deudas = df_ventas[df_ventas['Estado_Pago_Prov'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            
            if not df_deudas.empty:
                col_monto = 'Compra $'
                
                st.write("📊 **Resumen: ¿Cuánto le debemos a cada proveedor?**")
                resumen_totales = df_deudas.groupby('Proveedor')[col_monto].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                resumen_totales.columns = ['Proveedor', 'Deuda Total ($)']
                st.dataframe(resumen_totales.style.format({'Deuda Total ($)': '${:,.0f}'}), hide_index=True)
                
                st.write("📝 **Desglose exacto de las compras pendientes:**")
                cols_mostrar = ['Fecha', 'Proveedor', 'Vehículo', 'Detalle', col_monto]
                cols_finales = [c for c in cols_mostrar if c in df_deudas.columns]
                
                df_detalle = df_deudas[cols_finales].copy()
                df_detalle[col_monto] = pd.to_numeric(df_detalle[col_monto], errors='coerce').fillna(0)
                st.dataframe(df_detalle.style.format({col_monto: '${:,.0f}'}), hide_index=True, use_container_width=True)
                
                st.divider()
                
                opciones = df_deudas['Fecha'].astype(str) + " | " + df_deudas['Proveedor'].astype(str) + " | " + df_deudas['Vehículo'].astype(str)
                seleccion = st.multiselect("Seleccioná la o las deudas a pagar (podés elegir varias):", opciones.tolist())
                
                if st.button("💸 Registrar Pago(s)"):
                    if seleccion:
                        for sel in seleccion:
                            fecha_sel = sel.split(" | ")[0]
                            prov_sel = sel.split(" | ")[1]
                            saldar_deuda(fecha_sel, prov_sel, "Proveedor")
                        st.success(f"✅ {len(seleccion)} pago(s) registrado(s). El Excel se actualizó a 'Pagado'.")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para pagar.")
            else:
                st.success("✅ No le debemos a ningún proveedor. ¡Cuentas al día!")
                st.divider()
                
    except Exception as e:
        st.error(f"⚠️ Error al cargar las deudas: {e}")

st.divider()
st.subheader("💸 Gestión de Gastos e Inversiones")

with st.expander("Abrir panel para registrar una salida de dinero"):
    with st.form("form_gastos", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_gasto = st.date_input("Fecha", format="DD/MM/YYYY")
            clasificacion = st.selectbox("Clasificación (¡Clave para los números!)", ["Gasto Operativo", "Inversión en Stock"])
            categoria = st.selectbox("Categoría", ["Cadetería / Fletes", "Impuestos / AFIP", "Compra de Mercadería", "Insumos de Taller", "Otros"])
            proveedor = st.text_input("Proveedor o Destinatario (Ej: Icepar, Juan Cadete)")
            
        with col2:
            detalle = st.text_input("Detalle exacto (¿Qué se pagó?)")
            monto = st.number_input("Monto ($)", min_value=0, step=1000)
            estado_pago = st.selectbox("Estado del Pago", ["Pagado (Contado/Transf)", "Cuenta Corriente"])
            
        submit_gasto = st.form_submit_button("💾 Guardar Registro")
        
        if submit_gasto:
            if monto > 0 and detalle != "":
                # Formateamos la fecha al estilo argentino
                fecha_str = fecha_gasto.strftime("%d/%m/%Y")
                
                # Armamos el paquete de datos exacto para tu Excel
                datos_gasto = [fecha_str, clasificacion, categoria, detalle, monto, estado_pago, proveedor]
                
                try:
                    # 1. Leemos cómo está la hoja de Gastos AHORA
                    df_gastos = conn.read(spreadsheet=SHEET_URL, worksheet="Gastos", ttl=0)
                    
                    # 2. BLINDAJE: Le dictamos a la fuerza los nombres exactos de nuestras 7 columnas
                    columnas_estrictas = ["Fecha", "Clasificacion", "Categoria", "Detalle", "Monto $", "Estado_Pago", "Proveedor"]
                    
                    # 3. Armamos la nueva fila usando solo esas 7 columnas
                    nueva_fila = pd.DataFrame([datos_gasto], columns=columnas_estrictas)
                    
                    # 4. Si la hoja del Excel estaba vacía, la obligamos a usar nuestra estructura
                    if df_gastos.empty:
                        df_gastos = pd.DataFrame(columns=columnas_estrictas)
                    else:
                        # Si tenía algo, forzamos a que solo mire nuestras 7 columnas y borre la basura fantasma
                        df_gastos = df_gastos[columnas_estrictas]
                    
                    # 5. Pegamos la fila nueva abajo de todo
                    df_actualizado = pd.concat([df_gastos, nueva_fila], ignore_index=True)
                    
                    # 6. Inyectamos de vuelta al Excel
                    conn.update(spreadsheet=SHEET_URL, worksheet="Gastos", data=df_actualizado)
                    
                    # Limpiamos la memoria
                    st.cache_data.clear()
                    
                    st.success(f"✅ ¡Gasto registrado con éxito! {detalle} por ${monto}.")
                    
                except Exception as e:
                    st.error(f"⚠️ Error al inyectar los datos en el Excel: {e}")
                
            else:
                st.warning("⚠️ El monto debe ser mayor a $0 y el detalle no puede estar vacío.")


# 12. BUSCADOR DE CATÁLOGO (Optimizado con RAM - Session State)
st.divider()
st.header("🔍 Consultar Catálogo")

hoja_map = {
    "Embragues (Kits)": "Catalogo_Kits", 
    "Crapodinas": "Catalogo_Crapodinas", 
    "Distribución": "Catalogo_Distribucion"
}

tipo_busqueda = st.radio("¿Qué estás buscando?", list(hoja_map.keys()), horizontal=True)

# Creamos una clave única para guardar esta pestaña en la memoria de la app
session_key = f"df_{hoja_map[tipo_busqueda]}"

# Si el catálogo seleccionado todavía no está en memoria, lo traemos de Google Sheets
if session_key not in st.session_state:
    st.session_state[session_key] = leer_hoja(SHEET_URL, hoja_map[tipo_busqueda])

# A partir de acá, trabajamos 100% con la memoria RAM, sin pedirle datos a Google
df_b = st.session_state[session_key]

busqueda = st.text_input("✍️ Modelo de Auto o Código:")

# Si hay texto escrito, filtramos. Si está vacío (o se borró), no hace nada.
if busqueda:
    if not df_b.empty:
        palabras = busqueda.lower().split()
        mask = pd.Series(True, index=df_b.index)
        
        for palabra in palabras:
            mask &= df_b.fillna("").astype(str).apply(
                lambda x: x.str.contains(palabra, case=False, na=False)
            ).any(axis=1)
            
        df_filtrado = df_b[mask]
        
        if not df_filtrado.empty:
            st.dataframe(df_filtrado, use_container_width=True)
        else:
            st.info("No encontré resultados.")
    else:
        st.warning("El catálogo seleccionado está vacío en el Excel.")

st.divider()
st.subheader("📦 Gestión de Inventario y Stock")

with st.expander("Abrir panel para ingresar mercadería"):
    with st.form("form_stock", clear_on_submit=False):
        st.write("📝 **Carga de repuestos e insumos nuevos**")
        
        # Fila 1: Categoría, Vehículo y Motor
        col1, col2, col3 = st.columns(3)
        with col1:
            categoria_stock = st.selectbox("Categoría", ["Kits de Embrague", "Forros IAR Metal", "Crapodinas", "Distribución", "Frenos", "Otros"])
        with col2:
            vehiculo_stock = st.text_input("Vehículo (Ej: Gol Power)")
        with col3:
            motor_stock = st.text_input("Motor (Ej: 1.6)")
            
        # Fila 2: Marca, Código, Cantidad y Costo
        col4, col5, col6, col7 = st.columns(4)
        with col4:
            marca_stock = st.text_input("Marca (Ej: Sachs, LUK, Valeo)")
        with col5:
            codigo_stock = st.text_input("Código de Fábrica")
        with col6:
            cantidad_stock = st.number_input("Cantidad a ingresar", min_value=1, step=1)
        with col7:
            costo_stock = st.number_input("Costo Unitario ($)", min_value=0, step=1000)
            
        submit_stock = st.form_submit_button("📥 Guardar en Estantería")
        
        if submit_stock:
            # Validamos que al menos haya puesto un vehículo o un código, y que el costo sea mayor a 0
            if (vehiculo_stock != "" or codigo_stock != "") and costo_stock > 0:
                
                # Juntamos los textos para armar un detalle limpio
                partes_detalle = [p.strip() for p in [vehiculo_stock, motor_stock, marca_stock, codigo_stock] if p.strip() != ""]
                detalle_unido = " | ".join(partes_detalle)
                
                # Armamos el paquete exacto de 4 datos
                datos_stock = [categoria_stock, detalle_unido, cantidad_stock, costo_stock]
                
                try:
                    # 1. Leemos la hoja de Stock fresca
                    df_stock = conn.read(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", ttl=0)
                    
                    # 2. BLINDAJE: Nuestras 4 columnas obligatorias
                    columnas_estrictas_stock = ["Categoria", "Detalle_Articulo", "Cantidad", "Costo_Unitario"]
                    
                    # 3. Armamos la fila
                    nueva_fila_stock = pd.DataFrame([datos_stock], columns=columnas_estrictas_stock)
                    
                    # 4. Limpiamos la basura de Google Sheets
                    if df_stock.empty:
                        df_stock = pd.DataFrame(columns=columnas_estrictas_stock)
                    else:
                        df_stock = df_stock[columnas_estrictas_stock]
                    
                    # 5. Unimos y mandamos al Excel
                    df_actualizado_stock = pd.concat([df_stock, nueva_fila_stock], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", data=df_actualizado_stock)
                    
                    st.cache_data.clear()
                    st.success(f"✅ ¡Entró al stock! {cantidad_stock}x de: {detalle_unido}.")
                    
                except Exception as e:
                    st.error(f"⚠️ Error al guardar el stock: {e}")
            else:
                st.warning("⚠️ Asegurate de escribir al menos el Vehículo o el Código, y que el costo en pesos sea mayor a $0.")

st.divider()
st.subheader("🔄 Base de Datos Técnica (Actualización de Códigos)")

with st.expander("Abrir panel para cargar Códigos de Kits"):
    with st.form("form_actualizar_kits", clear_on_submit=False):
        st.write("📝 **Modificar o agregar equivalencias y códigos de fábrica**")
        
        # Fila 1: Identificación del vehículo
        col1, col2 = st.columns(2)
        with col1:
            vehiculo_cat = st.text_input("Vehículo exacto (Ej: Peugeot 307)")
        with col2:
            motor_cat = st.text_input("Motor (Ej: 2.0)")
            
        # Fila 2: El código nuevo a inyectar
        col3, col4 = st.columns(2)
        with col3:
            marca_cat = st.selectbox("¿De qué marca es el código?", ["LUK", "SACHS", "VALEO", "PHC_valeo", "ORIGINAL", "OTRA"])
        with col4:
            codigo_cat = st.text_input("Nuevo Código de Fábrica")
            
        submit_cat_kits = st.form_submit_button("💾 Guardar Código en Base de Datos")
        
        if submit_cat_kits:
            # Ahora obligamos a que sí o sí haya escrito un vehículo y un código
            if vehiculo_cat != "" and codigo_cat != "":
                try:
                    df_kits = conn.read(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", ttl=0)
                    
                    # BLINDAJE: Las 15 columnas exactas de tu Excel para no romper nada
                    columnas_kits = [
                        "Vehiculo", "Motor", "Proveedor", 
                        "Codigo_LUK", "Precio_LUK", "Codigo_SACHS", "Precio_SACHS", 
                        "Codigo_VALEO", "Precio_VALEO", "Codigo_PHC_valeo", "Precio_PHC_valeo", 
                        "Codigo_ORIGINAL", "Precio_ORIGINAL", "Codigo_OTRA", "Precio_OTRA"
                    ]
                    
                    if df_kits.empty:
                        df_kits = pd.DataFrame(columns=columnas_kits)
                    else:
                        df_kits = df_kits[columnas_kits]
                    
                    df_kits['Veh_norm'] = df_kits['Vehiculo'].astype(str).str.strip().str.lower()
                    df_kits['Mot_norm'] = df_kits['Motor'].astype(str).str.strip().str.lower()
                    
                    veh_buscar = vehiculo_cat.strip().lower()
                    mot_buscar = motor_cat.strip().lower()
                    
                    mask = (df_kits['Veh_norm'] == veh_buscar) & (df_kits['Mot_norm'] == mot_buscar)
                    
                    col_codigo = f"Codigo_{marca_cat}"
                    
                    # BLINDAJE DE FORMATO: Ablandamos para que no tire error si el código tiene letras
                    df_kits[col_codigo] = df_kits[col_codigo].astype(object)
                    
                    if mask.any():
                        # EL AUTO EXISTE: Se mete en el renglón y guarda solo el código en la marca elegida
                        idx = df_kits[mask].index[0]
                        df_kits.at[idx, col_codigo] = codigo_cat
                        accion_msj = "actualizado"
                    else:
                        # EL AUTO NO EXISTE: Crea fila nueva y le asigna el código
                        nueva_fila = {col: "" for col in columnas_kits}
                        nueva_fila["Vehiculo"] = vehiculo_cat
                        nueva_fila["Motor"] = motor_cat
                        nueva_fila[col_codigo] = codigo_cat
                        
                        df_nueva = pd.DataFrame([nueva_fila])
                        df_kits = pd.concat([df_kits, df_nueva], ignore_index=True)
                        accion_msj = "creado"
                    
                    df_kits = df_kits.drop(columns=['Veh_norm', 'Mot_norm'])
                    conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df_kits)
                    
                    st.cache_data.clear()
                    st.success(f"✅ ¡Código {accion_msj} con éxito! {vehiculo_cat} {motor_cat} | {marca_cat}: {codigo_cat}")
                    
                except Exception as e:
                    st.error(f"⚠️ Error al guardar el código: {e}")
            else:
                st.warning("⚠️ Asegurate de escribir el Vehículo y el Nuevo Código.")

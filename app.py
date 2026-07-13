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
    
    if f_pago_input in ["Efectivo", "Transferencia"]:
        monto_neto_guardar = "-"
    elif f_pago_input == "Getnet - 1 Pago": monto_bruto = monto_limpio * GETNET_1
    elif f_pago_input == "Getnet - 3 Cuotas": monto_bruto = monto_limpio * GETNET_3
    elif f_pago_input == "Getnet - 6 Cuotas": monto_bruto = monto_limpio * GETNET_6
    elif f_pago_input == "Más Pagos - 1 Pago": monto_bruto = monto_limpio * MPAGOS_1
    elif f_pago_input == "Más Pagos - 3 Cuotas": monto_bruto = monto_limpio * MPAGOS_3
    elif f_pago_input == "Más Pagos - 6 Cuotas": monto_bruto = monto_limpio * MPAGOS_6
    
    # Inyectamos nro_trabajo_input en la función
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

# --- CALCULADORA INVERSA GETNET (Links) ---
st.sidebar.divider()
with st.sidebar.expander("🧮 Calculadora Links Getnet"):
    st.markdown("Calculá el Link para cobrar exacto el precio de contado.")
    
    # Input principal: El precio que pasaste de palabra
    precio_contado = st.number_input("Precio de Venta (Contado $):", min_value=0, value=250000, step=1000, key="calc_link_precio")
    calc_plan = st.selectbox("Plan (3 Cuotas):", ["Estándar (2 días)", "MiPyME (10 días)"], key="calc_link_plan")
    
    # Matemática: Queremos que nos quede el "precio_contado" libre de la comisión de Getnet (2.42%)
    if precio_contado > 0:
        monto_link = precio_contado / 0.9758
        st.info(f"**Generar Link por:**\n### $ {monto_link:,.0f}")
        
        # Proyección cliente
        st.write("---")
        if "Estándar" in calc_plan:
            cliente_paga = monto_link * 1.0913 
            st.caption("⏱️ **Acreditación:** 2 días hábiles.")
            st.caption(f"💳 **El cliente pagará aprox:** $ {cliente_paga:,.0f}")
        else:
            cliente_paga = monto_link * 1.0810 
            st.caption("⏱️ **Acreditación:** 10 días hábiles.")
            st.caption(f"💳 **El cliente pagará aprox:** $ {cliente_paga:,.0f}")


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

# 9. GESTIÓN DE SALDOS (CUENTAS CORRIENTES)
st.markdown("---")
st.markdown("### 📒 Gestión de Cuentas Corrientes")

if st.checkbox("Abrir panel de Cuentas Corrientes"):
    tipo_saldo = st.radio("¿Qué querés saldar?", ["Cobro a Cliente", "Pago a Proveedor"], horizontal=True)

    try:
        df_ventas = leer_fresca(SHEET_URL, "Ventas")
        
        if tipo_saldo == "Cobro a Cliente":
            # Filtramos solo los clientes que deben y hacemos una copia segura
            df_deudas = df_ventas[df_ventas['Estado_Cobro'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            
            if not df_deudas.empty:
                
                st.write("📊 **Resumen: ¿Cuánto nos debe cada cliente?**")
                
                # Apuntamos a 'Venta $'
                col_monto = None
                for col in ['Venta $', 'Monto_Neto', 'Monto Neto']:
                    if col in df_deudas.columns:
                        col_monto = col
                        break
                        
                if col_monto:
                    col_vehiculo = 'Vehículo' if 'Vehículo' in df_deudas.columns else None
                    col_detalle = 'Detalle' if 'Detalle' in df_deudas.columns else None
                    
                    # Fusionamos Vehículo y Detalle
                    if col_vehiculo and col_detalle:
                        df_deudas['Resumen_Item'] = df_deudas[col_vehiculo].astype(str) + " (" + df_deudas[col_detalle].astype(str) + ")"
                        agg_col = 'Resumen_Item'
                    else:
                        agg_col = col_vehiculo or col_detalle
                        
                    if agg_col:
                        resumen = df_deudas.groupby('Cliente').agg({
                            col_monto: lambda x: pd.to_numeric(x, errors='coerce').sum(),
                            agg_col: lambda x: ' + '.join([str(i) for i in x if str(i).strip()])
                        }).reset_index()
                        resumen.columns = ['Cliente', 'Deuda Total ($)', 'Detalle de Trabajos']
                    else:
                        resumen = df_deudas.groupby('Cliente')[col_monto].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                        resumen.columns = ['Cliente', 'Deuda Total ($)']
                        
                    st.dataframe(resumen, hide_index=True, use_container_width=True)
                else:
                    st.warning(f"⚠️ No encuentro la columna de cobro. Las columnas leídas son: {', '.join(df_deudas.columns)}")
                st.divider()
                
                # MULTISELECT
                opciones = df_deudas['Fecha'].astype(str) + " | " + df_deudas['Cliente'].astype(str) + " | " + df_deudas['Vehículo'].astype(str)
                seleccion = st.multiselect("Seleccioná la o las deudas a cobrar (podés elegir varias):", opciones.tolist())
                
                if st.button("💰 Registrar Cobro(s)"):
                    if seleccion:
                        for sel in seleccion:
                            fecha_sel = sel.split(" | ")[0]
                            cliente_sel = sel.split(" | ")[1]
                            saldar_deuda(fecha_sel, cliente_sel, "Cliente")
                        st.success(f"{len(seleccion)} cobro(s) registrado(s). El Excel se actualizó a 'Pagado'.")
                        st.rerun()
                    else:
                        st.warning("Seleccioná al menos una deuda para cobrar.")
            else:
                st.info("No hay clientes con cuentas corrientes pendientes.")
                
        elif tipo_saldo == "Pago a Proveedor":
            # Filtramos deudas de proveedores y hacemos copia segura
            df_deudas = df_ventas[df_ventas['Estado_Pago_Prov'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            
            if not df_deudas.empty:
                
                st.write("📊 **Resumen: ¿Cuánto le debemos a cada proveedor?**")
                
                # Apuntamos a 'Compra $'
                col_precio = None
                for col in ['Compra $', 'Precio_Compra', 'Precio Compra', 'Costo']:
                    if col in df_deudas.columns:
                        col_precio = col
                        break
                        
                if col_precio:
                    col_vehiculo = 'Vehículo' if 'Vehículo' in df_deudas.columns else None
                    col_detalle = 'Detalle' if 'Detalle' in df_deudas.columns else None
                    
                    # Fusionamos Vehículo y Detalle
                    if col_vehiculo and col_detalle:
                        df_deudas['Resumen_Item'] = df_deudas[col_vehiculo].astype(str) + " (" + df_deudas[col_detalle].astype(str) + ")"
                        agg_col = 'Resumen_Item'
                    else:
                        agg_col = col_vehiculo or col_detalle
                        
                    if agg_col:
                        resumen_prov = df_deudas.groupby('Proveedor').agg({
                            col_precio: lambda x: pd.to_numeric(x, errors='coerce').sum(),
                            agg_col: lambda x: ' + '.join([str(i) for i in x if str(i).strip()])
                        }).reset_index()
                        resumen_prov.columns = ['Proveedor', 'Deuda Total ($)', 'Detalle de Repuestos']
                    else:
                        resumen_prov = df_deudas.groupby('Proveedor')[col_precio].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                        resumen_prov.columns = ['Proveedor', 'Deuda Total ($)']
                        
                    st.dataframe(resumen_prov, hide_index=True, use_container_width=True)
                else:
                    st.warning(f"⚠️ No encuentro la columna de pago. Las columnas leídas son: {', '.join(df_deudas.columns)}")
                st.divider()
                
                # MULTISELECT
                opciones = df_deudas['Fecha'].astype(str) + " | " + df_deudas['Proveedor'].astype(str) + " | " + df_deudas['Vehículo'].astype(str)
                seleccion = st.multiselect("Seleccioná los repuestos a pagar (podés elegir varios):", opciones.tolist())
                
                if st.button("💸 Registrar Pago(s)"):
                    if seleccion:
                        for sel in seleccion:
                            fecha_sel = sel.split(" | ")[0]
                            prov_sel = sel.split(" | ")[1]
                            saldar_deuda(fecha_sel, prov_sel, "Proveedor")
                        st.success(f"{len(seleccion)} pago(s) registrado(s). El Excel se actualizó a 'Pagado'.")
                        st.rerun()
                    else:
                        st.warning("Seleccioná al menos un repuesto para pagar.")
            else:
                st.info("No tenés cuentas corrientes pendientes con proveedores.")

    except Exception as e:
        st.error(f"Error general en cuentas corrientes: {e}")


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

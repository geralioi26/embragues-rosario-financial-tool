import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse
import re
import unicodedata

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
    
    # Mantenemos Más Pagos operativo para futura comparación de tasas
    MPAGOS_1 = a_numero(cfg["MASPAGOS_1_PAGO"])
    MPAGOS_3 = a_numero(cfg["MASPAGOS_3_CUOTAS"])
    MPAGOS_6 = a_numero(cfg["MASPAGOS_6_CUOTAS"])
    
    # NUEVO: LECTURA DEL DIVISOR PARA LINK DE PAGO GETNET
    # Si por algún motivo se borra del Excel, usa 0.9758 por defecto como mecanismo de seguridad.
    LINK_GETNET_DIVISOR = a_numero(cfg.get("LINK_GETNET_DIVISOR", 0.9758))

except Exception as e:
    st.error(f"🚨 ERROR TÉCNICO DETALLADO: {e}")
    st.error("Verificá la tabla de abajo. Así es exactamente como la aplicación está leyendo tu Excel. Si falta algún dato, ahí está la fuga.")
    try:
        st.dataframe(df_cfg) # Le pedimos que nos muestre en pantalla qué fue lo que leyó
    except:
        pass
    st.stop()


# ==========================================
# MÓDULO DE CÁLCULO: LINK DE PAGO (GETNET)
# ==========================================
def calcular_link_pago(precio_lista):
    """
    Calcula el monto base limpio para cargar en el Link de Pago Getnet.
    Absorbe exactamente el 2% de arancel y el 21% de IVA sobre ese arancel.
    Los intereses de las cuotas los aplica directamente la plataforma al cliente.
    """
    monto_base_link = precio_lista / LINK_GETNET_DIVISOR
    return round(monto_base_link, 2)
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
        
        if 'Vehiculo' not in df.columns: df['Vehiculo'] = ""
        
        marca_up = str(marca).upper()
        col_cod = f"Codigo_{marca_up}"
        col_pre = f"Precio_{marca_up}"
        
        if col_cod not in df.columns:
            df[col_cod] = ""
            df[col_pre] = ""

        vehiculo_limpio = str(vehiculo).strip()
        veh_l = vehiculo_limpio.lower()
        cod_limpio = str(codigo).split('.')[0].strip()
        
        # 1. Buscamos primero si el CÓDIGO ya existe en esta marca
        m_codigo = (df[col_cod].astype(str).str.strip() == cod_limpio) & (cod_limpio != "")
        
        if m_codigo.any():
            # EL CÓDIGO EXISTE: Actualizamos precio y agregamos vehículo si no está
            idx = df.index[m_codigo][0]
            veh_actual = str(df.at[idx, 'Vehiculo']).strip()
            
            if veh_l not in veh_actual.lower():
                if veh_actual == "" or veh_actual.lower() == "nan":
                    df.at[idx, 'Vehiculo'] = vehiculo_limpio
                else:
                    df.at[idx, 'Vehiculo'] = veh_actual + " / " + vehiculo_limpio
            
            df.at[idx, col_pre] = precio
            if motor: df.at[idx, "Motor"] = motor
            if proveedor: df.at[idx, "Proveedor"] = proveedor
            
        else:
            # 2. EL CÓDIGO NO EXISTE: Buscamos si el Vehículo ya tiene fila para inyectarle este código
            m_vehiculo = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l)
            
            if m_vehiculo.any():
                idx = df.index[m_vehiculo][0]
                df.at[idx, col_cod] = cod_limpio
                df.at[idx, col_pre] = precio
                if motor: df.at[idx, "Motor"] = motor
                if proveedor: df.at[idx, "Proveedor"] = proveedor
            else:
                # 3. NO EXISTE NADA: Creamos una fila totalmente nueva
                fila = {c: "" for c in df.columns}
                fila["Vehiculo"] = vehiculo_limpio
                fila["Motor"] = motor
                fila["Proveedor"] = proveedor
                fila[col_cod] = cod_limpio
                fila[col_pre] = precio
                df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
                
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        st.cache_data.clear()
        
        # --- BLINDAJE DEL BUSCADOR: Destruimos la memoria RAM vieja ---
        if "df_Catalogo_Kits" in st.session_state:
            del st.session_state["df_Catalogo_Kits"]
            
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

        vehiculo_limpio = str(vehiculo).strip()
        veh_l = vehiculo_limpio.lower()
        desc_l = str(descripcion).strip().lower()
        cod_limpio = str(codigo).strip()
        
        # 1. Buscamos primero si el CÓDIGO ya existe en esta marca
        m_codigo = (df[col_cod].astype(str).str.strip() == cod_limpio) & (cod_limpio != "")
        
        if m_codigo.any():
            # EL CÓDIGO EXISTE: Actualizamos precio y agregamos vehículo
            idx = df.index[m_codigo][0]
            veh_actual = str(df.at[idx, 'Vehiculo']).strip()
            
            if veh_l not in veh_actual.lower():
                if veh_actual == "" or veh_actual.lower() == "nan":
                    df.at[idx, 'Vehiculo'] = vehiculo_limpio
                else:
                    df.at[idx, 'Vehiculo'] = veh_actual + " / " + vehiculo_limpio
            
            df.at[idx, col_pre] = precio
            
        else:
            # 2. EL CÓDIGO NO EXISTE: Buscamos coincidencia exacta de Vehículo + Descripción
            m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                       (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
                       
            if m_exacto.any():
                idx = df.index[m_exacto][0]
                df.at[idx, col_cod] = cod_limpio
                df.at[idx, col_pre] = precio
            else:
                # 3. NO EXISTE NADA: Creamos fila nueva
                fila = {c: "" for c in df.columns}
                fila["Vehiculo"] = vehiculo_limpio
                fila["Descripcion"] = descripcion
                fila[col_cod] = cod_limpio
                fila[col_pre] = precio
                df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
                
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", data=df)
        st.cache_data.clear()
        
        # --- BLINDAJE DEL BUSCADOR: Destruimos la memoria RAM vieja ---
        if "df_Catalogo_Crapodinas" in st.session_state:
            del st.session_state["df_Catalogo_Crapodinas"]
            
    except Exception as e:
        st.error(f"Falla al guardar en Crapodinas: {e}")

# --- NUEVO: FUNCIÓN INTELIGENTE PARA LEER PRECIOS DEL INVENTARIO ---
def obtener_costo_stock(codigo):
    if not codigo or str(codigo).strip() == "":
        return 0
    try:
        df_stock = leer_fresca(SHEET_URL, "Inventario_Stock")
        filtro = df_stock['Código'].astype(str).str.strip() == str(codigo).strip()
        
        if filtro.any():
            indice = df_stock.index[filtro].tolist()[0]
            costo = df_stock.at[indice, 'Costo_Unitario']
            return float(pd.to_numeric(costo, errors='coerce'))
    except Exception:
        pass
    return 0
# ------------------------------------------------------------------

def descontar_stock(codigo, cantidad_a_restar):
    if not codigo or str(codigo).strip() == "":
        return
        
    try:
        st.cache_data.clear()
        df_stock = leer_fresca(SHEET_URL, "Inventario_Stock")
        
        filtro = df_stock['Código'].astype(str).str.strip() == str(codigo).strip()
        
        if filtro.any():
            indice = df_stock.index[filtro].tolist()[0]
            stock_actual = int(df_stock.at[indice, 'Cantidad'])
            
            nuevo_stock = stock_actual - cantidad_a_restar
            df_stock.at[indice, 'Cantidad'] = nuevo_stock
            
            conn.update(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", data=df_stock)
            st.cache_data.clear()
        else:
            st.warning(f"Atención: El repuesto código '{codigo}' no se encontró en el inventario.")
            
    except Exception as e:
        st.error(f"Error interno al descontar stock del código {codigo}: {e}")

def guardar_en_google(nro_trabajo, categoria, cliente, vehiculo, detalle, monto_bruto, monto_neto, costo, proveedor,
                      cod_kit, cod_crap, f_pago, e_cliente, e_prov, f_pago_prov,
                      m_forros, c_forros, costo_f, ganancia,
                      desc_kit, desc_crap, desc_forros, factura_texto): 
                      
    fecha_hoy = (pd.Timestamp.now() - pd.Timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    
    columnas = ["Fecha", "Nro_Trabajo", "Categoría", "Cliente", "Vehículo", "Detalle",
                "Venta $", "Compra $", "Proveedor", "Código", "Cod_Crapodina",
                "Forma_de_pago", "Estado_Cobro", "Estado_Pago_Prov", "Forma_Pago_Prov",
                "Marca_Forros", "Cod_Forros", "Costo_Forros", "Ganancia", "Monto Neto Esperado", "Facturado"]
                
    try:
        df_existente = leer_fresca(SHEET_URL, "Ventas")
    except Exception as e:
        st.error(f"Error al leer Ventas: {e}")
        st.stop()
        
    nueva = pd.DataFrame([[fecha_hoy, nro_trabajo, categoria, cliente, vehiculo, detalle,
                           monto_bruto, costo, proveedor, cod_kit, cod_crap,
                           f_pago, e_cliente, e_prov, f_pago_prov,
                           m_forros, c_forros, costo_f, ganancia, monto_neto, factura_texto]],
                         columns=columnas)
                         
    df_nuevo = pd.concat([df_existente, nueva], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_nuevo)
    leer_hoja.clear()

    # --- DESCUENTO DE STOCK FÍSICO ---
    if desc_forros and c_forros and str(c_forros).strip() != "":
        if "|" in str(c_forros):
            codigos = str(c_forros).split("|")
            descontar_stock(codigos[0].strip(), 1)
            descontar_stock(codigos[1].strip(), 1)
        else:
            descontar_stock(str(c_forros).strip(), 2)
            
    if desc_kit and cod_kit and str(cod_kit).strip() != "":
        descontar_stock(str(cod_kit).strip(), 1)
        
    if desc_crap and cod_crap and str(cod_crap).strip() != "":
        descontar_stock(str(cod_crap).strip(), 1)

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

m_kit = m_forros = forros_codigo = crap_codigo = tipo_crap = codigo_manual = cod_kit_final = cod_crap_final = ""
forros_costo = crap_costo = precio_compra = 0
m_crap = []
desc_kit = desc_crap = desc_forros = False

tipo_item = st.sidebar.selectbox("Tipo de Trabajo:",
    ["Embrague Nuevo (Venta)", "Reparación de Embrague", "Rectificación de Volante", "Kit de Distribución", "Repuesto Suelto", "Otro"], key=f"tipo_{fk}")

if "Nuevo" in tipo_item:
    cat_f, icono, incl_rectif = "Venta", "⚙️", False
    m_kit = st.sidebar.selectbox("Marca del Kit:", ["LUK","SACHS","VALEO","PHC_VALEO","ORIGINAL","OTRA"], key=f"mkit_{fk}")
    sugerencia = f"KIT nuevo marca *{m_kit}*"
    
elif "Reparación" in tipo_item:
    cat_f, icono, incl_rectif = "Reparación", "🔧", True
    
    # --- BLOQUE CRAPODINA AUTOMATIZADO ---
    m_crap = st.sidebar.multiselect("Marcas de Crapodina:", ["Luk","Skf","Ina","Dbh","The"], default=["Luk","Skf"], key=f"mcrap_{fk}")
    tipo_crap = st.sidebar.selectbox("⚙️ Tipo de Crapodina:", ["Hidráulica","Mecánica"], key=f"tipocrap_{fk}")
    crap_codigo = st.sidebar.text_input("Código de Crapodina:", "", key=f"crapcod_{fk}")
    
    costo_crap_auto = 0
    if crap_codigo:
        desc_crap = st.sidebar.checkbox("📉 Descontar Crapodina del Stock", value=False, key=f"desc_crap_{fk}")
        if desc_crap:
            costo_crap_auto = obtener_costo_stock(crap_codigo)
            
    crap_costo = st.sidebar.number_input("Costo de Crapodina ($):", min_value=0, value=int(costo_crap_auto), key=f"crapcost_{fk}")
    if desc_crap and costo_crap_auto > 0:
        st.sidebar.success(f"✔️ Costo extraído del Stock: ${costo_crap_auto:,.0f}")
    
    # --- BLOQUE FORROS AUTOMATIZADO ---
    m_forros = st.sidebar.selectbox("Marca de Forros:", ["IAR Metal","Fras-le","Termolite","Otro"], key=f"mforro_{fk}")
    forros_combinados = st.sidebar.checkbox("¿Forros combinados (distinto espesor)?", key=f"fcomb_{fk}")
    
    cod1 = cod2 = ""
    if forros_combinados:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            cod1 = st.sidebar.text_input("Código 1:", key=f"fcod1_{fk}")
        with col2:
            cod2 = st.sidebar.text_input("Código 2:", key=f"fcod2_{fk}")
        forros_codigo = f"{cod1} | {cod2}" if cod1 and cod2 else ""
    else:
        forros_codigo = st.sidebar.text_input("Código de Forros (2 iguales):", "", key=f"forrocod_{fk}")
        
    costo_forros_auto = 0
    if forros_codigo:
        desc_forros = st.sidebar.checkbox("📉 Descontar Forros del Stock", value=False, key=f"desc_forros_{fk}")
        if desc_forros:
            if forros_combinados:
                costo_forros_auto = obtener_costo_stock(cod1) + obtener_costo_stock(cod2)
            else:
                costo_forros_auto = obtener_costo_stock(forros_codigo) * 2
                
    forros_costo = st.sidebar.number_input("Costo Total de Forros ($):", min_value=0, value=int(costo_forros_auto), key=f"forrocost_{fk}")
    if desc_forros and costo_forros_auto > 0:
        st.sidebar.success(f"✔️ Costo extraído del Stock: ${costo_forros_auto:,.0f}")
        
    m_neg = [f"*{m}*" for m in m_crap]
    t_m = (", ".join(m_neg[:-1]) + " o " + m_neg[-1]) if len(m_neg) > 1 else (m_neg[0] if m_neg else "*primera marca*")
    sugerencia = f"reparado completo placa disco con forros originales volante rectificado y balanceado con crapodina {t_m}"

elif "Rectificación" in tipo_item:
    cat_f, icono, incl_rectif = "Rectificación", "⚙️", True
    sugerencia = "Rectificación de volante"

elif "Distribución" in tipo_item:
    cat_f, icono, incl_rectif = "Venta", "🛠️", False
    sugerencia = "KIT de distribución"

elif "Repuesto Suelto" in tipo_item:
    cat_f, icono, incl_rectif = "Repuesto Suelto", "📦", False
    detalle_suelto = st.sidebar.text_input("Detalle (Ej: Volante Bimasa Tiida):", key=f"detsuelto_{fk}")
    marca_suelta = st.sidebar.text_input("Marca:", key=f"msuelta_{fk}")
    sugerencia = f"{detalle_suelto} marca {marca_suelta}".strip()
    
else:
    cat_f, icono, incl_rectif = "Otro", "📝", False
    sugerencia = "Venta / Reparación"

# --- CAMPOS GENERALES ---
if tipo_item != "Rectificación de Volante":
    nro_trabajo_input = st.sidebar.text_input("Nro. de Trabajo (Ej: 168):", value="", key=f"nrotrabajo_{fk}")
else:
    nro_trabajo_input = ""

monto_limpio = st.sidebar.number_input("Precio de VENTA ($):", min_value=0, value=0, key=f"montolimpio_{fk}")

# --- NUEVO: CONTROL DE FACTURACIÓN (TERMÓMETRO) ---
con_factura = st.sidebar.checkbox("🧾 Con Factura (Suma a Categoría C)", value=False, key=f"factura_{fk}")
# --------------------------------------------------

vehiculo_input = st.sidebar.text_input("Vehículo:", value="", key=f"vehiculo_{fk}")
motor_input = st.sidebar.text_input("Motor:", value="", key=f"motor_{fk}")

if tipo_item != "Rectificación de Volante":
    proveedor_input = st.sidebar.text_input("Proveedor:", value="", key=f"proveedor_{fk}")
else:
    proveedor_input = "Taller Propio"

if tipo_item == "Rectificación de Volante":
    detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Rectificación volante", key=f"detalle_{fk}")
elif "Repuesto Suelto" in tipo_item:
    detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Venta Repuesto Suelto", key=f"detalle_{fk}")
else:
    detalle_excel = st.sidebar.text_input("📝 Detalle para Excel:", value="Venta / Reparación", key=f"detalle_{fk}")
    
cliente_input = st.sidebar.text_input("Nombre del Cliente:", value="", key=f"cliente_{fk}")
detalle_final = st.sidebar.text_area("💬 Detalle en WhatsApp:", value=sugerencia, key=f"detwhats_{fk}")

st.sidebar.divider()
st.sidebar.write("📸 **Uso Interno**")

# --- LÓGICA DE COSTOS Y STOCK INTEGRADA AUTOMATIZADA ---
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
    
    costo_kit_auto = 0
    if codigo_manual:
        desc_kit = st.sidebar.checkbox("📉 Descontar Repuesto del Stock", value=False, key=f"desc_kit_{fk}")
        if desc_kit:
            costo_kit_auto = obtener_costo_stock(codigo_manual)
            
    precio_compra_input = st.sidebar.number_input("Precio de COMPRA ($):", min_value=0, value=int(costo_kit_auto), key=f"precomp_{fk}")
    
    if desc_kit and costo_kit_auto > 0:
        precio_compra = costo_kit_auto # Forzamos a que use el costo del stock real para la ganancia
        st.sidebar.success(f"✔️ Costo extraído del Stock: ${costo_kit_auto:,.0f}")
    else:
        precio_compra = precio_compra_input

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
    elif "Link" in f_pago_input: 
        monto_bruto = int(calcular_link_pago(monto_limpio))
    elif f_pago_input == "Getnet - 1 Pago": monto_bruto = int(round(monto_limpio * GETNET_1))
    elif f_pago_input == "Getnet - 3 Cuotas": monto_bruto = int(round(monto_limpio * GETNET_3))
    elif f_pago_input == "Getnet - 6 Cuotas": monto_bruto = int(round(monto_limpio * GETNET_6))
    elif f_pago_input == "Más Pagos - 1 Pago": monto_bruto = int(round(monto_limpio * MPAGOS_1))
    elif f_pago_input == "Más Pagos - 3 Cuotas": monto_bruto = int(round(monto_limpio * MPAGOS_3))
    elif f_pago_input == "Más Pagos - 6 Cuotas": monto_bruto = int(round(monto_limpio * MPAGOS_6))
    
    # Transformamos el tilde en un SI o NO para el Excel
    factura_texto = "SI" if con_factura else "NO"
    
    guardar_en_google(nro_trabajo_input, cat_f, cliente_input, vehiculo_input, detalle_excel,
              monto_bruto, monto_neto_guardar, precio_compra, proveedor_input,
              cod_kit_final, cod_crap_final, f_pago_input,
              estado_cliente, estado_p_prov,
              "", 
              m_forros, forros_codigo, forros_costo, ganancia,
              desc_kit, desc_crap, desc_forros, factura_texto)
                      
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
    
    # Matemática quirúrgica: Conectada a la función global (extrae el divisor directo del Excel)
    monto_link = calcular_link_pago(monto_limpio)
    
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
        # --- DASHBOARD DE GANANCIAS Y GASTOS (RENTA NETA) ---
        with st.expander("📊 Tablero de Finanzas (Mes a Mes)"):
            import pandas as pd
            import datetime
            import calendar 
            
            # 1. Preparamos los datos de VENTAS
            df_dash = df_ver.copy()
            df_dash['Fecha'] = pd.to_datetime(df_dash['Fecha'], dayfirst=True, errors='coerce')
            df_dash['Ganancia'] = pd.to_numeric(df_dash['Ganancia'], errors='coerce').fillna(0)
            df_dash['Venta $'] = pd.to_numeric(df_dash['Venta $'], errors='coerce').fillna(0)
            df_dash['Compra $'] = pd.to_numeric(df_dash['Compra $'], errors='coerce').fillna(0)
            
            # 2. Preparamos los datos de GASTOS leyendo directo de la base
            try:
                df_gastos = leer_hoja(SHEET_URL, "Gastos").copy()
                df_gastos['Fecha'] = pd.to_datetime(df_gastos['Fecha'], dayfirst=True, errors='coerce')
                df_gastos['Monto $'] = pd.to_numeric(df_gastos['Monto $'], errors='coerce').fillna(0)
            except Exception:
                df_gastos = pd.DataFrame(columns=['Fecha', 'Clasificacion', 'Monto $'])
            
            # --- NUEVO FILTRO DE MESES ---
            meses_nombres = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
            
            if not df_gastos.empty:
                fechas_totales = pd.concat([df_dash['Fecha'], df_gastos['Fecha']]).dropna()
            else:
                fechas_totales = df_dash['Fecha'].dropna()
                
            hoy = (datetime.datetime.now() - datetime.timedelta(hours=3)).date()
            
            if not fechas_totales.empty:
                # --- ACÁ ESTÁ LA SOLUCIÓN AL ERROR ---
                # Lo convertimos a Serie de Pandas para que permita usar sort_values sin chillar
                periodos = pd.Series(fechas_totales.dt.to_period('M').unique()).sort_values(ascending=False)
                opciones_periodos = [f"{meses_nombres[p.month]} {p.year}" for p in periodos]
                valores_periodos = [(p.month, p.year) for p in periodos]
            else:
                opciones_periodos = [f"{meses_nombres[hoy.month]} {hoy.year}"]
                valores_periodos = [(hoy.month, hoy.year)]
            
            st.markdown("### 🗓️ Filtrar periodo")
            periodo_sel_str = st.selectbox("Seleccionar Mes a visualizar:", opciones_periodos)
            idx_sel = opciones_periodos.index(periodo_sel_str)
            mes_actual, anio_actual = valores_periodos[idx_sel] 
            # -----------------------------
            
            # 3. Calculamos tiempos del mes pasado 
            if mes_actual == 1:
                mes_pasado = 12
                anio_pasado = anio_actual - 1
            else:
                mes_pasado = mes_actual - 1
                anio_pasado = anio_actual
                
            # 4. Filtramos Ventas por el mes SELECCIONADO
            df_mes_actual = df_dash[(df_dash['Fecha'].dt.month == mes_actual) & (df_dash['Fecha'].dt.year == anio_actual)]
            df_mes_pasado = df_dash[(df_dash['Fecha'].dt.month == mes_pasado) & (df_dash['Fecha'].dt.year == anio_pasado)]
            
            # 5. Filtramos Gastos por mes y separamos los Operativos
            if not df_gastos.empty:
                gastos_actuales = df_gastos[(df_gastos['Fecha'].dt.month == mes_actual) & (df_gastos['Fecha'].dt.year == anio_actual)]
                gastos_pasados = df_gastos[(df_gastos['Fecha'].dt.month == mes_pasado) & (df_gastos['Fecha'].dt.year == anio_pasado)]
                
                op_actuales = gastos_actuales[gastos_actuales['Clasificacion'].astype(str).str.strip() == "Gasto Operativo"]['Monto $'].sum()
                op_pasados = gastos_pasados[gastos_pasados['Clasificacion'].astype(str).str.strip() == "Gasto Operativo"]['Monto $'].sum()
            else:
                op_actuales = 0
                op_pasados = 0
            
            # --- MATEMÁTICA FINANCIERA ---
            ganancia_bruta_actual = df_mes_actual['Ganancia'].sum()
            ganancia_bruta_pasada = df_mes_pasado['Ganancia'].sum()
            
            neta_actual = ganancia_bruta_actual - op_actuales
            neta_pasada = ganancia_bruta_pasada - op_pasados
            diferencia_neta = neta_actual - neta_pasada
            
            # Cuentas Corrientes
            df_cobrar = df_dash[df_dash['Estado_Cobro'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            plata_en_calle_bruta = df_cobrar['Venta $'].sum()
            
            # --- NUEVO: RESTAMOS LOS CANJES AL TOTAL EN LA CALLE ---
            try:
                df_saldos_metric = leer_fresca(SHEET_URL, "Saldos_y_Canjes")
                if not df_saldos_metric.empty:
                    total_canjes = pd.to_numeric(df_saldos_metric['Monto a Favor'], errors='coerce').sum()
                else:
                    total_canjes = 0
            except:
                total_canjes = 0
                
            plata_en_calle = plata_en_calle_bruta - total_canjes
            # -------------------------------------------------------
            
            df_pagar = df_dash[df_dash['Estado_Pago_Prov'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            deuda_diaria = df_pagar['Compra $'].sum()
            
            if not df_gastos.empty:
                gastos_deuda = df_gastos[df_gastos['Estado_Pago'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
                deuda_stock = gastos_deuda['Monto $'].sum()
            else:
                deuda_stock = 0
                
            deuda_prov = deuda_diaria + deuda_stock
            
            # --- CÁLCULO DE CAPITAL INMOVILIZADO (STOCK) ---
            try:
                df_stock = leer_fresca(SHEET_URL, "Inventario_Stock")
                df_stock['Cantidad'] = pd.to_numeric(df_stock['Cantidad'], errors='coerce').fillna(0)
                df_stock['Costo_Unitario'] = pd.to_numeric(df_stock['Costo_Unitario'], errors='coerce').fillna(0)
                
                capital_inmovilizado = (df_stock['Cantidad'] * df_stock['Costo_Unitario']).sum()
            except Exception:
                capital_inmovilizado = 0

            # --- RENDERIZADO DEL TABLERO ---
            st.markdown("**💰 Radiografía Financiera (Realidad del Mes)**")
            
            c1, c2 = st.columns(2)
            with c1:
                st.metric(label="💵 Ganancia NETA (Bolsillo)", value=f"${neta_actual:,.0f}", delta=f"${diferencia_neta:,.0f} vs Mes Pasado")
            with c2:
                st.metric(label="📉 Gastos Operativos", value=f"${op_actuales:,.0f}", delta=f"Ganancia Bruta: ${ganancia_bruta_actual:,.0f}", delta_color="off")
            
            st.divider()
            
            st.markdown("**📦 Patrimonio y Flujo de Capital**")
            c3, c4, c5 = st.columns(3)
            with c3:
                st.metric(label="🧱 Capital Inmovilizado (Stock)", value=f"${capital_inmovilizado:,.0f}", delta="Valor de costo en taller", delta_color="off")
            with c4:
                st.metric(label="⏳ En la Calle (A Cobrar)", value=f"${plata_en_calle:,.0f}", delta="Fiado a clientes", delta_color="off")
            with c5:
                st.metric(label="⚠️ Deuda a Prov. (A Pagar)", value=f"${deuda_prov:,.0f}", delta="Cuentas pendientes", delta_color="off")
            
            # --- DETALLE DE DEUDORES Y ACREEDORES ---
            st.markdown("---")
            col_det_1, col_det_2 = st.columns(2)
            
            with col_det_1:
                st.markdown("**🎯 ¿Quién me debe?**")
                if not df_cobrar.empty:
                    temp_cobrar = df_cobrar.copy()
                    temp_cobrar['Cliente'] = temp_cobrar['Cliente'].astype(str).str.strip().str.upper()
                    
                    # 1. Calculamos la deuda bruta de Ventas
                    detalle_clientes = temp_cobrar.groupby('Cliente')['Venta $'].sum().reset_index()
                    
                    # 2. Leemos los canjes y los restamos para mostrar la deuda REAL
                    try:
                        df_saldos_dash = leer_fresca(SHEET_URL, "Saldos_y_Canjes")
                        if not df_saldos_dash.empty:
                            df_saldos_dash['Cliente'] = df_saldos_dash['Cliente'].astype(str).str.strip().str.upper()
                            saldos_agrupados = df_saldos_dash.groupby('Cliente')['Monto a Favor'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                            
                            # Cruzamos los datos
                            detalle_clientes = pd.merge(detalle_clientes, saldos_agrupados, on='Cliente', how='left').fillna(0)
                            # Restamos
                            detalle_clientes['Venta $'] = detalle_clientes['Venta $'] - detalle_clientes['Monto a Favor']
                            # Limpiamos la columna extra
                            detalle_clientes = detalle_clientes.drop(columns=['Monto a Favor'])
                    except:
                        pass
                    
                    # Filtramos a los que ya quedaron en cero
                    detalle_clientes = detalle_clientes[detalle_clientes['Venta $'] > 0]
                    
                    if not detalle_clientes.empty:
                        st.dataframe(detalle_clientes.style.format({'Venta $': '${:,.0f}'}), hide_index=True, use_container_width=True)
                    else:
                        st.success("Nadie te debe plata. ¡Excelente!")
                else:
                    st.success("Nadie te debe plata. ¡Excelente!")
                    
            with col_det_2:
                st.markdown("**🏭 ¿A quién le debo?**")
                
                deudas_diarias = pd.DataFrame()
                if not df_pagar.empty:
                    deudas_diarias = df_pagar[['Proveedor', 'Compra $']].rename(columns={'Compra $': 'Monto'})
                
                deudas_stock = pd.DataFrame()
                if not df_gastos.empty:
                    gastos_deuda = df_gastos[df_gastos['Estado_Pago'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
                    if not gastos_deuda.empty:
                        deudas_stock = gastos_deuda[['Proveedor', 'Monto $']].rename(columns={'Monto $': 'Monto'})
                
                df_deuda_total = pd.concat([deudas_diarias, deudas_stock]).dropna()
                
                if not df_deuda_total.empty:
                    df_deuda_total['Proveedor'] = df_deuda_total['Proveedor'].astype(str).str.strip().str.upper()
                    
                    detalle_prov = df_deuda_total.groupby('Proveedor')['Monto'].sum().reset_index()
                    detalle_prov = detalle_prov[detalle_prov['Monto'] > 0]
                    
                    if not detalle_prov.empty:
                        st.dataframe(detalle_prov.style.format({'Monto': '${:,.0f}'}), hide_index=True, use_container_width=True)
                    else:
                        st.success("No le debés a ningún proveedor.")
                else:
                    st.success("No le debés a ningún proveedor.")

            st.markdown("---")
                
            # --- GRÁFICO DE EVOLUCIÓN ---
            st.markdown(f"**Evolución Diaria de Ganancias ({periodo_sel_str})**")
            if not df_mes_actual.empty:
                grafico_datos = df_mes_actual.groupby(df_mes_actual['Fecha'].dt.date)['Ganancia'].sum()
                
                _, ultimo_dia = calendar.monthrange(anio_actual, mes_actual)
                
                if mes_actual == hoy.month and anio_actual == hoy.year:
                    fin_grafico = hoy
                else:
                    fin_grafico = datetime.date(anio_actual, mes_actual, ultimo_dia)
                    
                rango_fechas = pd.date_range(start=datetime.date(anio_actual, mes_actual, 1), end=fin_grafico).date
                grafico_datos = grafico_datos.reindex(rango_fechas, fill_value=0)
                
                grafico_datos.index = [f"{d.day:02d}/{d.month:02d}" for d in grafico_datos.index]
                
                st.bar_chart(grafico_datos)
            else:
                st.info(f"No hay ventas registradas en {periodo_sel_str} para graficar.")
                
        # --- HISTORIAL ---
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
        
        try:
            df_saldos = leer_fresca(SHEET_URL, "Saldos_y_Canjes")
        except:
            df_saldos = pd.DataFrame(columns=["Fecha", "Cliente", "Detalle", "Monto a Favor"])

        # ==========================================
        # OPCIÓN 1: COBRO A CLIENTES Y CANJES
        # ==========================================
        if tipo_saldo == "Cobro a Cliente":
            df_deudas = df_ventas[df_ventas['Estado_Cobro'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            
            st.write("📊 **Resumen: ¿Cuánto nos debe cada cliente REALMENTE?**")
            
            df_deudas['Cliente'] = df_deudas['Cliente'].astype(str).str.strip().str.upper()
            if not df_deudas.empty:
                resumen_deudas = df_deudas.groupby('Cliente')['Venta $'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                resumen_deudas.columns = ['Cliente', 'Deuda por Trabajos ($)']
            else:
                resumen_deudas = pd.DataFrame(columns=['Cliente', 'Deuda por Trabajos ($)'])
            
            if not df_saldos.empty:
                df_saldos['Cliente'] = df_saldos['Cliente'].astype(str).str.strip().str.upper()
                resumen_a_favor = df_saldos.groupby('Cliente')['Monto a Favor'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                resumen_a_favor.columns = ['Cliente', 'Saldo a Favor ($)']
            else:
                resumen_a_favor = pd.DataFrame(columns=['Cliente', 'Saldo a Favor ($)'])
            
            if not resumen_deudas.empty or not resumen_a_favor.empty:
                resumen_total = pd.merge(resumen_deudas, resumen_a_favor, on='Cliente', how='outer').fillna(0)
                resumen_total['DEUDA REAL FINAL ($)'] = resumen_total['Deuda por Trabajos ($)'] - resumen_total['Saldo a Favor ($)']
                
                resumen_total = resumen_total[resumen_total['DEUDA REAL FINAL ($)'] != 0]
                
                st.dataframe(resumen_total.style.format({
                    'Deuda por Trabajos ($)': '${:,.0f}', 
                    'Saldo a Favor ($)': '${:,.0f}', 
                    'DEUDA REAL FINAL ($)': '${:,.0f}'
                }), hide_index=True)
            else:
                st.success("✅ No hay deudas registradas ni saldos a favor.")
            
            st.divider()
            
            if not df_deudas.empty:
                st.write("📝 **Desglose de trabajos pendientes (Para cobrar sueltos):**")
                cols_mostrar = ['Fecha', 'Cliente', 'Vehículo', 'Detalle', 'Venta $']
                cols_finales = [c for c in cols_mostrar if c in df_deudas.columns]
                
                df_detalle = df_deudas[cols_finales].copy()
                df_detalle['Venta $'] = pd.to_numeric(df_detalle['Venta $'], errors='coerce').fillna(0)
                st.dataframe(df_detalle.style.format({'Venta $': '${:,.0f}'}), hide_index=True, use_container_width=True)
                
                opciones = df_deudas['Fecha'].astype(str) + " | " + df_deudas['Cliente'].astype(str) + " | " + df_deudas['Vehículo'].astype(str)
                seleccion = st.multiselect("Seleccioná la o las deudas a procesar:", opciones.tolist())
                
                forma_cobro = st.selectbox("¿Cómo saldamos esto?", ["Efectivo", "Transferencia", "Débito", "Otro"])
                
                if st.button("💰 Procesar Cobro"):
                    if seleccion:
                        try:
                            df_ventas_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
                            
                            for sel in seleccion:
                                fecha_sel = sel.split(" | ")[0]
                                cliente_sel = sel.split(" | ")[1]
                                vehiculo_sel = sel.split(" | ")[2]
                                
                                mascara = (df_ventas_actual['Fecha'].astype(str) == fecha_sel) & \
                                          (df_ventas_actual['Cliente'].astype(str).str.strip().str.upper() == cliente_sel.upper()) & \
                                          (df_ventas_actual['Vehículo'].astype(str) == vehiculo_sel)
                                
                                df_ventas_actual.loc[mascara, 'Estado_Cobro'] = 'Pagado'
                                df_ventas_actual.loc[mascara, 'Forma_de_pago'] = forma_cobro
                                
                            conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_ventas_actual)
                            st.cache_data.clear()
                            st.success(f"✅ {len(seleccion)} cobro(s) registrado(s) en {forma_cobro}. Excel actualizado.")
                                
                        except Exception as e:
                            st.error(f"⚠️ Error al actualizar cobros: {e}")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para procesar.")

            # ==========================================
            # --- PANEL DE AJUSTES MANUALES Y FIFO ---
            # ==========================================
            st.markdown("---")
            st.markdown("### 🔄 Entregas a Cuenta y Ajustes Manuales")
            st.info("Anotá entregas de plata a cuenta. Después usá el botón azul para que el sistema cancele boletas viejas automáticamente.")
            
            lista_clientes = resumen_total['Cliente'].tolist() if 'resumen_total' in locals() and not resumen_total.empty else []
            if "REPUESTOS ARIEL" not in lista_clientes:
                lista_clientes.append("REPUESTOS ARIEL")
                
            with st.form("form_canje", clear_on_submit=True):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    fecha_canje = st.date_input("Fecha del Movimiento", format="DD/MM/YYYY")
                    cliente_canje = st.selectbox("¿A qué cliente le ajustamos la cuenta?", lista_clientes)
                    tipo_movimiento = st.radio("Acción a realizar:", [
                        "Suma a Favor (Entregó Plata a cuenta o Mercadería)", 
                        "Restar del Saldo (Ajuste o compensación manual)"
                    ])
                with col_c2:
                    monto_canje = st.number_input("Monto ($)", min_value=0, step=1000)
                    detalle_canje = st.text_input("Detalle (Ej: $55.000 a cuenta, Ajuste manual)")
                    
                    # --- NUEVA CASILLA PARA AFIP ---
                    facturar_ingreso = st.checkbox("🧾 Declarar este ingreso (Suma a Categoría C)")
                
                submit_canje = st.form_submit_button("🔄 Registrar Movimiento en Cuenta")
                
                if submit_canje:
                    if monto_canje > 0 and detalle_canje != "":
                        try:
                            monto_final = monto_canje if "Suma" in tipo_movimiento else -abs(monto_canje)
                            
                            # Filtro de seguridad: Solo es "SI" si entra plata y tildaste la caja
                            es_facturado = "SI" if facturar_ingreso and "Suma" in tipo_movimiento else "NO"
                            
                            df_saldos_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", ttl=0)
                            
                            nueva_fila = pd.DataFrame([{
                                "Fecha": fecha_canje.strftime("%d/%m/%Y"),
                                "Cliente": cliente_canje,
                                "Detalle": detalle_canje,
                                "Monto a Favor": monto_final,
                                "Facturado": es_facturado
                            }])
                            
                            if df_saldos_actual.empty or len(df_saldos_actual.columns) == 0:
                                df_actualizado = nueva_fila
                            else:
                                df_actualizado = pd.concat([df_saldos_actual, nueva_fila], ignore_index=True)
                            
                            conn.update(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", data=df_actualizado)
                            st.cache_data.clear()
                            
                            if "Suma" in tipo_movimiento:
                                st.success(f"✅ ¡Guardado! Se agregaron ${monto_canje:,.0f} a favor de {cliente_canje}.")
                            else:
                                st.success(f"✅ ¡Ajuste aplicado! Se restaron ${monto_canje:,.0f} del saldo de {cliente_canje}.")
                        except Exception as e:
                            st.error(f"⚠️ Error al guardar el ajuste: {e}")
                    else:
                        st.warning("⚠️ Ingresá un monto mayor a $0 y detallá de qué se trata.")

            # --- BOTÓN INTELIGENTE (FIFO) ---
            st.markdown("#### 🤖 Liquidación Automática de Boletas")
            cliente_fifo = st.selectbox("Seleccionar cliente para liquidar boletas con su Saldo a Favor:", lista_clientes, key="cliente_fifo")
            
            if st.button(f"⚡ Liquidar Trabajos Viejos de {cliente_fifo} usando su Saldo", type="primary"):
                try:
                    df_v = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
                    df_s = conn.read(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", ttl=0)
                    
                    # 1. Chequeamos si el cliente tiene saldo a favor
                    saldo_disp = 0
                    if not df_s.empty:
                        mask_s = df_s['Cliente'].astype(str).str.strip().str.upper() == cliente_fifo.upper()
                        saldo_disp = pd.to_numeric(df_s.loc[mask_s, 'Monto a Favor'], errors='coerce').sum()
                        
                    if saldo_disp <= 0:
                        st.warning(f"⚠️ {cliente_fifo} no tiene Saldo a Favor disponible para compensar boletas.")
                    else:
                        # 2. Agarramos los trabajos pendientes del cliente
                        mask_v = (df_v['Cliente'].astype(str).str.strip().str.upper() == cliente_fifo.upper()) & \
                                 (df_v['Estado_Cobro'].astype(str).str.strip().str.lower() == "cuenta corriente")
                        
                        trabajos_pendientes = df_v[mask_v].copy()
                        
                        if trabajos_pendientes.empty:
                            st.info(f"✅ {cliente_fifo} no tiene trabajos en Cuenta Corriente para pagar.")
                        else:
                            # Aseguramos que la columna de plata sea un número
                            trabajos_pendientes['Venta $'] = pd.to_numeric(trabajos_pendientes['Venta $'], errors='coerce').fillna(0)
                            
                            saldo_usado = 0
                            boletas_pagadas = 0
                            
                            # 3. Empieza la magia (lee desde arriba hacia abajo, o sea desde el más viejo)
                            for idx, row in trabajos_pendientes.iterrows():
                                costo_trabajo = row['Venta $']
                                
                                if costo_trabajo > 0 and saldo_disp >= costo_trabajo:
                                    # Alcanza la plata: Pagamos la boleta
                                    df_v.at[idx, 'Estado_Cobro'] = 'Pagado'
                                    df_v.at[idx, 'Forma_de_pago'] = 'Compensado con Saldo'
                                    saldo_disp -= costo_trabajo
                                    saldo_usado += costo_trabajo
                                    boletas_pagadas += 1
                                else:
                                    # No alcanza para cubrir ESTA boleta entera, frena la máquina.
                                    break
                                    
                            if boletas_pagadas > 0:
                                # Guardamos los cambios en Ventas
                                conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_v)
                                
                                # Anotamos la resta en la hoja de Saldos para que cuadre
                                nueva_resta = pd.DataFrame([{
                                    "Fecha": pd.Timestamp.now().strftime("%d/%m/%Y"),
                                    "Cliente": cliente_fifo,
                                    "Detalle": f"Liquidación automática de {boletas_pagadas} boleta(s)",
                                    "Monto a Favor": -abs(saldo_usado)
                                }])
                                df_s_actualizado = pd.concat([df_s, nueva_resta], ignore_index=True)
                                conn.update(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", data=df_s_actualizado)
                                
                                st.cache_data.clear()
                                st.success(f"🔥 ¡Éxito! El sistema liquidó automáticamente {boletas_pagadas} boleta(s) viejas usando ${saldo_usado:,.0f} del saldo a favor de {cliente_fifo}.")
                                
                                import time
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning(f"⚠️ El saldo a favor de {cliente_fifo} (${saldo_disp:,.0f}) no alcanza para cubrir la totalidad de su boleta más vieja.")
                
                except Exception as e:
                    st.error(f"⚠️ Fallo crítico en la automatización: {e}")

        # ==========================================
        # OPCIÓN 2: PAGO A PROVEEDORES (UNIFICADO VENTAS + GASTOS)
        # ==========================================
        elif tipo_saldo == "Pago a Proveedor":
            # 1. Buscamos deudas en VENTAS
            df_deudas_ventas = df_ventas[df_ventas['Estado_Pago_Prov'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            if not df_deudas_ventas.empty:
                df_deudas_ventas['Origen'] = 'Ventas'
                df_deudas_ventas['Monto_Deuda'] = pd.to_numeric(df_deudas_ventas['Compra $'], errors='coerce').fillna(0)
                df_deudas_ventas['Vehículo'] = df_deudas_ventas['Vehículo'].astype(str)
            else:
                df_deudas_ventas = pd.DataFrame()

            # 2. Buscamos deudas en GASTOS
            try:
                df_gastos = leer_fresca(SHEET_URL, "Gastos")
                df_deudas_gastos = df_gastos[df_gastos['Estado_Pago'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
                if not df_deudas_gastos.empty:
                    df_deudas_gastos['Origen'] = 'Gastos'
                    df_deudas_gastos['Monto_Deuda'] = pd.to_numeric(df_deudas_gastos['Monto $'], errors='coerce').fillna(0)
                    df_deudas_gastos['Vehículo'] = "N/A (Stock/Inversión)" # Gastos no tiene vehículo, rellenamos
                else:
                    df_deudas_gastos = pd.DataFrame()
            except:
                df_deudas_gastos = pd.DataFrame()

            # 3. Unificamos las dos tablas
            if not df_deudas_ventas.empty or not df_deudas_gastos.empty:
                df_deudas_prov = pd.concat([df_deudas_ventas, df_deudas_gastos], ignore_index=True)
            else:
                df_deudas_prov = pd.DataFrame()

            if not df_deudas_prov.empty:
                st.write("📊 **Resumen: ¿Cuánto le debemos a cada proveedor en total? (Ventas + Gastos)**")
                
                df_deudas_prov['Proveedor'] = df_deudas_prov['Proveedor'].astype(str).str.strip().str.upper()
                
                resumen_totales_prov = df_deudas_prov.groupby('Proveedor')['Monto_Deuda'].sum().reset_index()
                resumen_totales_prov.columns = ['Proveedor', 'Deuda Total ($)']
                st.dataframe(resumen_totales_prov.style.format({'Deuda Total ($)': '${:,.0f}'}), hide_index=True)
                
                st.write("📝 **Desglose exacto de las compras pendientes:**")
                cols_mostrar = ['Origen', 'Fecha', 'Proveedor', 'Vehículo', 'Detalle', 'Monto_Deuda']
                df_detalle_prov = df_deudas_prov[cols_mostrar].copy()
                st.dataframe(df_detalle_prov.style.format({'Monto_Deuda': '${:,.0f}'}), hide_index=True, use_container_width=True)
                
                st.divider()
                
                opciones_prov = df_deudas_prov['Fecha'].astype(str) + " | " + df_deudas_prov['Proveedor'].astype(str) + " | " + df_deudas_prov['Vehículo'].astype(str) + " | " + df_deudas_prov['Origen'].astype(str) + " | " + df_deudas_prov['Detalle'].astype(str)
                seleccion_prov = st.multiselect("Seleccioná la o las deudas a pagar (podés elegir varias):", opciones_prov.tolist())
                
                forma_pago_prov = st.selectbox("¿Cómo le pagaste al proveedor?", ["Efectivo", "Transferencia", "Otro"])
                
                if st.button("💸 Registrar Pago(s)"):
                    if seleccion_prov:
                        try:
                            df_ventas_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
                            df_gastos_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Gastos", ttl=0)
                            
                            if 'Estado_Pago_Prov' not in df_ventas_actual.columns:
                                df_ventas_actual['Estado_Pago_Prov'] = ""
                            if 'Forma_Pago_Prov' not in df_ventas_actual.columns:
                                df_ventas_actual['Forma_Pago_Prov'] = ""
                                
                            if 'Forma_de_pago' not in df_gastos_actual.columns:
                                df_gastos_actual['Forma_de_pago'] = ""
                            
                            hubo_cambios_ventas = False
                            hubo_cambios_gastos = False

                            for sel in seleccion_prov:
                                partes = sel.split(" | ")
                                fecha_sel = partes[0]
                                prov_sel = partes[1]
                                veh_sel = partes[2]
                                origen_sel = partes[3]
                                det_sel = partes[4]
                                
                                if origen_sel == 'Ventas':
                                    mascara = (df_ventas_actual['Fecha'].astype(str) == fecha_sel) & \
                                              (df_ventas_actual['Proveedor'].astype(str).str.strip().str.upper() == prov_sel) & \
                                              (df_ventas_actual['Vehículo'].astype(str) == veh_sel)
                                    df_ventas_actual.loc[mascara, 'Estado_Pago_Prov'] = 'Pagado'
                                    df_ventas_actual.loc[mascara, 'Forma_Pago_Prov'] = forma_pago_prov
                                    hubo_cambios_ventas = True
                                    
                                elif origen_sel == 'Gastos':
                                    mascara = (df_gastos_actual['Fecha'].astype(str) == fecha_sel) & \
                                              (df_gastos_actual['Proveedor'].astype(str).str.strip().str.upper() == prov_sel) & \
                                              (df_gastos_actual['Detalle'].astype(str) == det_sel)
                                    df_gastos_actual.loc[mascara, 'Estado_Pago'] = 'Pagado (Contado/Transf)'
                                    df_gastos_actual.loc[mascara, 'Forma_de_pago'] = forma_pago_prov
                                    hubo_cambios_gastos = True
                            
                            if hubo_cambios_ventas:
                                conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_ventas_actual)
                            if hubo_cambios_gastos:
                                conn.update(spreadsheet=SHEET_URL, worksheet="Gastos", data=df_gastos_actual)
                                
                            st.cache_data.clear()
                            st.success(f"✅ {len(seleccion_prov)} pago(s) registrado(s) en {forma_pago_prov}. Excel actualizado.")
                        except Exception as e:
                            st.error(f"⚠️ Error al actualizar pagos: {e}")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para pagar.")
            else:
                st.success("✅ No le debemos a ningún proveedor. ¡Cuentas al día!")
                st.divider()
                
    except Exception as e:
        st.error(f"⚠️ Error al cargar las deudas: {e}")


# 12. BUSCADOR GLOBAL INTELIGENTE (Optimizado con RAM - Session State)
st.divider()
st.header("🔍 Consultar Catálogo y Stock")

# 1. Agregamos TODAS las hojas, conectando lo técnico con el galpón
hoja_map = {
    "Embragues (Kits)": "Catalogo_Kits", 
    "Crapodinas": "Catalogo_Crapodinas", 
    "Distribución": "Catalogo_Distribucion",
    "Stock Físico (Galpón)": "Inventario_Stock"
}

tipo_busqueda = st.radio("¿Qué estás buscando?", list(hoja_map.keys()), horizontal=True)

# Creamos una clave única para guardar esta pestaña en la memoria de la app
session_key = f"df_{hoja_map[tipo_busqueda]}"

# Si el catálogo seleccionado todavía no está en memoria, lo traemos de Google Sheets
if session_key not in st.session_state:
    st.session_state[session_key] = leer_hoja(SHEET_URL, hoja_map[tipo_busqueda])

# A partir de acá, trabajamos 100% con la memoria RAM, sin pedirle datos a Google
df_b = st.session_state[session_key]

busqueda = st.text_input("✍️ Búsqueda Inteligente (Ej: peugeot c4 bimasa):")

# Si hay texto escrito, filtramos.
if busqueda:
    if not df_b.empty:
        # --- LÓGICA DE NORMALIZACIÓN ---
        # 1. Limpiamos lo que tipeaste (sacamos tildes, pasamos a minúscula y cambiamos barras por espacios)
        busqueda_limpia = busqueda.lower()
        busqueda_limpia = re.sub(r'[/_\-]', ' ', busqueda_limpia)
        busqueda_limpia = ''.join(c for c in unicodedata.normalize('NFD', busqueda_limpia) if unicodedata.category(c) != 'Mn')
        palabras_buscadas = busqueda_limpia.split()
        
        # 2. Limpiamos internamente el Excel en tiempo real (unimos toda la fila, sacamos tildes y símbolos)
        texto_filas = df_b.fillna("").astype(str).apply(lambda x: ' '.join(x), axis=1).str.lower()
        texto_filas = texto_filas.str.replace(r'[/_\-]', ' ', regex=True)
        texto_filas = texto_filas.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        
        # 3. Cruzamos los datos: exigimos que TODAS las palabras que tipeaste estén en la fila
        mask = pd.Series(True, index=df_b.index)
        for palabra in palabras_buscadas:
            mask &= texto_filas.str.contains(palabra, case=False, regex=False)
            
        df_filtrado = df_b[mask]
        
        # --- RENDERIZADO EN PANTALLA ---
        if not df_filtrado.empty:
            # Si estás buscando en el stock, le damos formato de Pesos al costo unitario para que se vea profesional
            if tipo_busqueda == "Stock Físico (Galpón)" and 'Costo_Unitario' in df_filtrado.columns:
                st.dataframe(df_filtrado.style.format({'Costo_Unitario': '${:,.0f}', 'Cantidad': '{:.0f}'}), use_container_width=True, hide_index=True)
            else:
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("No encontré resultados con esos datos.")
    else:
        st.warning("La base de datos seleccionada está vacía.")

st.divider()
st.subheader("📦 Gestión de Inventario y Stock")

# --- TABLERO INTELIGENTE DE INVENTARIO ---
categoria_ver = st.selectbox("¿Qué categoría querés revisar?", 
    ["Kits de Embrague", "Forros", "Crapodinas", "Distribución", "Conjuntos de Embrague", "Volantes Bimasa", "Frenos", "Otros"])

try:
    df_stock_total = leer_fresca(SHEET_URL, "Inventario_Stock")
    
    if not df_stock_total.empty:
        # Filtramos solo lo que elegiste ver y hacemos una copia segura
        df_filtrado = df_stock_total[df_stock_total['Categoria'].astype(str).str.strip() == categoria_ver].copy()
        
        if not df_filtrado.empty:
            # Aseguramos que la cantidad sea un número para que no falle la matemática
            df_filtrado['Cantidad'] = pd.to_numeric(df_filtrado['Cantidad'], errors='coerce').fillna(0)
            
            # REGLA VISUAL DE COLOR: Pinta toda la fila si queda 1 o 0
            def resaltar_critico(fila):
                if fila['Cantidad'] <= 1:
                    return ['background-color: #ffe6e6; color: #900000; font-weight: bold'] * len(fila)
                return [''] * len(fila)
            
            # Aplicamos tu regla de color y el formato de pesos al costo
            df_estilizado = df_filtrado.style.apply(resaltar_critico, axis=1).format({'Costo_Unitario': '${:,.0f}', 'Cantidad': '{:.0f}'})
            
            # Mostramos la tabla impecable en pantalla
            st.dataframe(df_estilizado, hide_index=True, use_container_width=True)
            
        else:
            st.info(f"Todavía no hay mercadería cargada en la categoría '{categoria_ver}'.")
    else:
        st.info("El galpón está vacío. No hay stock registrado en el sistema.")
        
except Exception as e:
    st.error(f"Falla al cargar el tablero de inventario: {e}")

st.divider()
# -----------------------------------------

with st.expander("📥 Abrir Panel UNIFICADO (Ingresa Stock y Gasto a la vez)"):
    with st.form("form_ingreso_unificado", clear_on_submit=True):
        
        st.markdown("### 1. Datos Comerciales (Gastos y Proveedor)")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            # Corrección de formato de fecha a Día/Mes/Año
            fecha_compra = st.date_input("Fecha de Compra", format="DD/MM/YYYY")
        with col2:
            proveedor_compra = st.text_input("Proveedor (Ej: Icepar, Cosimi)")
        with col3:
            estado_pago = st.selectbox("Estado de Pago", ["Cuenta Corriente", "Pagado (Contado/Transf)"])
        with col4:
            forma_pago = st.selectbox("Forma de Pago", ["Aún no pagado", "Efectivo", "Transferencia"])

        st.markdown("### 2. Datos del Repuesto (Inventario)")
        col5, col6, col7, col8 = st.columns(4)
        with col5:
            categoria_rep = st.selectbox("Categoría", [
                "Kits de Embrague", "Conjuntos de Embrague", "Volantes Bimasa", 
                "Crapodinas", "Forros", "Frenos", "Distribución", "Otros"
            ])
        with col6:
            # Corrección de marcas: Se agregaron DBH y THE
            marca_opcion = st.selectbox("Marca", [
                "Sachs", "LuK", "Valeo", "PHCValeo", "INA", 
                "IAR Metal", "Termolite", "Frasle", "DBH", "THE", "Otra..."
            ])
            marca_otra = st.text_input("Si es 'Otra...', escribila acá:")
        with col7:
            codigo_rep = st.text_input("Código exacto")
        with col8:
            app_rep = st.text_input("Aplicación (Vehículos)")

        st.markdown("### 3. Costos y Cantidades (Pesos Argentinos)")
        col9, col10 = st.columns(2)
        with col9:
            cantidad_compra = st.number_input("Cantidad de piezas ingresadas", min_value=1, step=1)
        with col10:
            precio_unitario = st.number_input("Costo Unitario ($)", min_value=0.0, step=1000.0)

        submit_unificado = st.form_submit_button("💾 Procesar Ingreso Total")

        if submit_unificado:
            marca_final = marca_otra.strip() if marca_opcion == "Otra..." else marca_opcion
            
            if proveedor_compra == "" or codigo_rep == "" or marca_final == "":
                st.warning("⚠️ Proveedor, Marca y Código son obligatorios.")
            else:
                try:
                    # -- ACCIÓN 1: STOCK --
                    df_stock = conn.read(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", ttl=0)
                    
                    cod_buscar = codigo_rep.strip().lower()
                    marca_buscar = marca_final.strip().lower()
                    
                    mask = (df_stock['Código'].astype(str).str.strip().str.lower() == cod_buscar) & \
                           (df_stock['Marca'].astype(str).str.strip().str.lower() == marca_buscar)
                           
                    if mask.any():
                        idx = df_stock[mask].index[0]
                        
                        cant_actual = pd.to_numeric(df_stock.at[idx, 'Cantidad'], errors='coerce')
                        if pd.isna(cant_actual): cant_actual = 0
                        df_stock.at[idx, 'Cantidad'] = int(cant_actual + cantidad_compra)
                        
                        app_actual = str(df_stock.at[idx, 'Aplicación']).strip() 
                        app_nueva = app_rep.strip()
                        if app_nueva.lower() not in app_actual.lower() and app_nueva != "":
                            if app_actual == "" or app_actual.lower() == "nan":
                                df_stock.at[idx, 'Aplicación'] = app_nueva
                            else:
                                df_stock.at[idx, 'Aplicación'] = app_actual + " / " + app_nueva
                                
                        df_stock.at[idx, 'Costo_Unitario'] = float(precio_unitario)
                        
                    else:
                        nueva_fila_stock = pd.DataFrame([{
                            'Categoria': categoria_rep,
                            'Marca': marca_final,
                            'Código': codigo_rep.strip(),
                            'Aplicación': app_rep.strip(),
                            'Cantidad': int(cantidad_compra),
                            'Costo_Unitario': float(precio_unitario)
                        }])
                        df_stock = pd.concat([df_stock, nueva_fila_stock], ignore_index=True)
                    
                    conn.update(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", data=df_stock)

                    # -- ACCIÓN 2: GASTOS --
                    df_gastos = conn.read(spreadsheet=SHEET_URL, worksheet="Gastos", ttl=0)
                    
                    monto_total = float(cantidad_compra * precio_unitario)
                    detalle_construido = f"{cantidad_compra}x {categoria_rep} {marca_final} ({codigo_rep})"
                    
                    # La fecha que se manda al Excel se asegura de ir en formato DD/MM/YYYY
                    nueva_fila_gasto = pd.DataFrame([{
                        'Fecha': fecha_compra.strftime("%d/%m/%Y"),
                        'Clasificacion': "Inversión en Stock",
                        'Categoria': "Compra de Mercadería",
                        'Detalle': detalle_construido,
                        'Monto $': monto_total,
                        'Estado_Pago': estado_pago,
                        'Proveedor': proveedor_compra,
                        'Forma_de_pago': forma_pago
                    }])
                    
                    df_gastos = pd.concat([df_gastos, nueva_fila_gasto], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, worksheet="Gastos", data=df_gastos)
                    
                    st.cache_data.clear()
                    st.success(f"✅ ¡Operación exitosa! Se sumaron {cantidad_compra}x {marca_final} al stock y se registró el gasto de ${monto_total:,.2f} en {proveedor_compra}.")
                    
                except Exception as e:
                    st.error(f"⚠️ Error en la operación unificada: {e}")
st.divider()
st.subheader("🔄 Base de Datos Técnica (Actualización de Códigos)")

# El selector maestro va AFUERA del form para que actualice la pantalla en tiempo real
tipo_catalogo = st.selectbox("¿Qué base de datos vas a actualizar?", ["Kits de Embrague", "Crapodinas"])

with st.expander(f"Abrir panel para cargar Códigos de {tipo_catalogo}"):
    with st.form("form_actualizar_codigos", clear_on_submit=False):
        st.write(f"📝 **Modificar o agregar equivalencias para {tipo_catalogo}**")
        
        # Fila 1: Identificación del vehículo adaptada al catálogo
        col1, col2 = st.columns(2)
        with col1:
            vehiculo_cat = st.text_input("Vehículo exacto (Ej: Peugeot 307 / 206)")
        with col2:
            if tipo_catalogo == "Kits de Embrague":
                detalle_cat = st.text_input("Motor (Ej: 2.0)")
                marcas_disponibles = ["LUK", "SACHS", "VALEO", "PHC_valeo", "ORIGINAL", "OTRA"]
            else: # Crapodinas
                detalle_cat = st.text_input("Descripción (Ej: Crapodina Mecánica)")
                marcas_disponibles = ["LUK", "SKF", "DBH", "THE", "ORIGINAL", "OTRA"]
                
        # Fila 2: El código nuevo a inyectar con las marcas dinámicas
        col3, col4 = st.columns(2)
        with col3:
            marca_cat = st.selectbox("¿De qué marca es el código?", marcas_disponibles)
        with col4:
            codigo_cat = st.text_input("Nuevo Código de Fábrica")
            
        submit_cat = st.form_submit_button("💾 Guardar Código en Base de Datos")
        
        if submit_cat:
            if vehiculo_cat != "" and codigo_cat != "":
                try:
                    # Seteamos las reglas estrictas dependiendo de lo que elegiste
                    if tipo_catalogo == "Kits de Embrague":
                        nombre_hoja = "Catalogo_Kits"
                        columnas_cat = [
                            "Vehiculo", "Motor", "Proveedor", 
                            "Codigo_LUK", "Precio_LUK", "Codigo_SACHS", "Precio_SACHS", 
                            "Codigo_VALEO", "Precio_VALEO", "Codigo_PHC_valeo", "Precio_PHC_valeo", 
                            "Codigo_ORIGINAL", "Precio_ORIGINAL", "Codigo_OTRA", "Precio_OTRA"
                        ]
                        col_detalle_nombre = "Motor"
                    else: # Crapodinas
                        nombre_hoja = "Catalogo_Crapodinas"
                        columnas_cat = [
                            "Vehiculo", "Descripcion", 
                            "Codigo_LUK", "Precio_LUK", "Codigo_SKF", "Precio_SKF", 
                            "Codigo_DBH", "Precio_DBH", "Codigo_THE", "Precio_THE", 
                            "Codigo_ORIGINAL", "Precio_ORIGINAL", "Codigo_OTRA", "Precio_OTRA"
                        ]
                        col_detalle_nombre = "Descripcion"

                    df_cat = conn.read(spreadsheet=SHEET_URL, worksheet=nombre_hoja, ttl=0)
                    
                    if df_cat.empty:
                        df_cat = pd.DataFrame(columns=columnas_cat)
                    else:
                        df_cat = df_cat[columnas_cat]
                    
                    df_cat['Veh_norm'] = df_cat['Vehiculo'].astype(str).str.strip().str.lower()
                    df_cat['Det_norm'] = df_cat[col_detalle_nombre].astype(str).str.strip().str.lower()
                    
                    veh_buscar = vehiculo_cat.strip().lower()
                    det_buscar = detalle_cat.strip().lower()
                    
                    mask = (df_cat['Veh_norm'] == veh_buscar) & (df_cat['Det_norm'] == det_buscar)
                    
                    col_codigo = f"Codigo_{marca_cat}"
                    
                    # BLINDAJE DE FORMATO
                    df_cat[col_codigo] = df_cat[col_codigo].astype(object)
                    
                    if mask.any():
                        # EL REPUESTO EXISTE: actualiza el código en la marca elegida
                        idx = df_cat[mask].index[0]
                        df_cat.at[idx, col_codigo] = codigo_cat
                        accion_msj = "actualizado"
                    else:
                        # EL REPUESTO NO EXISTE: crea fila nueva
                        nueva_fila = {col: "" for col in columnas_cat}
                        nueva_fila["Vehiculo"] = vehiculo_cat
                        nueva_fila[col_detalle_nombre] = detalle_cat
                        nueva_fila[col_codigo] = codigo_cat
                        
                        df_nueva = pd.DataFrame([nueva_fila])
                        df_cat = pd.concat([df_cat, df_nueva], ignore_index=True)
                        accion_msj = "creado"
                    
                    df_cat = df_cat.drop(columns=['Veh_norm', 'Det_norm'])
                    conn.update(spreadsheet=SHEET_URL, worksheet=nombre_hoja, data=df_cat)
                    
                    st.cache_data.clear()
                    
                    # --- CORRECCIÓN QUIRÚRGICA: Limpiamos la RAM del buscador ---
                    key_a_borrar = f"df_{nombre_hoja}"
                    if key_a_borrar in st.session_state:
                        del st.session_state[key_a_borrar]
                    # ------------------------------------------------------------
                    
                    st.success(f"✅ ¡Código {accion_msj} con éxito en {tipo_catalogo}! {vehiculo_cat} {detalle_cat} | {marca_cat}: {codigo_cat}")
                    
                except Exception as e:
                    st.error(f"⚠️ Error al guardar el código: {e}")
            else:
                st.warning("⚠️ Asegurate de escribir el Vehículo y el Nuevo Código.")


# ==========================================
# 13. MÓDULO AFIP Y MONOTRIBUTO
# ==========================================
st.markdown("---")
st.markdown("### 🏛️ Control AFIP y Monotributo")

# --- 1. TERMÓMETRO MONOTRIBUTO ---
st.markdown("#### 🌡️ Termómetro Categoría C")
st.info("Actualizá tu facturación previa y el tope de la categoría. El sistema sumará automáticamente los trabajos nuevos marcados 'Con Factura'.")

col_t1, col_t2 = st.columns(2)
with col_t1:
    facturacion_previa = st.number_input("Facturación Previa 2026 ($):", min_value=0, value=3344772, step=100000, help="Ingresá lo que ya tenés facturado en el año hasta hoy.")
with col_t2:
    # El tope se puede modificar si ARCA/AFIP actualiza las escalas
    tope_cat_c = st.number_input("Tope Anual Categoría C ($):", min_value=1, value=24670494, step=100000)

# Calculamos lo facturado desde la App (Ventas + Entregas a Cuenta)
facturado_app = 0
frames_mariano = []

try:
    # 1. Leemos las ventas directas (Mostrador)
    df_ventas_afip = leer_fresca(SHEET_URL, "Ventas")
    if 'Facturado' in df_ventas_afip.columns:
        df_facturado_ventas = df_ventas_afip[df_ventas_afip['Facturado'].astype(str).str.strip().str.upper() == "SI"].copy()
        if not df_facturado_ventas.empty:
            facturado_app += pd.to_numeric(df_facturado_ventas['Venta $'], errors='coerce').fillna(0).sum()
            # Preparamos tabla para Mariano
            df_v = df_facturado_ventas[['Fecha', 'Cliente', 'Detalle', 'Venta $']].copy()
            df_v.rename(columns={'Venta $': 'Monto Facturado ($)'}, inplace=True)
            df_v['Origen'] = 'Venta Directa'
            frames_mariano.append(df_v)
            
    # 2. Leemos las entregas a cuenta (Ej: Transferencias de Ariel)
    df_saldos_afip = leer_fresca(SHEET_URL, "Saldos_y_Canjes")
    if 'Facturado' in df_saldos_afip.columns:
        df_facturado_saldos = df_saldos_afip[df_saldos_afip['Facturado'].astype(str).str.strip().str.upper() == "SI"].copy()
        if not df_facturado_saldos.empty:
            facturado_app += pd.to_numeric(df_facturado_saldos['Monto a Favor'], errors='coerce').fillna(0).sum()
            # Preparamos tabla para Mariano
            df_s = df_facturado_saldos[['Fecha', 'Cliente', 'Detalle', 'Monto a Favor']].copy()
            df_s.rename(columns={'Monto a Favor': 'Monto Facturado ($)'}, inplace=True)
            df_s['Origen'] = 'Entrega a Cuenta'
            frames_mariano.append(df_s)
            
except Exception as e:
    st.error(f"⚠️ Error calculando datos de AFIP: {e}")

# Matemática del termómetro
total_facturado = facturacion_previa + facturado_app
porcentaje = (total_facturado / tope_cat_c) * 100 if tope_cat_c > 0 else 0

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.metric("Total Facturado Anual", f"${total_facturado:,.0f}", f"{porcentaje:.1f}% del tope")

# Barra de progreso visual
st.progress(min(porcentaje / 100, 1.0))

# Alertas inteligentes de límite
if porcentaje >= 90:
    st.error("⚠️ ALERTA ROJA: Estás al límite de la Categoría C. Frena la facturación.")
elif porcentaje >= 75:
    st.warning("⚠️ Cuidado: Ya superaste el 75% del tope de la Categoría C.")
else:
    st.success("✅ Margen seguro para facturar.")

# --- 2. REPORTE PARA MARIANO ---
st.markdown("#### 📄 Reporte para Mariano (Contador)")
if frames_mariano:
    # Unimos todo en un solo Excel limpio para el contador
    df_reporte_final = pd.concat(frames_mariano, ignore_index=True)
    csv_mariano = df_reporte_final.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Descargar Excel de Trabajos Facturados",
        data=csv_mariano,
        file_name="Facturacion_Embragues_Rosario.csv",
        mime="text/csv",
        type="primary"
    )
else:
    st.info("No hay trabajos ni ingresos marcados como 'Con Factura' para exportar todavía.")

# --- 3. CHECKLIST PLANES DE PAGO AFIP ---
st.markdown("#### 📅 Planes de Pago AFIP")
st.write("Control visual de cuotas debitadas.")

col_p1, col_p2 = st.columns(2)

with col_p1:
    st.markdown("**Plan V664000 (17 Cuotas)**")
    # Las primeras 5 ya están pagas, las bloqueamos.
    for i in range(1, 18):
        if i <= 5:
            st.checkbox(f"Cuota {i} - Pagada", value=True, disabled=True, key=f"plan17_c{i}")
        else:
            st.checkbox(f"Cuota {i}", value=False, key=f"plan17_c{i}")

with col_p2:
    st.markdown("**Plan W391567 (5 Cuotas)**")
    # Plan nuevo, todas disponibles para tildar.
    for i in range(1, 6):
        st.checkbox(f"Cuota {i}", value=False, key=f"plan5_c{i}")

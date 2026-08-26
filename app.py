import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import urllib.parse
import re
import unicodedata
import calendar 

# 1. IDENTIDAD
st.set_page_config(page_title="Embragues Rosario", page_icon="logo.png")
try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Embragues Rosario")
st.markdown("Crespo 4117, Rosario | **IIBB: EXENTO**")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1YJHJ006kr-izLHG9Ib5CRUX5VUdu6INRDsKn4u0x32Y/edit"

# 2. CONEXIÓN
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_conn()

# 3. MEMORIAS INDEPENDIENTES (FRANCOTIRADORES)
def _leer_fresca_base(hoja):
    df = conn.read(spreadsheet=SHEET_URL, worksheet=hoja, ttl=900).copy()
    df = df.replace(["", " ", "None"], None)
    df = df.dropna(how='all')
    return df

@st.cache_data(ttl=600, show_spinner=False)
def leer_ventas(): return _leer_fresca_base("Ventas")

@st.cache_data(ttl=600, show_spinner=False)
def leer_stock(): return _leer_fresca_base("Inventario_Stock")

@st.cache_data(ttl=600, show_spinner=False)
def leer_gastos(): return _leer_fresca_base("Gastos")

@st.cache_data(ttl=600, show_spinner=False)
def leer_saldos(): return _leer_fresca_base("Saldos_y_Canjes")

@st.cache_data(ttl=600, show_spinner=False)
def leer_kits(): return _leer_fresca_base("Catalogo_Kits")

@st.cache_data(ttl=600, show_spinner=False)
def leer_crapodinas(): return _leer_fresca_base("Catalogo_Crapodinas")

@st.cache_data(ttl=600, show_spinner=False)
def leer_distribucion(): return _leer_fresca_base("Catalogo_Distribucion")

# 4. COEFICIENTES FINANCIEROS (BLINDADOS EN CÓDIGO)
COEF_POSNET_BASE = 1.04  # +4% de escudo para cubrir el arancel a 10 días
COEF_CLIENTE_1 = 1.04  # +4% de recargo final a mostrar al cliente en 1 pago
COEF_CLIENTE_3 = 1.12    # +12% de recargo final a mostrar al cliente
COEF_CLIENTE_6 = 1.19    # +19% de recargo final a mostrar al cliente

# 5. CATÁLOGOS (Lectura Inicial)
try:
    df_kits = leer_kits()
    df_crapo = leer_crapodinas()
    df_distri = leer_distribucion()
except Exception as e:
    df_kits = df_crapo = df_distri = pd.DataFrame()

# 6. FUNCIONES DE ESCRITURA Y ACTUALIZACIÓN

def saldar_deuda(fecha, nombre, tipo_actor):
    try:
        df = leer_ventas()
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
                
        conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df)
        leer_ventas.clear() # Francotirador
        return True
    except Exception as e:
        st.error(f"Falla al saldar deuda: {e}")
        return False

def actualizar_catalogo_kits(vehiculo, descripcion, codigo, precio, marca, motor, proveedor):
    try:
        df = leer_kits()
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
        
        m_codigo = (df[col_cod].astype(str).str.strip() == cod_limpio) & (cod_limpio != "")
        
        if m_codigo.any():
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
            m_vehiculo = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l)
            if m_vehiculo.any():
                idx = df.index[m_vehiculo][0]
                df.at[idx, col_cod] = cod_limpio
                df.at[idx, col_pre] = precio
                if motor: df.at[idx, "Motor"] = motor
                if proveedor: df.at[idx, "Proveedor"] = proveedor
            else:
                fila = {c: "" for c in df.columns}
                fila["Vehiculo"] = vehiculo_limpio
                fila["Motor"] = motor
                fila["Proveedor"] = proveedor
                fila[col_cod] = cod_limpio
                fila[col_pre] = precio
                df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
                
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Kits", data=df)
        leer_kits.clear() # Francotirador
    except Exception as e:
        st.error(f"Falla al guardar en Kits: {e}")

def actualizar_catalogo_crapodinas(vehiculo, descripcion, codigo, precio, marca):
    try:
        df = leer_crapodinas()
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
        
        m_codigo = (df[col_cod].astype(str).str.strip() == cod_limpio) & (cod_limpio != "")
        
        if m_codigo.any():
            idx = df.index[m_codigo][0]
            veh_actual = str(df.at[idx, 'Vehiculo']).strip()
            if veh_l not in veh_actual.lower():
                if veh_actual == "" or veh_actual.lower() == "nan":
                    df.at[idx, 'Vehiculo'] = vehiculo_limpio
                else:
                    df.at[idx, 'Vehiculo'] = veh_actual + " / " + vehiculo_limpio
            df.at[idx, col_pre] = precio
        else:
            m_exacto = (df['Vehiculo'].astype(str).str.strip().str.lower() == veh_l) & \
                       (df['Descripcion'].astype(str).str.strip().str.lower() == desc_l)
            if m_exacto.any():
                idx = df.index[m_exacto][0]
                df.at[idx, col_cod] = cod_limpio
                df.at[idx, col_pre] = precio
            else:
                fila = {c: "" for c in df.columns}
                fila["Vehiculo"] = vehiculo_limpio
                fila["Descripcion"] = descripcion
                fila[col_cod] = cod_limpio
                fila[col_pre] = precio
                df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
                
        conn.update(spreadsheet=SHEET_URL, worksheet="Catalogo_Crapodinas", data=df)
        leer_crapodinas.clear() # Francotirador
    except Exception as e:
        st.error(f"Falla al guardar en Crapodinas: {e}")

def obtener_costo_stock(codigo):
    if not codigo or str(codigo).strip() == "": return 0
    try:
        df_stock = leer_stock()
        filtro = df_stock['Código'].astype(str).str.strip() == str(codigo).strip()
        if filtro.any():
            indice = df_stock.index[filtro].tolist()[0]
            costo = df_stock.at[indice, 'Costo_Unitario']
            return float(pd.to_numeric(costo, errors='coerce'))
    except:
        pass
    return 0

def descontar_stock(codigo, cantidad_a_restar):
    if not codigo or str(codigo).strip() == "": return
    try:
        df_stock = conn.read(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", ttl=0)
        filtro = df_stock['Código'].astype(str).str.strip() == str(codigo).strip()
        
        if filtro.any():
            indice = df_stock.index[filtro].tolist()[0]
            stock_actual = int(df_stock.at[indice, 'Cantidad'])
            nuevo_stock = stock_actual - cantidad_a_restar
            df_stock.at[indice, 'Cantidad'] = nuevo_stock
            
            conn.update(spreadsheet=SHEET_URL, worksheet="Inventario_Stock", data=df_stock)
            leer_stock.clear() # Francotirador
        else:
            st.warning(f"Atención: El repuesto código '{codigo}' no se encontró en el inventario.")
    except Exception as e:
        st.error(f"Error interno al descontar stock del código {codigo}: {e}")

def guardar_en_google(nro_trabajo, categoria, cliente, vehiculo, detalle, monto_bruto, monto_neto, costo, proveedor,
                      cod_kit, cod_crap, f_pago, e_cliente, e_prov, f_pago_prov,
                      m_forros, c_forros, costo_f, ganancia,
                      desc_kit, desc_crap, desc_forros, factura_texto, monto_final_afip): 
                      
    fecha_hoy = (pd.Timestamp.now() - pd.Timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    
    # === ACÁ METIMOS LA COLUMNA NUEVA EXACTAMENTE COMO ESTÁ EN TU EXCEL ===
    columnas = ["Fecha", "Nro_Trabajo", "Categoría", "Cliente", "Vehículo", "Detalle",
                "Venta $", "Monto_Facturado_AFIP", "Compra $", "Proveedor", "Código", "Cod_Crapodina",
                "Forma_de_pago", "Estado_Cobro", "Estado_Pago_Prov", "Forma_Pago_Prov",
                "Marca_Forros", "Cod_Forros", "Costo_Forros", "Ganancia", "Monto Neto Esperado", "Facturado"]
                
    try:
        df_existente = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
    except Exception as e:
        st.error(f"Error al leer Ventas: {e}")
        st.stop()
        
    # === ACÁ ENCHUFAMOS EL DATO (después de monto_bruto y antes de costo) ===
    nueva = pd.DataFrame([[fecha_hoy, nro_trabajo, categoria, cliente, vehiculo, detalle,
                           monto_bruto, monto_final_afip, costo, proveedor, cod_kit, cod_crap,
                           f_pago, e_cliente, e_prov, f_pago_prov,
                           m_forros, c_forros, costo_f, ganancia, monto_neto, factura_texto]],
                         columns=columnas)
                         
    df_nuevo = pd.concat([df_existente, nueva], ignore_index=True)
    conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_nuevo)
    leer_ventas.clear() # Francotirador

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
    # Aca le inyectamos a fuego tu frase de cabecera
    sugerencia = f"KIT nuevo marca *{m_kit}* con rectificación y balanceo de volante incluido"
    
elif "Reparación" in tipo_item:
    cat_f, icono, incl_rectif = "Reparación", "🔧", True
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
    
    m_forros = st.sidebar.selectbox("Marca de Forros:", ["IAR Metal","Fras-le","Termolite","Otro"], key=f"mforro_{fk}")
    forros_combinados = st.sidebar.checkbox("¿Forros combinados (distinto espesor)?", key=f"fcomb_{fk}")
    
    cod1 = cod2 = ""
    if forros_combinados:
        col1, col2 = st.sidebar.columns(2)
        with col1: cod1 = st.sidebar.text_input("Código 1:", key=f"fcod1_{fk}")
        with col2: cod2 = st.sidebar.text_input("Código 2:", key=f"fcod2_{fk}")
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

if tipo_item != "Rectificación de Volante":
    nro_trabajo_input = st.sidebar.text_input("Nro. de Trabajo (Ej: 168):", value="", key=f"nrotrabajo_{fk}")
else:
    nro_trabajo_input = ""

monto_limpio = st.sidebar.number_input("Precio de VENTA ($):", min_value=0, value=0, key=f"montolimpio_{fk}")

con_factura = st.sidebar.checkbox("🧾 Con Factura (Suma a Categoría C)", value=False, key=f"factura_{fk}")

# === NUEVO: CAJITA INTELIGENTE PARA AFIP ===
monto_afip = 0
if con_factura:
    monto_afip = st.sidebar.number_input(
        "Monto a Facturar en AFIP ($):", 
        min_value=0, 
        value=int(monto_limpio), 
        step=1000,
        key=f"monto_afip_{fk}",
        help="Si el ticket tiene recargo de tarjeta, tipeá acá el monto inflado exacto. Si es efectivo o transf, dejalo igual."
    )
# ===========================================

# === NUEVO: BUSCADOR INTELIGENTE DE VEHÍCULOS ===
vehiculos_existentes = []
try:
    if 'df_kits' in locals() and not df_kits.empty:
        vehiculos_existentes.extend(df_kits['Vehiculo'].dropna().unique().tolist())
    if 'df_crapo' in locals() and not df_crapo.empty:
        vehiculos_existentes.extend(df_crapo['Vehiculo'].dropna().unique().tolist())
    # Limpiamos duplicados, vacíos y ordenamos alfabéticamente
    vehiculos_existentes = sorted(list(set([str(v).strip() for v in vehiculos_existentes if str(v).strip() != "" and str(v).strip().lower() != "nan"])))
except:
    pass

st.sidebar.markdown("---")
st.sidebar.markdown("🚗 **Datos del Vehículo**")

nuevo_vehiculo = st.sidebar.checkbox("➕ Cargar un vehículo nuevo (que no está en la base)", value=False, key=f"nuevo_veh_{fk}")

if nuevo_vehiculo or not vehiculos_existentes:
    vehiculo_input = st.sidebar.text_input("Nombre del Vehículo (NUEVO):", value="", key=f"vehiculo_{fk}")
else:
    vehiculo_input = st.sidebar.selectbox("Seleccionar Vehículo (Tipeá para buscar):", [""] + vehiculos_existentes, key=f"vehiculo_{fk}")

motor_input = st.sidebar.text_input("Motor:", value="", key=f"motor_{fk}")
st.sidebar.markdown("---")

if tipo_item != "Rectificación de Volante":
    proveedor_input = st.sidebar.text_input("Proveedor:", value="", key=f"proveedor_{fk}")
else:
    proveedor_input = "Taller Propio"
# ===============================================

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
        precio_compra = costo_kit_auto
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
        "Efectivo", "Transferencia", "Débito", "Más Pagos - Posnet/QR", "Más Pagos - Link", "Combinado", "Otro"], key=f"fpago_{fk}")

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
    elif "Más Pagos" in f_pago_input: 
        monto_bruto = int(round(monto_limpio * COEF_POSNET_BASE))
        monto_neto_guardar = monto_limpio
    
    factura_texto = "SI" if con_factura else "NO"
    
    # === NUEVO: DEFINIMOS QUÉ DATO VA A LA COLUMNA DE AFIP ===
    monto_final_afip = monto_afip if con_factura else 0
    
    guardar_en_google(nro_trabajo_input, cat_f, cliente_input, vehiculo_input, detalle_excel,
              monto_bruto, monto_neto_guardar, precio_compra, proveedor_input,
              cod_kit_final, cod_crap_final, f_pago_input,
              estado_cliente, estado_p_prov,
              "", 
              m_forros, forros_codigo, forros_costo, ganancia,
              desc_kit, desc_crap, desc_forros, factura_texto,
              monto_final_afip)
                      
    if cod_kit_final and cat_f == "Venta":
        marca_k = m_kit[0] if isinstance(m_kit, list) and m_kit else (m_kit or "OTRA")
        actualizar_catalogo_kits(vehiculo_input, "Kit de Embrague", cod_kit_final, precio_compra, marca_k, motor_input, proveedor_input)
    if cod_crap_final and cat_f == "Reparación":
        actualizar_catalogo_crapodinas(vehiculo_input, f"Crapodina {tipo_crap}", cod_crap_final, crap_costo, m_crap[0] if m_crap else "OTRA")
                                       
    st.session_state.form_key += 1
    st.session_state["venta_exitosa"] = "✅ Venta registrada correctamente."
    st.rerun()

# -------------------------------------------------------------
if "form_key" not in st.session_state:
    st.session_state.form_key = 0
fk = st.session_state.form_key
# -------------------------------------------------------------
# 8. CALCULADORA DE CUOTAS
st.markdown("### 💳 Calculadora de Cuotas (+Pagos Nación)")

tipo_pos = st.radio("Herramienta de cobro:", ["POSNET / QR (En el local)", "LINK DE PAGO (A distancia)"], horizontal=True)
nombre_pos = "+PAGOS"

t1 = monto_limpio * COEF_POSNET_BASE 
t3 = monto_limpio * COEF_CLIENTE_3
t6 = monto_limpio * COEF_CLIENTE_6

st.info(f"👉 **MONTO A TIPEAR EN LA MÁQUINA / LINK:** $ {t1:,.0f} (Incluye tu blindaje del 4%)")
st.divider()
st.markdown(f"""
<div style='background:#d4edda;padding:10px;border-radius:5px;text-align:center;border:2px solid #28a745;'>
  <h2 style='color:#155724;margin:0;'>💰 CONTADO / TRANSF: ${monto_limpio:,.0f}</h2>
  <p style='margin:0;font-size:0.9em;'>(Este monto te queda limpio)</p>
</div>""", unsafe_allow_html=True)

st.write("**Presupuesto para el cliente:**")
ca, cb, cc = st.columns(3)
with ca: st.metric("1 PAGO / QR",   f"${t1:,.0f}")
with cb: st.metric("3 CUOTAS (12%)", f"${t3/3:,.2f}", f"Total: ${t3:,.0f}")
with cc: st.metric("6 CUOTAS (19%)", f"${t6/6:,.2f}", f"Total: ${t6:,.0f}")

# 9. WHATSAPP (MULTI-COTIZADOR INTELIGENTE)
st.divider()
st.markdown("### 📱 Armador de Presupuestos (WhatsApp)")

# Definimos tu frase de cabecera para las reparaciones
texto_rep_default = "Reparado completo placa disco con forros originales volante rectificado y balanceado"

with st.expander("➕ Agregar opciones al presupuesto (Ej: Reparado, otras marcas)"):
    st.info("La Opción 1 ya está cargada con los datos de tu barra lateral. Llená las siguientes solo si querés comparar precios.")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        d2 = st.text_input("Opción 2 - Detalle (Ej: Kit embrague PHC Valeo):", key="d2")
        p2 = st.number_input("Opción 2 - Precio Contado ($):", min_value=0, value=0, step=1000, key="p2")
        d4 = st.text_input("Opción 4 - Detalle:", key="d4")
        p4 = st.number_input("Opción 4 - Precio Contado ($):", min_value=0, value=0, step=1000, key="p4")
    with col_w2:
        # Aca inyectamos el texto predeterminado en la caja 3
        d3 = st.text_input("Opción 3 - Detalle (Reparado):", value=texto_rep_default, key="d3")
        p3 = st.number_input("Opción 3 - Precio Contado ($):", min_value=0, value=0, step=1000, key="p3")

opciones = [
    (detalle_final, monto_limpio),
    (d2, p2), 
    (d3, p3), 
    (d4, p4)
]

lineas_mensaje = [
    f"🚗 *EMBRAGUES ROSARIO*",
    f"¡Hola! Presupuesto para: *{vehiculo_input}*\n"
]

contador = 1
for desc, precio in opciones:
    tiene_desc = desc and desc.strip() != ""
    tiene_precio = precio > 0
    
    if tiene_desc and tiene_precio:
        # ACA INYECTAMOS EL CÁLCULO DE LA CUOTA ÚNICA
        t1_op = precio * COEF_CLIENTE_1
        t3_op = precio * COEF_CLIENTE_3 
        t6_op = precio * COEF_CLIENTE_6
        
        bloque = (
            f"⚙️ *{desc.strip()}*\n"
            f"💰 Contado/Transf: ${precio:,.0f}\n"
            f"💳 Tarjeta 1 cuota: ${t1_op:,.0f}\n"
            f"💳 Tarjeta 3 cuotas: ${t3_op:,.0f} (${t3_op/3:,.2f} c/u)\n"
            f"💳 Tarjeta 6 cuotas: ${t6_op:,.0f} (${t6_op/6:,.2f} c/u)\n"
        )
        lineas_mensaje.append(bloque)
    elif tiene_desc and not tiene_precio:
        # Excepción táctica: si es la frase por defecto y está en $0, la saltea en silencio
        if desc.strip() == texto_rep_default.strip() and precio == 0:
            pass
        elif contador > 1:
            st.error(f"⚠️ ¡OJO! Te olvidaste de ponerle el PRECIO a la Opción {contador}.")
    elif not tiene_desc and tiene_precio:
        if contador > 1:
            st.error(f"⚠️ ¡OJO! Pusiste un precio de ${precio:,.0f} en la Opción {contador}, pero dejaste el DETALLE vacío.")
            
    contador += 1

lineas_mensaje.append("📍 *Dirección:* Crespo 4117, Rosario")
lineas_mensaje.append("📍 *Ubicación:* https://www.google.com/maps?q=Crespo+4117+Rosario")
lineas_mensaje.append("📸 *Instagram:* @embraguesrosario")
lineas_mensaje.append("⏰ *Horario:* 8:30 a 17:00 hs\n")
lineas_mensaje.append("¡Te esperamos pronto! 👨🏻‍🔧")

mensaje_final = "\n".join(lineas_mensaje)

if monto_limpio > 0:
    st.write("---")
    st.info("👇 Presioná el botón gris para asegurar los datos antes de enviar al cliente.")
    
    if st.button("⚙️ 1. PROCESAR Y ARMAR MENSAJE", type="primary", use_container_width=True):
        import urllib.parse
        st.success("✅ Datos sincronizados. Ya podés enviarlo por WhatsApp.")
        st.link_button("🟢 2. ENVIAR PRESUPUESTO AHORA", f"https://wa.me/?text={urllib.parse.quote(mensaje_final)}", use_container_width=True)
        with st.expander("Ver vista previa del mensaje", expanded=True):
            st.code(mensaje_final, language="markdown")
else:
    st.warning("⚠️ Ingresá el Precio de VENTA en la barra lateral para generar el presupuesto.")
# 10. HISTORIAL Y DASHBOARD FINANCIERO
st.divider()
try:
    df_ver = leer_ventas()
    
    if not df_ver.empty:
        with st.expander("📊 Tablero de Finanzas (Mes a Mes)"):
            import datetime
            
            df_dash = df_ver.copy()
            df_dash['Fecha'] = pd.to_datetime(df_dash['Fecha'], dayfirst=True, errors='coerce')
            df_dash['Ganancia'] = pd.to_numeric(df_dash['Ganancia'], errors='coerce').fillna(0)
            df_dash['Venta $'] = pd.to_numeric(df_dash['Venta $'], errors='coerce').fillna(0)
            df_dash['Compra $'] = pd.to_numeric(df_dash['Compra $'], errors='coerce').fillna(0)
            
            try:
                df_gastos = leer_gastos().copy()
                df_gastos['Fecha'] = pd.to_datetime(df_gastos['Fecha'], dayfirst=True, errors='coerce')
                df_gastos['Monto $'] = pd.to_numeric(df_gastos['Monto $'], errors='coerce').fillna(0)
            except Exception:
                df_gastos = pd.DataFrame(columns=['Fecha', 'Clasificacion', 'Monto $'])
            
            meses_nombres = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
            
            if not df_gastos.empty:
                fechas_totales = pd.concat([df_dash['Fecha'], df_gastos['Fecha']]).dropna()
            else:
                fechas_totales = df_dash['Fecha'].dropna()
                
            hoy = (datetime.datetime.now() - datetime.timedelta(hours=3)).date()
            
            if not fechas_totales.empty:
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
            
            if mes_actual == 1:
                mes_pasado = 12
                anio_pasado = anio_actual - 1
            else:
                mes_pasado = mes_actual - 1
                anio_pasado = anio_actual
                
            df_mes_actual = df_dash[(df_dash['Fecha'].dt.month == mes_actual) & (df_dash['Fecha'].dt.year == anio_actual)]
            df_mes_pasado = df_dash[(df_dash['Fecha'].dt.month == mes_pasado) & (df_dash['Fecha'].dt.year == anio_pasado)]
            
            if not df_gastos.empty:
                gastos_actuales = df_gastos[(df_gastos['Fecha'].dt.month == mes_actual) & (df_gastos['Fecha'].dt.year == anio_actual)]
                gastos_pasados = df_gastos[(df_gastos['Fecha'].dt.month == mes_pasado) & (df_gastos['Fecha'].dt.year == anio_pasado)]
                op_actuales = gastos_actuales[gastos_actuales['Clasificacion'].astype(str).str.strip() == "Gasto Operativo"]['Monto $'].sum()
                op_pasados = gastos_pasados[gastos_pasados['Clasificacion'].astype(str).str.strip() == "Gasto Operativo"]['Monto $'].sum()
            else:
                op_actuales = 0
                op_pasados = 0
            
            ganancia_bruta_actual = df_mes_actual['Ganancia'].sum()
            ganancia_bruta_pasada = df_mes_pasado['Ganancia'].sum()
            neta_actual = ganancia_bruta_actual - op_actuales
            neta_pasada = ganancia_bruta_pasada - op_pasados
            diferencia_neta = neta_actual - neta_pasada
            
            df_cobrar = df_dash[df_dash['Estado_Cobro'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            plata_en_calle_bruta = df_cobrar['Venta $'].sum()
            
            try:
                df_saldos_metric = leer_saldos()
                if not df_saldos_metric.empty:
                    total_canjes = pd.to_numeric(df_saldos_metric['Monto a Favor'], errors='coerce').sum()
                else:
                    total_canjes = 0
            except:
                total_canjes = 0
                
            plata_en_calle = plata_en_calle_bruta - total_canjes
            
            df_pagar = df_dash[df_dash['Estado_Pago_Prov'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
            deuda_diaria = df_pagar['Compra $'].sum()
            
            if not df_gastos.empty:
                gastos_deuda = df_gastos[df_gastos['Estado_Pago'].astype(str).str.contains("Cuenta Corriente", case=False, na=False)]
                deuda_stock = gastos_deuda['Monto $'].sum()
            else:
                deuda_stock = 0
                
            deuda_prov = deuda_diaria + deuda_stock
            
            try:
                df_stock_inv = leer_stock()
                df_stock_inv['Cantidad'] = pd.to_numeric(df_stock_inv['Cantidad'], errors='coerce').fillna(0)
                df_stock_inv['Costo_Unitario'] = pd.to_numeric(df_stock_inv['Costo_Unitario'], errors='coerce').fillna(0)
                capital_inmovilizado = (df_stock_inv['Cantidad'] * df_stock_inv['Costo_Unitario']).sum()
            except Exception:
                capital_inmovilizado = 0

            st.markdown("**💰 Radiografía Financiera (Realidad del Mes)**")
            c1, c2 = st.columns(2)
            with c1: st.metric(label="💵 Ganancia NETA (Bolsillo)", value=f"${neta_actual:,.0f}", delta=f"${diferencia_neta:,.0f} vs Mes Pasado")
            with c2: st.metric(label="📉 Gastos Operativos", value=f"${op_actuales:,.0f}", delta=f"Ganancia Bruta: ${ganancia_bruta_actual:,.0f}", delta_color="off")
            
            st.divider()
            st.markdown("**📦 Patrimonio y Flujo de Capital**")
            c3, c4, c5 = st.columns(3)
            with c3: st.metric(label="🧱 Capital Inmovilizado (Stock)", value=f"${capital_inmovilizado:,.0f}", delta="Valor de costo en taller", delta_color="off")
            with c4: st.metric(label="⏳ En la Calle (A Cobrar)", value=f"${plata_en_calle:,.0f}", delta="Fiado a clientes", delta_color="off")
            with c5: st.metric(label="⚠️ Deuda a Prov. (A Pagar)", value=f"${deuda_prov:,.0f}", delta="Cuentas pendientes", delta_color="off")
            
            st.markdown("---")
            col_det_1, col_det_2 = st.columns(2)
            
            with col_det_1:
                st.markdown("**🎯 ¿Quién me debe?**")
                if not df_cobrar.empty:
                    temp_cobrar = df_cobrar.copy()
                    temp_cobrar['Cliente'] = temp_cobrar['Cliente'].astype(str).str.strip().str.upper()
                    detalle_clientes = temp_cobrar.groupby('Cliente')['Venta $'].sum().reset_index()
                    
                    try:
                        df_saldos_dash = leer_saldos()
                        if not df_saldos_dash.empty:
                            df_saldos_dash['Cliente'] = df_saldos_dash['Cliente'].astype(str).str.strip().str.upper()
                            saldos_agrupados = df_saldos_dash.groupby('Cliente')['Monto a Favor'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
                            detalle_clientes = pd.merge(detalle_clientes, saldos_agrupados, on='Cliente', how='left').fillna(0)
                            detalle_clientes['Venta $'] = detalle_clientes['Venta $'] - detalle_clientes['Monto a Favor']
                            detalle_clientes = detalle_clientes.drop(columns=['Monto a Favor'])
                    except:
                        pass
                    
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
        df_ventas = leer_ventas()
        try:
            df_saldos = leer_saldos()
        except:
            df_saldos = pd.DataFrame(columns=["Fecha", "Cliente", "Detalle", "Monto a Favor"])

        # ====================================================
        # OPCIÓN 1: COBRO A CLIENTES Y CANJES
        # ====================================================
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
                            leer_ventas.clear()
                            st.success(f"✅ {len(seleccion)} cobro(s) registrado(s) en {forma_cobro}. Excel actualizado.")
                        except Exception as e:
                            st.error(f"⚠️ Error al actualizar cobros: {e}")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para procesar.")

            # PANEL DE AJUSTES MANUALES Y FIFO
            st.markdown("---")
            st.markdown("### 🔄 Entregas a Cuenta y Ajustes Manuales")
            st.info("Anotá entregas de plata a cuenta. Después usá el botón azul para que el sistema cancele boletas viejas automáticamente.")
            
            lista_clientes = resumen_total['Cliente'].tolist() if 'resumen_total' in locals() and not resumen_total.empty else []
            if "REPUESTOS ARIEL" not in lista_clientes:
                lista_clientes.append("REPUESTOS ARIEL")
                
            with st.form("form_canje", clear_on_submit=True):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    hoy_arg = pd.Timestamp.now(tz='America/Argentina/Buenos_Aires').date()
                    fecha_canje = st.date_input("Fecha del Movimiento", value=hoy_arg, format="DD/MM/YYYY")
                    cliente_canje = st.selectbox("¿A qué cliente le ajustamos la cuenta?", lista_clientes)
                    tipo_movimiento = st.radio("Acción a realizar:", [
                        "Suma a Favor (Entregó Plata a cuenta o Mercadería)", 
                        "Restar del Saldo (Ajuste o compensación manual)"
                    ])
                with col_c2:
                    monto_canje = st.number_input("Monto Real Entregado ($)", min_value=0, step=1000)
                    detalle_canje = st.text_input("Detalle (Ej: $55.000 a cuenta, Ajuste manual)")
                    
                    monto_afip = st.number_input("Monto a Facturar en AFIP ($)", min_value=0, step=1000, help="Si dejás 0, no va a ARCA. Si tipeás un número, el sistema le pone 'SI' automático.")
                    st.caption("💡 El termómetro de la Categoría C sumará solo lo que anotes en la casilla de AFIP.")
                
                submit_canje = st.form_submit_button("🔄 Registrar Movimiento en Cuenta")
                
                if submit_canje:
                    if monto_canje > 0 and detalle_canje != "":
                        try:
                            monto_final = monto_canje if "Suma" in tipo_movimiento else -abs(monto_canje)
                            
                            if "Suma" in tipo_movimiento and monto_afip > 0:
                                es_facturado = "SI"
                                facturado_afip_final = monto_afip
                            else:
                                es_facturado = "NO"
                                facturado_afip_final = 0
                            
                            df_saldos_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", ttl=0)
                            
                            nueva_fila = pd.DataFrame([{
                                "Fecha": fecha_canje.strftime("%d/%m/%Y"), 
                                "Cliente": cliente_canje,
                                "Detalle": detalle_canje,
                                "Monto a Favor": monto_final,
                                "Facturado": es_facturado,
                                "Monto_Facturado_AFIP": facturado_afip_final
                            }])
                            
                            if df_saldos_actual.empty or len(df_saldos_actual.columns) == 0:
                                df_actualizado = nueva_fila
                            else:
                                df_actualizado = pd.concat([df_saldos_actual, nueva_fila], ignore_index=True)
                            
                            conn.update(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", data=df_actualizado)
                            leer_saldos.clear() 
                            
                            if "Suma" in tipo_movimiento:
                                st.success(f"✅ ¡Guardado! Se agregaron ${monto_canje:,.0f} a favor de {cliente_canje}.")
                                if es_facturado == "SI":
                                    st.info(f"🧾 ARCA: Se sumaron ${facturado_afip_final:,.0f} al termómetro de Mariano.")
                            else:
                                st.success(f"✅ ¡Ajuste aplicado! Se restaron ${monto_canje:,.0f} del saldo de {cliente_canje}.")
                        except Exception as e:
                            st.error(f"⚠️ Error al guardar el ajuste: {e}")
                    else:
                        st.warning("⚠️ Ingresá un monto mayor a $0 y detallá de qué se trata.")

            # BOTÓN INTELIGENTE (FIFO)
            st.markdown("#### 🤖 Liquidación Automática de Boletas")
            st.info("Elegí el cliente y cómo te pagó para cancelar sus deudas atrasadas. Las boletas marcadas para ARCA sumarán al termómetro de AFIP.")
            
            col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
            with col_f1:
                cliente_fifo = st.selectbox("Cliente a liquidar:", lista_clientes, key="cliente_fifo")
            with col_f2:
                metodo_pago_fifo = st.selectbox("Forma de pago de la entrega:", ["Efectivo", "Transferencia", "Mixto", "Canje"])
            with col_f3:
                if metodo_pago_fifo == "Canje":
                    st.write("") 
                    st.write("🚫 Canje no suma a AFIP")
                    marca_factura = "" 
                else:
                    st.write("") 
                    facturar_arca = st.checkbox("🧾 Facturar para ARCA", help="Le pondrá 'SI' en la columna Facturado")
                    marca_factura = "SI" if facturar_arca else ""
            
            if st.button(f"⚡ Liquidar Trabajos Viejos de {cliente_fifo} usando su Saldo", type="primary"):
                try:
                    df_v = conn.read(spreadsheet=SHEET_URL, worksheet="Ventas", ttl=0)
                    df_s = conn.read(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", ttl=0)
                    
                    saldo_disp = 0
                    if not df_s.empty:
                        mask_s = df_s['Cliente'].astype(str).str.strip().str.upper() == cliente_fifo.upper()
                        saldo_disp = pd.to_numeric(df_s.loc[mask_s, 'Monto a Favor'], errors='coerce').sum()
                        
                    if saldo_disp <= 0:
                        st.warning(f"⚠️ {cliente_fifo} no tiene Saldo a Favor disponible para compensar boletas.")
                    else:
                        mask_v = (df_v['Cliente'].astype(str).str.strip().str.upper() == cliente_fifo.upper()) & \
                                 (df_v['Estado_Cobro'].astype(str).str.strip().str.lower() == "cuenta corriente")
                        
                        trabajos_pendientes = df_v[mask_v].copy()
                        
                        if trabajos_pendientes.empty:
                            st.info(f"✅ {cliente_fifo} no tiene trabajos en Cuenta Corriente para pagar.")
                        else:
                            trabajos_pendientes['Venta $'] = pd.to_numeric(trabajos_pendientes['Venta $'], errors='coerce').fillna(0)
                            
                            saldo_usado = 0
                            boletas_pagadas = 0
                            
                            for idx, row in trabajos_pendientes.iterrows():
                                costo_trabajo = row['Venta $']
                                if costo_trabajo > 0 and saldo_disp >= costo_trabajo:
                                    df_v.at[idx, 'Estado_Cobro'] = 'Pagado'
                                    df_v.at[idx, 'Forma_de_pago'] = metodo_pago_fifo
                                    if marca_factura == "SI":
                                        df_v.at[idx, 'Facturado'] = "SI"
                                        df_v.at[idx, 'Monto_Facturado_AFIP'] = costo_trabajo
                                    
                                    saldo_disp -= costo_trabajo
                                    saldo_usado += costo_trabajo
                                    boletas_pagadas += 1
                                else:
                                    break
                                    
                            if boletas_pagadas > 0:
                                conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_v)
                                
                                nueva_resta = pd.DataFrame([{
                                    "Fecha": pd.Timestamp.now(tz='America/Argentina/Buenos_Aires').strftime("%d/%m/%Y"), 
                                    "Cliente": cliente_fifo,
                                    "Detalle": f"Liquidación automática ({metodo_pago_fifo})",
                                    "Monto a Favor": -abs(saldo_usado),
                                    "Facturado": "NO",
                                    "Monto_Facturado_AFIP": 0
                                }])
                                df_s_actualizado = pd.concat([df_s, nueva_resta], ignore_index=True)
                                conn.update(spreadsheet=SHEET_URL, worksheet="Saldos_y_Canjes", data=df_s_actualizado)
                                
                                leer_ventas.clear() 
                                leer_saldos.clear() 
                                st.success(f"🔥 ¡Éxito! Se liquidaron {boletas_pagadas} boleta(s) viejas usando ${saldo_usado:,.0f} del saldo de {cliente_fifo}.")
                                
                                import time
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.warning(f"⚠️ El saldo a favor de {cliente_fifo} (${saldo_disp:,.0f}) no alcanza para cubrir la totalidad de su boleta más vieja.")
                except Exception as e:
                    st.error(f"⚠️ Fallo crítico en la automatización: {e}")

        # ====================================================
        # OPCIÓN 2: PAGO A PROVEEDORES (UNIFICADO)
        # ====================================================
        if tipo_saldo == "Pago a Proveedor":
            df_deudas_ventas = df_ventas[df_ventas['Estado_Pago_Prov'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
            if not df_deudas_ventas.empty:
                df_deudas_ventas['Origen'] = 'Ventas'
                df_deudas_ventas['Monto_Deuda'] = pd.to_numeric(df_deudas_ventas['Compra $'], errors='coerce').fillna(0)
                df_deudas_ventas['Vehículo'] = df_deudas_ventas['Vehículo'].astype(str)
            else:
                df_deudas_ventas = pd.DataFrame()

            try:
                df_gastos = leer_gastos()
                df_deudas_gastos = df_gastos[df_gastos['Estado_Pago'].astype(str).str.strip().str.lower() == "cuenta corriente"].copy()
                if not df_deudas_gastos.empty:
                    df_deudas_gastos['Origen'] = 'Gastos'
                    df_deudas_gastos['Monto_Deuda'] = pd.to_numeric(df_deudas_gastos['Monto $'], errors='coerce').fillna(0)
                    df_deudas_gastos['Vehículo'] = "N/A (Stock/Inversión)"
                else:
                    df_deudas_gastos = pd.DataFrame()
            except:
                df_deudas_gastos = pd.DataFrame()

            if not df_deudas_ventas.empty or not df_deudas_gastos.empty:
                df_deudas_prov = pd.concat([df_deudas_ventas, df_deudas_gastos], ignore_index=True)
            else:
                df_deudas_prov = pd.DataFrame()

            if not df_deudas_prov.empty:
                # ---------------------------------------------------------
                # CIRUGÍA: ORDENAMIENTO CRONOLÓGICO ESTRICTO
                # ---------------------------------------------------------
                # 1. Convertimos la columna 'Fecha' (que es texto) a un formato de tiempo real (datetime)
                df_deudas_prov['Fecha_Orden'] = pd.to_datetime(df_deudas_prov['Fecha'], format="%d/%m/%Y %H:%M", errors='coerce').fillna(
                    pd.to_datetime(df_deudas_prov['Fecha'], format="%d/%m/%Y", errors='coerce')
                )
                
                # 2. Ordenamos toda la tabla usando esa nueva columna temporal
                df_deudas_prov = df_deudas_prov.sort_values(by='Fecha_Orden', ascending=True)
                
                # 3. Borramos la columna temporal auxiliar para que no se muestre en pantalla
                df_deudas_prov = df_deudas_prov.drop(columns=['Fecha_Orden'])
                # ---------------------------------------------------------

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
                            
                            if 'Estado_Pago_Prov' not in df_ventas_actual.columns: df_ventas_actual['Estado_Pago_Prov'] = ""
                            if 'Forma_Pago_Prov' not in df_ventas_actual.columns: df_ventas_actual['Forma_Pago_Prov'] = ""
                            if 'Forma_de_pago' not in df_gastos_actual.columns: df_gastos_actual['Forma_de_pago'] = ""
                            
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
                                    
                                if origen_sel == 'Gastos':
                                    mascara = (df_gastos_actual['Fecha'].astype(str) == fecha_sel) & \
                                              (df_gastos_actual['Proveedor'].astype(str).str.strip().str.upper() == prov_sel) & \
                                              (df_gastos_actual['Detalle'].astype(str) == det_sel)
                                    df_gastos_actual.loc[mascara, 'Estado_Pago'] = 'Pagado (Contado/Transf)'
                                    df_gastos_actual.loc[mascara, 'Forma_de_pago'] = forma_pago_prov
                                    hubo_cambios_gastos = True
                            
                            if hubo_cambios_ventas:
                                conn.update(spreadsheet=SHEET_URL, worksheet="Ventas", data=df_ventas_actual)
                                leer_ventas.clear() 
                            if hubo_cambios_gastos:
                                conn.update(spreadsheet=SHEET_URL, worksheet="Gastos", data=df_gastos_actual)
                                leer_gastos.clear() 
                                
                            st.success(f"✅ {len(seleccion_prov)} pago(s) registrado(s) en {forma_pago_prov}. Excel actualizado.")
                        except Exception as e:
                            st.error(f"⚠️ Error al actualizar pagos: {e}")
                    else:
                        st.warning("⚠️ Seleccioná al menos una deuda para pagar.")
            else:
                st.success("✅ No le debemos a ningún proveedor. ¡Cuentas al día!")
                st.divider()

    except Exception as e:
        st.error(f"⚠️ Error general al cargar las bases de datos: {e}")
# 12. BUSCADOR GLOBAL INTELIGENTE
st.divider()
st.header("🔍 Consultar Catálogo y Stock")

hoja_map = {
    "Embragues (Kits)": leer_kits, 
    "Crapodinas": leer_crapodinas, 
    "Distribución": leer_distribucion,
    "Stock Físico (Galpón)": leer_stock
}

tipo_busqueda = st.radio("¿Qué estás buscando?", list(hoja_map.keys()), horizontal=True)

# Llama a la memoria específica directamente
df_b = hoja_map[tipo_busqueda]()

busqueda = st.text_input("✍️ Búsqueda Inteligente (Ej: peugeot c4 bimasa):")

if busqueda:
    if not df_b.empty:
        busqueda_limpia = busqueda.lower()
        busqueda_limpia = re.sub(r'[/_\-]', ' ', busqueda_limpia)
        busqueda_limpia = ''.join(c for c in unicodedata.normalize('NFD', busqueda_limpia) if unicodedata.category(c) != 'Mn')
        palabras_buscadas = busqueda_limpia.split()
        
        texto_filas = df_b.fillna("").astype(str).apply(lambda x: ' '.join(x), axis=1).str.lower()
        texto_filas = texto_filas.str.replace(r'[/_\-]', ' ', regex=True)
        texto_filas = texto_filas.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        
        mask = pd.Series(True, index=df_b.index)
        for palabra in palabras_buscadas:
            mask &= texto_filas.str.contains(palabra, case=False, regex=False)
            
        df_filtrado = df_b[mask]
        
        if not df_filtrado.empty:
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

categoria_ver = st.selectbox("¿Qué categoría querés revisar?", 
    ["Kits de Embrague", "Forros", "Crapodinas", "Distribución", "Conjuntos de Embrague", "Volantes Bimasa", "Frenos", "Otros"])

try:
    df_stock_total = leer_stock()
    
    if not df_stock_total.empty:
        df_filtrado = df_stock_total[df_stock_total['Categoria'].astype(str).str.strip() == categoria_ver].copy()
        
        if not df_filtrado.empty:
            df_filtrado['Cantidad'] = pd.to_numeric(df_filtrado['Cantidad'], errors='coerce').fillna(0)
            
            def resaltar_critico(fila):
                if fila['Cantidad'] <= 1:
                    return ['background-color: #ffe6e6; color: #900000; font-weight: bold'] * len(fila)
                return [''] * len(fila)
            
            df_estilizado = df_filtrado.style.apply(resaltar_critico, axis=1).format({'Costo_Unitario': '${:,.0f}', 'Cantidad': '{:.0f}'})
            st.dataframe(df_estilizado, hide_index=True, use_container_width=True)
        else:
            st.info(f"Todavía no hay mercadería cargada en la categoría '{categoria_ver}'.")
    else:
        st.info("El galpón está vacío. No hay stock registrado en el sistema.")
except Exception as e:
    st.error(f"Falla al cargar el tablero de inventario: {e}")

st.divider()

st.divider()

with st.expander("📥 Abrir Panel UNIFICADO (Ingresa Stock y Gastos)"):
    # === EL INTERRUPTOR MÁGICO ===
    tipo_ingreso = st.radio("¿Qué vas a registrar?", ["📦 Inversión en Stock (Mercadería)", "💸 Gasto Operativo (Taller)"], horizontal=True)
    st.markdown("---")
    
    with st.form("form_ingreso_unificado", clear_on_submit=True):
        st.markdown("### 1. Datos Comerciales (Gastos y Proveedor)")
        col1, col2, col3, col4 = st.columns(4)
        with col1: fecha_compra = st.date_input("Fecha", format="DD/MM/YYYY")
        with col2: proveedor_compra = st.text_input("Proveedor (Ej: Icepar, Meta)")
        with col3: estado_pago = st.selectbox("Estado de Pago", ["Cuenta Corriente", "Pagado (Contado/Transf)"])
        with col4: forma_pago = st.selectbox("Forma de Pago", ["Aún no pagado", "Efectivo", "Transferencia"])

        if "Stock" in tipo_ingreso:
            # === RUTA A: INGRESO DE REPUESTOS ===
            st.markdown("### 2. Datos del Repuesto (Inventario)")
            col5, col6, col7, col8 = st.columns(4)
            with col5:
                categoria_rep = st.selectbox("Categoría", [
                    "Kits de Embrague", "Conjuntos de Embrague", "Volantes Bimasa", 
                    "Crapodinas", "Forros", "Frenos", "Distribución", "Otros"
                ])
            with col6:
                marca_opcion = st.selectbox("Marca", [
                    "Sachs", "LuK", "Valeo", "PHCValeo", "INA", 
                    "IAR Metal", "Termolite", "Frasle", "DBH", "THE", "Otra..."
                ])
                marca_otra = st.text_input("Si es 'Otra...', escribila acá:")
            with col7: codigo_rep = st.text_input("Código exacto")
            with col8: app_rep = st.text_input("Aplicación (Vehículos)")

            st.markdown("### 3. Costos y Cantidades")
            col9, col10 = st.columns(2)
            with col9: cantidad_compra = st.number_input("Cantidad de piezas ingresadas", min_value=1, step=1)
            with col10: precio_unitario = st.number_input("Costo Unitario ($)", min_value=0.0, step=1000.0)
            
        else:
            # === RUTA B: GASTO OPERATIVO ===
            st.markdown("### 2. Detalle del Gasto")
            col5, col6 = st.columns(2)
            with col5:
                categoria_gasto = st.selectbox("Categoría del Gasto:", [
                    "Publicidad / Marketing", 
                    "Cadetería / Fletes", 
                    "Insumos Taller / Limpieza", 
                    "Servicios (Luz, Internet, etc)", 
                    "Impuestos / Contable", 
                    "Otro Gasto Operativo"
                ])
            with col6:
                detalle_gasto = st.text_input("Detalle (Ej: Promo Instagram)")
                
            st.markdown("### 3. Monto Total")
            precio_unitario = st.number_input("Monto del Gasto ($)", min_value=0.0, step=1000.0)

        submit_unificado = st.form_submit_button("💾 Procesar Registro")

        if submit_unificado:
            if proveedor_compra == "":
                st.warning("⚠️ El Proveedor es obligatorio.")
            else:
                try:
                    df_gastos = conn.read(spreadsheet=SHEET_URL, worksheet="Gastos", ttl=0)
                    
                    if "Stock" in tipo_ingreso:
                        # LOGICA GUARDADO STOCK (Igual que antes)
                        marca_final = marca_otra.strip() if marca_opcion == "Otra..." else marca_opcion
                        if codigo_rep == "" or marca_final == "":
                            st.warning("⚠️ Marca y Código son obligatorios para Stock.")
                            st.stop()
                            
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
                        
                        monto_total = float(cantidad_compra * precio_unitario)
                        detalle_construido = f"{cantidad_compra}x {categoria_rep} {marca_final} ({codigo_rep})"
                        clasificacion_g = "Inversión en Stock"
                        categoria_g = "Compra de Mercadería"
                        msj_exito = f"✅ ¡Operación exitosa! Se sumaron {cantidad_compra}x al stock y se registró el gasto de ${monto_total:,.2f} en {proveedor_compra}."
                        leer_stock.clear()
                    
                    else:
                        # LOGICA GUARDADO GASTO OPERATIVO
                        monto_total = float(precio_unitario)
                        detalle_construido = detalle_gasto if detalle_gasto != "" else categoria_gasto
                        clasificacion_g = "Gasto Operativo"
                        categoria_g = categoria_gasto
                        msj_exito = f"✅ ¡Gasto Operativo registrado! ${monto_total:,.0f} en {categoria_g} ({proveedor_compra})."
                    
                    # GUARDADO COMÚN EN PESTAÑA GASTOS
                    nueva_fila_gasto = pd.DataFrame([{
                        'Fecha': fecha_compra.strftime("%d/%m/%Y"),
                        'Clasificacion': clasificacion_g,
                        'Categoria': categoria_g,
                        'Detalle': detalle_construido,
                        'Monto $': monto_total,
                        'Estado_Pago': estado_pago,
                        'Proveedor': proveedor_compra,
                        'Forma_de_pago': forma_pago
                    }])
                    
                    df_gastos = pd.concat([df_gastos, nueva_fila_gasto], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, worksheet="Gastos", data=df_gastos)
                    
                    leer_gastos.clear() 
                    st.success(msj_exito)
                    
                    import time
                    time.sleep(1.5)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"⚠️ Error en la operación: {e}")

st.divider()
st.subheader("🔄 Base de Datos Técnica (Actualización de Códigos)")

tipo_catalogo = st.selectbox("¿Qué base de datos vas a actualizar?", ["Kits de Embrague", "Crapodinas"])

with st.expander(f"Abrir panel para cargar Códigos de {tipo_catalogo}"):
    with st.form("form_actualizar_codigos", clear_on_submit=False):
        st.write(f"📝 **Modificar o agregar equivalencias para {tipo_catalogo}**")
        col1, col2 = st.columns(2)
        with col1: vehiculo_cat = st.text_input("Vehículo exacto (Ej: Peugeot 307 / 206)")
        with col2:
            if tipo_catalogo == "Kits de Embrague":
                detalle_cat = st.text_input("Motor (Ej: 2.0)")
                marcas_disponibles = ["LUK", "SACHS", "VALEO", "PHC_valeo", "ORIGINAL", "OTRA"]
            else: 
                detalle_cat = st.text_input("Descripción (Ej: Crapodina Mecánica)")
                marcas_disponibles = ["LUK", "SKF", "DBH", "THE", "ORIGINAL", "OTRA"]
                
        col3, col4 = st.columns(2)
        with col3: marca_cat = st.selectbox("¿De qué marca es el código?", marcas_disponibles)
        with col4: codigo_cat = st.text_input("Nuevo Código de Fábrica")
            
        submit_cat = st.form_submit_button("💾 Guardar Código en Base de Datos")
        
        if submit_cat:
            if vehiculo_cat != "" and codigo_cat != "":
                try:
                    if tipo_catalogo == "Kits de Embrague":
                        nombre_hoja = "Catalogo_Kits"
                        columnas_cat = ["Vehiculo", "Motor", "Proveedor", "Codigo_LUK", "Precio_LUK", "Codigo_SACHS", "Precio_SACHS", "Codigo_VALEO", "Precio_VALEO", "Codigo_PHC_valeo", "Precio_PHC_valeo", "Codigo_ORIGINAL", "Precio_ORIGINAL", "Codigo_OTRA", "Precio_OTRA"]
                        col_detalle_nombre = "Motor"
                        funcion_memoria = leer_kits
                    else:
                        nombre_hoja = "Catalogo_Crapodinas"
                        columnas_cat = ["Vehiculo", "Descripcion", "Codigo_LUK", "Precio_LUK", "Codigo_SKF", "Precio_SKF", "Codigo_DBH", "Precio_DBH", "Codigo_THE", "Precio_THE", "Codigo_ORIGINAL", "Precio_ORIGINAL", "Codigo_OTRA", "Precio_OTRA"]
                        col_detalle_nombre = "Descripcion"
                        funcion_memoria = leer_crapodinas

                    df_cat = conn.read(spreadsheet=SHEET_URL, worksheet=nombre_hoja, ttl=0)
                    
                    if df_cat.empty: df_cat = pd.DataFrame(columns=columnas_cat)
                    else: df_cat = df_cat[columnas_cat]
                    
                    df_cat['Veh_norm'] = df_cat['Vehiculo'].astype(str).str.strip().str.lower()
                    df_cat['Det_norm'] = df_cat[col_detalle_nombre].astype(str).str.strip().str.lower()
                    
                    veh_buscar = vehiculo_cat.strip().lower()
                    det_buscar = detalle_cat.strip().lower()
                    
                    mask = (df_cat['Veh_norm'] == veh_buscar) & (df_cat['Det_norm'] == det_buscar)
                    col_codigo = f"Codigo_{marca_cat}"
                    
                    df_cat[col_codigo] = df_cat[col_codigo].astype(object)
                    
                    if mask.any():
                        idx = df_cat[mask].index[0]
                        df_cat.at[idx, col_codigo] = codigo_cat
                        accion_msj = "actualizado"
                    else:
                        nueva_fila = {col: "" for col in columnas_cat}
                        nueva_fila["Vehiculo"] = vehiculo_cat
                        nueva_fila[col_detalle_nombre] = detalle_cat
                        nueva_fila[col_codigo] = codigo_cat
                        
                        df_nueva = pd.DataFrame([nueva_fila])
                        df_cat = pd.concat([df_cat, df_nueva], ignore_index=True)
                        accion_msj = "creado"
                    
                    df_cat = df_cat.drop(columns=['Veh_norm', 'Det_norm'])
                    conn.update(spreadsheet=SHEET_URL, worksheet=nombre_hoja, data=df_cat)
                    
                    funcion_memoria.clear() # Francotirador
                    
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

st.markdown("#### 🌡️ Termómetro Categoría C")
st.info("Actualizá tu facturación previa y el tope de la categoría. El sistema sumará automáticamente los trabajos nuevos marcados 'Con Factura'.")

col_t1, col_t2 = st.columns(2)
with col_t1:
    facturacion_previa = st.number_input("Facturación Previa 2026 ($):", min_value=0, value=4555572, step=100000, help="Ingresá lo que ya tenés facturado en el año hasta hoy.")
with col_t2:
    tope_cat_c = st.number_input("Tope Anual Categoría C ($):", min_value=1, value=24670494, step=100000)

facturado_app = 0
df_facturado_ventas = pd.DataFrame()
df_facturado_saldos = pd.DataFrame()

try:
    df_ventas_afip = leer_ventas()
    if 'Facturado' in df_ventas_afip.columns:
        df_facturado_ventas = df_ventas_afip[df_ventas_afip['Facturado'].astype(str).str.strip().str.upper() == "SI"].copy()
        if not df_facturado_ventas.empty:
            # ACÁ SE LEE LA COLUMNA NUEVA PARA EL TERMÓMETRO
            facturado_app += pd.to_numeric(df_facturado_ventas['Monto_Facturado_AFIP'], errors='coerce').fillna(0).sum()
            
    df_saldos_afip = leer_saldos()
    if 'Facturado' in df_saldos_afip.columns:
        df_facturado_saldos = df_saldos_afip[df_saldos_afip['Facturado'].astype(str).str.strip().str.upper() == "SI"].copy()
        if not df_facturado_saldos.empty:
            facturado_app += pd.to_numeric(df_facturado_saldos['Monto a Favor'], errors='coerce').fillna(0).sum()
            
except Exception as e:
    st.error(f"⚠️ Error calculando datos de AFIP: {e}")

total_facturado = facturacion_previa + facturado_app
porcentaje = (total_facturado / tope_cat_c) * 100 if tope_cat_c > 0 else 0

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.metric("Total Facturado Anual", f"${total_facturado:,.0f}", f"{porcentaje:.1f}% del tope")

st.progress(min(porcentaje / 100, 1.0))

if porcentaje >= 90: st.error("⚠️ ALERTA ROJA: Estás al límite de la Categoría C. Frena la facturación.")
elif porcentaje >= 75: st.warning("⚠️ Cuidado: Ya superaste el 75% del tope de la Categoría C.")
else: st.success("✅ Margen seguro para facturar.")

# --- 2. REPORTE PARA MARIANO ---
st.markdown("#### 📄 Reporte Contable para Mariano")

if not df_facturado_ventas.empty or not df_facturado_saldos.empty or facturacion_previa > 0:
    reporte_data = []

    reporte_data.append({
        'Fecha': (pd.Timestamp.now() - pd.Timedelta(hours=3)).strftime("%d/%m/%Y"),
        'Concepto': 'FACTURACIÓN PREVIA ACUMULADA',
        'Detalle': 'Arrastre anual declarado en ARCA',
        'Monto Facturado ($)': facturacion_previa
    })

    if not df_facturado_ventas.empty:
        for _, row in df_facturado_ventas.iterrows():
            reporte_data.append({
                'Fecha': row['Fecha'],
                'Concepto': f"Venta - {row['Cliente']}",
                'Detalle': row['Detalle'],
                # ACÁ SE LEE LA COLUMNA NUEVA PARA EL REPORTE DEL EXCEL
                'Monto Facturado ($)': pd.to_numeric(row['Monto_Facturado_AFIP'], errors='coerce')
            })

    if not df_facturado_saldos.empty:
        for _, row in df_facturado_saldos.iterrows():
            reporte_data.append({
                'Fecha': row['Fecha'],
                'Concepto': f"Ingreso a Cuenta - {row['Cliente']}",
                'Detalle': row['Detalle'],
                'Monto Facturado ($)': pd.to_numeric(row['Monto a Favor'], errors='coerce')
            })

    df_reporte_final = pd.DataFrame(reporte_data)
    total_reporte = df_reporte_final['Monto Facturado ($)'].sum()
    
    df_reporte_final.loc[len(df_reporte_final)] = {
        'Fecha': '',
        'Concepto': 'TOTAL ACUMULADO CATEGORÍA C',
        'Detalle': '',
        'Monto Facturado ($)': total_reporte
    }

    csv_mariano = df_reporte_final.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
    
    st.download_button(
        label="⬇️ Descargar Excel Contable para Mariano",
        data=csv_mariano,
        file_name=f"Reporte_ARCA_EmbraguesRosario.csv",
        mime="text/csv",
        type="primary"
    )
else:
    st.info("No hay datos suficientes para generar el reporte.")

# --- 3. CHECKLIST PLANES DE PAGO AFIP ---
st.markdown("#### 📅 Planes de Pago AFIP")
st.write("Control visual de cuotas debitadas, montos y vencimientos.")

col_p1, col_p2 = st.columns(2)

with col_p1:
    st.markdown("**Plan V664000 (17 Cuotas)**")
    montos_v66 = [
        50250.61, 50250.61, 50250.61, 50250.61, 50250.61, 
        50250.61, 50250.61, 50250.61, 50250.61, 50250.61, 
        50250.61, 50250.61, 50250.61, 50250.61, 50250.61, 
        50250.61, 50250.61
    ]
    fechas_v66 = [
        "16/03/2026", "16/04/2026", "16/05/2026", "16/06/2026", "16/07/2026",
        "16/08/2026", "16/09/2026", "16/10/2026", "16/11/2026", "16/12/2026",
        "16/01/2027", "16/02/2027", "16/03/2027", "16/04/2027", "16/05/2027",
        "16/06/2027", "16/07/2027"
    ]
    for i in range(1, 18):
        monto_str = f"${montos_v66[i-1]:,.2f}"
        fecha_str = fechas_v66[i-1]
        if i <= 6: 
            st.checkbox(f"Cuota {i} - {monto_str} (Vence: {fecha_str}) - Pagada", value=True, disabled=True, key=f"plan17_c{i}")
        else: 
            st.checkbox(f"Cuota {i} - {monto_str} (Vence: {fecha_str})", value=False, key=f"plan17_c{i}")

with col_p2:
    st.markdown("**Plan W391567 (5 Cuotas)**")
    montos_w39 = [59162.71, 59162.72, 59162.72, 59162.72, 59162.72]
    fechas_w39 = ["16/08/2026", "16/09/2026", "16/10/2026", "16/11/2026", "16/12/2026"]
    for i in range(1, 6):
        monto_str = f"${montos_w39[i-1]:,.2f}"
        fecha_str = fechas_w39[i-1]
        if i <= 1:
            st.checkbox(f"Cuota {i} - {monto_str} (Vence: {fecha_str}) - Pagada", value=True, disabled=True, key=f"plan5_c{i}")
        else:
            st.checkbox(f"Cuota {i} - {monto_str} (Vence: {fecha_str})", value=False, key=f"plan5_c{i}")

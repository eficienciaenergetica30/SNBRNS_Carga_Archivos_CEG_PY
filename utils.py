import pandas as pd

def buscar_indices_ep_enpf(df):
    """
    Busca los indices de "ENERGIA PORTEADA" y "ENERGIA NORMAL POR FALTANTE".
    Retorna un diccionario con las listas de indices.
    """
    indices_totales = {}
    
    # --- BUSQUEDA 1: ENERGIA PORTEADA ---
    # Convertimos a string, quitamos espacios y comparamos
    mask_porteada = df[1].astype(str).str.strip() == "ENERGIA PORTEADA"
    
    # Obtenemos la lista de indices directamente
    lista_porteada = df.index[mask_porteada].tolist()

    if lista_porteada:
        print(f"Se encontraron {len(lista_porteada)} registros de ENERGIA PORTEADA.")
        # Asignación directa (mucho más rápido que un for)
        indices_totales["energia_porteada"] = lista_porteada
    else:
        print("No se encontró 'ENERGIA PORTEADA'.")

    # --- BUSQUEDA 2: ENERGIA NORMAL POR FALTANTE ---
    mask_faltante = df[1].astype(str).str.strip() == "ENERGIA NORMAL POR FALTANTE"
    
    lista_faltante = df.index[mask_faltante].tolist()

    if lista_faltante:
        print(f"Se encontraron {len(lista_faltante)} registros de ENERGIA NORMAL POR FALTANTE.")
        indices_totales["energia_normal_por_faltante"] = lista_faltante
    else:
        print("No se encontró 'ENERGIA NORMAL POR FALTANTE'.")

    return indices_totales

def buscar_indices_et_en(df):
    """
    Busca los indices de "ENERGIA TOTAL" y "ENERGIA NORMAL".
    Retorna un diccionario con las listas de indices.
    """
    indices_totales = {}
    
    # --- BUSQUEDA 1: ENERGIA TOTAL ---
    mask_total = df[1].astype(str).str.strip() == "ENERGIA TOTAL"
    
    lista_total = df.index[mask_total].tolist()

    if lista_total:
        print(f"Se encontraron {len(lista_total)} registros de ENERGIA TOTAL.")
        indices_totales["energia_total"] = lista_total
    else:
        print("No se encontró 'ENERGIA TOTAL'.")

    # --- BUSQUEDA 2: ENERGIA NORMAL ---
    mask_normal = df[1].astype(str).str.strip() == "ENERGIA NORMAL"
    
    lista_normal = df.index[mask_normal].tolist()

    if lista_normal:
        print(f"Se encontraron {len(lista_normal)} registros de ENERGIA NORMAL.")
        indices_totales["energia_normal"] = lista_normal
    else:
        print("No se encontró 'ENERGIA NORMAL'.")

    return indices_totales



def buscar_periodo_facturacion(df):
    # print("Buscando período de facturación...")

    # 1. BUSCAMOS EN LA COLUMNA 1 (La B)
    # Convertimos a texto y limpiamos espacios para evitar errores
    buscar_fecha_facturacion = (
        df[0].astype(str).str.strip().str.startswith("Proceso del Permisionario:")
    )

    coincidencia = df.index[buscar_fecha_facturacion].tolist()

    if coincidencia:
        index_fecha = coincidencia[0]
        # print(f"Período de facturación encontrado en la fila {index_fecha}")

        # 2. EXTRAEMOS LA FILA COMPLETA
        # .iloc[fila, :] -> El ':' significa "todas las columnas"
        # Como la fila de facturación en la siguiente fia a la que buscamos, ponemos el +1 para sumar uno al index y asi obtener la fila correcta de la fecha
        fila_fecha_facturacion = df.iloc[index_fecha + 1 :]

        fecha = fila_fecha_facturacion.iloc[0, 0]

        mes_anio = str(fecha).split("Período")[0].strip()

        # print(mes_anio)

        return mes_anio
    return []

def extraer_rpu(sitio):
    """Extrae el RPU del formato PREFIX_RPU_NOMBRE"""
    try:
        partes = str(sitio).split("_")
        if len(partes) >= 2:
            return partes[1]  # El RPU está en la segunda posición
        return ""
    except:
        return ""
    
    pass

def corregir_fecha_mixta(valor):
    """
    Normaliza fechas que vienen con formatos mezclados (YYYY-DD-MM y MM/DD/YYYY).
    Retorna un objeto pd.Timestamp o NaT si falla.
    """
    # 1. Si ya es nulo (NaN/NaT), lo regresamos tal cual
    if pd.isna(valor):
        return pd.NaT

    # 2. Convertimos a string y quitamos horas (00:00:00)
    valor_str = str(valor).split(" ")[0]

    try:
        # CASO A: Fechas con guiones (YYYY-DD-MM -> El error "mentiroso" de Pandas)
        # Asumimos que si Pandas leyó guiones, invirtió día y mes.
        if "-" in valor_str:
            return pd.to_datetime(valor_str, format="%Y-%d-%m")

        # CASO B: Fechas con barras (MM/DD/YYYY -> El formato original "rebelde")
        elif "/" in valor_str:
            return pd.to_datetime(valor_str, format="%m/%d/%Y")

    except ValueError:
        pass  # Si falla el formato específico, pasamos al intento genérico

    # 3. Red de seguridad: Si no cayó en los casos anteriores, intento genérico
    return pd.to_datetime(valor, errors="coerce")

    pass


import os
import json
import logging
from hdbcli import dbapi

from utils import extraer_rpu


def load_env_from_dotenv():
    path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if not os.getenv(k):
                        os.environ[k] = v
    except Exception:
        pass


def get_hana_credentials():
    if not (
        os.getenv("HANA_HOST") and os.getenv("HANA_USER") and os.getenv("HANA_PASSWORD")
    ):
        vcap = os.getenv("VCAP_SERVICES")
        if vcap:
            try:
                data = json.loads(vcap)
                creds = None
                for _, services in data.items():
                    for s in services:
                        c = s.get("credentials", {})
                        if (
                            c.get("host")
                            and (c.get("user") or c.get("username"))
                            and c.get("password")
                        ):
                            creds = c
                            break
                    if creds:
                        break
                if creds:
                    os.environ.setdefault("HANA_HOST", str(creds.get("host")))
                    port_val = creds.get("port") or creds.get("port_tls")
                    if port_val is not None:
                        os.environ.setdefault("HANA_PORT", str(port_val))
                    os.environ.setdefault(
                        "HANA_USER", str(creds.get("user") or creds.get("username"))
                    )
                    os.environ.setdefault("HANA_PASSWORD", str(creds.get("password")))
                    if creds.get("schema"):
                        os.environ.setdefault("HANA_SCHEMA", str(creds.get("schema")))
            except Exception:
                pass
    return {
        "host": os.getenv("HANA_HOST"),
        "port": int(os.getenv("HANA_PORT")) if os.getenv("HANA_PORT") else None,
        "user": os.getenv("HANA_USER"),
        "password": os.getenv("HANA_PASSWORD"),
        "schema": os.getenv("HANA_SCHEMA"),
    }


def get_hana_connection():
    c = get_hana_credentials()
    missing = []
    for key in ["host", "user", "password", "schema"]:
        if not c.get(key):
            missing.append(key)
    if missing:
        raise ValueError(
            "Faltan variables de entorno para HANA: "
            + ", ".join(
                [
                    {
                        "host": "HANA_HOST",
                        "user": "HANA_USER",
                        "password": "HANA_PASSWORD",
                        "schema": "HANA_SCHEMA",
                    }[m]
                    for m in missing
                ]
            )
        )
    conn = dbapi.connect(
        address=c.get("host"),
        port=c.get("port") or 443,
        user=c.get("user"),
        password=c.get("password"),
        encrypt=True,
        sslValidateCertificate=False,
    )
    schema = c.get("schema")
    if schema:
        cur = conn.cursor()
        cur.execute(f'SET SCHEMA "{schema}"')
        cur.close()
    return conn


def insertar_detalle_facturacion(datos, batch_size=1000): # Agregamos batch_size
    conn = get_hana_connection()
    try:
        cursor = conn.cursor()
        schema = os.getenv("HANA_SCHEMA")
        table = os.getenv("TABLE_TFC")

        # 1. Truncate (Cuidado: esto borra todo lo anterior)
        cursor.execute(f'TRUNCATE TABLE "{schema}"."{table}"')
        
        sql = f"""INSERT INTO "{schema}"."{table}" (
            CL_RPU, ANIO_FAC, MES_FAC, 
            CONS_1P_CEG, CONS_2P_CEG, CONS_3P_CEG, CONS_CEG,
            DEM_1P_CEG, DEM_2P_CEG, DEM_3P_CEG, 
            FECHA, 
            DEM_TOT_1P_CEG, DEM_TOT_2P_CEG, DEM_TOT_3P_CEG
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

        # 2. Inserción por lotes (Chunks)
        # Esto evita timeouts si son muchos datos
        total_insertados = 0
        for i in range(0, len(datos), batch_size):
            lote = datos[i : i + batch_size]
            cursor.executemany(sql, lote)
            total_insertados += len(lote)
            logging.info(f"Insertando lote {i} a {i+len(lote)}...")

        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Carga finalizada. Total registros: {total_insertados}")
        return True, f"Se guardaron {total_insertados} registros."

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logging.error(f"Error DB: {str(e)}")
        return False, str(e)

def preparar_datos_para_bd(resultados):
    """
    Versión OPTIMIZADA: Usa vectorización de Pandas en lugar de iterrows.
    """
    if not resultados or "detalle_energia_porteada" not in resultados:
        return []

    df = resultados["detalle_energia_porteada"]

    if df is None or df.empty:
        return []

    # 1. Creamos una copia para no afectar el DF original en memoria
    df_upload = df.copy()

    # 2. Vectorización: Aplicamos la extracción de RPU a toda la columna de una vez
    # Esto es mucho más rápido que hacerlo dentro de un bucle for
    df_upload["CL_RPU"] = df_upload["Sitio"].apply(extraer_rpu)

    # 3. Aseguramos los tipos de datos (Casting masivo)
    # Convertimos a string las columnas que lo requieren
    cols_to_str = ["Año", "Mes", "Punta", "Fecha"]
    for col in cols_to_str:
        df_upload[col] = df_upload[col].astype(str)

    # 4. Seleccionamos y ordenamos las columnas EXACTAMENTE como las espera la BD
    # El orden aquí debe coincidir con el INSERT INTO (...)
    columnas_ordenadas = [
        "CL_RPU",
        "Año",
        "Mes",
        "Punta",  # CONS_1P_CEG
        "Intermedia",  # CONS_2P_CEG
        "Base",  # CONS_3P_CEG
        "Totales",  # CONS_CEG
        "Punta_PF",  # DEM_1P_CEG
        "Intermedia_PF",  # DEM_2P_CEG
        "Base_PF",  # DEM_3P_CEG
        "Fecha",
        "Demanda Punta (Total)",  # DEM_TOT_1P_CEG
        "Demanda Intermedia (Total)",  # DEM_TOT_2P_CEG
        "Demanda Base (Total)",  # DEM_TOT_3P_CEG
    ]

    # 5. Convertimos a lista de tuplas nativas de Python
    # .itertuples(index=False, name=None) es la forma más veloz de exportar a lista
    # name=None hace que devuelva tuplas simples (val1, val2...)
    df_final = df_upload[columnas_ordenadas]
    datos_para_bd = list(df_final.itertuples(index=False, name=None))

    return datos_para_bd


def get_sysuuid():
    """
    Genera un UUID único consultando SYSUUID de HANA.
    Retorna el UUID como string.
    """
    conn = get_hana_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SYSUUID FROM DUMMY")
        row = cursor.fetchone()
        cursor.close()
        val = row[0]
        if isinstance(val, (bytes, bytearray, memoryview)):
            return bytes(val).hex().upper()
        return str(val).replace("-", "").upper()
    finally:
        conn.close()
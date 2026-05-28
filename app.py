from flask import Flask, request, render_template, session, jsonify, flash
import pandas as pd
import db
import os
import secrets
import logging
import requests
from werkzeug.utils import secure_filename
import time

from utils import (
    buscar_periodo_facturacion,
    buscar_indices_ep_enpf,
    buscar_indices_et_en,
    corregir_fecha_mixta,
)
from db import preparar_datos_para_bd


app = Flask(__name__)

# 1: LLAVE FIJA (Para que BTP no invalide sesiones de mensajes flash) ---
app.secret_key = "clave_super_secreta_y_fija_para_produccion_123"

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.load_env_from_dotenv()


# ################ Energia Porteada 1 ####################
def extraer_info_energia_porteada(df, indices_ep_enpf):
    print("Extrayendo información de energía porteada...")

    lista_inicios = indices_ep_enpf.get("energia_porteada", [])
    lista_finales = indices_ep_enpf.get("energia_normal_por_faltante", [])

    if len(lista_inicios) != len(lista_finales):
        print("ERROR: Índices desiguales en Porteada.")
        return pd.DataFrame()  # Retorna vacío para no romper el flujo

    fragmentos_recolectados = []

    for inicio, fin in zip(lista_inicios, lista_finales):
        # Corte y limpieza
        nuevo_df = df.iloc[inicio + 1 : fin, 1:14].copy()
        columnas_a_mantener = [0, 1, 2, 3, 5, 6, 7, 8, 12]
        nuevo_df = nuevo_df.iloc[:, columnas_a_mantener]

        headers = [
            "Sitio",
            "Base",
            "Intermedia",
            "Punta",
            "Totales",
            "Base_PF",
            "Intermedia_PF",
            "Punta_PF",
            "Fecha",
        ]  # Renombré para evitar duplicados luego
        nuevo_df.columns = headers

        # Tratamiento de fechas
        nuevo_df["Fecha"] = nuevo_df["Fecha"].apply(corregir_fecha_mixta)
        nuevo_df.dropna(subset=["Fecha"], inplace=True)
        nuevo_df["Mes"] = nuevo_df["Fecha"].dt.strftime("%m")
        nuevo_df["Año"] = nuevo_df["Fecha"].dt.year
        nuevo_df["Fecha"] = nuevo_df["Fecha"].dt.strftime("%Y-%m-%d")

        nuevo_df.reset_index(drop=True, inplace=True)
        fragmentos_recolectados.append(nuevo_df)

    if fragmentos_recolectados:
        return pd.concat(fragmentos_recolectados, ignore_index=True)
    else:
        return pd.DataFrame()


def extraer_info_energia_normal(df, indices_et_en):
    print("Extrayendo información de energía normal...")

    # --- CORRECCIÓN DE LLAVES ---
    # El inicio del bloque es "ENERGIA TOTAL"
    lista_inicios = indices_et_en.get("energia_total", [])

    # El fin del bloque es "ENERGIA NORMAL"
    lista_finales = indices_et_en.get("energia_normal", [])

    # Depuración visual (Verás que ahora sí tienen datos)
    print(f"Indices inicio (Total): {lista_inicios}")
    print(f"Indices fin (Normal):   {lista_finales}")

    # 2. Validación
    if len(lista_inicios) != len(lista_finales):
        print(
            f"ERROR: Índices desiguales en Normal. Inicio: {len(lista_inicios)}, Fin: {len(lista_finales)}"
        )
        return pd.DataFrame()

    fragmentos_recolectados = []

    # 3. El bucle
    for inicio, fin in zip(lista_inicios, lista_finales):

        # Validación de orden: El inicio debe ser menor que el fin
        if inicio >= fin:
            print(
                f"Advertencia: Índice de inicio {inicio} es mayor o igual al fin {fin}. Saltando bloque."
            )
            continue

        # Selección de columnas H, I, J (Indices 7, 8, 9)
        # Nota: 7:10 toma 7, 8 y 9.
        nuevo_df = df.iloc[inicio + 1 : fin, 7:10].copy()

        headers = [
            "Demanda Base (Total)",
            "Demanda Intermedia (Total)",
            "Demanda Punta (Total)",
        ]

        # Verificar dimensiones antes de asignar
        if len(nuevo_df.columns) == len(headers):
            nuevo_df.columns = headers
            nuevo_df.reset_index(drop=True, inplace=True)
            fragmentos_recolectados.append(nuevo_df)
        else:
            print(
                f"Error de dimensiones: Se esperaban {len(headers)} columnas, se tienen {len(nuevo_df.columns)}"
            )

    # 4. Retorno final
    if fragmentos_recolectados:
        return pd.concat(fragmentos_recolectados, ignore_index=True)
    else:
        return pd.DataFrame()


# ################ Energia Porteada 2 ####################


def analizar_archivo_excel(file):
    print("Analizando archivo Excel...")

    resultados = {}

    try:

        # --- CAMBIO CRÍTICO AQUÍ ---
        # Usamos 'with' para que Python cierre el archivo automáticamente
        # apenas termine el bloque de código indentado.
        with pd.ExcelFile(file) as xls:

            sheet_names = xls.sheet_names
            # print(f"Hojas encontradas: {sheet_names}")

            # Verificamos que el archivo tenga al menos una hoja
            if len(sheet_names) > 0:
                print(
                    f"El archivo contiene {len(sheet_names)} hoja(s). Se procesará la hoja principal: '{sheet_names[0]}'."
                )

                # 1. Leemos SIEMPRE la primera hoja (o la que tú decidas)
                df_informacion = pd.read_excel(
                    xls, sheet_name=sheet_names[0], header=None
                )

                # 2. Buscamos la fecha de facturación
                resultados["fecha_facturacion"] = buscar_periodo_facturacion(
                    df_informacion
                )

                # 3. Buscamos TODOS los índices (Esto funciona haya 1 o N bloques de datos)
                indices_ep_enpf = buscar_indices_ep_enpf(df_informacion)
                indices_et_en = buscar_indices_et_en(df_informacion)

                # 4. Extracción Modular (Las nuevas funciones limpias)

                # Parte Izquierda (Energía Porteada) - Solo 2 argumentos
                df_porteada = extraer_info_energia_porteada(
                    df_informacion, indices_ep_enpf
                )

                # Parte Derecha (Demandas) - Solo 2 argumentos
                df_demandas = extraer_info_energia_normal(df_informacion, indices_et_en)

                # 5. Fusión de Datos
                # Verificamos que ambos DataFrames tengan datos
                if (
                    df_porteada is not None
                    and not df_porteada.empty
                    and df_demandas is not None
                    and not df_demandas.empty
                ):

                    if len(df_porteada) == len(df_demandas):
                        # Concatenamos lado a lado
                        df_completo = pd.concat([df_porteada, df_demandas], axis=1)

                        resultados["detalle_energia_porteada"] = df_completo
                        print(
                            "Éxito: Se generó la tabla completa uniendo Porteada y Demandas."
                        )
                    else:
                        print(
                            f"ERROR: Desajuste de filas. Porteada: {len(df_porteada)}, Demandas: {len(df_demandas)}"
                        )
                        resultados["detalle_energia_porteada"] = None
                else:
                    print(
                        "Advertencia: No se encontraron datos válidos en una de las secciones."
                    )
                    resultados["detalle_energia_porteada"] = None

            else:
                print("El archivo Excel no contiene hojas.")
    except Exception as e:
        print(f"Error analizando Excel: {e}")
        return None

    # --- AQUÍ EL ARCHIVO YA ESTÁ CERRADO ---
    # Como salimos del bloque 'with', Pandas soltó el archivo.
    # Ahora la función index() podrá hacer el os.remove() sin que Windows se queje.

    return resultados


@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    error = None
    filename_to_pass = None  # Variable para enviar al HTML

    if request.method == "POST":
        if "file" not in request.files:
            return "No file part", 400
        file = request.files["file"]

        if file.filename != "":
            try:
                # 1. Guardar archivo físico (Igual que App B)
                original_filename = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                unique_filename = f"{timestamp}_{original_filename}"
                filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(filepath)

                # 2. Guardamos el nombre para pasarlo al HTML
                filename_to_pass = unique_filename

                # 3. Procesar para mostrar la tabla (Previsualización)
                data_raw = analizar_archivo_excel(filepath)

                # Convertimos a dict solo para renderizar en HTML, NO guardamos en session
                if data_raw and data_raw.get("detalle_energia_porteada") is not None:
                    data = {
                        "fecha_facturacion": data_raw.get("fecha_facturacion", ""),
                        "detalle_energia_porteada": data_raw["detalle_energia_porteada"],
                    }

            except Exception as e:
                error = f"Error procesando el archivo: {str(e)}"
                # Si falla, intentamos borrar
                if "filepath" in locals() and os.path.exists(filepath):
                    os.remove(filepath)

    # Pasamos 'filename' al template para que el botón 'Guardar' sepa qué archivo procesar
    return render_template(
        "index.html", data=data, error=error, filename=filename_to_pass
    )


@app.route("/guardar", methods=["POST"])
def guardar_datos():
    """
    Recibe el nombre del archivo, lo busca en disco, lo procesa, guarda en BD y llama al servicio.
    """
    try:
        # --- CAMBIO 2: RECIBIR NOMBRE DE ARCHIVO DEL FRONTEND (NO DE SESIÓN) ---
        # Asegúrate de que tu JavaScript envíe: { "filename": "..." }
        req_data = request.get_json()
        filename = req_data.get("filename")

        if not filename:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No se recibió el nombre del archivo.",
                    }
                ),
                400,
            )

        filepath = os.path.join(UPLOAD_FOLDER, filename)

        if not os.path.exists(filepath):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "El archivo expiró o no existe. Cárgalo de nuevo.",
                    }
                ),
                400,
            )

        # 1. Re-procesar el archivo desde el disco
        # Esto evita el error de cookies de 4KB
        data_raw = analizar_archivo_excel(filepath)

        if not data_raw or data_raw.get("detalle_energia_porteada") is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Error al leer los datos del archivo.",
                    }
                ),
                400,
            )

        # 2. Preparar datos
        df = data_raw["detalle_energia_porteada"]
        resultados_struct = {
            "fecha_facturacion": data_raw.get("fecha_facturacion", ""),
            "detalle_energia_porteada": df,
        }

        datos_para_insertar = preparar_datos_para_bd(resultados_struct)

        if not datos_para_insertar:
            return (
                jsonify(
                    {"success": False, "message": "No hay datos válidos para insertar"}
                ),
                400,
            )

        # 3. Insertar en BD
        exito, mensaje_bd = db.insertar_detalle_facturacion(datos_para_insertar)

        if not exito:
            return jsonify({"success": False, "message": mensaje_bd})

        # ==============================================================================
        # 4. LLAMADA AL SERVICIO EXTERNO
        # ==============================================================================
        service_url = "https://snbrns-processes-hub-noisy-baboon-ll.cfapps.us10.hana.ondemand.com/snbrns-hub/hana/procedures/sp-snbrs-03"
        # service_url = "http://127.0.0.1:8000/snbrns-hub/hana/procedures/sp-snbrs-03"
        logging.info(f"Iniciando llamada al servicio: {service_url}")

        backend_success = False
        backend_message = ""

        try:
            rows_read = int(len(df)) if df is not None else 0
            rows_inserted_init = int(len(datos_para_insertar))
            execution_id_in = db.get_sysuuid()

            payload = {
                "rows_read": rows_read,
                "rows_inserted_init": rows_inserted_init,
                "execution_id_in": execution_id_in,
                "user": "CEG_USER",
            }
            response = requests.post(service_url, json=payload, timeout=300)

            if response.status_code in [200, 201]:
                try:
                    resp_json = response.json()
                    if (
                        isinstance(resp_json, dict)
                        and "success" in resp_json
                        and not resp_json["success"]
                    ):
                        backend_message = (
                            f"Servicio reportó error: {resp_json.get('message')}"
                        )
                        backend_success = False
                    else:
                        backend_success = True
                        backend_message = "Proceso completado con exito."
                except ValueError:
                    backend_success = True  # No es JSON pero es 200 OK
                    backend_message = "Proceso externo completado (No JSON)."
            else:
                backend_message = f"Error HTTP servicio: {response.status_code}"
                backend_success = False

        except Exception as e:
            backend_message = f"Error conectando al servicio: {str(e)}"
            backend_success = False

        # 5. LIMPIEZA FINAL
        try:
            os.remove(
                filepath
            )  # Borramos el archivo del disco para no llenar el servidor
        except:
            pass

        # 6. RETORNO
        if backend_success:
            return jsonify(
                {"success": True, "message": f"{mensaje_bd} {backend_message}"}
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "warning": True,
                    "message": f"{mensaje_bd}. ⚠️ Alerta: {backend_message}",
                }
            )

    except Exception as e:
        logging.error(f"Error crítico: {str(e)}")
        return jsonify({"success": False, "message": f"Error crítico: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)

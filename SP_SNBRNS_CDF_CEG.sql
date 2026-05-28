CREATE OR REPLACE PROCEDURE "SP_SNBRS_03"
(
    OUT success_flag INTEGER,
    OUT message NVARCHAR(1000)
)
LANGUAGE SQLSCRIPT
SQL SECURITY INVOKER 
AS
BEGIN

/*
  Nombre: SP_SNBRS_03
  Propósito: Carga de datos de facturación CEG desde tabla temporal a tabla RAW
  Fecha de creación: 2026-02-11
  Versión: 1.0
  Parámetros:
    - OUT success_flag: Indicador de éxito (1 = OK, 0 = error)
    - OUT message: Mensaje de error en caso de excepción
*/

    -- Declaraciones de variables
    DECLARE v_step NVARCHAR(200);

    /**********************************************/
    /* MANEJO DE ERRORES */
    /**********************************************/
    -- Manejador de errores: captura cualquier excepción SQL
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        -- Hacer rollback de la transacción
        ROLLBACK;
        -- Registrar o mostrar el error
        success_flag := 0;
        -- Mejora: Se agrega ::SQL_ERROR_MESSAGE para ver el error real de HANA
        message := v_step || '. Detalle: ' || ::SQL_ERROR_MESSAGE;
    END;

    -- Inicialización de variables de salida
    success_flag := 1;
    message := '';


    /**********************************************/
    /* UPSERT A GLOBALHITSS_EE_RAWFACTCEG */
    /**********************************************/
    v_step := 'Error al insertar datos en RAWFACTCEG';

    UPSERT "4A87446945C9455A8EAAFEC276742578"."GLOBALHITSS_EE_RAWFACTCEG_DEV"
    (
        "CL_RPU",
        "ANIO_FAC",
        "MES_FAC",
        "CONS_1P_CEG",
        "CONS_2P_CEG",
        "CONS_3P_CEG",
        "CONS_CEG",
        "DEM_1P_CEG",
        "DEM_2P_CEG",
        "DEM_3P_CEG",
        "FECHA",
        "DEM_TOT_1P_CEG",
        "DEM_TOT_2P_CEG",
        "DEM_TOT_3P_CEG"
    )
    SELECT
        LPAD("CL_RPU", 12, '0') AS "CL_RPU",
        "ANIO_FAC",
        LPAD("MES_FAC", 2, '0') AS "MES_FAC",
        "CONS_1P_CEG",
        "CONS_2P_CEG",
        "CONS_3P_CEG",
        "CONS_CEG",
        "DEM_1P_CEG",
        "DEM_2P_CEG",
        "DEM_3P_CEG",
        "FECHA",
        "DEM_TOT_1P_CEG",
        "DEM_TOT_2P_CEG",
        "DEM_TOT_3P_CEG"
    FROM "4A87446945C9455A8EAAFEC276742578"."GLOBALHITSS_EE_TEMPFACTCEG_DEV";



    /**********************************************/
    /* LIMPIEZA DE LA TABLA TEMPORAL */
    /**********************************************/
    v_step := 'Error al limpiar GLOBALHITSS_EE_TEMPFACTCEG';

    -- NOTA TÉCNICA: Se cambió TRUNCATE por DELETE.
    -- TRUNCATE hace commit implícito y anularía el ROLLBACK si algo fallara aquí.
    DELETE FROM "4A87446945C9455A8EAAFEC276742578"."GLOBALHITSS_EE_TEMPFACTCEG_DEV";

    -- Commit explícito
    COMMIT;

    -- ======================================================================
    -- CONFIGURAR SALIDA EXITOSA
    -- ======================================================================

    -- Mensaje de éxito
    message := 'Proceso facturación finalizado con éxito.';

END;
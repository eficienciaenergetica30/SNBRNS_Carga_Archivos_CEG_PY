# SNBRNS Carga Facturación Eléctrica CFE V2

Esta es una aplicación web construida con Flask.

## Requisitos Previos

*   Python 3.x
*   pip (gestor de paquetes de Python)

## Configuración del Entorno

Sigue estos pasos para configurar y ejecutar la aplicación en tu máquina local:

### 1. Crear un Entorno Virtual

Es recomendable utilizar un entorno virtual para aislar las dependencias del proyecto.

**Windows:**

```bash
python -m venv venv
```

**macOS/Linux:**

```bash
python3 -m venv venv
```

### 2. Activar el Entorno Virtual

**Windows (Git Bash):**

```bash
source venv/Scripts/activate
```

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**

```cmd
venv\Scripts\activate
```

**macOS/Linux:**

```bash
source venv/bin/activate
```

Una vez activado, deberías ver `(venv)` al inicio de tu línea de comandos.

### 3. Instalar Dependencias

Con el entorno virtual activado, instala las librerías necesarias ejecutando:

```bash
pip install -r requirements.txt
```

## Ejecución de la Aplicación

Para iniciar el servidor de desarrollo, ejecuta el siguiente comando:

```bash
python app.py
```

La aplicación estará disponible en tu navegador web en: `http://127.0.0.1:5000/`

## Estructura del Proyecto

*   `app.py`: Archivo principal de la aplicación Flask.
*   `templates/`: Directorio que contiene las plantillas HTML.
    *   `index.html`: Página de inicio.
*   `requirements.txt`: Lista de dependencias del proyecto.

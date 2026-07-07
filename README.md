# Traductor en vivo de pantalla (EN → ES)

Aplicación en Python para traducir texto en inglés que aparece en la pantalla hacia español, mostrando la traducción como superposición visual sin bloquear la interacción con otras aplicaciones.

## Estado actual del proyecto

La versión actual ya incluye:

- Captura de pantalla continua del área de trabajo de Windows.
- OCR con RapidOCR para detectar texto legible en la imagen.
- Traducción automática a español mediante Google Translate.
- Superposición transparente sobre la pantalla, con comportamiento click-through para no interrumpir el uso de otras ventanas o juegos.
- Bucle en segundo plano que procesa captura → OCR → traducción.
- Icono en la bandeja del sistema con opciones para pausar/reanudar, limpiar caché y salir.
- Caché de traducciones y filtrado de texto para reducir repeticiones y mejorar rendimiento.
- Configuración centralizada en config.py.

## Requisitos

- Windows 10/11
- Python 3.10 o superior
- Conexión a internet
- Paquetes listados en requirements.txt

## Instalación rápida

1. Abre una terminal en la carpeta del proyecto.
2. Ejecuta:

```bat
iniciar.bat
```

O bien, de forma manual:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> Nota: la primera ejecución puede tardar un poco porque se carga el motor OCR y sus modelos.

## Uso

1. Ejecuta iniciar.bat o python main.py.
2. La aplicación se inicia en segundo plano y aparece en la bandeja del sistema.
3. Si detecta texto en inglés en la pantalla, mostrará la traducción como subtítulo superpuesto.
4. En el icono de la bandeja puedes:
   - Pausar o reanudar la traducción.
   - Limpiar la caché de traducciones.
   - Salir de la aplicación.

## Configuración

Puedes ajustar el comportamiento desde config.py.

| Parámetro | Descripción | Valor por defecto |
|-----------|-------------|-------------------|
| capture_interval | Segundos entre ciclos de captura | 0.35 |
| ocr_confidence | Confianza mínima del OCR | 0.45 |
| overlay_font_size | Tamaño de fuente del overlay | 12 |
| click_through | Permite que los clics pasen a través del overlay | True |
| hide_when_empty | Oculta el overlay si no hay texto visible | True |
| raise_interval_sec | Frecuencia con la que el overlay vuelve al frente | 1.5 |

## Limitaciones actuales

- Está pensado para Windows y usa APIs específicas de Windows.
- La calidad depende del tamaño, contraste y legibilidad del texto en pantalla.
- Requiere internet para traducir.
- El rendimiento puede variar según la potencia de la CPU y la cantidad de texto visible.

## Estructura del proyecto

```text
├── main.py          # Punto de entrada de la aplicación
├── config.py        # Configuración central
├── capture.py       # Captura de pantalla
├── ocr.py           # Motor OCR
├── translate.py     # Traducción automática
├── overlay.py       # Ventana superpuesta transparente
├── worker.py        # Lógica de procesamiento en segundo plano
├── tray.py          # Icono de bandeja del sistema
├── utils.py         # Utilidades compartidas
├── iniciar.bat      # Script de inicio rápido
└── requirements.txt
```

## Qué falta por agregar

Aunque la base ya funciona, aún se pueden añadir mejoras como:

- Selección de idioma de destino y origen configurable.
- Opción para elegir una región específica de la pantalla a traducir.
- Interfaz gráfica para cambiar configuración sin editar el código.
- Mejor manejo de errores y logs más detallados.
- Soporte para otros idiomas además de inglés/español.
- Optimización adicional para bajar el consumo de CPU.


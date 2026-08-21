# CAD LIBRE

Aplicación de escritorio para Windows 10/11 que **abre archivos DWG, los
visualiza (zoom, pan, selección, capas) y los exporta a DXF conservando
exactamente toda la información geoespacial**: coordenadas X/Y/Z originales,
sistema de coordenadas (CRS/EPSG), capas, bloques, textos, polilíneas y cotas.

## Funciones

- Visor con zoom, pan, selección de entidades y panel de capas.
- **Temas**: fondo oscuro, blanco, gris claro o azul noche. Sobre fondo claro,
  los colores luminosos del DXF (blanco, amarillo) se oscurecen *al pintarlos*
  para que sigan siendo legibles; el archivo nunca se modifica.
- **Selección de entidades como en AutoCAD**: clic sobre una línea o polilínea
  para elegirla, Ctrl+clic para añadir más. Exporta exactamente eso, sin
  arrastrar las cotas ni los textos que caen alrededor.
- **Exportación selectiva**: todo el dibujo, o las entidades seleccionadas, o
  las capas visibles y/o un contorno dibujado a mano alzada.
- **Salida a Shapefile** además de DXF: genera `_poligonos`, `_lineas`,
  `_puntos` y `_textos`, cada uno con su `.prj`, listos para QGIS y ArcGIS.
- **Salida a PDF** vectorial: conserva los colores del dibujo, oscureciendo
  solo los tonos que no se leerían sobre papel blanco. Al pie anota la escala
  de impresión, el EPSG y el rango de coordenadas.
- El área a exportar se marca **a mano alzada o como rectángulo**.
- **Actualización automática** desde GitHub Releases.

## Garantía de fidelidad

- La conversión DWG→DXF la hace **ODA File Converter** (el mismo motor que usa
  QGIS): es una traducción 1:1 del contenido, sin mover, escalar ni rotar nada.
- Exportando **todo el dibujo**, la app nunca reescribe el DXF convertido: es
  una copia binaria exacta de ese resultado.
- Exportando **una selección**, se abre el DXF y se *eliminan* las entidades
  descartadas en vez de reconstruir el documento. Lo que queda conserva sus
  coordenadas, el GEODATA, los estilos y las definiciones de capa intactos.
- La versión DXF de salida es siempre R2010+ (por defecto R2018), porque el
  objeto **GEODATA** —la georreferenciación embebida— solo existe desde R2010.
- Junto al DXF se generan automáticamente:
  - `<nombre>.prj` — WKT ESRI del CRS detectado. **ArcGIS lo asocia solo** al
    DXF del mismo nombre.
  - `<nombre>.georref.txt` / `.json` — EPSG detectado e instrucciones para
    asignar el SRC en QGIS (p. ej. `EPSG:9377` MAGNA-SIRGAS Origen Nacional).

## Arquitectura

```
CAD LIBRE/
├── app/                  # Interfaz: Electron + React + TypeScript (electron-vite)
│   └── src/
│       ├── main/         # Proceso principal (ventana, diálogos, IPC, spawn de Python)
│       ├── preload/      # Puente seguro renderer ↔ main
│       └── renderer/src/ # React: Visor (canvas 2D), PanelCapas, barras
├── cadlibre/             # Motor Python
│   ├── converter.py      # DWG→DXF vía ODA File Converter o dwg2dxf (LibreDWG)
│   ├── geodata.py        # Lectura GEODATA/EPSG, generación .prj y metadatos
│   ├── render_json.py    # Geometría del visor (aplanado de curvas, bloques, cotas)
│   ├── filtro.py         # Exportación selectiva por capas, contorno o selección
│   ├── shp.py            # Exportación a shapefile (polígonos/líneas/puntos/textos)
│   ├── pdf.py            # Exportación a PDF vectorial con contraste para papel
│   ├── geometria2d.py    # Punto-en-polígono para el contorno libre
│   ├── verify.py         # Inventario: capas, bloques, entidades, extensión
│   ├── bridge.py         # CLI JSON que consume Electron (abrir/exportar/motor)
│   ├── pipeline.py       # Orquestación para uso por consola
│   └── gui.py            # GUI alternativa en Tkinter (respaldo sin Node)
└── tests/                # crear_dxf_prueba.py: predio georreferenciado EPSG:9377
```

El visor compila la geometría a objetos `Path2D` agrupados por capa+color y
solo re-traza con la transformación de cámara en cada cuadro: los dibujos
grandes se manejan con poca memoria y el JSON del motor se escribe en
streaming.

## Requisitos

1. **Node.js 18+** y **Python 3.10+**.
2. **ODA File Converter** (gratuito) para abrir DWG:
   <https://www.opendesign.com/guestfiles/oda_file_converter>
   — sin él, la app igualmente abre y exporta DXF. Se detecta solo en
   `C:\Program Files\ODA\`.

## Desarrollo

```powershell
# Motor Python (una vez)
uv venv .venv
uv pip install --python .venv -r requirements.txt

# Interfaz
cd app
npm install
npm run dev        # arranca Electron con recarga
```

## Compilar instalador

El motor Python se empaqueta primero con PyInstaller (así el usuario final no
necesita tener Python instalado) y luego se construye la app:

```powershell
.venv\Scripts\pyinstaller.exe --noconfirm --name cadlibre-motor `
  --collect-all pyproj --collect-submodules ezdxf `
  --distpath build_motor/dist --workpath build_motor/work `
  --specpath build_motor motor_entrada.py

cd app
npm run dist       # instalador NSIS en app/dist/
```

## Publicar una versión

`npm run release` compila y sube el instalador a GitHub Releases; las copias
ya instaladas lo detectan y se actualizan solas.

```powershell
$env:GH_TOKEN = (gh auth token)
cd app
npm version minor --no-git-tag-version   # o patch / major
npm run release
```

## Uso por consola (sin interfaz)

```powershell
.venv\Scripts\python.exe -m cadlibre plano.dwg -o carpeta_salida
```

Convierte, genera `.prj` + metadatos e imprime el inventario (capas, bloques,
entidades y extensión espacial) para verificar que nada se perdió.

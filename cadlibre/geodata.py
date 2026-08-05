# -*- coding: utf-8 -*-
"""Lectura de la georreferenciación del DXF y generación de archivos laterales.

El DXF (R2010+) almacena la georreferenciación en el objeto GEODATA vinculado
al espacio modelo. Este módulo lo lee SIN reescribir el DXF (solo lectura,
para garantizar que el dibujo no se toque) y produce:

- <nombre>.prj                 → WKT ESRI; ArcGIS lo asocia automáticamente
                                 al DXF del mismo nombre y QGIS puede leerlo.
- <nombre>.georref.txt         → metadatos legibles con el EPSG detectado e
                                 instrucciones para asignarlo en QGIS/ArcGIS.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import ezdxf

try:
    from pyproj import CRS
    from pyproj.enums import WktVersion
    _HAY_PYPROJ = True
except Exception:  # pragma: no cover - pyproj es opcional
    _HAY_PYPROJ = False

# WKT ESRI de respaldo para los CRS más usados en catastro colombiano,
# por si pyproj no está disponible.
_WKT_RESPALDO = {
    9377: 'PROJCS["MAGNA-SIRGAS_2018_Origen-Nacional",GEOGCS["GCS_MAGNA-SIRGAS_2018",DATUM["D_MAGNA-SIRGAS_2018",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",5000000.0],PARAMETER["False_Northing",2000000.0],PARAMETER["Central_Meridian",-73.0],PARAMETER["Scale_Factor",0.9992],PARAMETER["Latitude_Of_Origin",4.0],UNIT["Meter",1.0]]',
    4686: 'GEOGCS["GCS_MAGNA",DATUM["D_MAGNA",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
    3116: 'PROJCS["MAGNA_Colombia_Bogota",GEOGCS["GCS_MAGNA",DATUM["D_MAGNA",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",1000000.0],PARAMETER["False_Northing",1000000.0],PARAMETER["Central_Meridian",-74.07750791666666],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",4.596200416666666],UNIT["Meter",1.0]]',
}


@dataclass
class InfoGeorref:
    """Georreferenciación detectada en un DXF."""
    tiene_geodata: bool = False
    epsg: int | None = None
    nombre_crs: str | None = None
    wkt_original: str | None = None      # definición tal cual viene en el DXF
    wkt_esri: str | None = None          # WKT listo para el .prj
    punto_diseno: tuple | None = None    # coordenada del dibujo (design point)
    punto_referencia: tuple | None = None  # coordenada geográfica asociada
    unidades: str | None = None
    observaciones: list[str] = field(default_factory=list)


def leer_georreferenciacion(ruta_dxf: str) -> InfoGeorref:
    """Extrae la georreferenciación de un DXF abriéndolo SOLO en lectura."""
    info = InfoGeorref()
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    geodata = msp.get_geodata()
    if geodata is None:
        info.observaciones.append(
            "El archivo no contiene objeto GEODATA (georreferenciación embebida). "
            "Las coordenadas de las entidades se conservan igual; si conoce el "
            "CRS del plano, asígnelo manualmente en QGIS/ArcGIS."
        )
        return info

    info.tiene_geodata = True
    definicion = (geodata.coordinate_system_definition or "").strip()
    info.wkt_original = definicion or None

    if geodata.dxf.hasattr("design_point"):
        info.punto_diseno = tuple(geodata.dxf.design_point)
    if geodata.dxf.hasattr("reference_point"):
        info.punto_referencia = tuple(geodata.dxf.reference_point)

    # 1) Intento con el parser propio de ezdxf
    try:
        epsg, _xy = geodata.get_crs()
        if epsg:
            info.epsg = int(epsg)
    except Exception:
        pass
    # 2) Regex sobre la definición (WKT1 AUTHORITY, WKT2 ID, o "EPSG:n")
    if info.epsg is None and definicion:
        info.epsg = _extraer_epsg(definicion)
    # 3) pyproj puede identificar el CRS a partir del WKT completo
    if info.epsg is None and definicion and _HAY_PYPROJ:
        try:
            crs = CRS.from_wkt(definicion)
            codigo = crs.to_epsg(min_confidence=25)
            if codigo:
                info.epsg = int(codigo)
        except Exception:
            pass

    _completar_wkt(info)
    return info


def _extraer_epsg(texto: str) -> int | None:
    patrones = (
        r'AUTHORITY\s*\[\s*"EPSG"\s*,\s*"?(\d{4,6})"?\s*\]',
        r'ID\s*\[\s*"EPSG"\s*,\s*(\d{4,6})\s*\]',
        r'EPSG[:\s"]*(\d{4,6})',
    )
    for patron in patrones:
        coincidencias = re.findall(patron, texto, flags=re.IGNORECASE)
        if coincidencias:
            return int(coincidencias[-1])  # la última AUTHORITY es la del CRS completo
    return None


def _completar_wkt(info: InfoGeorref) -> None:
    """Obtiene nombre y WKT ESRI del CRS detectado."""
    if _HAY_PYPROJ:
        crs = None
        try:
            if info.epsg:
                crs = CRS.from_epsg(info.epsg)
            elif info.wkt_original:
                crs = CRS.from_wkt(info.wkt_original)
        except Exception:
            crs = None
        if crs is not None:
            info.nombre_crs = crs.name
            try:
                info.wkt_esri = crs.to_wkt(WktVersion.WKT1_ESRI, pretty=False)
            except Exception:
                info.wkt_esri = crs.to_wkt(pretty=False)
            return
    if info.epsg in _WKT_RESPALDO:
        info.wkt_esri = _WKT_RESPALDO[info.epsg]
        info.nombre_crs = re.match(r'\w+\["([^"]+)"', info.wkt_esri).group(1)
    elif info.wkt_original and info.wkt_original.upper().startswith(("PROJCS", "GEOGCS", "PROJCRS", "GEOGCRS")):
        # La definición del DXF ya es WKT: se usa tal cual.
        info.wkt_esri = info.wkt_original


def escribir_sidecars(ruta_dxf: str, info: InfoGeorref) -> list[str]:
    """Genera .prj y metadatos junto al DXF. Devuelve las rutas creadas.

    Nunca modifica el DXF.
    """
    creados: list[str] = []
    base = os.path.splitext(ruta_dxf)[0]

    if info.wkt_esri:
        ruta_prj = base + ".prj"
        with open(ruta_prj, "w", encoding="utf-8") as f:
            f.write(info.wkt_esri)
        creados.append(ruta_prj)

    ruta_txt = base + ".georref.txt"
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(_texto_metadatos(ruta_dxf, info))
    creados.append(ruta_txt)

    ruta_json = base + ".georref.json"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "archivo": os.path.basename(ruta_dxf),
                "tiene_geodata": info.tiene_geodata,
                "epsg": info.epsg,
                "nombre_crs": info.nombre_crs,
                "punto_diseno": info.punto_diseno,
                "punto_referencia": info.punto_referencia,
                "wkt": info.wkt_esri,
                "observaciones": info.observaciones,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    creados.append(ruta_json)
    return creados


def _texto_metadatos(ruta_dxf: str, info: InfoGeorref) -> str:
    nombre = os.path.basename(ruta_dxf)
    lineas = [
        "GEORREFERENCIACIÓN — generado por CAD LIBRE",
        "=" * 50,
        f"Archivo DXF : {nombre}",
    ]
    if info.epsg:
        lineas.append(f"EPSG        : {info.epsg}")
    if info.nombre_crs:
        lineas.append(f"CRS         : {info.nombre_crs}")
    if info.punto_diseno:
        lineas.append(f"Punto diseño     : {info.punto_diseno}")
    if info.punto_referencia:
        lineas.append(f"Punto referencia : {info.punto_referencia}")
    if not info.tiene_geodata:
        lineas.append("El DWG no traía georreferenciación embebida (GEODATA).")
    lineas.append("")
    lineas.append("Las coordenadas del dibujo NO fueron modificadas: cada entidad")
    lineas.append("conserva sus X, Y, Z originales del DWG.")
    lineas.append("")
    if info.epsg or info.wkt_esri:
        lineas += [
            "Cómo abrirlo en la posición correcta:",
            "- ArcGIS / ArcMap: lee automáticamente el archivo .prj que está",
            "  junto al DXF (mismo nombre). No requiere pasos adicionales.",
            "- QGIS: al cargar el DXF, si pregunta por el SRC elija "
            + (f"EPSG:{info.epsg}." if info.epsg else "el CRS indicado arriba."),
            "  O clic derecho sobre la capa → «Establecer SRC de la capa».",
        ]
    for obs in info.observaciones:
        lineas.append("Nota: " + obs)
    return "\n".join(lineas) + "\n"

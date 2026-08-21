# -*- coding: utf-8 -*-
"""Puente entre la aplicación Electron y el motor Python.

Cada comando imprime UNA línea JSON en stdout (utf-8):

    python -m cadlibre.bridge abrir <archivo.dwg|dxf> --workdir <carpeta>
    python -m cadlibre.bridge exportar <archivo.dxf> <destino.dxf>
    python -m cadlibre.bridge motor

`abrir` convierte el DWG a DXF (1:1, sin transformar nada) en la carpeta de
trabajo, lee la georreferenciación y genera el JSON de geometría del visor.
`exportar` copia el DXF convertido al destino elegido —sin reescribirlo— y
genera a su lado el .prj y los metadatos de georreferenciación.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback

from .converter import VERSION_SALIDA_DEFECTO, convertir_dwg_a_dxf, detectar_motor
from .filtro import exportar_filtrado
from .pdf import exportar_pdf
from .shp import exportar_shp
from .geodata import escribir_sidecars, leer_georreferenciacion
from .render_json import extraer_geometria
from .verify import inventariar


def _responder(datos: dict, codigo: int = 0):
    sys.stdout.write(json.dumps(datos, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(codigo)


def _fallar(mensaje: str):
    _responder({"ok": False, "error": mensaje}, 1)


def cmd_abrir(args):
    ruta = os.path.abspath(args.archivo)
    if not os.path.isfile(ruta):
        _fallar(f"No existe el archivo: {ruta}")
    os.makedirs(args.workdir, exist_ok=True)
    extension = os.path.splitext(ruta)[1].lower()

    if extension == ".dwg":
        ruta_dxf = convertir_dwg_a_dxf(ruta, args.workdir, VERSION_SALIDA_DEFECTO)
    elif extension == ".dxf":
        ruta_dxf = ruta  # se visualiza tal cual; nunca se reescribe
    else:
        _fallar(f"Extensión no soportada: {extension}")

    info = leer_georreferenciacion(ruta_dxf)
    inv = inventariar(ruta_dxf)
    nombre = os.path.splitext(os.path.basename(ruta_dxf))[0]
    ruta_geom = os.path.join(args.workdir, nombre + ".geom.json")
    resumen_geom = extraer_geometria(ruta_dxf, ruta_geom)

    _responder({
        "ok": True,
        "origen": ruta,
        "dxf": ruta_dxf,
        "geometria": ruta_geom,
        "georref": {
            "tieneGeodata": info.tiene_geodata,
            "epsg": info.epsg,
            "nombreCrs": info.nombre_crs,
            "observaciones": info.observaciones,
        },
        "inventario": {
            "versionDxf": inv.version_dxf,
            "unidades": inv.unidades,
            "extmin": inv.extmin,
            "extmax": inv.extmax,
            "capas": len(inv.capas),
            "bloques": len(inv.bloques),
            "entidades": inv.total_entidades,
            "porTipo": dict(inv.entidades),
        },
        "resumenGeometria": resumen_geom,
    })


def cmd_exportar(args):
    origen = os.path.abspath(args.dxf)
    destino = os.path.abspath(args.destino)
    if not os.path.isfile(origen):
        _fallar(f"No existe el DXF convertido: {origen}")
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    capas = json.loads(args.capas) if args.capas else None
    handles = json.loads(args.handles) if args.handles else None
    area = None
    if args.poligono:
        area = json.loads(args.poligono)  # [[x, y], …] contorno libre
    elif args.area:
        partes = [float(v) for v in args.area.split(",")]
        if len(partes) != 4:
            _fallar("El área debe ser x1,y1,x2,y2")
        area = list(partes)

    # La georreferenciación se lee del ORIGEN: el filtrado la conserva, pero
    # el formato SHP no la lleva dentro y necesita el WKT para su .prj.
    info_origen = leer_georreferenciacion(origen)

    if args.formato == "pdf":
        r = exportar_pdf(
            origen, destino, capas, area, args.modo_area, handles,
            args.tamano_pdf, info_origen.epsg,
        )
        _responder({
            "ok": True,
            "formato": "pdf",
            "pdf": r.ruta,
            "epsg": info_origen.epsg,
            "nombreCrs": info_origen.nombre_crs,
            "resumenPdf": {
                "entidades": r.entidades,
                "textos": r.textos,
                "omitidas": r.omitidas,
                "escala": r.escala,
            },
        })

    if args.formato == "shp":
        base = os.path.splitext(destino)[0]
        r = exportar_shp(
            origen, base, info_origen.wkt_esri, capas, area, args.modo_area, handles
        )
        _responder({
            "ok": True,
            "formato": "shp",
            "base": base,
            "archivos": r.archivos,
            "epsg": info_origen.epsg,
            "nombreCrs": info_origen.nombre_crs,
            "resumenShp": {
                "poligonos": r.poligonos,
                "lineas": r.lineas,
                "puntos": r.puntos,
                "textos": r.textos,
                "omitidas": r.omitidas,
                "total": r.total,
            },
        })

    filtrado = None
    if capas is not None or area is not None or handles is not None:
        # Exportación selectiva: se eliminan del DXF las entidades que no
        # pasan el filtro; lo conservado queda idéntico al original.
        r = exportar_filtrado(origen, destino, capas, area, args.modo_area, handles)
        filtrado = {
            "conservadas": r.conservadas,
            "eliminadas": r.eliminadas,
            "capasExcluidas": r.capas_excluidas,
            "sinGeometria": r.sin_geometria,
        }
    elif origen != destino:
        shutil.copy2(origen, destino)  # copia binaria exacta: nada se reescribe

    info = leer_georreferenciacion(destino)
    laterales = escribir_sidecars(destino, info)
    _responder({
        "ok": True,
        "formato": "dxf",
        "dxf": destino,
        "laterales": laterales,
        "epsg": info.epsg,
        "nombreCrs": info.nombre_crs,
        "filtrado": filtrado,
    })


def cmd_motor(_args):
    motor = detectar_motor()
    _responder({
        "ok": True,
        "motor": motor.nombre if motor else None,
        "ejecutable": motor.ejecutable if motor else None,
    })


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="cadlibre.bridge")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("abrir")
    p.add_argument("archivo")
    p.add_argument("--workdir", required=True)
    p.set_defaults(func=cmd_abrir)

    p = sub.add_parser("exportar")
    p.add_argument("dxf")
    p.add_argument("destino")
    p.add_argument("--capas", help="JSON con la lista de capas a conservar")
    p.add_argument("--area", help="Rectángulo x1,y1,x2,y2 en coordenadas del dibujo")
    p.add_argument("--poligono", help="JSON [[x,y], …] con el contorno libre dibujado")
    p.add_argument("--handles", help="JSON con los handles de las entidades elegidas")
    p.add_argument(
        "--formato", default="dxf", choices=["dxf", "shp", "pdf"],
        help="dxf: copia fiel; shp: shapefiles para QGIS/ArcGIS; pdf: plano vectorial",
    )
    p.add_argument(
        "--tamano-pdf", default="A4", choices=["A4", "A3"],
        help="Tamaño de hoja del PDF",
    )
    p.add_argument(
        "--modo-area", default="contenida", choices=["contenida", "intersecta"],
        help="contenida: solo lo totalmente dentro; intersecta: también lo que toca el borde",
    )
    p.set_defaults(func=cmd_exportar)

    p = sub.add_parser("motor")
    p.set_defaults(func=cmd_motor)

    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        _fallar(str(e))


if __name__ == "__main__":
    main()

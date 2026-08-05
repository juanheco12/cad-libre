# -*- coding: utf-8 -*-
"""Punto de entrada.

Sin argumentos abre la interfaz gráfica. Con archivos, funciona por consola:

    python -m cadlibre plano.dwg [otro.dwg ...] [-o CARPETA] [-v ACAD2018]
"""

from __future__ import annotations

import argparse
import sys


def main(argv=None):
    # La consola de Windows suele usar cp1252; se fuerza UTF-8 tolerante
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="cadlibre",
        description="Convierte DWG a DXF conservando toda la georreferenciación.",
    )
    parser.add_argument("archivos", nargs="*", help="Archivos .dwg o .dxf")
    parser.add_argument("-o", "--salida", help="Carpeta de salida (por defecto, la del archivo)")
    parser.add_argument(
        "-v", "--version-dxf", default="ACAD2018",
        choices=["ACAD2010", "ACAD2013", "ACAD2018"],
        help="Versión DXF de salida (todas conservan GEODATA)",
    )
    args = parser.parse_args(argv)

    if not args.archivos:
        from .gui import main as gui_main
        gui_main()
        return 0

    from .pipeline import procesar

    fallos = 0
    for ruta in args.archivos:
        try:
            resultado = procesar(ruta, args.salida, args.version_dxf)
            print(resultado.reporte())
            print()
        except Exception as e:
            fallos += 1
            print(f"✘ {ruta}: {e}", file=sys.stderr)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())

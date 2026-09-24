# -*- coding: utf-8 -*-
"""Pruebas de la deducción del sistema de coordenadas."""

import os
import sys
import warnings

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cadlibre.crs_detect import info_crs, sugerir_crs  # noqa: E402


def probar():
    # ---- Un plano real de Montería solo encaja en el origen nacional ----
    monteria = sugerir_crs(4687666.496, 2534381.933)
    assert len(monteria) == 1, [c.epsg for c in monteria]
    assert monteria[0].epsg == 9377, monteria[0]
    assert abs(monteria[0].lon + 75.8403) < 0.001, monteria[0].lon
    assert abs(monteria[0].lat - 8.8253) < 0.001, monteria[0].lat

    # ---- En la zona Bogotá hay varios candidatos y manda el vigente ----
    bogota = sugerir_crs(1000000, 1000000)
    assert bogota[0].epsg == 3116, [c.epsg for c in bogota]
    assert 21897 in [c.epsg for c in bogota], "falta el datum antiguo"

    # ---- Dibujos en coordenadas locales: no se inventa un origen ----
    assert sugerir_crs(0, 0) == [], "un dibujo en el origen no es georreferenciable"
    assert sugerir_crs(250, 180) == []
    assert sugerir_crs(-430.5, 912.75) == []

    # ---- Coordenadas fuera de Colombia no producen sugerencias ----
    assert sugerir_crs(500000, 4600000) == [], "eso está en España, no en Colombia"

    # ---- Un plano ya en grados se reconoce como WGS84 ----
    grados = sugerir_crs(-75.84, 8.82)
    assert grados and grados[0].epsg == 4326, [c.epsg for c in grados]

    # ---- La definición para el visor no lleva la marca que rompe proj4js ----
    datos = info_crs(9377)
    assert datos["epsg"] == 9377
    assert "MAGNA" in datos["nombre"], datos["nombre"]
    assert datos["proj4"] and "+type=crs" not in datos["proj4"], datos["proj4"]
    assert "+proj=tmerc" in datos["proj4"]
    assert "+x_0=5000000" in datos["proj4"], "falso este del origen nacional"
    # El WKT del .prj sí conserva el código EPSG
    assert datos["wkt"] and "MAGNA" in datos["wkt"]

    print("crs: TODAS LAS PRUEBAS PASARON")


if __name__ == "__main__":
    probar()

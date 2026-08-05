# -*- coding: utf-8 -*-
"""Genera un DXF de prueba georreferenciado en MAGNA-SIRGAS / Origen Nacional
(EPSG:9377) con capas, bloques, textos, polilíneas, arcos y una cota, para
verificar que CAD LIBRE conserva todo al visualizar y exportar."""

import os
import sys

import ezdxf
from ezdxf import units

WKT_9377 = (
    'PROJCS["MAGNA-SIRGAS 2018 / Origen-Nacional",'
    'GEOGCS["MAGNA-SIRGAS 2018",DATUM["Marco_Geocentrico_Nacional_de_Referencia_2018",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",4],PARAMETER["central_meridian",-73],'
    'PARAMETER["scale_factor",0.9992],'
    'PARAMETER["false_easting",5000000],PARAMETER["false_northing",2000000],'
    'UNIT["metre",1],AUTHORITY["EPSG","9377"]]'
)

# Predio ficticio cerca de Bogotá en coordenadas planas Origen Nacional
X0, Y0 = 4871500.0, 2091300.0


def crear(ruta: str) -> None:
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.M
    msp = doc.modelspace()

    doc.layers.add("LINDEROS", color=3)
    doc.layers.add("CONSTRUCCION", color=1)
    doc.layers.add("TEXTOS", color=2)
    doc.layers.add("MOJONES", color=4)
    doc.layers.add("COTAS", color=6)

    # Georreferenciación embebida (GEODATA)
    geodata = msp.new_geodata()
    geodata.setup_local_grid(design_point=(X0, Y0), reference_point=(-74.1, 4.82))
    geodata.coordinate_system_definition = WKT_9377
    geodata.dxf.horizontal_unit_scale = 1.0
    geodata.dxf.vertical_unit_scale = 1.0

    # Lindero del predio (polilínea cerrada con coordenadas reales)
    lindero = [
        (X0, Y0), (X0 + 84.25, Y0 + 3.10), (X0 + 88.60, Y0 + 61.75),
        (X0 + 6.40, Y0 + 66.20), (X0, Y0),
    ]
    msp.add_lwpolyline(lindero, dxfattribs={"layer": "LINDEROS", "closed": True})

    # Construcción con elevación (Z) para verificar que Z se conserva
    msp.add_lwpolyline(
        [(X0 + 20, Y0 + 15), (X0 + 45, Y0 + 15), (X0 + 45, Y0 + 32), (X0 + 20, Y0 + 32)],
        dxfattribs={"layer": "CONSTRUCCION", "closed": True, "elevation": 2585.35},
    )
    msp.add_circle((X0 + 60, Y0 + 45), radius=4.5, dxfattribs={"layer": "CONSTRUCCION"})
    msp.add_arc((X0 + 15, Y0 + 50), radius=8, start_angle=0, end_angle=180,
                dxfattribs={"layer": "CONSTRUCCION"})

    # Bloque de mojón insertado en las esquinas
    bloque = doc.blocks.new(name="MOJON")
    bloque.add_circle((0, 0), radius=0.8)
    bloque.add_line((-1.2, 0), (1.2, 0))
    bloque.add_line((0, -1.2), (0, 1.2))
    for i, punto in enumerate(lindero[:-1], start=1):
        msp.add_blockref("MOJON", punto, dxfattribs={"layer": "MOJONES"})
        msp.add_text(
            f"M-{i}", height=1.8, dxfattribs={"layer": "TEXTOS"},
        ).set_placement((punto[0] + 1.5, punto[1] + 1.5))

    msp.add_text(
        "PREDIO LA ESPERANZA — 000100020045000", height=3.0,
        dxfattribs={"layer": "TEXTOS"},
    ).set_placement((X0 + 8, Y0 + 70))

    # Cota lineal sobre el lindero sur
    dim = msp.add_linear_dim(
        base=(X0, Y0 - 8), p1=lindero[0], p2=lindero[1],
        dxfattribs={"layer": "COTAS"},
    )
    dim.render()

    doc.saveas(ruta)
    print(f"DXF de prueba creado: {ruta}")
    print(f"  Esquina inicial del lindero: E={X0:,.2f}  N={Y0:,.2f} (EPSG:9377)")


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "datos", "predio_magna9377.dxf"
    )
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    crear(destino)

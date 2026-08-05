# -*- coding: utf-8 -*-
"""Pruebas de la exportación selectiva (capas y área)."""

import os
import sys
import tempfile

import ezdxf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cadlibre.filtro import exportar_filtrado  # noqa: E402
from cadlibre.geodata import leer_georreferenciacion  # noqa: E402

WKT_9377 = (
    'PROJCS["MAGNA-SIRGAS 2018 / Origen-Nacional",GEOGCS["MAGNA-SIRGAS 2018",'
    'DATUM["Marco_Geocentrico_Nacional_de_Referencia_2018",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",4],PARAMETER["central_meridian",-73],'
    'PARAMETER["scale_factor",0.9992],PARAMETER["false_easting",5000000],'
    'PARAMETER["false_northing",2000000],UNIT["metre",1],'
    'AUTHORITY["EPSG","9377"]]'
)


def crear_dxf(ruta):
    doc = ezdxf.new("R2018", setup=True)
    doc.layers.add("LINDEROS", color=1)
    doc.layers.add("ROTULO", color=2)
    msp = doc.modelspace()
    geo = msp.new_geodata()
    geo.coordinate_system_definition = WKT_9377
    geo.dxf.design_point = (4879000, 2100000, 0)
    geo.dxf.reference_point = (-74.1, 4.9, 0)
    # Lindero dentro del área de interés
    msp.add_lwpolyline(
        [(4879000, 2100000), (4879100, 2100000), (4879100, 2100080), (4879000, 2100000)],
        dxfattribs={"layer": "LINDEROS"},
    )
    # Lindero lejos (fuera del área)
    msp.add_lwpolyline(
        [(4880000, 2101000), (4880050, 2101000), (4880050, 2101050)],
        dxfattribs={"layer": "LINDEROS"},
    )
    # Texto del rótulo (capa a excluir), dentro del área
    msp.add_text(
        "ROTULO DEL PLANO", dxfattribs={"layer": "ROTULO", "height": 5.0}
    ).set_placement((4879050, 2100040))
    doc.saveas(ruta)


def probar():
    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "origen.dxf")
        crear_dxf(origen)

        # --- Filtro por capas ---
        destino1 = os.path.join(tmp, "solo_linderos.dxf")
        r1 = exportar_filtrado(origen, destino1, capas=["LINDEROS"])
        d1 = ezdxf.readfile(destino1)
        tipos1 = [e.dxftype() for e in d1.modelspace()]
        assert r1.conservadas == 2 and r1.eliminadas == 1, (r1.conservadas, r1.eliminadas)
        assert tipos1.count("LWPOLYLINE") == 2 and "TEXT" not in tipos1, tipos1
        assert "ROTULO" in r1.capas_excluidas
        # La definición de capa sigue existiendo aunque sus entidades no
        assert "ROTULO" in [c.dxf.name for c in d1.layers]

        # --- Filtro por área (contenida) ---
        destino2 = os.path.join(tmp, "area.dxf")
        r2 = exportar_filtrado(
            origen, destino2, area=(4878950, 2099950, 4879200, 2100100)
        )
        d2 = ezdxf.readfile(destino2)
        tipos2 = [e.dxftype() for e in d2.modelspace()]
        assert sorted(tipos2) == ["LWPOLYLINE", "TEXT"], tipos2

        # --- Área + capas combinadas ---
        destino3 = os.path.join(tmp, "area_capas.dxf")
        r3 = exportar_filtrado(
            origen, destino3, capas=["LINDEROS"],
            area=(4878950, 2099950, 4879200, 2100100),
        )
        d3 = ezdxf.readfile(destino3)
        entidades3 = list(d3.modelspace())
        assert len(entidades3) == 1 and entidades3[0].dxftype() == "LWPOLYLINE"

        # --- Coordenadas idénticas a las originales ---
        original = ezdxf.readfile(origen)
        pol_orig = [e for e in original.modelspace().query("LWPOLYLINE")][0]
        pol_filt = entidades3[0]
        puntos_orig = [tuple(p) for p in pol_orig.get_points()]
        puntos_filt = [tuple(p) for p in pol_filt.get_points()]
        assert puntos_orig == puntos_filt, "¡Las coordenadas cambiaron!"

        # --- La georreferenciación sobrevive al filtrado ---
        for destino in (destino1, destino2, destino3):
            info = leer_georreferenciacion(destino)
            assert info.tiene_geodata, f"GEODATA perdida en {destino}"
            assert info.epsg == 9377, f"EPSG perdido en {destino}: {info.epsg}"

        # --- Modo intersecta incluye la polilínea que toca el borde ---
        destino4 = os.path.join(tmp, "cruce.dxf")
        exportar_filtrado(
            origen, destino4, area=(4879050, 2100010, 4879990, 2100990),
            modo_area="intersecta",
        )
        d4 = ezdxf.readfile(destino4)
        assert len(list(d4.modelspace())) >= 2

    print("filtro: TODAS LAS PRUEBAS PASARON")


if __name__ == "__main__":
    probar()

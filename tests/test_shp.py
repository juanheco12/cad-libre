# -*- coding: utf-8 -*-
"""Pruebas de la exportación a shapefile y de la selección por entidades."""

import os
import sys
import tempfile

import ezdxf
import shapefile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cadlibre.filtro import exportar_filtrado  # noqa: E402
from cadlibre.geodata import leer_georreferenciacion  # noqa: E402
from cadlibre.shp import exportar_shp  # noqa: E402
from tests.test_filtro import WKT_9377, crear_dxf  # noqa: E402


def crear_dxf_rico(ruta):
    """DXF con lindero cerrado, línea suelta, cota, texto y punto."""
    doc = ezdxf.new("R2018", setup=True)
    doc.layers.add("LINDEROS", color=1)
    doc.layers.add("COTAS", color=2)
    msp = doc.modelspace()
    geo = msp.new_geodata()
    geo.coordinate_system_definition = WKT_9377
    geo.dxf.design_point = (4879000, 2100000, 0)
    geo.dxf.reference_point = (-74.1, 4.9, 0)

    # Lindero cerrado (debe salir como POLÍGONO)
    lindero = msp.add_lwpolyline(
        [(4879000, 2100000), (4879100, 2100000), (4879100, 2100080), (4879000, 2100080)],
        close=True, dxfattribs={"layer": "LINDEROS"},
    )
    # Línea abierta (debe salir como LÍNEA)
    linea = msp.add_line(
        (4879200, 2100000), (4879300, 2100050), dxfattribs={"layer": "LINDEROS"}
    )
    # Cota: lo que el usuario NO quiere exportar
    cota = msp.add_linear_dim(
        base=(4879050, 2099950), p1=(4879000, 2100000), p2=(4879100, 2100000),
        dxfattribs={"layer": "COTAS"},
    )
    cota.render()
    texto = msp.add_text(
        "LOTE 1", dxfattribs={"layer": "LINDEROS", "height": 5.0}
    ).set_placement((4879050, 2100040))
    punto = msp.add_point((4879000, 2100000), dxfattribs={"layer": "LINDEROS"})

    doc.saveas(ruta)
    return {
        "lindero": lindero.dxf.handle,
        "linea": linea.dxf.handle,
        "texto": texto.dxf.handle,
        "punto": punto.dxf.handle,
    }


def leer_shp(base, sufijo):
    ruta = f"{base}_{sufijo}.shp"
    if not os.path.exists(ruta):
        return None
    r = shapefile.Reader(ruta)
    registros = [dict(zip([c[0] for c in r.fields[1:]], reg)) for reg in r.records()]
    formas = r.shapes()
    r.close()
    return registros, formas


def probar():
    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "plano.dxf")
        handles = crear_dxf_rico(origen)

        # ---- Selección manual: solo el lindero, sin la cota ----
        destino = os.path.join(tmp, "solo_lindero.dxf")
        r = exportar_filtrado(origen, destino, handles=[handles["lindero"]])
        d = ezdxf.readfile(destino)
        entidades = list(d.modelspace())
        assert len(entidades) == 1, [e.dxftype() for e in entidades]
        assert entidades[0].dxftype() == "LWPOLYLINE"
        assert entidades[0].dxf.handle == handles["lindero"]
        assert r.conservadas == 1 and r.eliminadas >= 3, (r.conservadas, r.eliminadas)

        # Las coordenadas del lindero no cambiaron
        orig = ezdxf.readfile(origen).entitydb[handles["lindero"]]
        assert [tuple(p) for p in orig.get_points()] == \
               [tuple(p) for p in entidades[0].get_points()]
        # Y la georreferenciación sobrevive
        assert leer_georreferenciacion(destino).epsg == 9377

        # ---- Selección de varias entidades ----
        destino2 = os.path.join(tmp, "dos.dxf")
        exportar_filtrado(
            origen, destino2, handles=[handles["lindero"], handles["linea"]]
        )
        tipos = sorted(e.dxftype() for e in ezdxf.readfile(destino2).modelspace())
        assert tipos == ["LINE", "LWPOLYLINE"], tipos

        # ---- Exportación completa a SHP ----
        base = os.path.join(tmp, "salida")
        rs = exportar_shp(origen, base, WKT_9377)
        assert rs.poligonos >= 1, rs
        assert rs.lineas >= 1, rs
        assert rs.puntos >= 1, rs
        assert rs.textos >= 1, rs

        # El lindero cerrado salió como polígono, con coordenadas exactas
        registros, formas = leer_shp(base, "poligonos")
        assert any(reg["capa"] == "LINDEROS" for reg in registros), registros
        pts = formas[0].points
        xs = [p[0] for p in pts]
        assert min(xs) == 4879000 and max(xs) == 4879100, (min(xs), max(xs))

        # El texto viaja con su contenido como atributo. Ojo: exportando todo
        # también sale el texto de la cota, así que se busca el que interesa.
        registros_txt, formas_txt = leer_shp(base, "textos")
        indice = next(i for i, reg in enumerate(registros_txt)
                      if reg["texto"] == "LOTE 1")
        assert registros_txt[indice]["capa"] == "LINDEROS"
        assert formas_txt[indice].points[0] == (4879050.0, 2100040.0),             formas_txt[indice].points
        # La cota aporta su propio texto: por eso la selección manual importa
        assert any(reg["capa"] == "COTAS" for reg in registros_txt), registros_txt

        # Cada shapefile lleva su .prj
        prj = base + "_poligonos.prj"
        assert os.path.exists(prj)
        assert "9377" in open(prj, encoding="utf-8").read()

        # ---- SHP solo de lo seleccionado: sin la cota ----
        base2 = os.path.join(tmp, "sel")
        rs2 = exportar_shp(origen, base2, WKT_9377, handles=[handles["lindero"]])
        assert rs2.poligonos == 1 and rs2.lineas == 0, rs2
        assert rs2.textos == 0 and rs2.puntos == 0, rs2
        assert leer_shp(base2, "lineas") is None, "no debe crearse el shp de líneas"

    print("shp + seleccion: TODAS LAS PRUEBAS PASARON")


if __name__ == "__main__":
    probar()

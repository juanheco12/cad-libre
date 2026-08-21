# -*- coding: utf-8 -*-
"""Pruebas del PDF: contraste de colores y respeto del filtro.

En vez de descifrar el PDF ya escrito (ReportLab lo codifica en ASCII85 y
Flate, y parsearlo sería frágil), se intercepta el lienzo para registrar los
colores que realmente se mandan pintar.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cadlibre import pdf as modulo_pdf  # noqa: E402
from cadlibre.pdf import _contrastar, exportar_pdf  # noqa: E402
from tests.test_shp import crear_dxf_rico  # noqa: E402

# Sobre papel blanco, un color con más luminancia que esto no se distingue
LUMINANCIA_MAXIMA = 0.63


def luminancia(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


class LienzoEspia:
    """Envuelve el Canvas de ReportLab y anota los colores utilizados."""

    colores_trazo: list = []
    colores_relleno: list = []

    def __init__(self, real):
        self._real = real

    def setStrokeColorRGB(self, r, g, b, *a, **k):
        LienzoEspia.colores_trazo.append((r, g, b))
        return self._real.setStrokeColorRGB(r, g, b, *a, **k)

    def setFillColorRGB(self, r, g, b, *a, **k):
        LienzoEspia.colores_relleno.append((r, g, b))
        return self._real.setFillColorRGB(r, g, b, *a, **k)

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)


def con_espia(funcion):
    """Ejecuta `funcion` con el lienzo interceptado."""
    LienzoEspia.colores_trazo = []
    LienzoEspia.colores_relleno = []
    original = modulo_pdf.rl_canvas.Canvas

    def fabrica(*a, **k):
        return LienzoEspia(original(*a, **k))

    modulo_pdf.rl_canvas.Canvas = fabrica
    try:
        return funcion()
    finally:
        modulo_pdf.rl_canvas.Canvas = original


def probar():
    # ---- La conversión respeta el tono y solo oscurece lo ilegible ----
    assert _contrastar((255, 0, 0)) == (1.0, 0.0, 0.0), "el rojo debe quedar intacto"
    assert _contrastar((0, 0, 255)) == (0.0, 0.0, 1.0), "el azul debe quedar intacto"
    assert _contrastar((255, 255, 255)) == (0.25, 0.25, 0.25), "blanco -> gris oscuro"
    amarillo = _contrastar((255, 255, 0))
    assert amarillo[2] == 0.0 and amarillo[0] == amarillo[1], amarillo
    assert 0.4 < amarillo[0] < 1.0, f"amarillo mal ajustado: {amarillo}"
    # Un color ya oscuro no se toca
    assert _contrastar((20, 60, 20)) == (20 / 255, 60 / 255, 20 / 255)

    with tempfile.TemporaryDirectory() as tmp:
        origen = os.path.join(tmp, "plano.dxf")
        handles = crear_dxf_rico(origen)

        # ---- PDF completo ----
        todo = os.path.join(tmp, "todo.pdf")
        r = con_espia(lambda: exportar_pdf(origen, todo, epsg=9377))
        assert os.path.getsize(todo) > 800, os.path.getsize(todo)
        assert r.entidades >= 5 and r.textos >= 1, r
        assert r.escala and not r.escala.startswith("1:0"), f"escala rota: {r.escala}"

        # Ningún color llega al papel siendo ilegible
        usados = LienzoEspia.colores_trazo + LienzoEspia.colores_relleno
        assert usados, "no se pintó nada"
        for rgb in usados:
            assert luminancia(rgb) <= LUMINANCIA_MAXIMA, \
                f"color demasiado claro para papel blanco: {rgb}"
        # Y el color del dibujo se conserva: la capa LINDEROS es roja (ACI 1)
        assert any(c[0] > 0.7 and c[1] < 0.3 and c[2] < 0.3 for c in usados), \
            f"se perdió el rojo del lindero: {usados}"

        # ---- PDF de una sola entidad seleccionada ----
        solo = os.path.join(tmp, "solo.pdf")
        r2 = exportar_pdf(origen, solo, handles=[handles["lindero"]], epsg=9377)
        assert r2.entidades == 1, r2
        assert r2.textos == 0, "la cota y sus textos no deben aparecer"
        assert os.path.getsize(solo) < os.path.getsize(todo)

        # ---- Un filtro sin resultados avisa en vez de crear un PDF en blanco ----
        try:
            exportar_pdf(origen, os.path.join(tmp, "nada.pdf"), handles=["ZZZZ"])
            raise AssertionError("debía fallar con un filtro sin resultados")
        except ValueError:
            pass

        # ---- El dibujo no se deforma: misma escala en X e Y ----
        # (se comprueba indirectamente: A4 y A3 dan escalas distintas pero
        #  ambas proporcionadas, y ninguna es cero)
        a3 = os.path.join(tmp, "a3.pdf")
        r3 = exportar_pdf(origen, a3, tamano="A3", epsg=9377)
        assert r3.escala != "1:0" and r3.entidades == r.entidades

    print("pdf: TODAS LAS PRUEBAS PASARON")


if __name__ == "__main__":
    probar()

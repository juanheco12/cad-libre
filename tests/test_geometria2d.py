# -*- coding: utf-8 -*-
"""Pruebas de la geometría del contorno libre."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cadlibre.geometria2d import (  # noqa: E402
    caja_dentro_de_poligono,
    caja_toca_poligono,
    punto_en_poligono,
    rectangulo_a_poligono,
)

CUADRADO = [(0, 0), (10, 0), (10, 10), (0, 10)]
# Forma de "L" (cóncava): el cuadrante superior derecho queda fuera
L = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]


def probar():
    # --- punto en polígono ---
    assert punto_en_poligono(5, 5, CUADRADO)
    assert not punto_en_poligono(15, 5, CUADRADO)
    assert not punto_en_poligono(-1, 5, CUADRADO)
    assert punto_en_poligono(2, 8, L)
    assert not punto_en_poligono(8, 8, L), "el entrante de la L debe quedar fuera"

    # --- caja contenida ---
    assert caja_dentro_de_poligono(2, 2, 8, 8, CUADRADO)
    assert not caja_dentro_de_poligono(2, 2, 12, 8, CUADRADO)
    # En la L: cajas que caben en cada brazo
    assert caja_dentro_de_poligono(1, 1, 9, 3.5, L), "brazo horizontal de la L"
    assert caja_dentro_de_poligono(1, 1, 3, 9, L), "brazo vertical de la L"
    assert not caja_dentro_de_poligono(3, 3, 5, 5, L), "cruza el entrante de la L"

    # --- caja que toca ---
    assert caja_toca_poligono(8, 8, 20, 20, CUADRADO)
    assert not caja_toca_poligono(20, 20, 30, 30, CUADRADO)
    # Polígono íntegramente dentro de la caja
    assert caja_toca_poligono(-5, -5, 25, 25, CUADRADO)
    # Cruce sin vértices dentro: banda horizontal que atraviesa el cuadrado
    assert caja_toca_poligono(-5, 4, 25, 6, CUADRADO)

    # --- rectángulo a polígono ---
    assert rectangulo_a_poligono(10, 10, 0, 0) == CUADRADO

    print("geometria2d: TODAS LAS PRUEBAS PASARON")


if __name__ == "__main__":
    probar()

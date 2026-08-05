# -*- coding: utf-8 -*-
"""Utilidades geométricas 2D para la selección libre por polígono.

Se usan en la exportación selectiva para decidir si una entidad cae dentro
del contorno que el usuario dibujó a mano alzada en el visor.
"""

from __future__ import annotations

Punto = tuple[float, float]


def punto_en_poligono(x: float, y: float, poligono: list[Punto]) -> bool:
    """Ray casting: cuenta cruces de una semirrecta horizontal hacia +X.

    Funciona con polígonos cóncavos y auto-intersecantes (regla par-impar),
    que es justo lo que produce un trazo libre.
    """
    dentro = False
    n = len(poligono)
    j = n - 1
    for i in range(n):
        xi, yi = poligono[i]
        xj, yj = poligono[j]
        if (yi > y) != (yj > y):
            # Abscisa donde el lado corta la horizontal que pasa por (x, y)
            corte = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < corte:
                dentro = not dentro
        j = i
    return dentro


def _segmentos_cruzan(p1: Punto, p2: Punto, p3: Punto, p4: Punto) -> bool:
    def orientacion(a: Punto, b: Punto, c: Punto) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1 = orientacion(p3, p4, p1)
    d2 = orientacion(p3, p4, p2)
    d3 = orientacion(p1, p2, p3)
    d4 = orientacion(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def caja_dentro_de_poligono(
    minx: float, miny: float, maxx: float, maxy: float, poligono: list[Punto]
) -> bool:
    """La caja está completamente dentro del polígono.

    Requiere que las cuatro esquinas estén dentro y que ningún lado del
    polígono atraviese la caja (lo segundo importa en polígonos cóncavos,
    donde un entrante puede colarse sin dejar esquinas fuera).
    """
    esquinas = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    if not all(punto_en_poligono(x, y, poligono) for x, y in esquinas):
        return False
    lados_caja = [
        (esquinas[0], esquinas[1]), (esquinas[1], esquinas[2]),
        (esquinas[2], esquinas[3]), (esquinas[3], esquinas[0]),
    ]
    n = len(poligono)
    for i in range(n):
        lado_pol = (poligono[i], poligono[(i + 1) % n])
        for lado_caja in lados_caja:
            if _segmentos_cruzan(lado_pol[0], lado_pol[1], lado_caja[0], lado_caja[1]):
                return False
    return True


def caja_toca_poligono(
    minx: float, miny: float, maxx: float, maxy: float, poligono: list[Punto]
) -> bool:
    """La caja solapa el polígono en alguna medida."""
    esquinas = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    if any(punto_en_poligono(x, y, poligono) for x, y in esquinas):
        return True
    # Un polígono pequeño puede estar íntegramente dentro de la caja
    for px, py in poligono:
        if minx <= px <= maxx and miny <= py <= maxy:
            return True
    # O cruzarla de lado a lado sin que ningún vértice caiga dentro
    lados_caja = [
        (esquinas[0], esquinas[1]), (esquinas[1], esquinas[2]),
        (esquinas[2], esquinas[3]), (esquinas[3], esquinas[0]),
    ]
    n = len(poligono)
    for i in range(n):
        a, b = poligono[i], poligono[(i + 1) % n]
        for c, d in lados_caja:
            if _segmentos_cruzan(a, b, c, d):
                return True
    return False


def rectangulo_a_poligono(x1: float, y1: float, x2: float, y2: float) -> list[Punto]:
    minx, maxx = min(x1, x2), max(x1, x2)
    miny, maxy = min(y1, y2), max(y1, y2)
    return [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]

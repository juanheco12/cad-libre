# -*- coding: utf-8 -*-
"""Exportación selectiva: solo ciertas capas y/o solo un área del plano.

Estrategia deliberada: en lugar de construir un DXF nuevo y copiarle las
entidades elegidas —lo que obligaría a reconstruir a mano capas, estilos,
bloques, unidades y el objeto GEODATA, con riesgo de perder algo— se abre el
DXF original y se ELIMINAN las entidades que no pasan el filtro.

Consecuencia: todo lo que no se borra queda exactamente como estaba. Las
entidades conservan sus coordenadas X, Y, Z originales, y el encabezado, la
georreferenciación, las definiciones de capa, los estilos de texto y de cota
siguen intactos. La exportación sigue sin mover, escalar ni rotar nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import ezdxf
from ezdxf import bbox

# Modos de selección por área, equivalentes a los de AutoCAD:
#   "contenida"  → solo entidades totalmente dentro del rectángulo (window)
#   "intersecta" → además, las que lo tocan aunque se salgan (crossing)
MODOS_AREA = ("contenida", "intersecta")


@dataclass
class ResultadoFiltro:
    conservadas: int = 0
    eliminadas: int = 0
    capas_excluidas: list[str] = field(default_factory=list)
    sin_geometria: int = 0  # entidades sin caja envolvente calculable


def _caja(entidad):
    """Caja envolvente de una entidad, o None si no se puede calcular.

    `bbox.extents` desglosa internamente los bloques (INSERT) y las cotas,
    así que un bloque se evalúa por la extensión real de su contenido.
    """
    try:
        caja = bbox.extents([entidad], fast=False)
    except Exception:
        return None
    if not caja.has_data:
        return None
    return caja


def _dentro(caja, area, modo: str) -> bool:
    x1, y1, x2, y2 = area
    minx, miny = min(x1, x2), min(y1, y2)
    maxx, maxy = max(x1, x2), max(y1, y2)
    ext_min, ext_max = caja.extmin, caja.extmax
    if modo == "intersecta":
        # Se descarta solo si no hay solape en algún eje
        return not (
            ext_max.x < minx or ext_min.x > maxx
            or ext_max.y < miny or ext_min.y > maxy
        )
    return (
        ext_min.x >= minx and ext_max.x <= maxx
        and ext_min.y >= miny and ext_max.y <= maxy
    )


def exportar_filtrado(
    origen: str,
    destino: str,
    capas: list[str] | None = None,
    area: tuple[float, float, float, float] | None = None,
    modo_area: str = "contenida",
) -> ResultadoFiltro:
    """Escribe en `destino` el DXF con solo las entidades que pasan el filtro.

    capas: nombres de las capas a conservar (None = todas).
    area:  (x1, y1, x2, y2) en coordenadas del dibujo (None = todo el plano).
    """
    if modo_area not in MODOS_AREA:
        raise ValueError(f"Modo de área no válido: {modo_area}")
    if capas is None and area is None:
        raise ValueError("Sin filtro no debe usarse esta ruta: copie el DXF tal cual.")

    doc = ezdxf.readfile(origen)
    msp = doc.modelspace()
    permitidas = set(capas) if capas is not None else None
    resultado = ResultadoFiltro()

    a_eliminar = []
    for entidad in msp:
        if permitidas is not None:
            try:
                if entidad.dxf.layer not in permitidas:
                    a_eliminar.append(entidad)
                    continue
            except Exception:
                pass
        if area is not None:
            caja = _caja(entidad)
            if caja is None:
                # Sin caja calculable no se puede decidir: se conserva, para
                # no perder información por un fallo de medición.
                resultado.sin_geometria += 1
            elif not _dentro(caja, area, modo_area):
                a_eliminar.append(entidad)
                continue
        resultado.conservadas += 1

    for entidad in a_eliminar:
        try:
            msp.delete_entity(entidad)
            resultado.eliminadas += 1
        except Exception:
            resultado.conservadas += 1  # no se pudo borrar: sigue en el dibujo

    if permitidas is not None:
        resultado.capas_excluidas = sorted(
            capa.dxf.name for capa in doc.layers if capa.dxf.name not in permitidas
        )

    # Las extensiones guardadas dejan de ser válidas al quitar entidades.
    # Se marcan para que AutoCAD/QGIS las recalculen en vez de heredar un
    # encuadre erróneo. Esto no altera ninguna coordenada.
    try:
        doc.header["$EXTMIN"] = (1e20, 1e20, 1e20)
        doc.header["$EXTMAX"] = (-1e20, -1e20, -1e20)
    except Exception:
        pass

    doc.saveas(destino)
    return resultado

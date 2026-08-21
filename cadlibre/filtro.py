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

El área puede ser cualquier contorno cerrado (el usuario lo dibuja a mano
alzada en el visor), no solo un rectángulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import ezdxf
from ezdxf import bbox

from .geometria2d import (
    Punto,
    caja_dentro_de_poligono,
    caja_toca_poligono,
    rectangulo_a_poligono,
)

# Modos de selección por área, equivalentes a los de AutoCAD:
#   "contenida"  → solo entidades totalmente dentro del contorno (window)
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


def _pasa_area(caja, poligono: list[Punto], modo: str) -> bool:
    minx, miny = caja.extmin.x, caja.extmin.y
    maxx, maxy = caja.extmax.x, caja.extmax.y
    if modo == "intersecta":
        return caja_toca_poligono(minx, miny, maxx, maxy, poligono)
    return caja_dentro_de_poligono(minx, miny, maxx, maxy, poligono)


def normalizar_area(area) -> list[Punto] | None:
    """Acepta un rectángulo [x1,y1,x2,y2] o un polígono [[x,y], …]."""
    if not area:
        return None
    if len(area) == 4 and all(isinstance(v, (int, float)) for v in area):
        return rectangulo_a_poligono(*area)
    poligono = [(float(p[0]), float(p[1])) for p in area]
    if len(poligono) < 3:
        raise ValueError("El área libre necesita al menos 3 puntos.")
    return poligono


def exportar_filtrado(
    origen: str,
    destino: str,
    capas: list[str] | None = None,
    area=None,
    modo_area: str = "contenida",
    handles: list[str] | None = None,
) -> ResultadoFiltro:
    """Escribe en `destino` el DXF con solo las entidades que pasan el filtro.

    capas:   nombres de las capas a conservar (None = todas).
    area:    rectángulo [x1,y1,x2,y2] o polígono [[x,y], …] en coordenadas del
             dibujo (None = todo el plano).
    handles: identificadores de las entidades elegidas una a una en el visor
             (None = no se filtra por selección). Es el filtro más preciso:
             exporta exactamente esas entidades y nada más.
    """
    if modo_area not in MODOS_AREA:
        raise ValueError(f"Modo de área no válido: {modo_area}")
    poligono = normalizar_area(area)
    elegidos = {h.upper() for h in handles} if handles else None
    if capas is None and poligono is None and elegidos is None:
        raise ValueError("Sin filtro no debe usarse esta ruta: copie el DXF tal cual.")

    doc = ezdxf.readfile(origen)
    msp = doc.modelspace()
    permitidas = set(capas) if capas is not None else None
    resultado = ResultadoFiltro()

    a_eliminar = []
    for entidad in msp:
        if elegidos is not None:
            # La selección manual es explícita: lo que no se eligió, se va,
            # sin consultar capa ni área.
            handle = entidad.dxf.get("handle", "") or ""
            if handle.upper() not in elegidos:
                a_eliminar.append(entidad)
                continue
            resultado.conservadas += 1
            continue
        if permitidas is not None:
            try:
                if entidad.dxf.layer not in permitidas:
                    a_eliminar.append(entidad)
                    continue
            except Exception:
                pass
        if poligono is not None:
            caja = _caja(entidad)
            if caja is None:
                # Sin caja calculable no se puede decidir: se conserva, para
                # no perder información por un fallo de medición.
                resultado.sin_geometria += 1
            elif not _pasa_area(caja, poligono, modo_area):
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

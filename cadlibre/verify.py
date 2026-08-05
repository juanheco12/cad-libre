# -*- coding: utf-8 -*-
"""Inventario del DXF resultante para verificar que nada se perdió ni se movió.

Se abre el DXF únicamente en lectura y se reporta: versión, unidades,
extensión espacial (coordenadas reales), capas, bloques y conteo de
entidades por tipo (polilíneas, textos, cotas, inserciones de bloque, etc.).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import ezdxf

_UNIDADES = {
    0: "sin unidad", 1: "pulgadas", 2: "pies", 4: "milímetros",
    5: "centímetros", 6: "metros", 7: "kilómetros",
}


@dataclass
class Inventario:
    version_dxf: str = ""
    unidades: str = ""
    extmin: tuple | None = None
    extmax: tuple | None = None
    capas: list[str] = field(default_factory=list)
    bloques: list[str] = field(default_factory=list)
    entidades: Counter = field(default_factory=Counter)
    total_entidades: int = 0
    tiene_geodata: bool = False


def inventariar(ruta_dxf: str) -> Inventario:
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    inv = Inventario()
    inv.version_dxf = doc.acad_release or doc.dxfversion
    inv.unidades = _UNIDADES.get(doc.header.get("$INSUNITS", 0), "otras")
    extmin = doc.header.get("$EXTMIN")
    extmax = doc.header.get("$EXTMAX")
    # AutoCAD usa 1e20 como marcador de "extensión no calculada"
    if extmin and extmax and abs(extmin[0]) < 1e19:
        inv.extmin = tuple(round(c, 4) for c in extmin)
        inv.extmax = tuple(round(c, 4) for c in extmax)
    inv.capas = sorted(capa.dxf.name for capa in doc.layers)
    inv.bloques = sorted(
        b.name for b in doc.blocks
        if not b.name.lower().startswith(("*model_space", "*paper_space"))
    )
    for entidad in msp:
        inv.entidades[entidad.dxftype()] += 1
    inv.total_entidades = sum(inv.entidades.values())
    inv.tiene_geodata = msp.get_geodata() is not None
    return inv


def resumen(inv: Inventario) -> str:
    lineas = [
        f"Versión DXF   : {inv.version_dxf}",
        f"Unidades      : {inv.unidades}",
    ]
    if inv.extmin and inv.extmax:
        lineas.append(
            f"Extensión     : X {inv.extmin[0]:,.2f} → {inv.extmax[0]:,.2f}   "
            f"Y {inv.extmin[1]:,.2f} → {inv.extmax[1]:,.2f}"
        )
    lineas.append(f"Capas         : {len(inv.capas)}")
    lineas.append(f"Bloques       : {len(inv.bloques)}")
    lineas.append(f"Entidades     : {inv.total_entidades}")
    for tipo, n in inv.entidades.most_common():
        lineas.append(f"   {tipo:<14} {n}")
    lineas.append(
        "Georreferencia embebida (GEODATA): " + ("sí" if inv.tiene_geodata else "no")
    )
    return "\n".join(lineas)

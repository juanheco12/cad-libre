# -*- coding: utf-8 -*-
"""Extracción de geometría del DXF para el visor de la aplicación Electron.

Convierte las entidades del espacio modelo a un JSON compacto de polilíneas y
textos en coordenadas de mundo (las originales del plano — sin transformar).
Los bloques (INSERT) y las cotas (DIMENSION) se desglosan visualmente con
`virtual_entities()`, pero cada fragmento conserva el handle del objeto padre
para que la selección identifique la entidad real.

El archivo se escribe de forma incremental para no cargar en memoria todo el
JSON de dibujos grandes.
"""

from __future__ import annotations

import json
import math

import ezdxf
from ezdxf import colors as ezcolors
from ezdxf import path as ezpath

# Tipos que se aplanan a polilíneas mediante ezdxf.path
_TIPOS_CURVA = {
    "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE",
    "SPLINE", "SOLID", "TRACE", "3DFACE", "HELIX",
}
_TIPOS_TEXTO = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}
_MAX_PROFUNDIDAD_BLOQUE = 8


def _hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


class _Extractor:
    def __init__(self, doc):
        self.doc = doc
        self.capas_color: dict[str, str] = {}
        self.min_x = self.min_y = math.inf
        self.max_x = self.max_y = -math.inf
        self.total_vertices = 0
        self.omitidas = 0
        # Distancia de aplanado de curvas relativa al tamaño del dibujo
        self.distancia = self._distancia_aplanado()

    def _distancia_aplanado(self) -> float:
        extmin = self.doc.header.get("$EXTMIN", (0, 0, 0))
        extmax = self.doc.header.get("$EXTMAX", (1, 1, 0))
        try:
            diag = math.hypot(extmax[0] - extmin[0], extmax[1] - extmin[1])
        except Exception:
            diag = 0.0
        if not math.isfinite(diag) or diag <= 0 or diag > 1e18:
            diag = 1000.0
        return max(diag / 20000.0, 1e-9)

    # ------------------------------------------------------------- colores
    def color_capa(self, nombre: str) -> str:
        if nombre not in self.capas_color:
            color = "#dddddd"
            try:
                capa = self.doc.layers.get(nombre)
                if capa.rgb is not None:
                    color = _hex(capa.rgb)
                else:
                    aci = abs(capa.dxf.color) or 7
                    color = _hex(ezcolors.aci2rgb(aci))
            except Exception:
                pass
            if color == "#ffffff":  # blanco ACI 7 no se ve sobre fondo claro/oscuro
                color = "#dddddd"
            self.capas_color[nombre] = color
        return self.capas_color[nombre]

    def color_entidad(self, e, color_padre: str | None = None) -> str:
        try:
            if e.dxf.hasattr("true_color"):
                return _hex(ezcolors.int2rgb(e.dxf.true_color))
            aci = e.dxf.color
            if aci == 0:  # BYBLOCK
                return color_padre or self.color_capa(e.dxf.layer)
            if aci == 256 or aci is None:  # BYLAYER
                return self.color_capa(e.dxf.layer)
            return _hex(ezcolors.aci2rgb(abs(aci) or 7))
        except Exception:
            return "#dddddd"

    # ------------------------------------------------------------ geometría
    def _registrar(self, x: float, y: float):
        if x < self.min_x: self.min_x = x
        if x > self.max_x: self.max_x = x
        if y < self.min_y: self.min_y = y
        if y > self.max_y: self.max_y = y

    def polilineas(self, e) -> list[list[float]]:
        """Aplana una entidad a listas planas [x1,y1,x2,y2,...]."""
        resultado = []
        try:
            camino = ezpath.make_path(e)
            for sub in camino.sub_paths():
                puntos: list[float] = []
                for v in sub.flattening(self.distancia):
                    x, y = round(v.x, 6), round(v.y, 6)
                    if puntos and puntos[-2] == x and puntos[-1] == y:
                        continue
                    puntos.extend((x, y))
                    self._registrar(x, y)
                if len(puntos) >= 4:
                    resultado.append(puntos)
                    self.total_vertices += len(puntos) // 2
        except Exception:
            self.omitidas += 1
        return resultado

    def entidad_texto(self, e, tipo: str, handle: str, color: str) -> dict | None:
        try:
            if tipo == "MTEXT":
                texto = e.plain_text(fast=True)
                pos = e.dxf.insert
                altura = float(e.dxf.char_height)
                rot = float(e.dxf.rotation)
            else:
                texto = e.dxf.text if not hasattr(e, "plain_text") else e.plain_text()
                pos = e.dxf.insert
                altura = float(e.dxf.height)
                rot = float(e.dxf.rotation)
            texto = (texto or "").strip()
            if not texto:
                return None
            x, y = round(pos[0], 6), round(pos[1], 6)
            self._registrar(x, y)
            return {
                "t": "TEXTO", "h": handle, "l": e.dxf.layer, "c": color,
                "x": x, "y": y, "alt": round(altura, 6), "rot": round(rot, 3),
                "s": texto[:512],
            }
        except Exception:
            self.omitidas += 1
            return None

    def procesar(self, e, salida, handle_padre=None, color_padre=None, capa_padre=None,
                 profundidad=0):
        """Procesa una entidad y escribe sus fragmentos en `salida` (callable)."""
        tipo = e.dxftype()
        handle = handle_padre or (e.dxf.handle if e.dxf.hasattr("handle") else "")
        capa = capa_padre or e.dxf.layer
        color = self.color_entidad(e, color_padre)

        if tipo in _TIPOS_TEXTO:
            item = self.entidad_texto(e, tipo, handle, color)
            if item:
                item["l"] = capa
                salida(item)
        elif tipo == "POINT":
            try:
                x, y = round(e.dxf.location[0], 6), round(e.dxf.location[1], 6)
                self._registrar(x, y)
                salida({"t": "PUNTO", "h": handle, "l": capa, "c": color, "x": x, "y": y})
            except Exception:
                self.omitidas += 1
        elif tipo in _TIPOS_CURVA:
            lineas = self.polilineas(e)
            if lineas:
                salida({"t": tipo, "h": handle, "l": capa, "c": color, "p": lineas})
        elif tipo in ("INSERT", "DIMENSION", "LEADER", "MLEADER", "MULTILEADER"):
            if profundidad >= _MAX_PROFUNDIDAD_BLOQUE:
                return
            etiqueta = handle if handle_padre else (
                e.dxf.handle if e.dxf.hasattr("handle") else ""
            )
            try:
                virtuales = list(e.virtual_entities())
            except Exception:
                self.omitidas += 1
                return
            for sub in virtuales:
                self.procesar(
                    sub, salida,
                    handle_padre=etiqueta,
                    color_padre=color,
                    capa_padre=capa,
                    profundidad=profundidad + 1,
                )
        elif tipo == "HATCH":
            # Solo el contorno del sombreado (el relleno no aporta al visor)
            try:
                for camino in ezpath.from_hatch(e):
                    puntos = []
                    for v in camino.flattening(self.distancia):
                        x, y = round(v.x, 6), round(v.y, 6)
                        puntos.extend((x, y))
                        self._registrar(x, y)
                    if len(puntos) >= 4:
                        salida({"t": "HATCH", "h": handle, "l": capa,
                                "c": color, "p": [puntos]})
                        self.total_vertices += len(puntos) // 2
            except Exception:
                self.omitidas += 1
        else:
            self.omitidas += 1


def extraer_geometria(ruta_dxf: str, ruta_json: str) -> dict:
    """Genera el JSON de geometría del visor y devuelve el resumen."""
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    extractor = _Extractor(doc)

    capas = []
    for capa in doc.layers:
        nombre = capa.dxf.name
        apagada = capa.dxf.color < 0 or capa.is_frozen()
        capas.append({
            "nombre": nombre,
            "color": extractor.color_capa(nombre),
            "visible": not apagada,
        })
    capas.sort(key=lambda c: c["nombre"].lower())

    n = 0
    with open(ruta_json, "w", encoding="utf-8") as f:
        f.write('{"entidades":[')
        primero = True

        def salida(item):
            nonlocal primero, n
            if not primero:
                f.write(",")
            json.dump(item, f, ensure_ascii=False, separators=(",", ":"))
            primero = False
            n += 1

        for e in msp:
            extractor.procesar(e, salida)

        if math.isfinite(extractor.min_x):
            extension = [extractor.min_x, extractor.min_y,
                         extractor.max_x, extractor.max_y]
        else:
            extension = [0, 0, 1, 1]
        f.write('],"capas":')
        json.dump(capas, f, ensure_ascii=False)
        f.write(',"extension":')
        json.dump(extension, f)
        f.write("}")

    return {
        "fragmentos": n,
        "vertices": extractor.total_vertices,
        "omitidas": extractor.omitidas,
        "extension": extension,
        "capas": len(capas),
    }

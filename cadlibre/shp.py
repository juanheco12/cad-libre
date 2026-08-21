# -*- coding: utf-8 -*-
"""Exportación a Shapefile (formato nativo de QGIS y ArcGIS).

Un shapefile solo admite UN tipo de geometría, así que el dibujo se reparte
en varios archivos según lo que sea cada entidad:

    <nombre>_poligonos.shp   polilíneas cerradas (linderos de predios)
    <nombre>_lineas.shp      polilíneas abiertas, arcos, círculos, splines
    <nombre>_puntos.shp      puntos
    <nombre>_textos.shp      textos, como puntos con el contenido en atributo

Las coordenadas son las ORIGINALES del DXF: no se mueve, escala ni rota nada.
Se conserva la Z usando los tipos *Z de shapefile. Junto a cada .shp se
escribe su .prj con el CRS detectado, para que abra georreferenciado.

Las curvas (arcos, círculos, splines) no existen en shapefile: se aplanan a
segmentos rectos, que es lo que hace cualquier conversor. La tolerancia se
calcula a partir del tamaño del dibujo para que el error sea imperceptible.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import ezdxf
import shapefile
from ezdxf import path as ezpath

from .geometria2d import Punto, caja_dentro_de_poligono, caja_toca_poligono

# Entidades que se aplanan a listas de vértices
_TIPOS_CURVA = {
    "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE",
    "SPLINE", "SOLID", "TRACE", "3DFACE", "HELIX",
}
_TIPOS_TEXTO = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}
_MAX_PROFUNDIDAD_BLOQUE = 8
# Un contorno se considera cerrado si sus extremos distan menos que esta
# proporción de la magnitud de las coordenadas.
_TOLERANCIA_CIERRE = 1e-9


@dataclass
class ResultadoShp:
    archivos: list[str] = field(default_factory=list)
    poligonos: int = 0
    lineas: int = 0
    puntos: int = 0
    textos: int = 0
    omitidas: int = 0

    @property
    def total(self) -> int:
        return self.poligonos + self.lineas + self.puntos + self.textos


class _Escritor:
    """Envuelve un shapefile.Writer y lo crea solo si llega alguna geometría."""

    def __init__(self, ruta_base: str, sufijo: str, tipo: int, campos: list[tuple]):
        self.ruta = f"{ruta_base}_{sufijo}"
        self.tipo = tipo
        self.campos = campos
        self.w = None
        self.n = 0

    def _abrir(self):
        if self.w is None:
            self.w = shapefile.Writer(self.ruta, shapeType=self.tipo)
            for nombre, tipo_campo, tam in self.campos:
                self.w.field(nombre, tipo_campo, tam)

    def escribir(self, dibujar, atributos):
        self._abrir()
        dibujar(self.w)
        self.w.record(*atributos)
        self.n += 1

    def cerrar(self, wkt):
        if self.w is None:
            return []
        self.w.close()
        creados = [self.ruta + ext for ext in (".shp", ".shx", ".dbf")
                   if os.path.exists(self.ruta + ext)]
        if wkt:
            ruta_prj = self.ruta + ".prj"
            with open(ruta_prj, "w", encoding="utf-8") as f:
                f.write(wkt)
            creados.append(ruta_prj)
        return creados


def _distancia_aplanado(doc) -> float:
    extmin = doc.header.get("$EXTMIN", (0, 0, 0))
    extmax = doc.header.get("$EXTMAX", (1, 1, 0))
    try:
        diag = math.hypot(extmax[0] - extmin[0], extmax[1] - extmin[1])
    except Exception:
        diag = 0.0
    if not math.isfinite(diag) or diag <= 0 or diag > 1e18:
        diag = 1000.0
    return max(diag / 50000.0, 1e-9)


def _cerrado(puntos) -> bool:
    if len(puntos) < 4:
        return False
    x0, y0 = puntos[0][0], puntos[0][1]
    xn, yn = puntos[-1][0], puntos[-1][1]
    escala = max(abs(x0), abs(y0), 1.0)
    return math.hypot(xn - x0, yn - y0) <= escala * _TOLERANCIA_CIERRE


def _orientar(anillo):
    """Shapefile exige el anillo exterior en sentido horario."""
    area = 0.0
    for i in range(len(anillo) - 1):
        x1, y1 = anillo[i][0], anillo[i][1]
        x2, y2 = anillo[i + 1][0], anillo[i + 1][1]
        area += (x2 - x1) * (y2 + y1)
    return anillo if area > 0 else anillo[::-1]


class _Exportador:
    def __init__(self, doc, base: str):
        self.doc = doc
        self.distancia = _distancia_aplanado(doc)
        campos_geo = [("capa", "C", 64), ("tipo", "C", 20), ("handle", "C", 16)]
        self.poligonos = _Escritor(base, "poligonos", shapefile.POLYGONZ, campos_geo)
        self.lineas = _Escritor(base, "lineas", shapefile.POLYLINEZ, campos_geo)
        self.puntos = _Escritor(base, "puntos", shapefile.POINTZ, campos_geo)
        self.textos = _Escritor(
            base, "textos", shapefile.POINTZ,
            campos_geo + [("texto", "C", 254), ("altura", "N", 18),
                          ("rotacion", "N", 12)],
        )
        self.resultado = ResultadoShp()

    def _vertices(self, entidad):
        salida = []
        try:
            camino = ezpath.make_path(entidad)
            for sub in camino.sub_paths():
                pts = []
                for v in sub.flattening(self.distancia):
                    p = [float(v.x), float(v.y), float(v.z)]
                    if pts and pts[-1][0] == p[0] and pts[-1][1] == p[1]:
                        continue
                    pts.append(p)
                if len(pts) >= 2:
                    salida.append(pts)
        except Exception:
            self.resultado.omitidas += 1
        return salida

    def procesar(self, entidad, handle_padre=None, capa_padre=None, profundidad=0):
        tipo = entidad.dxftype()
        try:
            handle = handle_padre or (entidad.dxf.get("handle", "") or "")
            capa = capa_padre or entidad.dxf.layer
        except Exception:
            self.resultado.omitidas += 1
            return

        if tipo in _TIPOS_TEXTO:
            self._texto(entidad, tipo, handle, capa)
        elif tipo == "POINT":
            try:
                p = entidad.dxf.location
                self.puntos.escribir(
                    lambda w: w.pointz(float(p[0]), float(p[1]), float(p[2])),
                    (capa, tipo, handle),
                )
                self.resultado.puntos += 1
            except Exception:
                self.resultado.omitidas += 1
        elif tipo in _TIPOS_CURVA:
            for pts in self._vertices(entidad):
                if _cerrado(pts) and len(pts) >= 4:
                    anillo = _orientar(pts)
                    self.poligonos.escribir(
                        lambda w, a=anillo: w.polyz([a]), (capa, tipo, handle)
                    )
                    self.resultado.poligonos += 1
                else:
                    self.lineas.escribir(
                        lambda w, p=pts: w.linez([p]), (capa, tipo, handle)
                    )
                    self.resultado.lineas += 1
        elif tipo in ("INSERT", "DIMENSION", "LEADER", "MLEADER", "MULTILEADER"):
            if profundidad >= _MAX_PROFUNDIDAD_BLOQUE:
                return
            try:
                virtuales = list(entidad.virtual_entities())
            except Exception:
                self.resultado.omitidas += 1
                return
            for sub in virtuales:
                self.procesar(sub, handle, capa, profundidad + 1)
        elif tipo == "HATCH":
            try:
                for camino in ezpath.from_hatch(entidad):
                    pts = [[float(v.x), float(v.y), float(v.z)]
                           for v in camino.flattening(self.distancia)]
                    if len(pts) >= 4:
                        anillo = _orientar(pts)
                        self.poligonos.escribir(
                            lambda w, a=anillo: w.polyz([a]), (capa, tipo, handle)
                        )
                        self.resultado.poligonos += 1
            except Exception:
                self.resultado.omitidas += 1
        else:
            self.resultado.omitidas += 1

    def _texto(self, e, tipo, handle, capa):
        try:
            if tipo == "MTEXT":
                contenido = e.plain_text(fast=True)
                altura = float(e.dxf.char_height)
            else:
                contenido = e.plain_text() if hasattr(e, "plain_text") else e.dxf.text
                altura = float(e.dxf.height)
            contenido = (contenido or "").strip()
            if not contenido:
                return
            pos = e.dxf.insert
            rot = float(e.dxf.rotation) if e.dxf.hasattr("rotation") else 0.0
            self.textos.escribir(
                lambda w: w.pointz(float(pos[0]), float(pos[1]), float(pos[2])),
                (capa, tipo, handle, contenido[:254], round(altura, 6), round(rot, 3)),
            )
            self.resultado.textos += 1
        except Exception:
            self.resultado.omitidas += 1

    def cerrar(self, wkt):
        for escritor in (self.poligonos, self.lineas, self.puntos, self.textos):
            self.resultado.archivos.extend(escritor.cerrar(wkt))
        return self.resultado


def exportar_shp(
    ruta_dxf: str,
    ruta_base: str,
    wkt=None,
    capas=None,
    area=None,
    modo_area: str = "contenida",
    handles=None,
) -> ResultadoShp:
    """Convierte el DXF a shapefiles. `ruta_base` es la ruta sin extensión.

    Acepta los mismos filtros que la exportación a DXF: capas visibles,
    contorno dibujado y selección manual de entidades.
    """
    from .filtro import normalizar_area  # import local: evita ciclo de importación

    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    poligono = normalizar_area(area)
    permitidas = set(capas) if capas is not None else None
    elegidos = {h.upper() for h in handles} if handles else None

    carpeta = os.path.dirname(ruta_base)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    exportador = _Exportador(doc, ruta_base)

    for entidad in msp:
        if elegidos is not None:
            # La selección manual manda: lo que no se eligió no se exporta.
            try:
                if (entidad.dxf.get("handle", "") or "").upper() not in elegidos:
                    continue
            except Exception:
                continue
        else:
            if permitidas is not None:
                try:
                    if entidad.dxf.layer not in permitidas:
                        continue
                except Exception:
                    pass
            if poligono is not None and not _dentro_area(entidad, poligono, modo_area):
                continue
        exportador.procesar(entidad)

    return exportador.cerrar(wkt)


def _dentro_area(entidad, poligono, modo: str) -> bool:
    from ezdxf import bbox
    try:
        caja = bbox.extents([entidad], fast=False)
    except Exception:
        return True  # sin caja no se puede decidir: se conserva
    if not caja.has_data:
        return True
    minx, miny = caja.extmin.x, caja.extmin.y
    maxx, maxy = caja.extmax.x, caja.extmax.y
    if modo == "intersecta":
        return caja_toca_poligono(minx, miny, maxx, maxy, poligono)
    return caja_dentro_de_poligono(minx, miny, maxx, maxy, poligono)

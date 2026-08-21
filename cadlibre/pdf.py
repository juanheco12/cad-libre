# -*- coding: utf-8 -*-
"""Exportación a PDF vectorial, conservando los colores del dibujo.

El PDF se imprime sobre papel blanco, así que los colores claros del CAD
(blanco, amarillo, cian) resultarían ilegibles tal cual. Se aplica el mismo
criterio que el visor en tema claro: se oscurecen SOLO los colores con poco
contraste sobre blanco, respetando el tono. Un lindero rojo sigue rojo; una
línea blanca pasa a gris oscuro.

Es vectorial (no una captura de pantalla): se puede acercar sin pixelar, y
los textos van como texto real, seleccionable y buscable.

El dibujo se encuadra en la página con su relación de aspecto intacta: no se
deforma. La escala resultante se anota al pie junto al EPSG.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import ezdxf
from ezdxf import colors as ezcolors
from ezdxf import path as ezpath
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from .geometria2d import caja_dentro_de_poligono, caja_toca_poligono

_TIPOS_CURVA = {
    "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE",
    "SPLINE", "SOLID", "TRACE", "3DFACE", "HELIX",
}
_TIPOS_TEXTO = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}
_MAX_PROFUNDIDAD_BLOQUE = 8

TAMANOS = {"A4": A4, "A3": A3}
# Milímetros que vale una unidad de dibujo, según $INSUNITS del DXF.
_MM_POR_UNIDAD = {
    1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 7: 1000000.0,
}
MARGEN = 12 * mm
# Luminancia por encima de la cual un color no se distingue sobre papel blanco
_LUMINANCIA_MAXIMA = 0.62


@dataclass
class ResultadoPdf:
    ruta: str = ""
    entidades: int = 0
    textos: int = 0
    omitidas: int = 0
    escala: str = ""


def _luminancia(rgb) -> float:
    r, g, b = rgb
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _contrastar(rgb):
    """Oscurece un color hasta que se lea sobre blanco, conservando el tono."""
    lum = _luminancia(rgb)
    if lum <= _LUMINANCIA_MAXIMA:
        return tuple(c / 255.0 for c in rgb)
    if max(rgb) - min(rgb) < 12:
        # Gris o blanco: no hay tono que conservar, se lleva a gris oscuro
        return (0.25, 0.25, 0.25)
    factor = _LUMINANCIA_MAXIMA / lum
    return tuple(min(1.0, (c / 255.0) * factor) for c in rgb)


class _Pintor:
    def __init__(self, doc, c, transformar):
        self.doc = doc
        self.c = c
        self.t = transformar
        self.capas_color = {}
        self.resultado = ResultadoPdf()
        self.distancia = self._distancia()

    def _distancia(self) -> float:
        extmin = self.doc.header.get("$EXTMIN", (0, 0, 0))
        extmax = self.doc.header.get("$EXTMAX", (1, 1, 0))
        try:
            diag = math.hypot(extmax[0] - extmin[0], extmax[1] - extmin[1])
        except Exception:
            diag = 0.0
        if not math.isfinite(diag) or diag <= 0 or diag > 1e18:
            diag = 1000.0
        return max(diag / 60000.0, 1e-9)

    def color_capa(self, nombre):
        if nombre not in self.capas_color:
            rgb = (221, 221, 221)
            try:
                capa = self.doc.layers.get(nombre)
                rgb = capa.rgb if capa.rgb is not None else \
                    ezcolors.aci2rgb(abs(capa.dxf.color) or 7)
            except Exception:
                pass
            self.capas_color[nombre] = rgb
        return self.capas_color[nombre]

    def color(self, e, color_padre=None):
        try:
            if e.dxf.hasattr("true_color"):
                return ezcolors.int2rgb(e.dxf.true_color)
            aci = e.dxf.color
            if aci == 0:
                return color_padre or self.color_capa(e.dxf.layer)
            if aci == 256 or aci is None:
                return self.color_capa(e.dxf.layer)
            return ezcolors.aci2rgb(abs(aci) or 7)
        except Exception:
            return (221, 221, 221)

    def procesar(self, e, color_padre=None, profundidad=0):
        tipo = e.dxftype()
        rgb = self.color(e, color_padre)
        pluma = _contrastar(rgb)

        if tipo in _TIPOS_TEXTO:
            self._texto(e, tipo, pluma)
        elif tipo == "POINT":
            try:
                x, y = self.t(e.dxf.location[0], e.dxf.location[1])
                self.c.setStrokeColorRGB(*pluma)
                self.c.setLineWidth(0.5)
                self.c.line(x - 1.5, y, x + 1.5, y)
                self.c.line(x, y - 1.5, x, y + 1.5)
                self.resultado.entidades += 1
            except Exception:
                self.resultado.omitidas += 1
        elif tipo in _TIPOS_CURVA:
            self._trazar(e, pluma)
        elif tipo in ("INSERT", "DIMENSION", "LEADER", "MLEADER", "MULTILEADER"):
            if profundidad >= _MAX_PROFUNDIDAD_BLOQUE:
                return
            try:
                virtuales = list(e.virtual_entities())
            except Exception:
                self.resultado.omitidas += 1
                return
            for sub in virtuales:
                self.procesar(sub, rgb, profundidad + 1)
        elif tipo == "HATCH":
            try:
                for camino in ezpath.from_hatch(e):
                    self._trazar_camino(camino, pluma)
            except Exception:
                self.resultado.omitidas += 1
        else:
            self.resultado.omitidas += 1

    def _trazar(self, e, pluma):
        try:
            camino = ezpath.make_path(e)
        except Exception:
            self.resultado.omitidas += 1
            return
        for sub in camino.sub_paths():
            self._trazar_camino(sub, pluma)

    def _trazar_camino(self, camino, pluma):
        try:
            puntos = list(camino.flattening(self.distancia))
        except Exception:
            self.resultado.omitidas += 1
            return
        if len(puntos) < 2:
            return
        p = self.c.beginPath()
        x, y = self.t(puntos[0].x, puntos[0].y)
        p.moveTo(x, y)
        for v in puntos[1:]:
            x, y = self.t(v.x, v.y)
            p.lineTo(x, y)
        self.c.setStrokeColorRGB(*pluma)
        self.c.setLineWidth(0.4)
        self.c.drawPath(p, stroke=1, fill=0)
        self.resultado.entidades += 1

    def _texto(self, e, tipo, pluma):
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
            x, y = self.t(pos[0], pos[1])
            # La altura del texto se escala igual que el dibujo
            x2, _ = self.t(pos[0] + altura, pos[1])
            tam = max(abs(x2 - x), 1.2)
            rot = float(e.dxf.rotation) if e.dxf.hasattr("rotation") else 0.0

            self.c.saveState()
            self.c.setFillColorRGB(*pluma)
            self.c.setFont("Helvetica", tam)
            if rot:
                self.c.translate(x, y)
                self.c.rotate(rot)
                self.c.drawString(0, 0, contenido)
            else:
                self.c.drawString(x, y, contenido)
            self.c.restoreState()
            self.resultado.textos += 1
        except Exception:
            self.resultado.omitidas += 1


def _entidades_filtradas(msp, capas, poligono, modo_area, handles):
    permitidas = set(capas) if capas is not None else None
    elegidos = {h.upper() for h in handles} if handles else None
    for e in msp:
        if elegidos is not None:
            try:
                if (e.dxf.get("handle", "") or "").upper() not in elegidos:
                    continue
            except Exception:
                continue
        else:
            if permitidas is not None:
                try:
                    if e.dxf.layer not in permitidas:
                        continue
                except Exception:
                    pass
            if poligono is not None and not _dentro(e, poligono, modo_area):
                continue
        yield e


def _dentro(entidad, poligono, modo):
    from ezdxf import bbox
    try:
        caja = bbox.extents([entidad], fast=False)
    except Exception:
        return True
    if not caja.has_data:
        return True
    minx, miny = caja.extmin.x, caja.extmin.y
    maxx, maxy = caja.extmax.x, caja.extmax.y
    if modo == "intersecta":
        return caja_toca_poligono(minx, miny, maxx, maxy, poligono)
    return caja_dentro_de_poligono(minx, miny, maxx, maxy, poligono)


def _extension(entidades):
    from ezdxf import bbox
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for e in entidades:
        try:
            caja = bbox.extents([e], fast=True)
        except Exception:
            continue
        if not caja.has_data:
            continue
        minx = min(minx, caja.extmin.x)
        miny = min(miny, caja.extmin.y)
        maxx = max(maxx, caja.extmax.x)
        maxy = max(maxy, caja.extmax.y)
    if not math.isfinite(minx):
        return None
    return minx, miny, maxx, maxy


def exportar_pdf(
    ruta_dxf: str,
    destino: str,
    capas=None,
    area=None,
    modo_area: str = "contenida",
    handles=None,
    tamano: str = "A4",
    epsg=None,
) -> ResultadoPdf:
    """Dibuja en un PDF vectorial lo que pase el filtro."""
    from .filtro import normalizar_area

    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    poligono = normalizar_area(area)

    seleccionadas = list(
        _entidades_filtradas(msp, capas, poligono, modo_area, handles)
    )
    if not seleccionadas:
        raise ValueError("No hay nada que exportar con ese filtro.")

    ext = _extension(seleccionadas)
    if ext is None:
        raise ValueError("No se pudo calcular la extensión de lo seleccionado.")
    minx, miny, maxx, maxy = ext
    ancho_dib = max(maxx - minx, 1e-9)
    alto_dib = max(maxy - miny, 1e-9)

    # La hoja se pone horizontal si el dibujo lo es: aprovecha mejor el papel
    pagina = TAMANOS.get(tamano.upper(), A4)
    if ancho_dib > alto_dib:
        pagina = landscape(pagina)
    ancho_pag, alto_pag = pagina

    util_x = ancho_pag - MARGEN * 2
    util_y = alto_pag - MARGEN * 2 - 8 * mm  # deja sitio al pie
    escala = min(util_x / ancho_dib, util_y / alto_dib)
    # Centrado dentro de la zona útil
    desplaz_x = MARGEN + (util_x - ancho_dib * escala) / 2
    desplaz_y = MARGEN + 8 * mm + (util_y - alto_dib * escala) / 2

    def transformar(x, y):
        return (desplaz_x + (x - minx) * escala, desplaz_y + (y - miny) * escala)

    os.makedirs(os.path.dirname(os.path.abspath(destino)) or ".", exist_ok=True)
    c = rl_canvas.Canvas(destino, pagesize=pagina)
    c.setTitle(os.path.basename(destino))

    pintor = _Pintor(doc, c, transformar)
    for e in seleccionadas:
        pintor.procesar(e)

    # Pie: escala real y georreferencia, útil para verificar el plano impreso.
    # La escala solo tiene sentido si se sabe cuánto vale una unidad de dibujo:
    # sin $INSUNITS declarado no se inventa un número.
    unidades_por_mm = (1.0 / escala) * mm
    insunits = doc.header.get("$INSUNITS", 0)
    mm_por_unidad = _MM_POR_UNIDAD.get(insunits)
    if mm_por_unidad:
        denominador = unidades_por_mm * mm_por_unidad
        if denominador >= 100:
            texto_escala = f"1:{denominador:.0f}"
        elif denominador >= 1:
            texto_escala = f"1:{denominador:.1f}"
        else:
            texto_escala = f"{1 / denominador:.1f}:1"  # ampliado
        pie = f"Escala {texto_escala}"
    else:
        texto_escala = "sin unidades declaradas"
        pie = f"{unidades_por_mm:,.3g} unidades de dibujo por mm de papel"
    if epsg:
        pie += f"   ·   EPSG:{epsg}"
    pie += f"   ·   X {minx:,.2f} a {maxx:,.2f}   Y {miny:,.2f} a {maxy:,.2f}"
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont("Helvetica", 6.5)
    c.drawString(MARGEN, MARGEN, pie)

    c.showPage()
    c.save()

    pintor.resultado.ruta = destino
    pintor.resultado.escala = texto_escala
    return pintor.resultado

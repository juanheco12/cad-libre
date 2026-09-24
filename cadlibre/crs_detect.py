# -*- coding: utf-8 -*-
"""Deducción del sistema de coordenadas cuando el DWG no lo declara.

Muchos planos catastrales vienen sin GEODATA, pero sus coordenadas solo
tienen sentido en un origen concreto. Se prueban los sistemas usados en
Colombia y se conservan aquellos con los que el dibujo cae dentro del país:
si un origen equivocado se usara, el plano aterrizaría en el mar o en otro
continente, así que el filtro descarta casi todo.

Esto es una SUGERENCIA para que el usuario confirme, nunca una asignación
automática: asignar mal el origen desplazaría el plano cientos de metros.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from pyproj import CRS, Transformer
    _HAY_PYPROJ = True
except Exception:  # pragma: no cover
    _HAY_PYPROJ = False

# Sistemas habituales en catastro colombiano, del más actual al más antiguo.
CANDIDATOS = [
    9377,   # MAGNA-SIRGAS 2018 / Origen-Nacional (el vigente del IGAC)
    3116,   # MAGNA-SIRGAS / Colombia Bogotá zone
    3115,   # MAGNA-SIRGAS / Colombia West zone
    3117,   # MAGNA-SIRGAS / Colombia East Central zone
    3118,   # MAGNA-SIRGAS / Colombia East zone
    3114,   # MAGNA-SIRGAS / Colombia Far West zone
    21897,  # Bogota 1975 / Colombia Bogota zone (datum antiguo)
    32618,  # WGS 84 / UTM 18N
    32619,  # WGS 84 / UTM 19N
    4326,   # WGS 84 (grados)
]

# Caja que contiene a Colombia con holgura (lon_min, lat_min, lon_max, lat_max)
COLOMBIA = (-82.5, -4.6, -66.0, 13.8)


@dataclass
class Candidato:
    epsg: int
    nombre: str
    lon: float
    lat: float
    """Distancia al centro del país: ordena los empates de forma estable."""
    holgura: float


def _parece_grados(x: float, y: float) -> bool:
    """El dibujo ya viene en longitud/latitud (EPSG:4326)."""
    return _dentro_de_colombia(x, y)


def _dentro_de_colombia(lon: float, lat: float) -> bool:
    x1, y1, x2, y2 = COLOMBIA
    return x1 <= lon <= x2 and y1 <= lat <= y2


def sugerir_crs(x: float, y: float, limite: int = 4) -> list[Candidato]:
    """Sistemas con los que el punto (x, y) del dibujo cae dentro de Colombia."""
    if not _HAY_PYPROJ:
        return []
    # Un dibujo alrededor del origen está en coordenadas locales, no en un
    # sistema proyectado: cualquier origen lo colocaría en algún lugar
    # plausible del país y la sugerencia sería pura casualidad.
    if abs(x) < 1000 and abs(y) < 1000 and not _parece_grados(x, y):
        return []
    encontrados: list[Candidato] = []
    for epsg in CANDIDATOS:
        try:
            transformador = Transformer.from_crs(epsg, 4326, always_xy=True)
            lon, lat = transformador.transform(x, y)
        except Exception:
            continue
        if lon is None or lat is None:
            continue
        if not (abs(lon) <= 180 and abs(lat) <= 90):
            continue
        if not _dentro_de_colombia(lon, lat):
            continue
        try:
            nombre = CRS.from_epsg(epsg).name
        except Exception:
            nombre = f"EPSG:{epsg}"
        # Cuanto más al centro del país, más verosímil frente a un borde justo
        holgura = min(
            lon - COLOMBIA[0], COLOMBIA[2] - lon,
            lat - COLOMBIA[1], COLOMBIA[3] - lat,
        )
        encontrados.append(Candidato(epsg, nombre, round(lon, 6), round(lat, 6),
                                     round(holgura, 4)))
    encontrados.sort(key=lambda c: -c.holgura)
    return encontrados[:limite]


def info_crs(epsg: int) -> dict:
    """Nombre y definiciones de un EPSG, para el visor y los archivos .prj."""
    datos = {"epsg": epsg, "nombre": f"EPSG:{epsg}", "proj4": None, "wkt": None}
    if not _HAY_PYPROJ:
        return datos
    try:
        crs = CRS.from_epsg(epsg)
        datos["nombre"] = crs.name
        # proj4 pierde matices frente a WKT, pero es lo que entiende proj4js
        # en el visor; el .prj sigue generándose desde el WKT completo.
        # "+type=crs" es una marca interna de PROJ que proj4js no reconoce y
        # que le hace rechazar toda la definición.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            datos["proj4"] = crs.to_proj4().replace("+type=crs", "").strip()
        from pyproj.enums import WktVersion
        datos["wkt"] = crs.to_wkt(WktVersion.WKT1_ESRI, pretty=False)
    except Exception:
        pass
    return datos

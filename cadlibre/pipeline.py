# -*- coding: utf-8 -*-
"""Orquestación: convertir → leer georreferenciación → sidecars → inventario."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from .converter import VERSION_SALIDA_DEFECTO, convertir_dwg_a_dxf, detectar_motor
from .geodata import InfoGeorref, escribir_sidecars, leer_georreferenciacion
from .verify import Inventario, inventariar, resumen


@dataclass
class Resultado:
    origen: str
    dxf: str
    info: InfoGeorref
    inventario: Inventario
    sidecars: list[str] = field(default_factory=list)

    def reporte(self) -> str:
        lineas = [
            f"✔ {os.path.basename(self.origen)} → {os.path.basename(self.dxf)}",
        ]
        if self.info.epsg:
            crs = f"EPSG:{self.info.epsg}"
            if self.info.nombre_crs:
                crs += f" ({self.info.nombre_crs})"
            lineas.append(f"Georreferencia: {crs}")
        elif self.info.tiene_geodata:
            lineas.append("Georreferencia: GEODATA presente (sin código EPSG explícito)")
        else:
            lineas.append("Georreferencia: no embebida en el DWG (coordenadas intactas)")
        for ruta in self.sidecars:
            lineas.append(f"Generado: {os.path.basename(ruta)}")
        lineas.append(resumen(self.inventario))
        return "\n".join(lineas)


def procesar(
    ruta_entrada: str,
    carpeta_salida: str | None = None,
    version: str = VERSION_SALIDA_DEFECTO,
) -> Resultado:
    """Procesa un DWG (o un DXF ya existente) y devuelve el resultado.

    - .dwg → se convierte 1:1 a DXF y se generan los archivos laterales.
    - .dxf → no se convierte ni reescribe; solo se generan los laterales.
    """
    ruta_entrada = os.path.abspath(ruta_entrada)
    if carpeta_salida is None:
        carpeta_salida = os.path.dirname(ruta_entrada)
    extension = os.path.splitext(ruta_entrada)[1].lower()

    if extension == ".dwg":
        ruta_dxf = convertir_dwg_a_dxf(ruta_entrada, carpeta_salida, version)
    elif extension == ".dxf":
        destino = os.path.join(carpeta_salida, os.path.basename(ruta_entrada))
        if os.path.abspath(destino) != ruta_entrada:
            os.makedirs(carpeta_salida, exist_ok=True)
            shutil.copy2(ruta_entrada, destino)
        ruta_dxf = destino
    else:
        raise ValueError(f"Extensión no soportada: {extension} (use .dwg o .dxf)")

    info = leer_georreferenciacion(ruta_dxf)
    sidecars = escribir_sidecars(ruta_dxf, info)
    inventario = inventariar(ruta_dxf)
    return Resultado(ruta_entrada, ruta_dxf, info, inventario, sidecars)


def motor_disponible() -> str | None:
    motor = detectar_motor()
    return f"{motor.nombre} ({motor.ejecutable})" if motor else None

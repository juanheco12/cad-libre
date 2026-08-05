# -*- coding: utf-8 -*-
"""Conversión DWG → DXF sin alterar el dibujo.

Motores soportados (en orden de preferencia):

1. ODA File Converter (gratuito, https://www.opendesign.com/guestfiles/oda_file_converter)
   Es el mismo motor que usa QGIS para importar DWG. Hace una conversión
   1:1 del contenido: coordenadas, capas, bloques, textos, polilíneas,
   cotas y el objeto GEODATA (georreferenciación) pasan intactos.

2. dwg2dxf (LibreDWG), si está en el PATH.

La versión DXF de salida por defecto es ACAD2018 porque el objeto GEODATA
solo existe en DXF R2010 o superior; exportar a una versión anterior
destruiría la georreferenciación.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

# Versiones DXF que conservan el objeto GEODATA (R2010+)
VERSIONES_SEGURAS = ("ACAD2010", "ACAD2013", "ACAD2018")
VERSION_SALIDA_DEFECTO = "ACAD2018"

_RUTAS_ODA = (
    r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
    r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe",
    r"C:\Program Files\ODA\*\ODAFileConverter.exe",
)


class ConversionError(Exception):
    pass


@dataclass
class MotorConversion:
    nombre: str          # "ODA File Converter" | "dwg2dxf (LibreDWG)"
    ejecutable: str


def detectar_motor() -> MotorConversion | None:
    """Busca un motor de conversión DWG→DXF instalado en el sistema."""
    exe = shutil.which("ODAFileConverter")
    if exe:
        return MotorConversion("ODA File Converter", exe)
    for patron in _RUTAS_ODA:
        candidatos = sorted(glob.glob(patron), reverse=True)  # versión más nueva primero
        if candidatos:
            return MotorConversion("ODA File Converter", candidatos[0])
    exe = shutil.which("dwg2dxf")
    if exe:
        return MotorConversion("dwg2dxf (LibreDWG)", exe)
    return None


def convertir_dwg_a_dxf(
    ruta_dwg: str,
    carpeta_salida: str,
    version: str = VERSION_SALIDA_DEFECTO,
    motor: MotorConversion | None = None,
) -> str:
    """Convierte un DWG a DXF de forma 1:1 y devuelve la ruta del DXF creado.

    No aplica ninguna transformación: las coordenadas X, Y, Z de cada entidad
    quedan exactamente como en el DWG original.
    """
    if version not in VERSIONES_SEGURAS:
        raise ConversionError(
            f"La versión {version} es anterior a R2010 y no conserva la "
            "georreferenciación (GEODATA). Use ACAD2010, ACAD2013 o ACAD2018."
        )
    motor = motor or detectar_motor()
    if motor is None:
        raise ConversionError(
            "No se encontró ningún motor de conversión DWG→DXF.\n"
            "Instale ODA File Converter (gratuito):\n"
            "https://www.opendesign.com/guestfiles/oda_file_converter"
        )
    ruta_dwg = os.path.abspath(ruta_dwg)
    if not os.path.isfile(ruta_dwg):
        raise ConversionError(f"No existe el archivo: {ruta_dwg}")
    os.makedirs(carpeta_salida, exist_ok=True)

    nombre = os.path.splitext(os.path.basename(ruta_dwg))[0]
    destino = os.path.join(carpeta_salida, nombre + ".dxf")

    if motor.nombre.startswith("ODA"):
        _convertir_con_oda(motor.ejecutable, ruta_dwg, destino, version)
    else:
        _convertir_con_libredwg(motor.ejecutable, ruta_dwg, destino, version)

    if not os.path.isfile(destino) or os.path.getsize(destino) == 0:
        raise ConversionError(
            f"El motor {motor.nombre} no generó el DXF esperado: {destino}"
        )
    return destino


def _convertir_con_oda(exe: str, ruta_dwg: str, destino: str, version: str) -> None:
    # ODA File Converter procesa carpetas completas, así que se aísla el DWG
    # en una carpeta temporal para convertir únicamente ese archivo.
    with tempfile.TemporaryDirectory(prefix="cadlibre_") as tmp_in, \
         tempfile.TemporaryDirectory(prefix="cadlibre_") as tmp_out:
        copia = os.path.join(tmp_in, os.path.basename(ruta_dwg))
        shutil.copy2(ruta_dwg, copia)
        # Argumentos: entrada salida version tipo recursivo auditar [filtro]
        cmd = [exe, tmp_in, tmp_out, version, "DXF", "0", "1"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        errores = glob.glob(os.path.join(tmp_out, "*.err"))
        generado = os.path.join(
            tmp_out, os.path.splitext(os.path.basename(ruta_dwg))[0] + ".dxf"
        )
        if not os.path.isfile(generado):
            detalle = ""
            for err in errores:
                with open(err, "r", errors="replace") as f:
                    detalle += f.read()
            raise ConversionError(
                "ODA File Converter falló al convertir "
                f"{os.path.basename(ruta_dwg)}.\n{detalle or res.stderr or res.stdout}"
            )
        shutil.move(generado, destino)


def _convertir_con_libredwg(exe: str, ruta_dwg: str, destino: str, version: str) -> None:
    numero = {"ACAD2010": "r2010", "ACAD2013": "r2013", "ACAD2018": "r2018"}[version]
    cmd = [exe, "--as", numero, "-o", destino, ruta_dwg]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise ConversionError(
            f"dwg2dxf falló ({res.returncode}):\n{res.stderr or res.stdout}"
        )

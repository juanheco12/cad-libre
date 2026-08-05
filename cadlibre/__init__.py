"""CAD LIBRE — Conversor DWG a DXF con preservación total de georreferenciación.

Principio de diseño: la conversión es 1:1. Nunca se mueve, escala, rota ni
modifica ninguna entidad. El DXF resultante jamás se reescribe después de la
conversión; toda la información geoespacial (EPSG/CRS) se entrega en archivos
laterales (.prj y metadatos) para QGIS y ArcGIS.
"""

__version__ = "1.0.0"

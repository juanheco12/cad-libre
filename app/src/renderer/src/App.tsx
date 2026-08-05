/** Composición principal: barra, visor, panel de capas y barra de estado. */
import { useCallback, useEffect, useState } from 'react';
import BarraEstado from './components/BarraEstado';
import BarraHerramientas from './components/BarraHerramientas';
import PanelCapas from './components/PanelCapas';
import Visor from './components/Visor';
import type { Documento, Seleccion } from './lib/tipos';

export default function App() {
  const [documento, setDocumento] = useState<Documento | null>(null);
  const [capasVisibles, setCapasVisibles] = useState<Record<string, boolean>>({});
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [motor, setMotor] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [ajustarSenal, setAjustarSenal] = useState(0);

  useEffect(() => {
    if (!window.cadlibre) return; // navegador sin Electron (solo para depurar estilos)
    window.cadlibre.estadoMotor().then((r) => setMotor(r.motor ?? null));
  }, []);

  const abrir = useCallback(async () => {
    setOcupado(true);
    setMensaje(null);
    try {
      const r = await window.cadlibre.abrirArchivo();
      if (r.cancelado) return;
      if (!r.ok) {
        setMensaje(String(r.error ?? 'Error desconocido al abrir el archivo'));
        return;
      }
      const doc = r as unknown as Documento;
      setDocumento(doc);
      const visibles: Record<string, boolean> = {};
      for (const capa of doc.geometria.capas) visibles[capa.nombre] = capa.visible;
      setCapasVisibles(visibles);
      setSeleccion(null);
      setAjustarSenal((n) => n + 1);
      const geo = doc.georref;
      setMensaje(
        geo.epsg
          ? `Abierto con georreferencia EPSG:${geo.epsg}`
          : geo.tieneGeodata
            ? 'Abierto: GEODATA presente sin EPSG explícito'
            : 'Abierto: el DWG no trae CRS embebido (coordenadas intactas)'
      );
    } finally {
      setOcupado(false);
    }
  }, []);

  const exportar = useCallback(async () => {
    setOcupado(true);
    setMensaje(null);
    try {
      const r = await window.cadlibre.exportarDxf();
      if (r.cancelado) return;
      if (!r.ok) {
        setMensaje(String(r.error ?? 'Error al exportar'));
        return;
      }
      const laterales = (r.laterales as string[] | undefined)?.length ?? 0;
      setMensaje(
        `DXF exportado sin modificar el dibujo` +
        (r.epsg ? ` · EPSG:${r.epsg} en .prj y metadatos` : '') +
        ` (${laterales} archivos laterales)`
      );
    } finally {
      setOcupado(false);
    }
  }, []);

  const cambiarCapa = useCallback((nombre: string, visible: boolean) => {
    setCapasVisibles((prev) => ({ ...prev, [nombre]: visible }));
  }, []);

  const todasLasCapas = useCallback((visible: boolean) => {
    setCapasVisibles((prev) => {
      const nuevo: Record<string, boolean> = {};
      for (const nombre of Object.keys(prev)) nuevo[nombre] = visible;
      return nuevo;
    });
  }, []);

  return (
    <div className="aplicacion">
      <BarraHerramientas
        documento={documento}
        ocupado={ocupado}
        onAbrir={abrir}
        onExportar={exportar}
        onAjustar={() => setAjustarSenal((n) => n + 1)}
      />
      <div className="cuerpo">
        <PanelCapas
          capas={documento?.geometria.capas ?? []}
          visibles={capasVisibles}
          onCambiar={cambiarCapa}
          onTodas={todasLasCapas}
        />
        <main className="zona-visor">
          {documento ? (
            <Visor
              geometria={documento.geometria}
              capasVisibles={capasVisibles}
              seleccion={seleccion}
              onSeleccion={setSeleccion}
              onCursor={(x, y) => setCursor([x, y])}
              ajustarSenal={ajustarSenal}
            />
          ) : (
            <div className="bienvenida">
              <h1>CAD <b>LIBRE</b></h1>
              <p>Visor DWG con exportación fiel a DXF georreferenciado.</p>
              <button className="principal" onClick={abrir} disabled={ocupado}>
                📂 Abrir un archivo DWG o DXF
              </button>
              <p className="nota">
                Las coordenadas nunca se mueven, escalan ni rotan: el DXF exportado
                abre en QGIS y ArcGIS en su ubicación geográfica real.
              </p>
            </div>
          )}
        </main>
      </div>
      <BarraEstado
        documento={documento}
        cursor={cursor}
        seleccion={seleccion}
        motor={motor}
        mensaje={mensaje}
      />
    </div>
  );
}

/** Composición principal: barra, visor, panel de capas y barra de estado. */
import { useCallback, useEffect, useState } from 'react';
import AvisoActualizacion from './components/AvisoActualizacion';
import BarraEstado from './components/BarraEstado';
import BarraHerramientas from './components/BarraHerramientas';
import DialogoExportar from './components/DialogoExportar';
import PanelCapas from './components/PanelCapas';
import Visor from './components/Visor';
import { TEMAS, guardarTema, leerTemaGuardado, type NombreTema } from './lib/tema';
import type {
  Documento, InfoActualizacion, OpcionesExportar, ResumenFiltrado, Seleccion
} from './lib/tipos';

export default function App() {
  const [documento, setDocumento] = useState<Documento | null>(null);
  const [capasVisibles, setCapasVisibles] = useState<Record<string, boolean>>({});
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [motor, setMotor] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [ajustarSenal, setAjustarSenal] = useState(0);
  const [modoArea, setModoArea] = useState(false);
  const [area, setArea] = useState<[number, number][] | null>(null);
  const [dialogoExportar, setDialogoExportar] = useState(false);
  const [tema, setTema] = useState<NombreTema>(leerTemaGuardado);
  const [version, setVersion] = useState('');
  const [actualizacion, setActualizacion] = useState<InfoActualizacion | null>(null);

  useEffect(() => {
    if (!window.cadlibre) return; // navegador sin Electron (solo para depurar estilos)
    window.cadlibre.estadoMotor().then((r) => setMotor(r.motor ?? null));
    window.cadlibre.version().then(setVersion);
    return window.cadlibre.alActualizar(setActualizacion);
  }, []);

  // El tema se aplica al documento para que la interfaz siga al visor.
  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    guardarTema(tema);
  }, [tema]);

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
      setArea(null);
      setModoArea(false);
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

  const cerrar = useCallback(async () => {
    await window.cadlibre.cerrarArchivo();
    setDocumento(null);
    setCapasVisibles({});
    setSeleccion(null);
    setArea(null);
    setModoArea(false);
    setCursor(null);
    setMensaje('Dibujo cerrado. Puede abrir otro archivo.');
  }, []);

  const exportar = useCallback(async (opciones: OpcionesExportar) => {
    setDialogoExportar(false);
    setOcupado(true);
    setMensaje(null);
    try {
      const r = await window.cadlibre.exportarDxf(opciones);
      if (r.cancelado) return;
      if (!r.ok) {
        setMensaje(String(r.error ?? 'Error al exportar'));
        return;
      }
      const filtrado = r.filtrado as ResumenFiltrado | null;
      const base = filtrado
        ? `DXF exportado: ${filtrado.conservadas} entidades conservadas, ` +
          `${filtrado.eliminadas} excluidas`
        : 'DXF exportado completo sin modificar el dibujo';
      setMensaje(base + (r.epsg ? ` · EPSG:${r.epsg} en .prj y metadatos` : ''));
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
        modoArea={modoArea}
        hayArea={area !== null}
        tema={tema}
        onAbrir={abrir}
        onCerrar={cerrar}
        onExportar={() => setDialogoExportar(true)}
        onAjustar={() => setAjustarSenal((n) => n + 1)}
        onModoArea={() => setModoArea((m) => !m)}
        onLimpiarArea={() => { setArea(null); setModoArea(false); }}
        onTema={setTema}
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
            <>
              <Visor
                geometria={documento.geometria}
                capasVisibles={capasVisibles}
                seleccion={seleccion}
                onSeleccion={setSeleccion}
                onCursor={(x, y) => setCursor([x, y])}
                ajustarSenal={ajustarSenal}
                tema={TEMAS[tema]}
                modoArea={modoArea}
                area={area}
                onArea={(a) => { setArea(a); if (a) setModoArea(false); }}
              />
              {modoArea && (
                <div className="pista-area">
                  Mantenga pulsado y dibuje el contorno de lo que quiere exportar
                </div>
              )}
            </>
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
        version={version}
      />
      {dialogoExportar && documento && (
        <DialogoExportar
          documento={documento}
          capasVisibles={capasVisibles}
          area={area}
          onCancelar={() => setDialogoExportar(false)}
          onExportar={exportar}
        />
      )}
      <AvisoActualizacion info={actualizacion} onCerrar={() => setActualizacion(null)} />
    </div>
  );
}

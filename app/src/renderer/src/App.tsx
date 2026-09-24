/** Composición principal: barra, visor, panel de capas y barra de estado. */
import { useCallback, useEffect, useState } from 'react';
import AvisoActualizacion from './components/AvisoActualizacion';
import BarraEstado from './components/BarraEstado';
import BarraHerramientas from './components/BarraHerramientas';
import ControlSatelital from './components/ControlSatelital';
import DialogoExportar from './components/DialogoExportar';
import PanelCapas from './components/PanelCapas';
import Visor from './components/Visor';
import { TEMAS, guardarTema, leerTemaGuardado, type NombreTema } from './lib/tema';
import type {
  Documento, FuenteSatelital, InfoActualizacion, OpcionesExportar, Proyeccion,
  ResumenFiltrado, ResumenPdf, ResumenShp, Seleccion
} from './lib/tipos';

export default function App() {
  const [documento, setDocumento] = useState<Documento | null>(null);
  const [capasVisibles, setCapasVisibles] = useState<Record<string, boolean>>({});
  const [seleccion, setSeleccion] = useState<Seleccion | null>(null);
  /** Entidades elegidas a mano para exportar (handles del DXF). */
  const [elegidos, setElegidos] = useState<Set<string>>(new Set());
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [motor, setMotor] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [ajustarSenal, setAjustarSenal] = useState(0);
  const [modoArea, setModoArea] = useState(false);
  const [formaArea, setFormaArea] = useState<'libre' | 'rectangulo'>('libre');
  const [area, setArea] = useState<[number, number][] | null>(null);
  const [dialogoExportar, setDialogoExportar] = useState(false);
  const [tema, setTema] = useState<NombreTema>(leerTemaGuardado);
  const [version, setVersion] = useState('');
  /** Sistema del plano: el del archivo, o el que el usuario asigne. */
  const [proyeccion, setProyeccion] = useState<Proyeccion | null>(null);
  const [fuentes, setFuentes] = useState<FuenteSatelital[]>([]);
  const [fuenteSatelital, setFuenteSatelital] = useState<string | null>(null);
  const [opacidadSatelital, setOpacidadSatelital] = useState(0.85);
  const [actualizacion, setActualizacion] = useState<InfoActualizacion | null>(null);

  useEffect(() => {
    if (!window.cadlibre) return; // navegador sin Electron (solo para depurar estilos)
    window.cadlibre.estadoMotor().then((r) => setMotor(r.motor ?? null));
    window.cadlibre.version().then(setVersion);
    window.cadlibre.fuentesSatelitales().then(setFuentes);
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
      setElegidos(new Set());
      setProyeccion(doc.proyeccion ?? null);
      // Si el plano nuevo no está georreferenciado, se apaga el fondo para
      // no dejarlo mostrando la zona del plano anterior.
      if (!doc.proyeccion) setFuenteSatelital(null);
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
    setElegidos(new Set());
    setProyeccion(null);
    setFuenteSatelital(null);
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
      // Si el dibujo no traía sistema pero el usuario asignó uno, se usa
      // para generar los .prj de la exportación.
      const conEpsg = documento?.georref.epsg || !proyeccion
        ? opciones
        : { ...opciones, epsg: proyeccion.epsg };
      const r = await window.cadlibre.exportarDxf(conEpsg);
      if (r.cancelado) return;
      if (!r.ok) {
        setMensaje(String(r.error ?? 'Error al exportar'));
        return;
      }
      let base: string;
      if (r.formato === 'pdf') {
        const p = r.resumenPdf as ResumenPdf;
        base = `PDF exportado: ${p.entidades} entidades` +
          (p.textos ? `, ${p.textos} textos` : '') + ` · escala ${p.escala}`;
      } else if (r.formato === 'shp') {
        const shp = r.resumenShp as ResumenShp;
        const partes = [
          shp.poligonos ? `${shp.poligonos} polígonos` : '',
          shp.lineas ? `${shp.lineas} líneas` : '',
          shp.puntos ? `${shp.puntos} puntos` : '',
          shp.textos ? `${shp.textos} textos` : ''
        ].filter(Boolean);
        base = partes.length
          ? `Shapefile exportado: ${partes.join(', ')}`
          : 'No había nada que exportar con ese filtro';
      } else {
        const filtrado = r.filtrado as ResumenFiltrado | null;
        base = filtrado
          ? `DXF exportado: ${filtrado.conservadas} entidades conservadas, ` +
            `${filtrado.eliminadas} excluidas`
          : 'DXF exportado completo sin modificar el dibujo';
      }
      setMensaje(base + (r.epsg ? ` · EPSG:${r.epsg} en .prj` : ''));
    } finally {
      setOcupado(false);
    }
  }, []);

  /** El usuario confirma en qué sistema está el plano (no lo declaraba). */
  const asignarCrs = useCallback(async (epsg: number) => {
    const r = await window.cadlibre.infoCrs(epsg);
    if (!r.ok || !r.proyeccion) {
      setMensaje(`No se pudo cargar la definición de EPSG:${epsg}`);
      return;
    }
    setProyeccion(r.proyeccion);
    setMensaje(
      `Sistema asignado: EPSG:${epsg}. Las coordenadas del dibujo no se ` +
      'modifican; ahora se sabe cómo interpretarlas.'
    );
  }, []);

  /** Clic en una entidad: acumula con Ctrl/Shift, reemplaza sin ellos. */
  const elegir = useCallback((handle: string, acumular: boolean) => {
    setElegidos((prev) => {
      if (!handle) return acumular ? prev : new Set<string>();
      if (!acumular) return new Set([handle]);
      const nuevo = new Set(prev);
      if (nuevo.has(handle)) nuevo.delete(handle);
      else nuevo.add(handle);
      return nuevo;
    });
  }, [documento, proyeccion]);

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
        formaArea={formaArea}
        onFormaArea={setFormaArea}
        hayArea={area !== null}
        elegidas={elegidos.size}
        onLimpiarSeleccion={() => setElegidos(new Set())}
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
        <div className="columna-izquierda">
          <PanelCapas
            capas={documento?.geometria.capas ?? []}
            visibles={capasVisibles}
            onCambiar={cambiarCapa}
            onTodas={todasLasCapas}
          />
          {documento && (
            <ControlSatelital
              proyeccion={proyeccion}
              sugeridos={documento.crsSugeridos ?? []}
              fuentes={fuentes}
              fuenteActiva={fuenteSatelital}
              opacidad={opacidadSatelital}
              onFuente={setFuenteSatelital}
              onOpacidad={setOpacidadSatelital}
              onAsignarCrs={asignarCrs}
            />
          )}
        </div>
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
                formaArea={formaArea}
                area={area}
                onArea={(a) => { setArea(a); if (a) setModoArea(false); }}
                elegidos={elegidos}
                onElegir={elegir}
                proj4Plano={proyeccion?.proj4 ?? null}
                fuenteSatelital={fuenteSatelital}
                opacidadSatelital={opacidadSatelital}
              />
              {modoArea && (
                <div className="pista-area">
                  {formaArea === 'libre'
                    ? 'Mantenga pulsado y dibuje el contorno de lo que quiere exportar'
                    : 'Mantenga pulsado y arrastre para marcar un rectángulo'}
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
          elegidos={elegidos}
          onCancelar={() => setDialogoExportar(false)}
          onExportar={exportar}
        />
      )}
      <AvisoActualizacion info={actualizacion} onCerrar={() => setActualizacion(null)} />
    </div>
  );
}

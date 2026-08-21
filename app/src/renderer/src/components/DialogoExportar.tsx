/** Diálogo de exportación: formato de salida y qué parte del dibujo. */
import { useMemo, useState } from 'react';
import type { Documento, OpcionesExportar } from '../lib/tipos';

interface Props {
  documento: Documento;
  capasVisibles: Record<string, boolean>;
  area: [number, number][] | null;
  elegidos: Set<string>;
  onCancelar: () => void;
  onExportar: (opciones: OpcionesExportar) => void;
}

type Alcance = 'todo' | 'seleccion' | 'filtros';

export default function DialogoExportar({
  documento, capasVisibles, area, elegidos, onCancelar, onExportar
}: Props) {
  const capas = documento.geometria.capas;
  const ocultas = useMemo(
    () => capas.filter((c) => capasVisibles[c.nombre] === false).map((c) => c.nombre),
    [capas, capasVisibles]
  );
  const hayElegidas = elegidos.size > 0;
  const hayFiltros = ocultas.length > 0 || area !== null;

  const [formato, setFormato] = useState<'dxf' | 'shp' | 'pdf'>('dxf');
  const [tamanoPdf, setTamanoPdf] = useState<'A4' | 'A3'>('A4');
  const [alcance, setAlcance] = useState<Alcance>(
    hayElegidas ? 'seleccion' : hayFiltros ? 'filtros' : 'todo'
  );
  const [usarCapas, setUsarCapas] = useState(ocultas.length > 0);
  const [usarArea, setUsarArea] = useState(area !== null);
  const [modoArea, setModoArea] = useState<'contenida' | 'intersecta'>('intersecta');

  const exportar = () => {
    const opciones: OpcionesExportar = { formato };
    if (formato === 'pdf') opciones.tamanoPdf = tamanoPdf;
    if (alcance === 'seleccion' && hayElegidas) {
      opciones.handles = [...elegidos];
    } else if (alcance === 'filtros') {
      if (usarCapas && ocultas.length > 0) {
        opciones.capas = capas
          .filter((c) => capasVisibles[c.nombre] !== false)
          .map((c) => c.nombre);
      }
      if (usarArea && area) {
        opciones.poligono = area;
        opciones.modoArea = modoArea;
      }
    }
    onExportar(opciones);
  };

  return (
    <div className="velo" onClick={onCancelar}>
      <div className="dialogo" onClick={(ev) => ev.stopPropagation()}>
        <h2>Exportar</h2>

        <div className="grupo-formato">
          <span className="etiqueta-grupo">Formato</span>
          <div className="botones-formato">
            <button
              className={formato === 'dxf' ? 'activo' : ''}
              onClick={() => setFormato('dxf')}
            >
              DXF
              <small>Dibujo CAD fiel</small>
            </button>
            <button
              className={formato === 'shp' ? 'activo' : ''}
              onClick={() => setFormato('shp')}
            >
              Shapefile
              <small>Capas SIG para QGIS</small>
            </button>
            <button
              className={formato === 'pdf' ? 'activo' : ''}
              onClick={() => setFormato('pdf')}
            >
              PDF
              <small>Plano para imprimir</small>
            </button>
          </div>
          {formato === 'pdf' && (
            <div className="modo-area">
              <label>
                <input
                  type="radio" name="tamanoPdf" checked={tamanoPdf === 'A4'}
                  onChange={() => setTamanoPdf('A4')}
                />
                Hoja A4
              </label>
              <label>
                <input
                  type="radio" name="tamanoPdf" checked={tamanoPdf === 'A3'}
                  onChange={() => setTamanoPdf('A3')}
                />
                Hoja A3
              </label>
            </div>
          )}
        </div>

        <span className="etiqueta-grupo">Qué exportar</span>

        <label className={`opcion${hayElegidas ? '' : ' deshabilitada'}`}>
          <input
            type="radio" name="alcance" checked={alcance === 'seleccion'}
            disabled={!hayElegidas}
            onChange={() => setAlcance('seleccion')}
          />
          <div>
            <strong>
              Solo lo seleccionado
              {hayElegidas && <span className="contador">{elegidos.size}</span>}
            </strong>
            <small>
              {hayElegidas
                ? 'Exactamente las entidades que marcó con clic: ni cotas ni nada más.'
                : 'Haga clic sobre las líneas en el plano (Ctrl+clic para añadir más).'}
            </small>
          </div>
        </label>

        <label className={`opcion${hayFiltros ? '' : ' deshabilitada'}`}>
          <input
            type="radio" name="alcance" checked={alcance === 'filtros'}
            disabled={!hayFiltros}
            onChange={() => setAlcance('filtros')}
          />
          <div>
            <strong>Por capas y área</strong>
            <small>
              {hayFiltros
                ? 'Lo que quede tras ocultar capas y marcar un contorno.'
                : 'Oculte capas en el panel izquierdo o dibuje un contorno con «✎ Marcar área».'}
            </small>
          </div>
        </label>

        {alcance === 'filtros' && hayFiltros && (
          <div className="sub-opciones">
            <label className={ocultas.length === 0 ? 'deshabilitada' : ''}>
              <input
                type="checkbox" checked={usarCapas} disabled={ocultas.length === 0}
                onChange={(ev) => setUsarCapas(ev.target.checked)}
              />
              Solo capas visibles
              {ocultas.length > 0 && (
                <small> — se excluyen {ocultas.length} de {capas.length}</small>
              )}
            </label>
            <label className={area ? '' : 'deshabilitada'}>
              <input
                type="checkbox" checked={usarArea} disabled={!area}
                onChange={(ev) => setUsarArea(ev.target.checked)}
              />
              Solo el área marcada
            </label>
            {usarArea && area && (
              <div className="modo-area">
                <label>
                  <input
                    type="radio" name="modoArea" checked={modoArea === 'intersecta'}
                    onChange={() => setModoArea('intersecta')}
                  />
                  Incluir lo que toca el borde
                </label>
                <label>
                  <input
                    type="radio" name="modoArea" checked={modoArea === 'contenida'}
                    onChange={() => setModoArea('contenida')}
                  />
                  Solo lo totalmente dentro
                </label>
              </div>
            )}
          </div>
        )}

        <label className="opcion">
          <input
            type="radio" name="alcance" checked={alcance === 'todo'}
            onChange={() => setAlcance('todo')}
          />
          <div>
            <strong>Todo el dibujo</strong>
            <small>
              {formato === 'dxf'
                ? 'Copia 1:1 exacta: ninguna entidad se toca.'
                : formato === 'shp'
                  ? 'Todas las entidades, repartidas por tipo de geometría.'
                  : 'Todo el plano encuadrado en la hoja.'}
            </small>
          </div>
        </label>

        <p className="nota-georref">
          {formato === 'shp'
            ? 'Se generan hasta cuatro archivos (polígonos, líneas, puntos y textos), ' +
              'cada uno con su .prj. Las coordenadas son las originales del plano.'
            : formato === 'pdf'
              ? 'PDF vectorial con los colores del dibujo, oscureciendo solo los ' +
                'tonos que no se leerían sobre papel blanco. Al pie va la escala y ' +
                'el rango de coordenadas.'
              : 'Las coordenadas y la georreferenciación se conservan intactas; ' +
                'junto al DXF se generan el .prj y los metadatos.'}
          {documento.georref.epsg ? ` EPSG:${documento.georref.epsg}.` : ''}
        </p>

        <div className="acciones-dialogo">
          <button onClick={onCancelar}>Cancelar</button>
          <button className="principal" onClick={exportar}>
            ⬇ Exportar {formato === 'shp' ? 'Shapefile' : formato === 'pdf' ? 'PDF' : 'DXF'}
          </button>
        </div>
      </div>
    </div>
  );
}

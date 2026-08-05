/** Diálogo de exportación: todo el dibujo o solo una selección. */
import { useMemo, useState } from 'react';
import type { Documento, OpcionesExportar } from '../lib/tipos';

interface Props {
  documento: Documento;
  capasVisibles: Record<string, boolean>;
  area: [number, number, number, number] | null;
  onCancelar: () => void;
  onExportar: (opciones: OpcionesExportar) => void;
}

export default function DialogoExportar({
  documento, capasVisibles, area, onCancelar, onExportar
}: Props) {
  const capas = documento.geometria.capas;
  const ocultas = useMemo(
    () => capas.filter((c) => capasVisibles[c.nombre] === false).map((c) => c.nombre),
    [capas, capasVisibles]
  );
  const hayFiltroPosible = ocultas.length > 0 || area !== null;

  const [alcance, setAlcance] = useState<'todo' | 'seleccion'>(
    hayFiltroPosible ? 'seleccion' : 'todo'
  );
  const [usarCapas, setUsarCapas] = useState(ocultas.length > 0);
  const [usarArea, setUsarArea] = useState(area !== null);
  const [modoArea, setModoArea] = useState<'contenida' | 'intersecta'>('intersecta');

  const exportar = () => {
    if (alcance === 'todo' || (!usarCapas && !usarArea)) {
      onExportar({});
      return;
    }
    onExportar({
      capas: usarCapas
        ? capas.filter((c) => capasVisibles[c.nombre] !== false).map((c) => c.nombre)
        : undefined,
      area: usarArea && area ? area : undefined,
      modoArea
    });
  };

  return (
    <div className="velo" onClick={onCancelar}>
      <div className="dialogo" onClick={(ev) => ev.stopPropagation()}>
        <h2>Exportar a DXF</h2>

        <label className="opcion">
          <input
            type="radio" name="alcance" checked={alcance === 'todo'}
            onChange={() => setAlcance('todo')}
          />
          <div>
            <strong>Todo el dibujo</strong>
            <small>
              Copia 1:1 exacta del DWG convertido: ninguna entidad se toca.
            </small>
          </div>
        </label>

        <label className={`opcion${hayFiltroPosible ? '' : ' deshabilitada'}`}>
          <input
            type="radio" name="alcance" checked={alcance === 'seleccion'}
            disabled={!hayFiltroPosible}
            onChange={() => setAlcance('seleccion')}
          />
          <div>
            <strong>Solo la selección</strong>
            <small>
              {hayFiltroPosible
                ? 'Exporta únicamente lo elegido. Lo exportado conserva sus coordenadas y georreferencia exactas.'
                : 'Para habilitarlo: oculte capas en el panel izquierdo o marque un área con el botón «▭ Marcar área».'}
            </small>
          </div>
        </label>

        {alcance === 'seleccion' && hayFiltroPosible && (
          <div className="sub-opciones">
            <label className={ocultas.length === 0 ? 'deshabilitada' : ''}>
              <input
                type="checkbox" checked={usarCapas} disabled={ocultas.length === 0}
                onChange={(ev) => setUsarCapas(ev.target.checked)}
              />
              Solo capas visibles
              {ocultas.length > 0 && (
                <small> — se excluyen {ocultas.length} de {capas.length} capas</small>
              )}
            </label>
            <label className={area ? '' : 'deshabilitada'}>
              <input
                type="checkbox" checked={usarArea} disabled={!area}
                onChange={(ev) => setUsarArea(ev.target.checked)}
              />
              Solo el área marcada
              {!area && <small> — no hay área marcada en el visor</small>}
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

        <p className="nota-georref">
          La georreferenciación (EPSG{documento.georref.epsg ? `:${documento.georref.epsg}` : ''})
          y las coordenadas originales se conservan en cualquiera de las dos opciones;
          junto al DXF se generan el .prj y los metadatos.
        </p>

        <div className="acciones-dialogo">
          <button onClick={onCancelar}>Cancelar</button>
          <button className="principal" onClick={exportar}>⬇ Exportar</button>
        </div>
      </div>
    </div>
  );
}

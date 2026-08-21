/** Barra superior: abrir, cerrar, marcar área, exportar, tema y datos del archivo. */
import { TEMAS, type NombreTema } from '../lib/tema';
import type { Documento } from '../lib/tipos';

interface Props {
  documento: Documento | null;
  ocupado: boolean;
  modoArea: boolean;
  formaArea: 'libre' | 'rectangulo';
  onFormaArea: (f: 'libre' | 'rectangulo') => void;
  hayArea: boolean;
  /** Cuántas entidades se han elegido con clic. */
  elegidas: number;
  onLimpiarSeleccion: () => void;
  tema: NombreTema;
  onAbrir: () => void;
  onCerrar: () => void;
  onExportar: () => void;
  onAjustar: () => void;
  onModoArea: () => void;
  onLimpiarArea: () => void;
  onTema: (t: NombreTema) => void;
}

export default function BarraHerramientas({
  documento, ocupado, modoArea, formaArea, onFormaArea, hayArea, elegidas, tema,
  onAbrir, onCerrar, onExportar, onAjustar, onModoArea, onLimpiarArea,
  onLimpiarSeleccion, onTema
}: Props) {
  const georref = documento?.georref;
  return (
    <header className="barra">
      <span className="logo">CAD <b>LIBRE</b></span>
      <button className="principal" onClick={onAbrir} disabled={ocupado}>
        {ocupado ? 'Procesando…' : documento ? '📂 Abrir otro' : '📂 Abrir DWG'}
      </button>
      {documento && (
        <button onClick={onCerrar} disabled={ocupado} title="Cerrar el dibujo actual">
          ✕ Cerrar
        </button>
      )}
      <button onClick={onAjustar} disabled={!documento}>⤢ Ajustar vista</button>
      <span className="grupo-area">
        <button
          className={modoArea ? 'activo' : ''}
          onClick={onModoArea}
          disabled={!documento}
          title="Marque en el plano la zona que quiere exportar"
        >
          {formaArea === 'libre' ? '✎' : '▭'} {modoArea ? 'Trazando…' : 'Marcar área'}
        </button>
        <select
          className="forma-area"
          value={formaArea}
          disabled={!documento}
          onChange={(ev) => onFormaArea(ev.target.value as 'libre' | 'rectangulo')}
          title="Forma del contorno"
        >
          <option value="libre">Libre</option>
          <option value="rectangulo">Rectángulo</option>
        </select>
      </span>
      {hayArea && (
        <button onClick={onLimpiarArea} title="Quitar el área marcada">✕ Quitar área</button>
      )}
      {elegidas > 0 && (
        <button
          className="seleccion-activa"
          onClick={onLimpiarSeleccion}
          title="Vaciar la selección de entidades"
        >
          ✕ {elegidas} seleccionada{elegidas === 1 ? '' : 's'}
        </button>
      )}
      <button className="exportar" onClick={onExportar} disabled={!documento || ocupado}>
        ⬇ Exportar DXF
      </button>

      <span className="espaciador" />

      <label className="selector-tema" title="Color de fondo del visor">
        🎨
        <select value={tema} onChange={(ev) => onTema(ev.target.value as NombreTema)}>
          {Object.values(TEMAS).map((t) => (
            <option key={t.nombre} value={t.nombre}>{t.etiqueta}</option>
          ))}
        </select>
      </label>

      {documento && (
        <span className="info-archivo" title={documento.origen}>
          {nombreBase(documento.origen)}
          {georref?.epsg ? (
            <span className="epsg" title={georref.nombreCrs ?? ''}>EPSG:{georref.epsg}</span>
          ) : georref?.tieneGeodata ? (
            <span className="epsg neutro">GEODATA</span>
          ) : (
            <span className="epsg neutro" title="El DWG no trae CRS embebido">sin CRS</span>
          )}
        </span>
      )}
    </header>
  );
}

function nombreBase(ruta: string): string {
  return ruta.split(/[\\/]/).pop() ?? ruta;
}

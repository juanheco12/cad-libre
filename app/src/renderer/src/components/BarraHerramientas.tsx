/** Barra superior: abrir, cerrar, marcar área, exportar, tema y datos del archivo. */
import { TEMAS, type NombreTema } from '../lib/tema';
import type { Documento } from '../lib/tipos';

interface Props {
  documento: Documento | null;
  ocupado: boolean;
  modoArea: boolean;
  hayArea: boolean;
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
  documento, ocupado, modoArea, hayArea, tema,
  onAbrir, onCerrar, onExportar, onAjustar, onModoArea, onLimpiarArea, onTema
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
      <button
        className={modoArea ? 'activo' : ''}
        onClick={onModoArea}
        disabled={!documento}
        title="Dibuje a mano alzada el contorno de lo que quiere exportar"
      >
        ✎ {modoArea ? 'Trazando…' : 'Marcar área'}
      </button>
      {hayArea && (
        <button onClick={onLimpiarArea} title="Quitar el área marcada">✕ Quitar área</button>
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

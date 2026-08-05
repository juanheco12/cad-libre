/** Barra superior: abrir, exportar, ajustar vista y datos del archivo. */
import type { Documento } from '../lib/tipos';

interface Props {
  documento: Documento | null;
  ocupado: boolean;
  onAbrir: () => void;
  onExportar: () => void;
  onAjustar: () => void;
}

export default function BarraHerramientas({
  documento, ocupado, onAbrir, onExportar, onAjustar
}: Props) {
  const georref = documento?.georref;
  return (
    <header className="barra">
      <span className="logo">CAD <b>LIBRE</b></span>
      <button className="principal" onClick={onAbrir} disabled={ocupado}>
        {ocupado ? 'Abriendo…' : '📂 Abrir DWG'}
      </button>
      <button onClick={onAjustar} disabled={!documento}>⤢ Ajustar vista</button>
      <button className="exportar" onClick={onExportar} disabled={!documento || ocupado}>
        ⬇ Exportar DXF
      </button>
      <span className="espaciador" />
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

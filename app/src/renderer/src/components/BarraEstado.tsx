/** Barra inferior: coordenadas del cursor, selección, motor y resumen. */
import type { Documento, Seleccion } from '../lib/tipos';

interface Props {
  documento: Documento | null;
  cursor: [number, number] | null;
  seleccion: Seleccion | null;
  motor: string | null;
  mensaje: string | null;
}

export default function BarraEstado({ documento, cursor, seleccion, motor, mensaje }: Props) {
  return (
    <footer className="estado">
      {cursor && (
        <span className="coordenadas">
          X: {formato(cursor[0])}&nbsp;&nbsp;Y: {formato(cursor[1])}
        </span>
      )}
      {seleccion && (
        <span className="seleccion">
          ▸ {seleccion.tipo} · capa «{seleccion.capa}» · handle {seleccion.handle}
        </span>
      )}
      {documento && (
        <span>
          {documento.inventario.entidades.toLocaleString('es-CO')} entidades ·{' '}
          {documento.inventario.capas} capas · {documento.inventario.unidades} ·{' '}
          DXF {documento.inventario.versionDxf}
        </span>
      )}
      <span className="espaciador" />
      {mensaje && <span className="mensaje">{mensaje}</span>}
      <span className={motor ? 'motor ok' : 'motor falta'}>
        {motor ? `Motor: ${motor}` : 'ODA File Converter no detectado (solo DXF)'}
      </span>
    </footer>
  );
}

const formato = (n: number) =>
  n.toLocaleString('es-CO', { minimumFractionDigits: 3, maximumFractionDigits: 3 });

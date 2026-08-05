/** Aviso flotante del estado de la actualización automática. */
import type { InfoActualizacion } from '../lib/tipos';

interface Props {
  info: InfoActualizacion | null;
  onCerrar: () => void;
}

export default function AvisoActualizacion({ info, onCerrar }: Props) {
  // Sin novedad o error se manejan en silencio: no vale la pena molestar.
  if (!info || info.estado === 'sin-novedad' || info.estado === 'error') return null;

  const textos: Record<string, string> = {
    buscando: 'Buscando actualizaciones…',
    disponible: `Versión ${info.version} disponible, descargando…`,
    descargando: `Descargando ${info.version}… ${Math.round(info.porcentaje ?? 0)}%`,
    lista: `Versión ${info.version} lista para instalar`
  };

  return (
    <div className={`aviso-actualizacion${info.estado === 'lista' ? ' listo' : ''}`}>
      <span>{textos[info.estado]}</span>
      {info.estado === 'lista' && (
        <button className="principal" onClick={() => window.cadlibre.instalarActualizacion()}>
          Reiniciar e instalar
        </button>
      )}
      <button className="cerrar" onClick={onCerrar} title="Ocultar">✕</button>
    </div>
  );
}

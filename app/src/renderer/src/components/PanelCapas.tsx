/** Panel lateral con las capas del dibujo y su visibilidad. */
import type { Capa } from '../lib/tipos';

interface Props {
  capas: Capa[];
  visibles: Record<string, boolean>;
  onCambiar: (nombre: string, visible: boolean) => void;
  onTodas: (visible: boolean) => void;
}

export default function PanelCapas({ capas, visibles, onCambiar, onTodas }: Props) {
  if (capas.length === 0) {
    return <aside className="panel-capas vacio">Sin dibujo abierto</aside>;
  }
  return (
    <aside className="panel-capas">
      <header>
        <span>Capas ({capas.length})</span>
        <span className="acciones">
          <button title="Mostrar todas" onClick={() => onTodas(true)}>👁</button>
          <button title="Ocultar todas" onClick={() => onTodas(false)}>✕</button>
        </span>
      </header>
      <ul>
        {capas.map((capa) => {
          const visible = visibles[capa.nombre] !== false;
          return (
            <li
              key={capa.nombre}
              className={visible ? '' : 'oculta'}
              onClick={() => onCambiar(capa.nombre, !visible)}
              title={capa.nombre}
            >
              <input type="checkbox" checked={visible} readOnly />
              <span className="muestra" style={{ background: capa.color }} />
              <span className="nombre">{capa.nombre}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

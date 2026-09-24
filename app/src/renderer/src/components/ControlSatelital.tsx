/**
 * Control de la imagen satelital de fondo.
 *
 * Solo tiene sentido si se sabe en qué sistema de coordenadas está el plano:
 * sin eso no hay forma de saber en qué parte del mundo colocarlo. Cuando el
 * archivo no lo declara, aquí se ofrece elegirlo entre los que encajan.
 */
import type { CrsSugerido, FuenteSatelital, Proyeccion } from '../lib/tipos';

interface Props {
  proyeccion: Proyeccion | null;
  sugeridos: CrsSugerido[];
  fuentes: FuenteSatelital[];
  fuenteActiva: string | null;
  opacidad: number;
  onFuente: (id: string | null) => void;
  onOpacidad: (v: number) => void;
  onAsignarCrs: (epsg: number) => void;
}

export default function ControlSatelital({
  proyeccion, sugeridos, fuentes, fuenteActiva, opacidad,
  onFuente, onOpacidad, onAsignarCrs
}: Props) {
  // Sin sistema de coordenadas conocido no se puede situar el plano
  if (!proyeccion) {
    if (sugeridos.length === 0) {
      return (
        <div className="panel-satelite sin-crs">
          <span className="titulo">🛰 Imagen satelital</span>
          <p>
            Este dibujo no declara su sistema de coordenadas y sus valores no
            corresponden a ninguno conocido de Colombia, así que no se puede
            situar sobre el mapa.
          </p>
        </div>
      );
    }
    return (
      <div className="panel-satelite sin-crs">
        <span className="titulo">🛰 Imagen satelital</span>
        <p>
          El dibujo no dice en qué sistema está. Con estos, el plano caería
          dentro de Colombia:
        </p>
        <ul className="sugerencias">
          {sugeridos.map((s) => (
            <li key={s.epsg}>
              <button onClick={() => onAsignarCrs(s.epsg)}>
                <strong>EPSG:{s.epsg}</strong>
                <span>{s.nombre}</span>
                <small>
                  lo situaría en {s.lat.toFixed(4)}°, {s.lon.toFixed(4)}°
                </small>
              </button>
            </li>
          ))}
        </ul>
        <p className="aviso">
          Confirme cuál corresponde: un sistema equivocado desplazaría el plano.
        </p>
      </div>
    );
  }

  return (
    <div className="panel-satelite">
      <div className="fila-titulo">
        <span className="titulo">🛰 Imagen satelital</span>
        <label className="interruptor" title="Encender o apagar el fondo">
          <input
            type="checkbox"
            checked={fuenteActiva !== null}
            onChange={(ev) => onFuente(ev.target.checked ? (fuentes[0]?.id ?? null) : null)}
          />
          <span className="palanca" />
        </label>
      </div>

      <span className="crs-actual" title={proyeccion.nombre}>
        EPSG:{proyeccion.epsg} · {proyeccion.nombre}
      </span>

      {fuenteActiva && (
        <>
          {fuentes.length > 1 && (
            <select
              value={fuenteActiva}
              onChange={(ev) => onFuente(ev.target.value)}
            >
              {fuentes.map((f) => (
                <option key={f.id} value={f.id}>{f.nombre}</option>
              ))}
            </select>
          )}
          <label className="deslizador">
            Opacidad
            <input
              type="range" min={20} max={100} step={5}
              value={Math.round(opacidad * 100)}
              onChange={(ev) => onOpacidad(Number(ev.target.value) / 100)}
            />
            <span>{Math.round(opacidad * 100)}%</span>
          </label>
          <small className="atribucion">
            {fuentes.find((f) => f.id === fuenteActiva)?.atribucion}
          </small>
        </>
      )}
    </div>
  );
}

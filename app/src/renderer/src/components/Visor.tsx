/**
 * Visor 2D sobre canvas.
 *
 * - Las coordenadas de mundo son las ORIGINALES del plano (no se transforman
 *   los datos: solo la cámara). El eje Y se invierte al dibujar porque el
 *   canvas crece hacia abajo.
 * - Para dibujos grandes, la geometría se compila una vez en objetos Path2D
 *   agrupados por capa+color; cada cuadro solo se re-traza con la transformación
 *   de cámara actual (rápido y con poca memoria).
 * - Rueda: zoom al cursor. Arrastre: pan. Clic corto: selección por cercanía.
 * - Modo área: se dibuja un contorno libre a mano alzada para exportar solo
 *   lo que quede dentro.
 */
import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { Entidad, EntidadPolilinea, EntidadTexto, Geometria, Seleccion } from '../lib/tipos';
import { colorVisible, type Tema } from '../lib/tema';

interface Props {
  geometria: Geometria | null;
  capasVisibles: Record<string, boolean>;
  seleccion: Seleccion | null;
  onSeleccion: (s: Seleccion | null) => void;
  /** Handles de las entidades elegidas para exportar. */
  elegidos: Set<string>;
  /** Alterna una entidad en la selección (clic) o la deja como única (sin acumular). */
  onElegir: (handle: string, acumular: boolean) => void;
  onCursor: (x: number, y: number) => void;
  ajustarSenal: number; // incrementa para pedir "zoom a extensión"
  tema: Tema;
  /** Modo "marcar área de exportación": el arrastre dibuja el contorno. */
  modoArea: boolean;
  /** Forma del contorno: a mano alzada o rectángulo. */
  formaArea: 'libre' | 'rectangulo';
  /** Contorno cerrado en coordenadas del dibujo, o null. */
  area: [number, number][] | null;
  onArea: (a: [number, number][] | null) => void;
}

interface Camara {
  escala: number;   // píxeles por unidad de dibujo
  cx: number;       // centro de la vista en coordenadas de mundo
  cy: number;
}

interface GrupoTrazo {
  capa: string;
  color: string;
  path: Path2D;
}

const COLOR_SELECCION = '#39ff14';
const COLOR_ELEGIDA = '#00d0ff';
/** Grosor en píxeles del resaltado de lo elegido (constante a cualquier zoom). */
const GROSOR_ELEGIDA = 4;
/** Por debajo de este tamaño en pantalla, la entidad se marca con un recuadro. */
const MINIMO_VISIBLE_PX = 70;
/** Movimiento total tolerado para que un arrastre siga contando como clic. */
const UMBRAL_CLIC_PX = 6;
const COLOR_AREA = '#ff8c00';
/** Separación mínima en píxeles entre puntos del trazo libre. */
const PASO_TRAZO = 4;

export default function Visor({
  geometria, capasVisibles, seleccion, onSeleccion, onCursor, ajustarSenal,
  tema, modoArea, formaArea, area, onArea, elegidos, onElegir
}: Props) {
  const refLienzo = useRef<HTMLCanvasElement>(null);
  const refCamara = useRef<Camara>({ escala: 1, cx: 0, cy: 0 });
  const refArrastre = useRef<
    { x: number; y: number; movido: boolean; x0: number; y0: number } | null
  >(null);
  const refPintar = useRef<() => void>(() => {});
  /** Contorno que se está trazando (coordenadas de mundo). */
  const refTrazo = useRef<[number, number][] | null>(null);
  /** Esquina donde empezó el rectángulo. */
  const refInicioArea = useRef<[number, number] | null>(null);

  // ---- compilación de la geometría a Path2D por (capa, color) -------------
  const grupos = useMemo<GrupoTrazo[]>(() => {
    if (!geometria) return [];
    const mapa = new Map<string, GrupoTrazo>();
    for (const e of geometria.entidades) {
      if (!('p' in e)) continue;
      const clave = `${e.l} ${e.c}`;
      let grupo = mapa.get(clave);
      if (!grupo) {
        grupo = { capa: e.l, color: e.c, path: new Path2D() };
        mapa.set(clave, grupo);
      }
      for (const linea of (e as EntidadPolilinea).p) {
        grupo.path.moveTo(linea[0], linea[1]);
        for (let i = 2; i < linea.length; i += 2) {
          grupo.path.lineTo(linea[i], linea[i + 1]);
        }
      }
    }
    return [...mapa.values()];
  }, [geometria]);

  const textos = useMemo<EntidadTexto[]>(
    () => (geometria ? geometria.entidades.filter((e): e is EntidadTexto => e.t === 'TEXTO') : []),
    [geometria]
  );
  const puntos = useMemo(
    () => (geometria ? geometria.entidades.filter((e) => e.t === 'PUNTO') : []),
    [geometria]
  );

  // ---- cámara -------------------------------------------------------------
  const ajustarVista = useCallback(() => {
    const lienzo = refLienzo.current;
    if (!lienzo || !geometria) return;
    const [minX, minY, maxX, maxY] = geometria.extension;
    const ancho = Math.max(maxX - minX, 1e-9);
    const alto = Math.max(maxY - minY, 1e-9);
    const margen = 0.94;
    refCamara.current = {
      escala: Math.min((lienzo.clientWidth / ancho), (lienzo.clientHeight / alto)) * margen,
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2
    };
    refPintar.current();
  }, [geometria]);

  const aMundo = useCallback((px: number, py: number): [number, number] => {
    const lienzo = refLienzo.current!;
    const { escala, cx, cy } = refCamara.current;
    return [
      cx + (px - lienzo.clientWidth / 2) / escala,
      cy - (py - lienzo.clientHeight / 2) / escala
    ];
  }, []);

  // ---- pintado ------------------------------------------------------------
  const pintar = useCallback(() => {
    const lienzo = refLienzo.current;
    if (!lienzo) return;
    const ctx = lienzo.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const ancho = lienzo.clientWidth;
    const alto = lienzo.clientHeight;
    if (lienzo.width !== ancho * dpr || lienzo.height !== alto * dpr) {
      lienzo.width = ancho * dpr;
      lienzo.height = alto * dpr;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = tema.fondo;
    ctx.fillRect(0, 0, ancho, alto);
    if (!geometria) return;

    const { escala, cx, cy } = refCamara.current;
    const aPantalla = () =>
      ctx.transform(escala, 0, 0, -escala, ancho / 2 - cx * escala, alto / 2 + cy * escala);

    // mundo → pantalla: trasladar al centro, escalar e invertir Y
    ctx.save();
    aPantalla();
    ctx.lineWidth = 1 / escala;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    for (const grupo of grupos) {
      if (capasVisibles[grupo.capa] === false) continue;
      ctx.strokeStyle = colorVisible(grupo.color, tema);
      ctx.stroke(grupo.path);
    }

    // puntos como cruces pequeñas
    const cruz = 3 / escala;
    for (const p of puntos) {
      if (capasVisibles[p.l] === false) continue;
      const punto = p as { x: number; y: number; c: string };
      ctx.strokeStyle = colorVisible(punto.c, tema);
      ctx.beginPath();
      ctx.moveTo(punto.x - cruz, punto.y);
      ctx.lineTo(punto.x + cruz, punto.y);
      ctx.moveTo(punto.x, punto.y - cruz);
      ctx.lineTo(punto.x, punto.y + cruz);
      ctx.stroke();
    }
    ctx.restore();

    // textos en espacio de pantalla (sin espejo por la inversión de Y)
    for (const t of textos) {
      if (capasVisibles[t.l] === false) continue;
      const alturaPx = t.alt * escala;
      if (alturaPx < 3 || alturaPx > 4000) continue; // ilegible o descomunal
      const sx = ancho / 2 + (t.x - cx) * escala;
      const sy = alto / 2 - (t.y - cy) * escala;
      ctx.save();
      ctx.translate(sx, sy);
      if (t.rot) ctx.rotate((-t.rot * Math.PI) / 180);
      ctx.font = `${alturaPx}px "Segoe UI", sans-serif`;
      ctx.fillStyle = colorVisible(t.c, tema);
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(t.s, 0, 0);
      ctx.restore();
    }

    // contorno del área (el marcado o el que se está trazando)
    const contorno = refTrazo.current ?? area;
    if (contorno && contorno.length >= 2) {
      ctx.save();
      aPantalla();
      ctx.beginPath();
      ctx.moveTo(contorno[0][0], contorno[0][1]);
      for (let i = 1; i < contorno.length; i++) ctx.lineTo(contorno[i][0], contorno[i][1]);
      if (!refTrazo.current) ctx.closePath(); // ya cerrado cuando está confirmado
      ctx.fillStyle = 'rgba(255, 140, 0, 0.10)';
      ctx.fill();
      ctx.lineWidth = 1.6 / escala;
      ctx.setLineDash([6 / escala, 4 / escala]);
      ctx.strokeStyle = COLOR_AREA;
      ctx.stroke();
      ctx.restore();
    }

    // Entidades elegidas para exportar. Se pinta en espacio de PANTALLA para
    // que el grosor no dependa del zoom, con un halo oscuro debajo que las
    // hace visibles sobre cualquier fondo, y un recuadro cuando la entidad
    // queda tan pequeña en pantalla que el trazo solo no se distinguiría.
    if (elegidos.size > 0) {
      const aPx = (x: number, y: number): [number, number] => [
        ancho / 2 + (x - cx) * escala,
        alto / 2 - (y - cy) * escala
      ];
      ctx.save();
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';

      for (const e of geometria.entidades) {
        if (!elegidos.has(e.h)) continue;

        if ('p' in e) {
          let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
          // Dos pasadas: halo oscuro ancho y encima el cian.
          for (const paso of [0, 1]) {
            ctx.strokeStyle = paso === 0 ? 'rgba(0,0,0,0.75)' : COLOR_ELEGIDA;
            ctx.lineWidth = paso === 0 ? GROSOR_ELEGIDA + 3 : GROSOR_ELEGIDA;
            for (const linea of (e as EntidadPolilinea).p) {
              ctx.beginPath();
              const [x0, y0] = aPx(linea[0], linea[1]);
              ctx.moveTo(x0, y0);
              if (paso === 0) {
                minX = Math.min(minX, x0); maxX = Math.max(maxX, x0);
                minY = Math.min(minY, y0); maxY = Math.max(maxY, y0);
              }
              for (let i = 2; i < linea.length; i += 2) {
                const [px, py] = aPx(linea[i], linea[i + 1]);
                ctx.lineTo(px, py);
                if (paso === 0) {
                  minX = Math.min(minX, px); maxX = Math.max(maxX, px);
                  minY = Math.min(minY, py); maxY = Math.max(maxY, py);
                }
              }
              ctx.stroke();
            }
          }
          // Si es diminuta en pantalla, un recuadro delata dónde está
          const anchoPx = maxX - minX;
          const altoPx = maxY - minY;
          if (Number.isFinite(anchoPx) &&
              Math.max(anchoPx, altoPx) < MINIMO_VISIBLE_PX) {
            const m = 10;
            ctx.strokeStyle = COLOR_ELEGIDA;
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(minX - m, minY - m, anchoPx + m * 2, altoPx + m * 2);
            ctx.setLineDash([]);
          }
        } else {
          // Textos y puntos: círculo con halo, siempre del mismo tamaño
          const p = e as unknown as { x: number; y: number };
          const [sx, sy] = aPx(p.x, p.y);
          for (const paso of [0, 1]) {
            ctx.beginPath();
            ctx.arc(sx, sy, 7, 0, Math.PI * 2);
            ctx.strokeStyle = paso === 0 ? 'rgba(0,0,0,0.75)' : COLOR_ELEGIDA;
            ctx.lineWidth = paso === 0 ? 5 : 2.5;
            ctx.stroke();
          }
        }
      }
      ctx.restore();
    }

    // resaltado de la selección
    if (seleccion) {
      ctx.save();
      aPantalla();
      ctx.lineWidth = 2.5 / escala;
      ctx.strokeStyle = COLOR_SELECCION;
      for (const e of geometria.entidades) {
        if (e.h !== seleccion.handle || !('p' in e)) continue;
        for (const linea of (e as EntidadPolilinea).p) {
          ctx.beginPath();
          ctx.moveTo(linea[0], linea[1]);
          for (let i = 2; i < linea.length; i += 2) ctx.lineTo(linea[i], linea[i + 1]);
          ctx.stroke();
        }
      }
      ctx.restore();
    }
  }, [geometria, grupos, textos, puntos, capasVisibles, seleccion, area, tema, elegidos]);

  refPintar.current = pintar;

  useEffect(() => { pintar(); }, [pintar]);
  useEffect(() => { ajustarVista(); }, [ajustarSenal, ajustarVista]);
  useEffect(() => {
    const observador = new ResizeObserver(() => refPintar.current());
    if (refLienzo.current) observador.observe(refLienzo.current);
    return () => observador.disconnect();
  }, []);

  // ---- selección ----------------------------------------------------------
  const seleccionar = useCallback((px: number, py: number) => {
    if (!geometria) return;
    const [wx, wy] = aMundo(px, py);
    const tolerancia = 6 / refCamara.current.escala;
    let mejor: { d: number; e: Entidad } | null = null;

    for (const e of geometria.entidades) {
      if (capasVisibles[e.l] === false) continue;
      if ('p' in e) {
        for (const linea of e.p) {
          for (let i = 0; i + 3 < linea.length; i += 2) {
            const d = distanciaSegmento(wx, wy, linea[i], linea[i + 1], linea[i + 2], linea[i + 3]);
            if (d < tolerancia && (!mejor || d < mejor.d)) mejor = { d, e };
          }
        }
      } else if (e.t === 'TEXTO') {
        const t = e as EntidadTexto;
        const anchoAprox = t.alt * t.s.length * 0.65;
        if (wx >= t.x && wx <= t.x + anchoAprox && wy >= t.y && wy <= t.y + t.alt) {
          if (!mejor) mejor = { d: tolerancia, e };
        }
      } else if (e.t === 'PUNTO') {
        const p = e as { x: number; y: number };
        const d = Math.hypot(wx - p.x, wy - p.y);
        if (d < tolerancia && (!mejor || d < mejor.d)) mejor = { d, e };
      }
    }
    onSeleccion(mejor ? { handle: mejor.e.h, tipo: mejor.e.t, capa: mejor.e.l } : null);
    return mejor ? mejor.e.h : null;
  }, [geometria, capasVisibles, aMundo, onSeleccion]);

  // ---- eventos de ratón ---------------------------------------------------
  const alRodar = useCallback((ev: React.WheelEvent) => {
    const lienzo = refLienzo.current!;
    const rect = lienzo.getBoundingClientRect();
    const px = ev.clientX - rect.left;
    const py = ev.clientY - rect.top;
    const [wx, wy] = aMundo(px, py);
    const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
    const cam = refCamara.current;
    cam.escala *= factor;
    // mantener el punto bajo el cursor fijo en pantalla
    cam.cx = wx - (px - lienzo.clientWidth / 2) / cam.escala;
    cam.cy = wy + (py - lienzo.clientHeight / 2) / cam.escala;
    refPintar.current();
  }, [aMundo]);

  const alPresionar = useCallback((ev: React.MouseEvent) => {
    if (modoArea && ev.button === 0) {
      const rect = refLienzo.current!.getBoundingClientRect();
      const inicio = aMundo(ev.clientX - rect.left, ev.clientY - rect.top);
      refInicioArea.current = inicio;
      refTrazo.current = [inicio];
      return;
    }
    refArrastre.current = {
      x: ev.clientX, y: ev.clientY, movido: false,
      x0: ev.clientX, y0: ev.clientY
    };
  }, [modoArea, aMundo]);

  const alMover = useCallback((ev: React.MouseEvent) => {
    const rect = refLienzo.current!.getBoundingClientRect();
    const [wx, wy] = aMundo(ev.clientX - rect.left, ev.clientY - rect.top);
    onCursor(wx, wy);

    const trazo = refTrazo.current;
    if (trazo) {
      if (formaArea === 'rectangulo') {
        // El trazo son las cuatro esquinas: la inicial manda una, el cursor
        // la opuesta.
        const [ax, ay] = refInicioArea.current!;
        refTrazo.current = [[ax, ay], [wx, ay], [wx, wy], [ax, wy]];
        refPintar.current();
        return;
      }
      // A mano alzada: se añade un punto solo cuando el cursor avanzó lo
      // suficiente, para no acumular miles de vértices casi idénticos.
      const [ux, uy] = trazo[trazo.length - 1];
      const escala = refCamara.current.escala;
      if (Math.hypot(wx - ux, wy - uy) * escala >= PASO_TRAZO) {
        trazo.push([wx, wy]);
        refPintar.current();
      }
      return;
    }

    const arrastre = refArrastre.current;
    if (!arrastre) return;
    const dx = ev.clientX - arrastre.x;
    const dy = ev.clientY - arrastre.y;
    // El desplazamiento se mide desde donde SE PULSÓ, no desde el último
    // punto: así un pequeño temblor con el botón pulsado no cancela el clic
    // (era lo que hacía fallar el Ctrl+clic para añadir a la selección).
    if (Math.hypot(ev.clientX - arrastre.x0, ev.clientY - arrastre.y0) > UMBRAL_CLIC_PX) {
      arrastre.movido = true;
    }
    if (arrastre.movido) {
      const cam = refCamara.current;
      cam.cx -= dx / cam.escala;
      cam.cy += dy / cam.escala;
      arrastre.x = ev.clientX;
      arrastre.y = ev.clientY;
      refPintar.current();
    }
  }, [aMundo, onCursor, formaArea]);

  const terminarTrazo = useCallback(() => {
    const trazo = refTrazo.current;
    refTrazo.current = null;
    refInicioArea.current = null;
    if (!trazo) return false;
    // Menos de 3 puntos no encierra ningún área: se interpreta como "limpiar"
    onArea(trazo.length >= 3 ? trazo : null);
    return true;
  }, [onArea]);

  const alSoltar = useCallback((ev: React.MouseEvent) => {
    if (terminarTrazo()) return;
    const arrastre = refArrastre.current;
    refArrastre.current = null;
    if (arrastre && !arrastre.movido && ev.button === 0) {
      const rect = refLienzo.current!.getBoundingClientRect();
      const handle = seleccionar(ev.clientX - rect.left, ev.clientY - rect.top);
      // Ctrl o Shift acumulan; un clic limpio reemplaza la selección, igual
      // que en AutoCAD. Clic en vacío la vacía.
      onElegir(handle ?? '', ev.ctrlKey || ev.shiftKey);
    }
  }, [seleccionar, terminarTrazo, onElegir]);

  return (
    <canvas
      ref={refLienzo}
      className={`visor${modoArea ? ' marcando-area' : ''}`}
      onWheel={alRodar}
      onMouseDown={alPresionar}
      onMouseMove={alMover}
      onMouseUp={alSoltar}
      onMouseLeave={() => {
        refArrastre.current = null;
        terminarTrazo();
      }}
    />
  );
}

function distanciaSegmento(
  px: number, py: number, x1: number, y1: number, x2: number, y2: number
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const l2 = dx * dx + dy * dy;
  let t = l2 === 0 ? 0 : ((px - x1) * dx + (py - y1) * dy) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

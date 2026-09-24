/**
 * Capa de imagen satelital bajo el dibujo.
 *
 * El plano está en su sistema proyectado (p. ej. MAGNA-SIRGAS Origen-Nacional)
 * y los mosaicos satelitales en Web Mercator. Aquí se hace la conversión entre
 * ambos con proj4 y se calcula qué mosaicos hacen falta para la vista actual.
 *
 * Importante: el DIBUJO NO SE TOCA. Se reproyecta la cuadrícula de mosaicos al
 * sistema del plano, no al revés, así que las coordenadas de las entidades
 * siguen siendo exactamente las del archivo.
 */
import proj4 from 'proj4';

const WEB_MERCATOR =
  '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 ' +
  '+units=m +nadgrids=@null +no_defs';
/** Media circunferencia terrestre en metros: el borde del mundo en Mercator. */
const BORDE = 20037508.342789244;
const TAM_TILE = 256;
/** Nunca se piden más mosaicos que esto por cuadro: protege la memoria. */
const MAX_TILES = 240;

export interface Tile {
  z: number;
  x: number;
  y: number;
  /** Rectángulo que ocupa, ya en coordenadas del DIBUJO. */
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export class Proyector {
  private aMercator: proj4.Converter;
  private aPlano: proj4.Converter;

  constructor(proj4Plano: string) {
    this.aMercator = proj4(proj4Plano, WEB_MERCATOR);
    this.aPlano = proj4(WEB_MERCATOR, proj4Plano);
  }

  planoAMercator(x: number, y: number): [number, number] {
    const r = this.aMercator.forward([x, y]);
    return [r[0], r[1]];
  }

  mercatorAPlano(x: number, y: number): [number, number] {
    const r = this.aPlano.forward([x, y]);
    return [r[0], r[1]];
  }
}

/** Zoom de mosaico cuyo detalle coincide con los píxeles por unidad actuales. */
export function zoomParaEscala(
  metrosPorPixel: number, latitudAprox: number, zoomMaximo: number
): number {
  // Resolución de Web Mercator: 156543.03 m/px en z0, ajustada por latitud
  const resolucionZ0 = (2 * BORDE) / TAM_TILE;
  const factorLatitud = Math.cos((latitudAprox * Math.PI) / 180);
  const z = Math.log2((resolucionZ0 * factorLatitud) / metrosPorPixel);
  return Math.max(0, Math.min(zoomMaximo, Math.round(z)));
}

/**
 * Mosaicos que cubren el rectángulo visible del dibujo.
 *
 * Se convierte la vista a Mercator, se calcula el rango de mosaicos y a cada
 * uno se le devuelve su rectángulo ya en coordenadas del plano, listo para
 * dibujarlo con la misma cámara que el resto.
 */
export function tilesParaVista(
  proyector: Proyector,
  vista: { minX: number; minY: number; maxX: number; maxY: number },
  z: number
): Tile[] {
  // Las cuatro esquinas: una proyección puede rotar ligeramente el rectángulo
  const esquinas: [number, number][] = [
    [vista.minX, vista.minY], [vista.maxX, vista.minY],
    [vista.maxX, vista.maxY], [vista.minX, vista.maxY]
  ];
  let mMinX = Infinity, mMinY = Infinity, mMaxX = -Infinity, mMaxY = -Infinity;
  for (const [x, y] of esquinas) {
    const [mx, my] = proyector.planoAMercator(x, y);
    if (!Number.isFinite(mx) || !Number.isFinite(my)) return [];
    mMinX = Math.min(mMinX, mx); mMaxX = Math.max(mMaxX, mx);
    mMinY = Math.min(mMinY, my); mMaxY = Math.max(mMaxY, my);
  }

  const n = 2 ** z;
  const tamMundo = (2 * BORDE) / n;
  const aIndiceX = (mx: number) => Math.floor((mx + BORDE) / tamMundo);
  // La Y de los mosaicos crece hacia el sur, al revés que Mercator
  const aIndiceY = (my: number) => Math.floor((BORDE - my) / tamMundo);

  const x0 = aIndiceX(mMinX), x1 = aIndiceX(mMaxX);
  const y0 = aIndiceY(mMaxY), y1 = aIndiceY(mMinY);
  if ((x1 - x0 + 1) * (y1 - y0 + 1) > MAX_TILES) return [];

  const tiles: Tile[] = [];
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      if (x < 0 || y < 0 || x >= n || y >= n) continue;
      const oesteM = -BORDE + x * tamMundo;
      const esteM = oesteM + tamMundo;
      const norteM = BORDE - y * tamMundo;
      const surM = norteM - tamMundo;
      // Se vuelve al sistema del plano para poder dibujarlo con la cámara
      const [ax, ay] = proyector.mercatorAPlano(oesteM, surM);
      const [bx, by] = proyector.mercatorAPlano(esteM, norteM);
      if (!Number.isFinite(ax) || !Number.isFinite(by)) continue;
      tiles.push({
        z, x, y,
        minX: Math.min(ax, bx), minY: Math.min(ay, by),
        maxX: Math.max(ax, bx), maxY: Math.max(ay, by)
      });
    }
  }
  return tiles;
}

/** Caché de imágenes ya decodificadas, para no rehacer el trabajo cada cuadro. */
export class CacheTiles {
  private imagenes = new Map<string, HTMLImageElement>();
  private pedidos = new Set<string>();
  private fallidos = new Set<string>();

  constructor(private alCargar: () => void, private limite = 400) {}

  clave(fuente: string, t: Tile): string {
    return `${fuente}/${t.z}/${t.x}/${t.y}`;
  }

  /** Imagen lista, o undefined si aún no está (se pide en segundo plano). */
  obtener(fuente: string, t: Tile): HTMLImageElement | undefined {
    const k = this.clave(fuente, t);
    const img = this.imagenes.get(k);
    if (img) return img;
    if (this.pedidos.has(k) || this.fallidos.has(k)) return undefined;

    this.pedidos.add(k);
    window.cadlibre
      .tileSatelital(fuente, t.z, t.x, t.y)
      .then((datos) => {
        this.pedidos.delete(k);
        if (!datos) {
          this.fallidos.add(k);
          return;
        }
        const imagen = new Image();
        imagen.onload = () => {
          if (this.imagenes.size >= this.limite) {
            // Se descarta el más antiguo: Map conserva el orden de inserción
            const primero = this.imagenes.keys().next().value;
            if (primero) this.imagenes.delete(primero);
          }
          this.imagenes.set(k, imagen);
          this.alCargar();
        };
        imagen.onerror = () => this.fallidos.add(k);
        imagen.src = datos;
      })
      .catch(() => {
        this.pedidos.delete(k);
        this.fallidos.add(k);
      });
    return undefined;
  }

  vaciar(): void {
    this.imagenes.clear();
    this.pedidos.clear();
    this.fallidos.clear();
  }
}

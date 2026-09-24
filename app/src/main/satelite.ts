/**
 * Servicio de mosaicos (tiles) de imagen satelital para el fondo del visor.
 *
 * Los tiles se descargan aquí, en el proceso principal, y no en el renderer:
 * así se evitan CORS y se pueden guardar en una caché de disco que sobrevive
 * entre sesiones (un plano que ya se abrió no vuelve a bajar nada).
 *
 * Sobre las fuentes: descargar tiles de Google Maps directamente incumple sus
 * condiciones de uso, que exigen pasar por su API de pago. Por eso la fuente
 * por defecto es Esri World Imagery —la misma que QGIS trae de serie, de uso
 * libre citando la fuente— y Google solo se ofrece si el usuario pone su
 * propia clave de la Map Tiles API.
 */
import { app, net } from 'electron';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export interface FuenteSatelital {
  id: string;
  nombre: string;
  atribucion: string;
  zoomMaximo: number;
  /** Plantilla de URL; {z} {x} {y} se sustituyen. */
  plantilla: string;
  /** true si hace falta una clave del usuario. */
  requiereClave?: boolean;
}

export const FUENTES: FuenteSatelital[] = [
  {
    id: 'esri',
    nombre: 'Esri World Imagery',
    atribucion: 'Esri, Maxar, Earthstar Geographics',
    zoomMaximo: 19,
    plantilla:
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
  },
  {
    id: 'esri_hibrido',
    nombre: 'Esri Imagery + calles',
    atribucion: 'Esri, Maxar, Earthstar Geographics',
    zoomMaximo: 19,
    plantilla:
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
  }
];

const CARPETA_CACHE = () => path.join(app.getPath('userData'), 'tiles');
/** Un tile se considera fresco 60 días: la imagen satelital cambia despacio. */
const VIDA_CACHE_MS = 60 * 24 * 60 * 60 * 1000;
const MAX_DESCARGAS_SIMULTANEAS = 6;

let enCurso = 0;
const cola: (() => void)[] = [];

function esperarTurno(): Promise<void> {
  if (enCurso < MAX_DESCARGAS_SIMULTANEAS) {
    enCurso++;
    return Promise.resolve();
  }
  return new Promise((resolver) => cola.push(() => { enCurso++; resolver(); }));
}

function liberarTurno(): void {
  enCurso--;
  const siguiente = cola.shift();
  if (siguiente) siguiente();
}

function rutaCache(fuente: string, z: number, x: number, y: number): string {
  const clave = createHash('md5').update(`${fuente}/${z}/${x}/${y}`).digest('hex');
  // Se reparte en subcarpetas: miles de archivos en una sola ralentizan Windows
  const carpeta = path.join(CARPETA_CACHE(), fuente, clave.slice(0, 2));
  return path.join(carpeta, `${clave}.jpg`);
}

function url(fuente: FuenteSatelital, z: number, x: number, y: number, clave?: string): string {
  let u = fuente.plantilla
    .replace('{z}', String(z))
    .replace('{x}', String(x))
    .replace('{y}', String(y));
  if (fuente.requiereClave && clave) u += (u.includes('?') ? '&' : '?') + `key=${clave}`;
  return u;
}

async function descargar(direccion: string): Promise<Buffer | null> {
  await esperarTurno();
  try {
    const respuesta = await net.fetch(direccion, {
      headers: { 'User-Agent': 'CAD-LIBRE/1.5 (visor catastral)' }
    });
    if (!respuesta.ok) return null;
    const datos = Buffer.from(await respuesta.arrayBuffer());
    // Un tile válido nunca es diminuto; los errores suelen venir como HTML
    return datos.length > 300 ? datos : null;
  } catch {
    return null;
  } finally {
    liberarTurno();
  }
}

/**
 * Devuelve el tile como data URL, de la caché o descargándolo.
 * null significa "no disponible": el visor simplemente deja ese hueco.
 */
export async function obtenerTile(
  idFuente: string, z: number, x: number, y: number, clave?: string
): Promise<string | null> {
  const fuente = FUENTES.find((f) => f.id === idFuente) ?? FUENTES[0];
  if (z < 0 || z > fuente.zoomMaximo) return null;
  const limite = 2 ** z;
  if (x < 0 || y < 0 || x >= limite || y >= limite) return null;

  const destino = rutaCache(fuente.id, z, x, y);
  if (existsSync(destino)) {
    try {
      const edad = Date.now() - statSync(destino).mtimeMs;
      if (edad < VIDA_CACHE_MS) {
        return 'data:image/jpeg;base64,' + readFileSync(destino).toString('base64');
      }
    } catch {
      /* caché ilegible: se vuelve a bajar */
    }
  }

  const datos = await descargar(url(fuente, z, x, y, clave));
  if (!datos) return null;
  try {
    mkdirSync(path.dirname(destino), { recursive: true });
    writeFileSync(destino, datos);
  } catch {
    /* sin caché en disco se sigue funcionando, solo que más lento */
  }
  return 'data:image/jpeg;base64,' + datos.toString('base64');
}

/** Tamaño ocupado por la caché, para poder informarlo o vaciarla. */
export function tamanoCache(): number {
  const raiz = CARPETA_CACHE();
  if (!existsSync(raiz)) return 0;
  let total = 0;
  const recorrer = (dir: string) => {
    for (const entrada of require('node:fs').readdirSync(dir, { withFileTypes: true })) {
      const completa = path.join(dir, entrada.name);
      if (entrada.isDirectory()) recorrer(completa);
      else total += statSync(completa).size;
    }
  };
  try {
    recorrer(raiz);
  } catch {
    /* ignora errores de lectura */
  }
  return total;
}

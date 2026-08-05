/**
 * Temas de la interfaz y del fondo del visor.
 *
 * El color de fondo del lienzo no es solo estético: los planos CAD usan
 * mucho el blanco y el amarillo, invisibles sobre papel blanco. Por eso,
 * en los fondos claros se oscurecen los colores demasiado luminosos al
 * pintarlos (los datos del DXF nunca se tocan, solo su representación).
 */

export type NombreTema = 'oscuro' | 'claro' | 'gris' | 'azul';

export interface Tema {
  nombre: NombreTema;
  etiqueta: string;
  /** Fondo del lienzo del visor. */
  fondo: string;
  /** true si el fondo es claro y hay que oscurecer los colores luminosos. */
  fondoClaro: boolean;
}

export const TEMAS: Record<NombreTema, Tema> = {
  oscuro: { nombre: 'oscuro', etiqueta: 'Oscuro', fondo: '#0d0d0d', fondoClaro: false },
  claro: { nombre: 'claro', etiqueta: 'Blanco', fondo: '#ffffff', fondoClaro: true },
  gris: { nombre: 'gris', etiqueta: 'Gris claro', fondo: '#e9e9e9', fondoClaro: true },
  azul: { nombre: 'azul', etiqueta: 'Azul noche', fondo: '#101a2b', fondoClaro: false }
};

const CLAVE = 'cadlibre.tema';

export function leerTemaGuardado(): NombreTema {
  const guardado = localStorage.getItem(CLAVE);
  return guardado && guardado in TEMAS ? (guardado as NombreTema) : 'oscuro';
}

export function guardarTema(nombre: NombreTema): void {
  localStorage.setItem(CLAVE, nombre);
}

/** Luminancia relativa aproximada (0 = negro, 1 = blanco). */
function luminancia(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

/**
 * Ajusta un color de entidad para que se distinga del fondo.
 * Sobre fondo claro, los colores casi blancos se llevan a un gris oscuro y
 * los muy luminosos (amarillo, cian) se oscurecen a la mitad.
 */
export function colorVisible(color: string, tema: Tema): string {
  if (!tema.fondoClaro || !/^#[0-9a-f]{6}$/i.test(color)) return color;
  const lum = luminancia(color);
  if (lum < 0.55) return color;
  const n = parseInt(color.slice(1), 16);
  const factor = lum > 0.9 ? 0.25 : 0.55;
  const r = Math.round(((n >> 16) & 255) * factor);
  const g = Math.round(((n >> 8) & 255) * factor);
  const b = Math.round((n & 255) * factor);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

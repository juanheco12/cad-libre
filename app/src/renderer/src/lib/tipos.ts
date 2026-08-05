/** Tipos compartidos del visor. Reflejan el JSON que produce cadlibre/render_json.py. */

export interface EntidadPolilinea {
  t: string;          // tipo DXF (LINE, LWPOLYLINE, ARC, INSERT desglosado, …)
  h: string;          // handle de la entidad real (para selección)
  l: string;          // capa
  c: string;          // color #rrggbb
  p: number[][];      // polilíneas aplanadas [x1,y1,x2,y2,...]
}

export interface EntidadTexto {
  t: 'TEXTO';
  h: string;
  l: string;
  c: string;
  x: number;
  y: number;
  alt: number;        // altura del texto en unidades de dibujo
  rot: number;        // rotación en grados
  s: string;          // contenido
}

export interface EntidadPunto {
  t: 'PUNTO';
  h: string;
  l: string;
  c: string;
  x: number;
  y: number;
}

export type Entidad = EntidadPolilinea | EntidadTexto | EntidadPunto;

export interface Capa {
  nombre: string;
  color: string;
  visible: boolean;
}

export interface Geometria {
  entidades: Entidad[];
  capas: Capa[];
  extension: [number, number, number, number]; // minX, minY, maxX, maxY
}

export interface Georref {
  tieneGeodata: boolean;
  epsg: number | null;
  nombreCrs: string | null;
  observaciones: string[];
}

export interface Inventario {
  versionDxf: string;
  unidades: string;
  extmin: number[] | null;
  extmax: number[] | null;
  capas: number;
  bloques: number;
  entidades: number;
  porTipo: Record<string, number>;
}

export interface Documento {
  origen: string;
  dxf: string;
  geometria: Geometria;
  georref: Georref;
  inventario: Inventario;
}

export interface Seleccion {
  handle: string;
  tipo: string;
  capa: string;
}

/** Filtros de la exportación selectiva; vacío = todo el dibujo (copia 1:1). */
export interface OpcionesExportar {
  /** Capas a conservar; undefined = todas. */
  capas?: string[];
  /** Rectángulo [x1, y1, x2, y2] en coordenadas del dibujo. */
  area?: [number, number, number, number];
  /** contenida = solo lo totalmente dentro; intersecta = también lo que toca. */
  modoArea?: 'contenida' | 'intersecta';
}

export interface ResumenFiltrado {
  conservadas: number;
  eliminadas: number;
  capasExcluidas: string[];
  sinGeometria: number;
}

declare global {
  interface Window {
    cadlibre: {
      estadoMotor(): Promise<{ ok: boolean; motor: string | null }>;
      abrirArchivo(): Promise<Record<string, unknown>>;
      exportarDxf(opciones?: OpcionesExportar): Promise<Record<string, unknown>>;
    };
  }
}

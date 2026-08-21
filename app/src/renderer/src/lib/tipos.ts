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
  /** dxf conserva el archivo tal cual; shp da capas SIG; pdf un plano imprimible. */
  formato?: 'dxf' | 'shp' | 'pdf';
  /** Tamaño de hoja del PDF. */
  tamanoPdf?: 'A4' | 'A3';
  /** Capas a conservar; undefined = todas. */
  capas?: string[];
  /** Contorno cerrado [[x, y], …] en coordenadas del dibujo. */
  poligono?: [number, number][];
  /** contenida = solo lo totalmente dentro; intersecta = también lo que toca. */
  modoArea?: 'contenida' | 'intersecta';
  /** Handles de las entidades elegidas una a una; manda sobre los demás filtros. */
  handles?: string[];
}

export interface ResumenPdf {
  entidades: number;
  textos: number;
  omitidas: number;
  escala: string;
}

export interface ResumenShp {
  poligonos: number;
  lineas: number;
  puntos: number;
  textos: number;
  omitidas: number;
  total: number;
}

export interface ResumenFiltrado {
  conservadas: number;
  eliminadas: number;
  capasExcluidas: string[];
  sinGeometria: number;
}

export interface InfoActualizacion {
  estado: 'buscando' | 'disponible' | 'descargando' | 'lista' | 'sin-novedad' | 'error';
  version?: string;
  porcentaje?: number;
  mensaje?: string;
}

declare global {
  interface Window {
    cadlibre: {
      estadoMotor(): Promise<{ ok: boolean; motor: string | null }>;
      abrirArchivo(): Promise<Record<string, unknown>>;
      cerrarArchivo(): Promise<{ ok: boolean }>;
      exportarDxf(opciones?: OpcionesExportar): Promise<Record<string, unknown>>;
      version(): Promise<string>;
      buscarActualizacion(): Promise<InfoActualizacion>;
      instalarActualizacion(): Promise<void>;
      alActualizar(cb: (info: InfoActualizacion) => void): () => void;
    };
  }
}

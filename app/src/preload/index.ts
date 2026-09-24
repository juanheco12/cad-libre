/** Puente seguro entre el renderer y el proceso principal. */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron';

contextBridge.exposeInMainWorld('cadlibre', {
  estadoMotor: () => ipcRenderer.invoke('motor:estado'),
  abrirArchivo: () => ipcRenderer.invoke('archivo:abrir'),
  cerrarArchivo: () => ipcRenderer.invoke('archivo:cerrar'),
  exportarDxf: (opciones?: unknown) => ipcRenderer.invoke('archivo:exportar', opciones),
  version: () => ipcRenderer.invoke('app:version'),
  fuentesSatelitales: () => ipcRenderer.invoke('satelite:fuentes'),
  tileSatelital: (fuente: string, z: number, x: number, y: number, clave?: string) =>
    ipcRenderer.invoke('satelite:tile', fuente, z, x, y, clave),
  tamanoCacheSatelital: () => ipcRenderer.invoke('satelite:cache'),
  infoCrs: (epsg: number) => ipcRenderer.invoke('crs:info', epsg),
  buscarActualizacion: () => ipcRenderer.invoke('app:buscar-actualizacion'),
  instalarActualizacion: () => ipcRenderer.invoke('app:instalar-actualizacion'),
  /** Suscribe al estado de la actualización; devuelve la función para desuscribir. */
  alActualizar: (cb: (info: unknown) => void) => {
    const oyente = (_ev: IpcRendererEvent, info: unknown) => cb(info);
    ipcRenderer.on('actualizacion:estado', oyente);
    return () => ipcRenderer.removeListener('actualizacion:estado', oyente);
  }
});

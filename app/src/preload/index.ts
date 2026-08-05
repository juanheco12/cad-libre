/** Puente seguro entre el renderer y el proceso principal. */
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('cadlibre', {
  estadoMotor: () => ipcRenderer.invoke('motor:estado'),
  abrirArchivo: () => ipcRenderer.invoke('archivo:abrir'),
  exportarDxf: () => ipcRenderer.invoke('archivo:exportar')
});

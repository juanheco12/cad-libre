/** Proceso principal de Electron: ventana, diálogos e IPC hacia el motor Python. */
import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { iniciarActualizador } from './actualizador';
import { ejecutarBridge } from './python';

let ventana: BrowserWindow | null = null;
let workdir: string | null = null;
/** Ruta del DXF 1:1 producido al abrir el DWG actual (fuente de la exportación). */
let dxfActual: string | null = null;

function crearVentana(): void {
  ventana = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0d0d0d',
    title: 'CAD LIBRE',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  ventana.setMenuBarVisibility(false);

  if (process.env.ELECTRON_RENDERER_URL) {
    ventana.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    ventana.loadFile(path.join(__dirname, '../renderer/index.html'));
  }
}

app.whenReady().then(() => {
  workdir = mkdtempSync(path.join(os.tmpdir(), 'cadlibre-'));
  crearVentana();
  iniciarActualizador(ventana!, app.isPackaged);
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) crearVentana();
  });
});

app.on('window-all-closed', () => {
  if (workdir) rmSync(workdir, { recursive: true, force: true });
  app.quit();
});

// ------------------------------------------------------------------- IPC

ipcMain.handle('motor:estado', async () => ejecutarBridge(['motor']));

ipcMain.handle('app:version', () => app.getVersion());

/** Libera el dibujo actual y su geometría temporal. */
ipcMain.handle('archivo:cerrar', () => {
  if (workdir) {
    // Se vacía la carpeta temporal: los dibujos grandes dejan JSON de
    // geometría de varios cientos de MB que no hay razón de conservar.
    rmSync(workdir, { recursive: true, force: true });
    workdir = mkdtempSync(path.join(os.tmpdir(), 'cadlibre-'));
  }
  dxfActual = null;
  return { ok: true };
});

ipcMain.handle('archivo:abrir', async () => {
  const seleccion = await dialog.showOpenDialog(ventana!, {
    title: 'Abrir dibujo CAD',
    filters: [
      { name: 'Dibujos CAD', extensions: ['dwg', 'dxf'] },
      { name: 'DWG', extensions: ['dwg'] },
      { name: 'DXF', extensions: ['dxf'] }
    ],
    properties: ['openFile']
  });
  if (seleccion.canceled || seleccion.filePaths.length === 0) {
    return { ok: false, cancelado: true };
  }
  const ruta = seleccion.filePaths[0];
  const respuesta = await ejecutarBridge(['abrir', ruta, '--workdir', workdir!]);
  if (!respuesta.ok) return respuesta;

  dxfActual = respuesta.dxf as string;
  // La geometría puede ser grande: se lee aquí y se entrega parseada.
  let geometria: unknown = null;
  try {
    geometria = JSON.parse(readFileSync(respuesta.geometria as string, 'utf-8'));
  } catch (e) {
    return { ok: false, error: `No se pudo leer la geometría: ${(e as Error).message}` };
  }
  return { ...respuesta, geometria };
});

interface OpcionesExportar {
  capas?: string[];
  poligono?: [number, number][];
  modoArea?: 'contenida' | 'intersecta';
}

ipcMain.handle('archivo:exportar', async (_ev, opciones?: OpcionesExportar) => {
  if (!dxfActual) return { ok: false, error: 'No hay ningún dibujo abierto.' };
  const nombre = path.basename(dxfActual);
  const seleccion = await dialog.showSaveDialog(ventana!, {
    title: 'Exportar DXF georreferenciado',
    defaultPath: nombre,
    filters: [{ name: 'DXF', extensions: ['dxf'] }]
  });
  if (seleccion.canceled || !seleccion.filePath) return { ok: false, cancelado: true };

  const args = ['exportar', dxfActual, seleccion.filePath];
  if (opciones?.capas) args.push('--capas', JSON.stringify(opciones.capas));
  if (opciones?.poligono) args.push('--poligono', JSON.stringify(opciones.poligono));
  if (opciones?.modoArea) args.push('--modo-area', opciones.modoArea);

  const respuesta = await ejecutarBridge(args);
  if (respuesta.ok) {
    shell.showItemInFolder(seleccion.filePath);
  }
  return respuesta;
});

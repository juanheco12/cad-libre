/**
 * Auto-actualización contra GitHub Releases.
 *
 * Al arrancar (solo en la app instalada) se consulta el último release del
 * repositorio. Si hay una versión nueva se descarga en segundo plano y se
 * avisa al usuario, que decide cuándo reiniciar; si no reinicia, la
 * actualización se aplica sola al cerrar el programa.
 */
import { BrowserWindow, ipcMain } from 'electron';
import { autoUpdater } from 'electron-updater';

export interface InfoActualizacion {
  estado: 'buscando' | 'disponible' | 'descargando' | 'lista' | 'sin-novedad' | 'error';
  version?: string;
  porcentaje?: number;
  mensaje?: string;
}

let ventanaAviso: BrowserWindow | null = null;

function avisar(info: InfoActualizacion): void {
  ventanaAviso?.webContents.send('actualizacion:estado', info);
}

export function iniciarActualizador(ventana: BrowserWindow, empaquetada: boolean): void {
  ventanaAviso = ventana;

  ipcMain.handle('app:instalar-actualizacion', () => {
    autoUpdater.quitAndInstall();
  });

  if (!empaquetada) {
    // En desarrollo no hay firma ni versión instalada contra la que comparar.
    ipcMain.handle('app:buscar-actualizacion', async () => ({
      estado: 'sin-novedad' as const,
      mensaje: 'Las actualizaciones solo funcionan en la app instalada.'
    }));
    return;
  }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => avisar({ estado: 'buscando' }));
  autoUpdater.on('update-available', (info) =>
    avisar({ estado: 'disponible', version: info.version })
  );
  autoUpdater.on('update-not-available', () => avisar({ estado: 'sin-novedad' }));
  autoUpdater.on('download-progress', (p) =>
    avisar({ estado: 'descargando', porcentaje: p.percent })
  );
  autoUpdater.on('update-downloaded', (info) =>
    avisar({ estado: 'lista', version: info.version })
  );
  autoUpdater.on('error', (e) => avisar({ estado: 'error', mensaje: e.message }));

  ipcMain.handle('app:buscar-actualizacion', async () => {
    try {
      const r = await autoUpdater.checkForUpdates();
      return r?.updateInfo
        ? { estado: 'disponible' as const, version: r.updateInfo.version }
        : { estado: 'sin-novedad' as const };
    } catch (e) {
      return { estado: 'error' as const, mensaje: (e as Error).message };
    }
  });

  // Una consulta al arrancar basta; el usuario puede repetirla desde la app.
  autoUpdater.checkForUpdates().catch((e) => {
    avisar({ estado: 'error', mensaje: e.message });
  });
}

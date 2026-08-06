'use strict';

/**
 * Genera los recursos de ícono a partir del vector build/logo.svg usando el
 * propio Electron para rasterizar (el conversor interno de electron-builder
 * falla con algunos PNG):
 *
 *   build/icon.png  (512x512)
 *   build/icon.ico  (multi-tamaño 256..16, el que usa el .exe de Windows)
 *
 * Uso:  npm run icono
 */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const RAIZ = path.join(__dirname, '..');
const RUTA_SVG = path.join(RAIZ, 'build', 'logo.svg');
// 512 y no más: una ventana más alta que la pantalla la recorta Windows, y
// entonces la captura sale rectangular y el reescalado deforma el dibujo.
// Como el origen es vectorial, rasterizar a 512 ya sale nítido.
const RENDER = 512;
const TAMANOS_ICO = [256, 128, 64, 48, 32, 16];

const SVG = fs
  .readFileSync(RUTA_SVG, 'utf8')
  .replace(/width="512"/, `width="${RENDER}"`)
  .replace(/height="512"/, `height="${RENDER}"`);

app.disableHardwareAcceleration();

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    width: RENDER,
    height: RENDER,
    show: false,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    useContentSize: true
  });

  const html =
    '<!doctype html><html><head><meta charset="utf-8">' +
    '<style>html,body{margin:0;padding:0;width:' + RENDER + 'px;height:' + RENDER +
    'px;background:transparent;overflow:hidden}</style>' +
    '</head><body>' + SVG + '</body></html>';

  await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
  // El escalado DPI de Windows (125%, 150%…) desplaza y recorta la captura:
  // se fija el zoom a 1 y se recorta un rectángulo explícito.
  win.webContents.setZoomFactor(1);
  await new Promise((r) => setTimeout(r, 900)); // deja asentar el render de fuentes

  const base = await win.webContents.capturePage({
    x: 0, y: 0, width: RENDER, height: RENDER
  });

  // Si la ventana no cupo en la pantalla, la captura sale rectangular y al
  // reescalarla a un cuadrado el dibujo se deforma. Mejor fallar que emitir
  // un icono estirado.
  const medida = base.getSize();
  if (medida.width !== medida.height) {
    throw new Error(
      `La captura salió ${medida.width}x${medida.height} en vez de cuadrada: ` +
      'la ventana no cabe en la pantalla. Baje RENDER.'
    );
  }
  const dirBuild = path.join(RAIZ, 'build');
  fs.mkdirSync(dirBuild, { recursive: true });

  const png512 = base.resize({ width: 512, height: 512, quality: 'best' }).toPNG();
  fs.writeFileSync(path.join(dirBuild, 'icon.png'), png512);

  const buffers = TAMANOS_ICO.map((n) =>
    base.resize({ width: n, height: n, quality: 'best' }).toPNG()
  );
  const pngToIco = (await import('png-to-ico')).default;
  const ico = await pngToIco(buffers);
  fs.writeFileSync(path.join(dirBuild, 'icon.ico'), ico);

  console.log('build/icon.png (512):', png512.length, 'bytes');
  console.log('build/icon.ico (' + TAMANOS_ICO.join('/') + '):', ico.length, 'bytes');
  app.exit(0);
}).catch((e) => {
  console.error('Error generando el ícono:', e);
  app.exit(1);
});

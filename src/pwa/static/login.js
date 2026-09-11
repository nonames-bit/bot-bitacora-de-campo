/* Lógica del botón "Instalar App" en login — extraída a fichero externo
   para cumplir el CSP de producción (script-src 'self', sin inline).
   Sin cambios de lógica respecto al bloque inline original. */
(function () {
  "use strict";
  var deferredPromptLogin = null;
  var esStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  var esIos = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  var boxInst = document.getElementById('box-instalar-login');
  var btnInst = document.getElementById('btn-instalar-login');

  if (!esStandalone) {
    if (boxInst) boxInst.style.display = 'block';
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPromptLogin = e;
      if (boxInst) boxInst.style.display = 'block';
    });
  }

  if (btnInst) {
    btnInst.addEventListener('click', function () {
      if (deferredPromptLogin) {
        deferredPromptLogin.prompt();
        deferredPromptLogin.userChoice.then(function (choice) {
          if (choice.outcome === 'accepted') {
            if (boxInst) boxInst.style.display = 'none';
          }
          deferredPromptLogin = null;
        });
      } else if (esIos) {
        alert("📲 Para instalar en iPhone / iPad:\n1. Toca el botón Compartir ⎋ (abajo en Safari).\n2. Desliza y elige 'Agregar a pantalla de inicio' ➕.\n3. Toca 'Agregar' arriba a la derecha.");
      } else {
        alert("📲 Para instalar en tu teléfono:\n1. Toca los tres puntos (⋮) arriba a la derecha en Chrome/Edge.\n2. Toca 'Instalar aplicación' o 'Agregar a la pantalla principal'.");
      }
    });
  }

  window.addEventListener('appinstalled', function () {
    if (boxInst) boxInst.style.display = 'none';
  });
})();

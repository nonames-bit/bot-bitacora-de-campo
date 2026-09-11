/* Registro del Service Worker — extraído a fichero externo para cumplir
   el CSP de producción (script-src 'self', sin inline). Best-effort. */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function (e) { /* best-effort */ });
  });
}

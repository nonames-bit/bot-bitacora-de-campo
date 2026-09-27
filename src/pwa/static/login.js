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

/* Login con huella / Face ID (WebAuthn). Muestra el botón solo si el
   navegador lo soporta, hay contexto seguro y ya existen credenciales
   registradas en la finca. El PIN/contraseña queda siempre como respaldo.
   Fichero externo por el CSP de producción (script-src 'self'). */
(function () {
  "use strict";
  var box = document.getElementById('box-huella-login');
  var btn = document.getElementById('btn-huella-login');
  var msg = document.getElementById('huella-msg');
  if (!box || !btn) return;

  var soportado = !!window.PublicKeyCredential && window.isSecureContext && !!navigator.credentials;
  if (!soportado) return;

  function setMsg(t) { if (msg) msg.textContent = t || ''; }

  function b64urlToBuf(s) {
    s = String(s || '').replace(/-/g, '+').replace(/_/g, '/');
    var pad = s.length % 4 ? new Array(5 - (s.length % 4)).join('=') : '';
    var raw = atob(s + pad);
    var buf = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
    return buf.buffer;
  }

  function bufToB64url(buf) {
    var bytes = new Uint8Array(buf);
    var bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function credToJSON(cred) {
    if (cred && typeof cred.toJSON === 'function') return cred.toJSON();
    var r = cred.response || {};
    var out = {
      id: cred.id,
      rawId: bufToB64url(cred.rawId),
      type: cred.type,
      response: { clientDataJSON: bufToB64url(r.clientDataJSON) },
      clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {}
    };
    if (r.authenticatorData) out.response.authenticatorData = bufToB64url(r.authenticatorData);
    if (r.signature) out.response.signature = bufToB64url(r.signature);
    if (r.userHandle) out.response.userHandle = bufToB64url(r.userHandle);
    return out;
  }

  fetch('/api/webauthn/disponible', { headers: { 'Accept': 'application/json' } })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d && d.disponible) {
        box.style.display = 'block';
        try { if (localStorage.getItem('ja_huella_preferida') === '1') btn.focus(); } catch (e) {}
      }
    })
    .catch(function () {});

  btn.addEventListener('click', function () {
    btn.disabled = true;
    setMsg('Confirme su huella en el teléfono…');
    fetch('/api/webauthn/login/opciones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok || !res.d || !res.d.opciones) throw new Error((res.d && res.d.error) || 'opciones');
        var pk = res.d.opciones;
        pk.challenge = b64urlToBuf(pk.challenge);
        (pk.allowCredentials || []).forEach(function (c) { c.id = b64urlToBuf(c.id); });
        return navigator.credentials.get({ publicKey: pk });
      })
      .then(function (cred) {
        if (!cred) throw new Error('sin_credencial');
        return fetch('/api/webauthn/login/verificar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ credencial: credToJSON(cred) })
        }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); });
      })
      .then(function (res) {
        if (res.ok && res.d && res.d.ok) {
          try { localStorage.setItem('ja_huella_preferida', '1'); } catch (e) {}
          window.location = res.d.redirect || '/';
          return;
        }
        btn.disabled = false;
        setMsg((res.d && res.d.error) || 'No se pudo ingresar con huella. Use su PIN.');
      })
      .catch(function () {
        btn.disabled = false;
        setMsg('No se pudo ingresar con huella. Use su PIN.');
      });
  });
})();

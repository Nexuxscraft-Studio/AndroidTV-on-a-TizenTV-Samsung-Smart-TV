/* Q60T Build 073: public read-only Tizen / Samsung ProductInfo APIs only. */
/* ES5-compatible intentionally for the Tizen 5.5 TV web engine. */
(function () {
  "use strict";

  var cards = [
    { title: "Gerät & Firmware", entries: [
      ["Modell (Tizen)", "build.model"], ["Hersteller", "build.manufacturer"],
      ["Tizen-Build", "build.buildVersion"], ["Samsung Modell", "product.model"],
      ["Modellcode", "product.modelCode"], ["Vollständiges Modell", "product.realModel"],
      ["Firmware", "product.firmware"], ["Samsung API-Version", "product.version"]
    ] },
    { title: "CPU & Plattform", entries: [
      ["CPU-Architektur", "cap.cpuArch"], ["Plattformprozessor", "cap.processor"],
      ["Tizen Core API", "cap.apiVersion"], ["Plattform", "cap.platform"],
      ["Build-ID", "cap.buildId"], ["Build-Release", "cap.buildRelease"],
      ["CPU-Last", "cpu.load"], ["Speicherdruck", "memory.status"]
    ] },
    { title: "Anzeige", entries: [
      ["Displaybreite", "display.resolutionWidth"], ["Displayhöhe", "display.resolutionHeight"],
      ["Panelbreite", "panel.panelWidth"], ["Panelhöhe", "panel.panelHeight"],
      ["Bildschirmfeature", "cap.screen"], ["Bildschirmfarbe", "cap.colorDepth"]
    ] },
    { title: "Technische Einordnung", entries: [
      ["Kernel-Version", "boundary.kernel"], ["Bootloader", "boundary.bootloader"],
      ["Root-Zugriff", "boundary.root"], ["RAM-Gesamtgröße", "boundary.ram"]
    ] }
  ];

  var capabilities = {
    "cap.cpuArch": "http://tizen.org/feature/platform.core.cpu.arch",
    "cap.processor": "http://tizen.org/system/platform.processor",
    "cap.apiVersion": "http://tizen.org/feature/platform.core.api.version",
    "cap.platform": "http://tizen.org/system/platform.name",
    "cap.buildId": "http://tizen.org/system/build.id",
    "cap.buildRelease": "http://tizen.org/system/build.release",
    "cap.screen": "http://tizen.org/feature/screen",
    "cap.colorDepth": "http://tizen.org/feature/screen.bpp"
  };
  var properties = [
    { id: "BUILD", fields: ["model", "manufacturer", "buildVersion"], prefix: "build." },
    { id: "CPU", fields: ["load"], prefix: "cpu." },
    { id: "MEMORY", fields: ["status"], prefix: "memory." },
    { id: "DISPLAY", fields: ["resolutionWidth", "resolutionHeight"], prefix: "display." },
    { id: "PANEL", fields: ["panelWidth", "panelHeight"], prefix: "panel." }
  ];
  var appState = {};
  var currentRun = 0;

  function labelText(value) {
    if (value === null || value === undefined || value === "") {
      return "Nicht verfügbar";
    }
    if (typeof value === "boolean") { return value ? "Ja" : "Nein"; }
    return String(value);
  }

  function setValue(id, value) {
    var node = document.getElementById("v-" + id.replace(/\./g, "-"));
    if (!node) { return; }
    node.textContent = labelText(value);
    node.className = "value" + (value === null || value === undefined || value === "" ? " muted" : "");
  }

  function setStatus(message) {
    var element = document.getElementById("state");
    if (element) { element.textContent = message; }
  }

  function create(tag, className, text) {
    var element = document.createElement(tag);
    if (className) { element.className = className; }
    if (text !== undefined) { element.textContent = text; }
    return element;
  }

  function buildUI() {
    var root = document.getElementById("results");
    root.textContent = "";
    for (var i = 0; i < cards.length; i++) {
      var card = create("section", "card");
      card.appendChild(create("h2", "", cards[i].title));
      for (var j = 0; j < cards[i].entries.length; j++) {
        var entry = cards[i].entries[j];
        var wrap = create("div", "kv");
        var value = create("div", "value muted", "Nicht verfügbar");
        value.id = "v-" + entry[1].replace(/\./g, "-");
        wrap.appendChild(create("div", "label", entry[0]));
        wrap.appendChild(value);
        card.appendChild(wrap);
      }
      root.appendChild(card);
    }
    setValue("boundary.kernel", "Keine offizielle API");
    setValue("boundary.bootloader", "Keine offizielle API");
    setValue("boundary.root", "Nicht angefordert");
    setValue("boundary.ram", "API meldet nur Speicherdruck");
  }

  function safeProductCall(api, method, id) {
    if (!api || typeof api[method] !== "function") {
      setValue(id, "Nicht unterstützt");
      return;
    }
    try {
      setValue(id, api[method]());
    } catch (e) {
      setValue(id, "Gesperrt / nicht verfügbar");
    }
  }

  function readProductInfo() {
    var api = (typeof webapis !== "undefined" && webapis.productinfo) ? webapis.productinfo : null;
    safeProductCall(api, "getModel", "product.model");
    safeProductCall(api, "getModelCode", "product.modelCode");
    safeProductCall(api, "getRealModel", "product.realModel");
    safeProductCall(api, "getFirmware", "product.firmware");
    safeProductCall(api, "getVersion", "product.version");
    /* Intentionally never call getDuid or fetch any unique device identifier. */
  }

  function readCapabilities() {
    if (typeof tizen === "undefined" || !tizen.systeminfo) { return; }
    for (var id in capabilities) {
      if (Object.prototype.hasOwnProperty.call(capabilities, id)) {
        try {
          var value = tizen.systeminfo.getCapability(capabilities[id]);
          if (value === 0 || value === null || value === "") {
            setValue(id, "Nicht verfügbar");
          } else {
            setValue(id, value);
          }
        } catch (e) {
          setValue(id, "Nicht unterstützt");
        }
      }
    }
  }

  function formatField(id, value) {
    if (id === "cpu.load" && typeof value === "number") {
      return (value * 100).toFixed(1) + " %";
    }
    if ((id === "display.resolutionWidth" || id === "display.resolutionHeight" ||
         id === "panel.panelWidth" || id === "panel.panelHeight") &&
        typeof value === "number") {
      return value + " px";
    }
    return value;
  }

  function readProperties() {
    var run = ++currentRun;
    readProductInfo();
    readCapabilities();
    if (typeof tizen === "undefined" || !tizen.systeminfo ||
        typeof tizen.systeminfo.getPropertyValue !== "function") {
      setStatus("Tizen API nicht verfügbar");
      return;
    }
    var pending = properties.length;
    setStatus("Lese Systemdaten …");

    function complete() {
      pending--;
      if (pending === 0 && run === currentRun) {
        setStatus("Abfrage abgeschlossen");
      }
    }

    for (var i = 0; i < properties.length; i++) {
      (function (property) {
        try {
          tizen.systeminfo.getPropertyValue(property.id, function (data) {
            if (run !== currentRun) { return; }
            for (var j = 0; j < property.fields.length; j++) {
              var field = property.fields[j];
              var id = property.prefix + field;
              setValue(id, formatField(id, data ? data[field] : null));
            }
            complete();
          }, function (err) {
            if (run !== currentRun) { return; }
            for (var j = 0; j < property.fields.length; j++) {
              setValue(property.prefix + property.fields[j], "Nicht unterstützt");
            }
            complete();
          });
        } catch (e) {
          if (run !== currentRun) { return; }
          for (var k = 0; k < property.fields.length; k++) {
            setValue(property.prefix + property.fields[k], "Nicht verfügbar");
          }
          complete();
        }
      }(properties[i]));
    }
  }

  function closeApp() {
    if (typeof tizen !== "undefined" && tizen.application &&
        typeof tizen.application.getCurrentApplication === "function") {
      try { tizen.application.getCurrentApplication().exit(); } catch (e) { /* ignore */ }
    }
  }

  function handleKeys(event) {
    var code = event.keyCode;
    if (code === 10009 || code === 27 || event.key === "Escape" ||
        event.key === "Backspace") {
      closeApp();
      return;
    }
    if (code === 38 || code === 40) {
      window.scrollBy(0, code === 38 ? -180 : 180);
      event.preventDefault();
    }
  }

  function start() {
    buildUI();
    document.getElementById("refresh").addEventListener("click", readProperties);
    document.addEventListener("keydown", handleKeys);
    readProperties();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());

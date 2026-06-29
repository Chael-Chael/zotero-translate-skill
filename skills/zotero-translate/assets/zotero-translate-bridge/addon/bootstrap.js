// Bootstrap layout follows windingwind/zotero-plugin-template and Zotero 7+
// bootstrapped plugin conventions: register chrome, then load content script.

var chromeHandle;

function install(data, reason) {}

async function startup({ id, version, resourceURI, rootURI }, reason) {
  var resolvedRootURI = rootURI || resourceURI?.spec;
  const aomStartup = Components.classes[
    "@mozilla.org/addons/addon-manager-startup;1"
  ].getService(Components.interfaces.amIAddonManagerStartup);
  const manifestURI = Services.io.newURI(resolvedRootURI + "manifest.json");

  chromeHandle = aomStartup.registerChrome(manifestURI, [
    ["content", "zotero-translate-bridge", resolvedRootURI + "content/"],
  ]);

  const ctx = { rootURI: resolvedRootURI };
  ctx._globalThis = ctx;

  Services.scriptloader.loadSubScript(
    resolvedRootURI + "content/scripts/zoteroTranslateBridge.js",
    ctx,
  );

  await Zotero.ZoteroTranslateBridge.startup({ id, version, rootURI: resolvedRootURI }, reason);
}

async function onMainWindowLoad({ window }, reason) {
  await Zotero.ZoteroTranslateBridge?.onMainWindowLoad?.(window, reason);
}

async function onMainWindowUnload({ window }, reason) {
  await Zotero.ZoteroTranslateBridge?.onMainWindowUnload?.(window, reason);
}

async function shutdown(data, reason) {
  if (reason === APP_SHUTDOWN) {
    return;
  }

  await Zotero.ZoteroTranslateBridge?.shutdown?.(data, reason);
  delete Zotero.ZoteroTranslateBridge;

  if (chromeHandle) {
    chromeHandle.destruct();
    chromeHandle = null;
  }
}

async function uninstall(data, reason) {}

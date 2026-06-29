// Bootstrap layout follows windingwind/zotero-plugin-template and Zotero 7+
// bootstrapped plugin conventions: register chrome, then load content script.

var chromeHandle;
var bridgeScope;

function install(data, reason) {}

async function startup({ id, version, resourceURI, rootURI }, reason) {
  const resolvedRootURI = rootURI || resourceURI?.spec;
  const aomStartup = Components.classes[
    "@mozilla.org/addons/addon-manager-startup;1"
  ].getService(Components.interfaces.amIAddonManagerStartup);
  const manifestURI = Services.io.newURI(resolvedRootURI + "manifest.json");

  chromeHandle = aomStartup.registerChrome(manifestURI, [
    ["content", "zotero-translate-bridge", resolvedRootURI + "content/"],
  ]);

  bridgeScope = {
    rootURI: resolvedRootURI,
    Zotero,
    Services,
    Components,
    Cc: Components.classes,
    Ci: Components.interfaces,
    Cu: Components.utils,
    console,
  };
  bridgeScope._globalThis = bridgeScope;
  bridgeScope.globalThis = bridgeScope;

  Services.scriptloader.loadSubScript(
    resolvedRootURI + "content/scripts/zoteroTranslateBridge.js",
    bridgeScope,
  );

  await bridgeScope.ZoteroTranslateBridge.startup({ id, version, rootURI: resolvedRootURI }, reason);
}

async function onMainWindowLoad({ window }, reason) {
  await bridgeScope?.ZoteroTranslateBridge?.onMainWindowLoad?.(window, reason);
}

async function onMainWindowUnload({ window }, reason) {
  await bridgeScope?.ZoteroTranslateBridge?.onMainWindowUnload?.(window, reason);
}

async function shutdown(data, reason) {
  if (reason === APP_SHUTDOWN) {
    return;
  }

  await bridgeScope?.ZoteroTranslateBridge?.shutdown?.(data, reason);
  bridgeScope = null;

  if (chromeHandle) {
    chromeHandle.destruct();
    chromeHandle = null;
  }
}

async function uninstall(data, reason) {}

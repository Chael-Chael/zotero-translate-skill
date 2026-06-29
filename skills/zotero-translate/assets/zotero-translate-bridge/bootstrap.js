const BRIDGE_ID = "zotero-translate-bridge@codex.local";
const BRIDGE_VERSION = "0.1.0";
const BRIDGE_BASE_PATH = "/zotero-translate-bridge";
const BRIDGE_TOKEN_HEADER = "x-zotero-translate-bridge-token";
const BRIDGE_TOKEN = "__ZOTERO_TRANSLATE_BRIDGE_TOKEN__";

let registeredBridgePaths = [];

function install(data, reason) {}

async function startup(data, reason) {
  if (Zotero?.initializationPromise) {
    await Zotero.initializationPromise;
  }
  registerBridgeEndpoints();
}

async function shutdown(data, reason) {
  if (reason === APP_SHUTDOWN) {
    return;
  }
  unregisterBridgeEndpoints();
}

function uninstall(data, reason) {}

function jsonResponse(status, payload) {
  return [status, "application/json", JSON.stringify(payload)];
}

function errorMessage(error) {
  if (error && typeof error.message === "string") {
    return error.message;
  }
  return String(error);
}

function getHeader(headers, name) {
  if (!headers) {
    return "";
  }
  const wanted = name.toLowerCase();
  for (const key of Object.keys(headers)) {
    if (key.toLowerCase() === wanted) {
      const value = headers[key];
      if (Array.isArray(value)) {
        return String(value[0] || "");
      }
      return String(value || "");
    }
  }
  return "";
}

function isAuthorized(headers) {
  return Boolean(BRIDGE_TOKEN) && getHeader(headers, BRIDGE_TOKEN_HEADER) === BRIDGE_TOKEN;
}

function parseBody(options) {
  const data = options?.data;
  if (!data) {
    return {};
  }
  if (typeof data === "string") {
    const text = data.trim();
    return text ? JSON.parse(text) : {};
  }
  return data;
}

async function fileExists(filePath) {
  if (typeof IOUtils !== "undefined" && typeof IOUtils.exists === "function") {
    return IOUtils.exists(filePath);
  }
  if (typeof OS !== "undefined" && OS.File?.exists) {
    return OS.File.exists(filePath);
  }
  const file = Components.classes["@mozilla.org/file/local;1"].createInstance(Components.interfaces.nsIFile);
  file.initWithPath(filePath);
  return file.exists();
}

async function resolveParentItem(body) {
  const rawID = body.parentItemID ?? body.parentItemId ?? body.itemID ?? body.itemId;
  if (rawID !== undefined && rawID !== null && String(rawID).trim()) {
    return Zotero.Items.getAsync(Number(rawID));
  }

  const key = body.parentKey ?? body.itemKey;
  const rawLibraryID = body.libraryID ?? body.libraryId;
  if (key && rawLibraryID !== undefined && rawLibraryID !== null && Zotero.Items.getByLibraryAndKey) {
    return Zotero.Items.getByLibraryAndKey(Number(rawLibraryID), String(key));
  }
  return null;
}

async function itemInfo(item) {
  return {
    id: item.id,
    key: item.key,
    libraryID: item.libraryID,
    title: item.getField?.("title") || "",
  };
}

async function attachmentInfo(item) {
  return {
    id: item.id,
    key: item.key,
    libraryID: item.libraryID,
    title: item.getField?.("title") || "",
    path: await item.getFilePathAsync?.(),
    contentType: item.attachmentContentType || "",
  };
}

function defaultTitle(filePath) {
  const parts = String(filePath).split(/[\\/]/);
  return parts[parts.length - 1] || "Translated PDF";
}

async function handleHealth(options) {
  return jsonResponse(200, {
    ok: true,
    id: BRIDGE_ID,
    version: BRIDGE_VERSION,
    endpoints: {
      attach: `${BRIDGE_BASE_PATH}/attach`,
      verify: `${BRIDGE_BASE_PATH}/verify`,
    },
  });
}

async function handleAttach(options) {
  const body = parseBody(options);
  const filePath = String(body.filePath || body.path || "").trim();
  if (!filePath || !filePath.toLowerCase().endsWith(".pdf")) {
    return jsonResponse(400, { ok: false, error: "filePath must point to a PDF" });
  }
  if (!(await fileExists(filePath))) {
    return jsonResponse(404, { ok: false, error: `PDF does not exist: ${filePath}` });
  }

  const parent = await resolveParentItem(body);
  if (!parent || !parent.isRegularItem?.()) {
    return jsonResponse(404, { ok: false, error: "Parent Zotero regular item not found" });
  }

  const title = String(body.title || defaultTitle(filePath)).trim() || defaultTitle(filePath);
  const attachment = await Zotero.Attachments.importFromFile({
    file: filePath,
    parentItemID: parent.id,
    title,
    contentType: "application/pdf",
  });

  return jsonResponse(200, {
    ok: true,
    parent: await itemInfo(parent),
    attached: await attachmentInfo(attachment),
  });
}

async function handleVerify(options) {
  const body = parseBody(options);
  const parent = await resolveParentItem(body);
  if (!parent || !parent.isRegularItem?.()) {
    return jsonResponse(404, { ok: false, error: "Parent Zotero regular item not found" });
  }

  const attachments = [];
  for (const id of await parent.getAttachments()) {
    const item = await Zotero.Items.getAsync(id);
    if (item) {
      attachments.push(await attachmentInfo(item));
    }
  }
  return jsonResponse(200, {
    ok: true,
    parent: await itemInfo(parent),
    attachments,
  });
}

function makeEndpoint(handler, methods) {
  return class {
    supportedMethods = methods;
    supportedDataTypes = ["application/json"];
    init = async (options) => {
      try {
        if (!isAuthorized(options?.headers)) {
          return jsonResponse(401, { ok: false, error: "unauthorized" });
        }
        return await handler(options || {});
      } catch (error) {
        Zotero.logError?.(error);
        return jsonResponse(500, { ok: false, error: errorMessage(error) });
      }
    };
  };
}

function registerBridgeEndpoints() {
  unregisterBridgeEndpoints();
  const endpoints = {
    [`${BRIDGE_BASE_PATH}/health`]: makeEndpoint(handleHealth, ["GET", "POST"]),
    [`${BRIDGE_BASE_PATH}/attach`]: makeEndpoint(handleAttach, ["POST"]),
    [`${BRIDGE_BASE_PATH}/verify`]: makeEndpoint(handleVerify, ["POST"]),
  };
  for (const [path, endpoint] of Object.entries(endpoints)) {
    Zotero.Server.Endpoints[path] = endpoint;
    registeredBridgePaths.push(path);
  }
  Zotero.debug?.(`Zotero Translate Bridge registered ${registeredBridgePaths.length} endpoints`);
}

function unregisterBridgeEndpoints() {
  for (const path of registeredBridgePaths) {
    delete Zotero.Server.Endpoints[path];
  }
  registeredBridgePaths = [];
}

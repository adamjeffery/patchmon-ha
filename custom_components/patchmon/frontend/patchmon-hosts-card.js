const DEFAULT_ENTITY = "sensor.patchmon_hosts_needing_updates";

const STYLE = `
  .empty { padding: 0 16px 16px; color: var(--secondary-text-color); }
  .row { display: flex; align-items: center; gap: 12px; padding: 8px 16px; }
  .row:last-child { padding-bottom: 16px; }
  .info { flex: 1; min-width: 0; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .detail { font-size: 0.875em; color: var(--secondary-text-color); }
  .security { color: var(--error-color); }
  .count { font-size: 1.25em; font-weight: 500; }
`;

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

class PatchMonHostsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = {
      entity: DEFAULT_ENTITY,
      title: "PatchMon hosts",
      show_all: false,
      ...config,
    };
    this._signature = undefined;
    this._maybeRender();
  }

  set hass(hass) {
    this._hass = hass;
    this._maybeRender();
  }

  getCardSize() {
    return 1 + this._rows().length;
  }

  static getStubConfig() {
    return {};
  }

  _rows() {
    const hosts = this._hass?.states[this._config.entity]?.attributes.hosts ?? [];
    return this._config.show_all ? hosts : hosts.filter((host) => host.updates > 0);
  }

  // Home Assistant sets `hass` on every state change anywhere, so skip unrelated ones.
  _maybeRender() {
    if (!this._hass || !this._config) return;
    const signature = JSON.stringify(this._rows());
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  _rowFor(host) {
    const row = document.createElement("div");
    row.className = "row";

    const info = document.createElement("div");
    info.className = "info";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = host.name;
    info.append(name);

    const detail = document.createElement("div");
    detail.className = "detail";
    if (host.security_updates > 0) {
      const security = document.createElement("span");
      security.className = "security";
      security.textContent = `${host.security_updates} security`;
      detail.append(security);
    }
    const notes = [];
    if (host.needs_reboot) notes.push("reboot needed");
    if (host.reporting_state && host.reporting_state !== "reporting") {
      notes.push(`agent ${host.reporting_state}`);
    }
    if (notes.length) {
      detail.append(`${detail.hasChildNodes() ? " · " : ""}${notes.join(" · ")}`);
    }
    if (detail.hasChildNodes()) info.append(detail);

    const count = document.createElement("div");
    count.className = "count";
    count.textContent = host.updates;
    count.title = plural(host.updates, "update");

    row.append(info, count);
    return row;
  }

  _render() {
    const card = document.createElement("ha-card");
    card.header = this._config.title;

    const rows = this._rows();
    if (rows.length) {
      card.append(...rows.map((host) => this._rowFor(host)));
    } else {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = this._hass.states[this._config.entity]
        ? "All hosts are up to date."
        : `Entity not found: ${this._config.entity}`;
      card.append(empty);
    }

    const style = document.createElement("style");
    style.textContent = STYLE;
    this.shadowRoot.replaceChildren(style, card);
  }
}

customElements.define("patchmon-hosts-card", PatchMonHostsCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "patchmon-hosts-card",
  name: "PatchMon hosts",
  description: "Hosts with outstanding updates.",
});

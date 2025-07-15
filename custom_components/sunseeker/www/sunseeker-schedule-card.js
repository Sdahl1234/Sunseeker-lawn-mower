class SunseekerScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._schedule = {};
    this._entity = "";
    this._editMode = false;
    this._localSchedule = null;
    this._collapsedDays = {};
    this._collapsedEntries = {};
    this._initCollapseState();
  }

  static getConfigElement() {
    return document.createElement("sunseeker-schedule-card-editor");
  }

  static getStubConfig(hass, entities) {
    return {
      type: "custom:sunseeker-schedule-card",
      entity: entities?.[0] || "",
      header: "Sunseeker Schedule",
      show_header: true,
    };
  }

  setConfig(config) {
    this.config = config;
    this._entity = config.entity;
    this._initCollapseState();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._entity) return;
    if (!this._editMode) {
      const stateObj = this._hass.states[this._entity];
      if (stateObj && stateObj.attributes.schedule) {
        this._schedule = stateObj.attributes.schedule;
        this._initCollapseState();
        this._render();
      }
    }
  }

  getCardSize() {
    return 8;
  }

  _initCollapseState() {
    const days = [
      "monday", "tuesday", "wednesday", "thursday",
      "friday", "saturday", "sunday"
    ];
    for (const day of days) {
      if (!(day in this._collapsedDays)) {
        this._collapsedDays[day] = false;
      }
      if (!this._collapsedEntries[day]) {
        this._collapsedEntries[day] = [true, true];
      }
      const schedule = this._editMode ? this._localSchedule : this._schedule;
      for (let idx = 0; idx < 2; idx++) {
        const enabled = schedule?.[day]?.[idx]?.enabled;
        this._collapsedEntries[day][idx] = !enabled;
      }
    }
  }

  _enterEditMode() {
    this._editMode = true;
    this._localSchedule = JSON.parse(JSON.stringify(this._schedule));
    this._initCollapseState();
    this._render();
  }

  _cancelEdit() {
    this._editMode = false;
    this._localSchedule = null;
    if (this._hass && this._entity) {
      const stateObj = this._hass.states[this._entity];
      if (stateObj && stateObj.attributes.schedule) {
        this._schedule = stateObj.attributes.schedule;
      }
    }
    this._initCollapseState();
    this._render();
  }

  _handleInput(day, idx, field, e) {
    if (!this._editMode) return;
    if (field === "enabled") {
      this._localSchedule[day][idx][field] = e.target.checked;
      this._collapsedEntries[day][idx] = !e.target.checked;
    } else {
      this._localSchedule[day][idx][field] = e.target.value;
    }
    this._render();
  }

  _toggleBoolean(key) {
    if (!this._editMode) return;
    if (key === "pause") {
      this._localSchedule.pause = !this._localSchedule.pause;
    } else if (key === "recommended_time_work" || key === "user_defined") {
      // Radio button behavior: only one can be true
      this._localSchedule.recommended_time_work = key === "recommended_time_work";
      this._localSchedule.user_defined = key === "user_defined";
    }
    this._render();
  }

  _toggleLocation(day, idx, loc) {
    if (!this._editMode) return;
    const entry = this._localSchedule[day][idx];
    if (!entry.locations) entry.locations = [];
    const i = entry.locations.indexOf(loc);
    if (i === -1) {
      entry.locations.push(loc);
    } else {
      entry.locations.splice(i, 1);
    }
    this._render();
  }

  _toggleDayCollapse(day) {
    this._collapsedDays[day] = !this._collapsedDays[day];
    this._render();
  }

  _toggleEntryCollapse(day, idx) {
    this._collapsedEntries[day][idx] = !this._collapsedEntries[day][idx];
    this._render();
  }

  _submit() {
    if (!this._editMode) return;
    this._hass.callService("sunseeker", "set_schedule", {
      entity_id: this._entity,
      schedule: this._localSchedule,
    });
    this._editMode = false;
    this._localSchedule = null;
    this._schedule = JSON.parse(JSON.stringify(this._schedule));
    if (window.dispatchEvent) {
      window.dispatchEvent(
        new CustomEvent("hass-notification", {
          detail: { message: this._t("notification") },
        })
      );
    }
    this._initCollapseState();
    this._render();
  }

  _getLang() {
    return (this._hass && this._hass.language && TRANSLATIONS[this._hass.language])
      ? this._hass.language
      : "en";
  }

  _t(key, subkey = null) {
    const lang = this._getLang();
    if (subkey) return TRANSLATIONS[lang]?.[key]?.[subkey] || TRANSLATIONS["en"][key][subkey];
    return TRANSLATIONS[lang]?.[key] || TRANSLATIONS["en"][key];
  }

  _render() {
    if (!this.shadowRoot) return;
    const days = [
      "monday", "tuesday", "wednesday", "thursday",
      "friday", "saturday", "sunday"
    ];
    const schedule = this._editMode ? this._localSchedule : this._schedule;
    const locations = schedule?.locations || [];
    const disabled = this._editMode ? "" : "disabled";
    const header = this.config?.show_header === false ? "" : (this.config?.header || this._t("header"));

    this.shadowRoot.innerHTML = `
      <style>
        ha-card .card-header {
          text-align: center;
        }
        .bool-buttons {
          display: flex;
          justify-content: center;
          gap: 8px;
          margin-bottom: 16px;
        }
        .bool-btn {
          padding: 4px 16px;
          border-radius: 12px;
          border: 1px solid #888;
          background: #eee;
          color: #000;
          cursor: pointer;
          transition: background 0.2s, color 0.2s;
        }
        .bool-btn.selected {
          background: #1976d2;
          color: #fff;
          border-color: #1976d2;
        }
        .bool-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .day-block {
          text-align: center;
          margin-bottom: 18px;
          border: 2px solid #fff;
          border-radius: 12px;
          padding: 12px 8px 8px 8px;
          background: transparent;
          box-shadow: 0 2px 6px rgba(0,0,0,0.03);
          max-width: 400px;
          margin-left: auto;
          margin-right: auto;
        }
        .day-label {
          font-weight: bold;
          margin-top: 8px;
          margin-bottom: 2px;
          display: block;
          font-size: 1.1em;
          cursor: pointer;
          user-select: none;
        }
        .entry-headline {
          font-weight: 500;
          margin-bottom: 4px;
          margin-top: 8px;
          display: block;
          font-size: 1em;
          cursor: pointer;
          user-select: none;
        }
        .entry-row {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          margin-bottom: 4px;
        }
        .location-buttons {
          margin-top: 4px;
          margin-bottom: 8px;
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
        }
        .location-btn {
          margin-right: 6px;
          margin-bottom: 2px;
          padding: 2px 10px;
          border-radius: 12px;
          border: 1px solid #888;
          background: #eee;
          color: #000;
          cursor: pointer;
          transition: background 0.2s, color 0.2s;
        }
        .location-btn.selected {
          background: #1976d2;
          color: #fff;
          border-color: #1976d2;
        }
        .location-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        ha-card {
          display: block;
        }
        .submit-btn, .edit-btn, .cancel-btn {
          margin-top: 12px;
          margin-right: 8px;
        }
        .button-row {
          margin-top: 16px;
          text-align: center;
        }
        .collapse-arrow {
          display: inline-block;
          margin-left: 6px;
          font-size: 0.9em;
          transition: transform 0.2s;
        }
        .collapsed > .entry-content {
          display: none;
        }
      </style>
      <ha-card header="${header}">
        <div style="padding: 16px;">
          <div class="bool-buttons">
            <button
              type="button"
              class="bool-btn${schedule.recommended_time_work ? " selected" : ""}"
              ${disabled}
              id="recommended-btn"
            >${this._t("recommended_time_work")}</button>
            <button
              type="button"
              class="bool-btn${schedule.user_defined ? " selected" : ""}"
              ${disabled}
              id="userdefined-btn"
            >${this._t("user_defined")}</button>
            <button
              type="button"
              class="bool-btn${schedule.pause ? " selected" : ""}"
              ${disabled}
              id="pause-btn"
            >${this._t("pause")}</button>
          </div>
          ${days.map(
            (day) => `
              <div class="day-block${this._collapsedDays[day] ? " collapsed" : ""}">
                <span class="day-label" data-day="${day}">
                  ${this._t("days", day)}
                  <span class="collapse-arrow" style="transform: rotate(${this._collapsedDays[day] ? 0 : 90}deg);">&#9654;</span>
                </span>
                <div class="entry-content">
                  ${[0, 1].map(idx => `
                    <div>
                      <span class="entry-headline" data-day="${day}" data-idx="${idx}">
                        ${this._t("entry")} ${idx + 1}
                        <span class="collapse-arrow" style="transform: rotate(${this._collapsedEntries[day][idx] ? 0 : 90}deg);">&#9654;</span>
                      </span>
                      <div class="entry-details" style="display:${this._collapsedEntries[day][idx] ? "none" : "block"}">
                        <div class="entry-row">
                          <label>
                            <input
                              type="checkbox"
                              ${schedule[day]?.[idx]?.enabled ? "checked" : ""}
                              ${disabled}
                              onchange="this.getRootNode().host._handleInput('${day}', ${idx}, 'enabled', event)"
                            /> ${this._t("enabled")}
                          </label>
                          <input
                            type="time"
                            value="${schedule[day]?.[idx]?.starttime || "00:00"}"
                            ${disabled}
                            oninput="this.getRootNode().host._handleInput('${day}', ${idx}, 'starttime', event)"
                          />
                          <input
                            type="time"
                            value="${schedule[day]?.[idx]?.endtime || "00:00"}"
                            ${disabled}
                            oninput="this.getRootNode().host._handleInput('${day}', ${idx}, 'endtime', event)"
                          />
                        </div>
                        <div class="location-buttons">
                          ${locations.map(
                            loc => `
                              <button
                                type="button"
                                class="location-btn${schedule[day]?.[idx]?.locations?.includes(loc) ? " selected" : ""}"
                                ${disabled}
                                onclick="this.getRootNode().host._toggleLocation('${day}', ${idx}, '${loc}')"
                              >${loc}</button>
                            `
                          ).join("")}
                        </div>
                      </div>
                    </div>
                  `).join("")}
                </div>
              </div>
            `
          ).join("")}
          <div class="button-row">
            ${this._editMode
              ? `
                <button class="submit-btn" type="button">${this._t("submit")}</button>
                <button class="cancel-btn" type="button">${this._t("cancel")}</button>
              `
              : `
                <button class="edit-btn" type="button">${this._t("edit")}</button>
              `
            }
          </div>
        </div>
      </ha-card>
    `;

    // Attach event handlers for boolean buttons
    if (this._editMode) {
      this.shadowRoot.getElementById("recommended-btn").onclick = () => this._toggleBoolean("recommended_time_work");
      this.shadowRoot.getElementById("userdefined-btn").onclick = () => this._toggleBoolean("user_defined");
      this.shadowRoot.getElementById("pause-btn").onclick = () => this._toggleBoolean("pause");
    }

    // Attach event handlers for collapse toggles
    days.forEach(day => {
      const dayLabel = this.shadowRoot.querySelector(`.day-label[data-day="${day}"]`);
      if (dayLabel) {
        dayLabel.onclick = () => this._toggleDayCollapse(day);
      }
    });
    this.shadowRoot.querySelectorAll('.entry-headline').forEach(el => {
      el.onclick = () => this._toggleEntryCollapse(el.dataset.day, Number(el.dataset.idx));
    });
    if (this._editMode) {
      this.shadowRoot.querySelector(".submit-btn").onclick = () => this._submit();
      this.shadowRoot.querySelector(".cancel-btn").onclick = () => this._cancelEdit();
    } else {
      this.shadowRoot.querySelector(".edit-btn").onclick = () => this._enterEditMode();
    }
  }
}

// Minimal GUI editor for Lovelace
class SunseekerScheduleCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  get _entity() {
    return this._config?.entity || "";
  }
  get _header() {
    return this._config?.header || "";
  }
  get _showHeader() {
    return this._config?.show_header !== false;
  }

  render() {
    if (!this._hass) return;
  // Ensure ha-entity-picker is loaded
  if (!customElements.get("ha-entity-picker")) {
    const el = document.createElement("ha-entity-picker");
    document.body.appendChild(el);
    document.body.removeChild(el);
  }

  this.innerHTML = `
    <div>
      <label>Entity</label>
      <span id="picker-container"></span>
      <br />
      <label>Header</label>
      <input
        type="text"
        value="${this._header}"
        data-config-value="header"
        placeholder="Header text"
      />
      <br />
      <label>
        <input
          type="checkbox"
          ${this._showHeader ? "checked" : ""}
          data-config-value="show_header"
        />
        Show header
      </label>
    </div>
  `;

    // Dynamically create and insert ha-entity-picker
    const picker = document.createElement("ha-entity-picker");
    picker.hass = this._hass;
    picker.value = this._entity;
    picker.setAttribute("data-config-value", "entity");
    picker.setAttribute("domain-filter", "sensor");
    picker.addEventListener("value-changed", (ev) => {
      this._config = {
        ...this._config,
        entity: ev.detail.value,
      };
      this.render();
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config: this._config },
          bubbles: true,
          composed: true,
        })
      );
    });
    this.querySelector("#picker-container").appendChild(picker);

    // Attach change handlers for other inputs
    this.querySelectorAll("input").forEach((el) => {
      el.onchange = (ev) => {
        const target = ev.target;
        let value;
        if (target.type === "checkbox") {
          value = target.checked;
        } else {
          value = target.value;
        }
        this._config = {
          ...this._config,
          [target.dataset.configValue]: value,
        };
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      };
    });
  }
}

customElements.define("sunseeker-schedule-card", SunseekerScheduleCard);
customElements.define("sunseeker-schedule-card-editor", SunseekerScheduleCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "sunseeker-schedule-card",
  name: "Sunseeker Schedule Card",
  preview: false,
  description: "Custom card to control the mowers schedule",
});

const TRANSLATIONS = {
  en: {
    header: "Sunseeker Schedule",
    enabled: "Enabled",
    edit: "Edit",
    submit: "Submit",
    cancel: "Cancel",
    notification: "Schedule submitted!",
    entry: "Entry",
    recommended_time_work: "Recommended",
    user_defined: "User defined",
    pause: "Pause",
    days: {
      monday: "Monday",
      tuesday: "Tuesday",
      wednesday: "Wednesday",
      thursday: "Thursday",
      friday: "Friday",
      saturday: "Saturday",
      sunday: "Sunday",
    }
  },
  da: {
    header: "Sunseeker planlægning 1",
    enabled: "Aktiveret",
    edit: "Rediger",
    submit: "Gem",
    cancel: "Annuller",
    notification: "Tidsplan gemt!",
    entry: "Periode",
    recommended_time_work: "Anbefalet",
    user_defined: "Brugerdefineret",
    pause: "Pause",
    days: {
      monday: "Mandag",
      tuesday: "Tirsdag",
      wednesday: "Onsdag",
      thursday: "Torsdag",
      friday: "Fredag",
      saturday: "Lørdag",
      sunday: "Søndag",
    }
  },
  de: {
    header: "Sunseeker zeitplan",
    enabled: "Aktiviert",
    edit: "Bearbeiten",
    submit: "Speichern",
    cancel: "Abbrechen",
    notification: "Zeitplan gespeichert!",
    entry: "Zeitraum",
    recommended_time_work: "Empfohlen",
    user_defined: "Benutzerdefiniert",
    pause: "Pause",
    days: {
      monday: "Montag",
      tuesday: "Dienstag",
      wednesday: "Mittwoch",
      thursday: "Donnerstag",
      friday: "Freitag",
      saturday: "Samstag",
      sunday: "Sonntag",
    }
  },
  fr: {
    header: "Programme Sunseeker",
    enabled: "Activé",
    edit: "Modifier",
    submit: "Enregistrer",
    cancel: "Annuler",
    notification: "Programme enregistré !",
    entry: "Plage",
    recommended_time_work: "Recommandé",
    user_defined: "Défini par l'utilisateur",
    pause: "Pause",
    days: {
      monday: "Lundi",
      tuesday: "Mardi",
      wednesday: "Mercredi",
      thursday: "Jeudi",
      friday: "Vendredi",
      saturday: "Samedi",
      sunday: "Dimanche",
    }
  }
};

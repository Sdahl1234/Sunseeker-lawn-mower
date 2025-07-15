const TRANSLATIONS = {
    en: {
        header: "Mower Control",
        start: "Start",
        pause: "Pause",
        stop: "Stop",
        home: "Home",
        state: "State",
        mower_entity: "Mower entity",
        zone_entity: "Zone select entity",
        camera_entity: "Camera/Image entity",
        header_label: "Header",
        show_header: "Show header",
    },
    da: {
        header: "Plæneklipper kontrol",
        start: "Start",
        pause: "Pause",
        stop: "Stop",
        home: "Hjem",
        state: "Status",
        mower_entity: "Plæneklipper enhed",
        zone_entity: "Zonevælger enhed",
        camera_entity: "Kamera/Billede enhed",
        header_label: "Overskrift",
        show_header: "Vis overskrift",
    },
    de: {
        header: "Mähersteuerung",
        start: "Start",
        pause: "Pause",
        stop: "Stopp",
        home: "Heim",
        state: "Status",
        mower_entity: "Mäher Entität",
        zone_entity: "Zonenauswahl Entität",
        camera_entity: "Kamera/Bild Entität",
        header_label: "Überschrift",
        show_header: "Überschrift anzeigen",
    },
    fr: {
        header: "Contrôle de la tondeuse",
        start: "Démarrer",
        pause: "Pause",
        stop: "Arrêter",
        home: "Accueil",
        state: "État",
        mower_entity: "Entité de la tondeuse",
        zone_entity: "Entité de sélection de zone",
        camera_entity: "Entité Caméra/Image",
        header_label: "En-tête",
        show_header: "Afficher l'en-tête",
    }
};

function _t(key, hass) {
    const lang = (hass && hass.language && TRANSLATIONS[hass.language])
        ? hass.language
        : "en";
    return TRANSLATIONS[lang]?.[key] || TRANSLATIONS["en"][key] || key;
}

class SunseekerMowerControlCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: "open" });
        this._entity = "";
        this._zoneEntity = "";
        this._cameraEntity = "";
        this._hass = null;
        this._zones = [];
        this._selectedZones = [];
        this._mowerState = "unknown";
        this._initialized = false;
    }

    static getConfigElement() {
        return document.createElement("sunseeker-mower-control-card-editor");
    }

    static getStubConfig(hass, entities) {
        const mower = entities.find(e => e.startsWith("mower.") || e.startsWith("vacuum.")) || "";
        const zone = entities.find(e => e.startsWith("select.")) || "";
        const camera = entities.find(e => e.startsWith("camera.") || e.startsWith("image.")) || "";
        return {
            type: "custom:sunseeker-mower-control-card",
            entity: mower,
            zone_entity: zone,
            camera_entity: camera,
            header: TRANSLATIONS[hass?.language || "en"].header,
            show_header: true,
        };
    }

    setConfig(config) {
        this.config = config;
        this._entity = config.entity;
        this._zoneEntity = config.zone_entity;
        this._cameraEntity = config.camera_entity;
        this._header = config.header || TRANSLATIONS["en"].header;
        this._showHeader = config.show_header !== false;
        this._render();
        this._initialized = true;
    }

    set hass(hass) {
        this._hass = hass;
        this._updateZones();
        this._updateMowerState();
        // Update embedded picture-entity card's hass property
        if (this.shadowRoot) {
            const pictureCard = this.shadowRoot.querySelector("hui-picture-entity-card");
            if (pictureCard) {
                pictureCard.hass = hass;
            }
        }
        if (this._initialized) {
            this._updateDom();
        }
    }

    _updateZones() {
        if (!this._hass || !this._zoneEntity) return;
        const stateObj = this._hass.states[this._zoneEntity];
        if (stateObj && stateObj.attributes.options) {
            this._zones = stateObj.attributes.options;
            if (!this._selectedZones.length && stateObj.state) {
                this._selectedZones = [stateObj.state];
            }
        }
    }

    _updateMowerState() {
        if (!this._hass || !this._entity) return;
        const stateObj = this._hass.states[this._entity];
        this._mowerState = stateObj ? stateObj.state : "unknown";
    }

    _toggleZone(zone) {
        const idx = this._selectedZones.indexOf(zone);
        if (idx === -1) {
            this._selectedZones.push(zone);
        } else {
            this._selectedZones.splice(idx, 1);
        }
        this._updateZoneButtons();
    }

    _callMowerService(action) {
        if (!this._hass || !this._entity) return;
        let service = "";
        let data = { entity_id: this._entity };
        switch (action) {
            case "start":
                this._hass.callService("sunseeker", "start_mowing", {
                    entity_id: this._entity,
                    zones: this._selectedZones
                });
                return;
            case "pause":
                service = "pause";
                break;
            case "stop":
                service = "stop";
                break;
            case "home":
                service = "return_to_base";
                break;
            default:
                return;
        }
        this._hass.callService("mower", service, data);
    }

    async _render() {
        if (!this.shadowRoot) return;
        this.shadowRoot.innerHTML = `
            <style>
                .mower-block {
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
                .zone-buttons {
                    margin-bottom: 16px;
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 8px;
                }
                .zone-btn {
                    padding: 4px 16px;
                    border-radius: 12px;
                    border: 1px solid #888;
                    background: #eee;
                    color: #000;
                    cursor: pointer;
                    transition: background 0.2s, color 0.2s;
                }
                .zone-btn.selected {
                    background: #1976d2;
                    color: #fff;
                    border-color: #1976d2;
                }
                .zone-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                .action-buttons {
                    display: flex;
                    justify-content: center;
                    gap: 12px;
                    margin-top: 16px;
                }
                .action-btn {
                    padding: 6px 18px;
                    border-radius: 12px;
                    border: 1px solid #888;
                    background: #eee;
                    color: #000;
                    cursor: pointer;
                    transition: background 0.2s, color 0.2s;
                    font-size: 1em;
                }
                .action-btn:active {
                    background: #1976d2;
                    color: #fff;
                    border-color: #1976d2;
                }
                .state-row {
                    margin-top: 10px;
                    font-weight: bold;
                }
            </style>
            <div id="card-content"></div>
        `;

        // Compose the picture-entity card using cardHelpers (async, recommended)
        const cardConfig = {
            type: "picture-entity",
            entity: this._cameraEntity,
            show_name: false,
            show_state: false,
            camera_view: "live",
        };

        // Ensure cardHelpers are loaded
        if (!window.cardHelpers) {
            window.cardHelpers = await window.loadCardHelpers();
        }

        let pictureCard;
        if (window.cardHelpers && window.cardHelpers.createCardElement) {
            pictureCard = await window.cardHelpers.createCardElement(cardConfig);
        } else if (window.createCardElement) {
            pictureCard = window.createCardElement(cardConfig);
        } else {
            pictureCard = document.createElement("hui-picture-entity-card");
            if (pictureCard.setConfig) {
                pictureCard.setConfig(cardConfig);
            }
        }
        pictureCard.hass = this._hass;

        // Add the picture card to the card-content
        const cardContent = this.shadowRoot.getElementById("card-content");
        cardContent.innerHTML = ""; // Clear
        cardContent.appendChild(pictureCard);

        // Add mower controls below the picture card
        const mowerBlock = document.createElement("div");
        mowerBlock.className = "mower-block";
        mowerBlock.innerHTML = `
            <div class="action-buttons">
                <button class="action-btn" id="start-btn">${_t("start", this._hass)}</button>
                <button class="action-btn" id="pause-btn">${_t("pause", this._hass)}</button>
                <button class="action-btn" id="stop-btn">${_t("stop", this._hass)}</button>
                <button class="action-btn" id="home-btn">${_t("home", this._hass)}</button>
            </div>
            <div class="state-row" id="state-row">
                ${_t("state", this._hass)}: ${this._mowerState}
            </div>
            <div class="zone-buttons" id="zone-buttons">
                ${this._zones
                    .filter(zone => zone.toLowerCase() !== "global")
                    .map(
                        zone => `
                        <button
                            type="button"
                            class="zone-btn${this._selectedZones.includes(zone) ? " selected" : ""}"
                            id="zone-btn-${zone.replace(/[^a-zA-Z0-9_-]/g, "_")}"
                        >${zone}</button>
                    `
                    ).join("")}
            </div>
        `;
        cardContent.appendChild(mowerBlock);

        // Attach event handlers for action buttons
        mowerBlock.querySelector("#start-btn").onclick = () => this._callMowerService("start");
        mowerBlock.querySelector("#pause-btn").onclick = () => this._callMowerService("pause");
        mowerBlock.querySelector("#stop-btn").onclick = () => this._callMowerService("stop");
        mowerBlock.querySelector("#home-btn").onclick = () => this._callMowerService("home");

        // Attach event handlers for zone buttons
        this._updateZoneButtons();
    }

    _updateZoneButtons() {
        // Update zone button selection and handlers
        if (!this.shadowRoot) return;
        const filteredZones = this._zones.filter(
            zone => zone.toLowerCase() !== "global"
        );
        filteredZones.forEach(zone => {
            const btn = this.shadowRoot.getElementById(`zone-btn-${zone.replace(/[^a-zA-Z0-9_-]/g, "_")}`);
            if (btn) {
                btn.classList.toggle("selected", this._selectedZones.includes(zone));
                btn.onclick = () => this._toggleZone(zone);
            }
        });
    }

    _updateDom() {
        // Only update state row and zone buttons
        const stateRow = this.shadowRoot.getElementById("state-row");
        if (stateRow) {
            stateRow.textContent = `${_t("state", this._hass)}: ${this._mowerState}`;
        }
        this._updateZoneButtons();
    }
}

// GUI editor for Lovelace configuration with dropdowns and translations
class SunseekerMowerControlCardEditor extends HTMLElement {
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
    get _zoneEntity() {
        return this._config?.zone_entity || "";
    }
    get _cameraEntity() {
        return this._config?.camera_entity || "";
    }
    get _header() {
        return this._config?.header || "";
    }
    get _showHeader() {
        return this._config?.show_header !== false;
    }

    async render() {
        if (!this._hass) return;

        // Dynamically import ha-entity-picker if not loaded
        if (!customElements.get("ha-entity-picker")) {
            await import(
                "/frontend_latest/ha-entity-picker.js"
            ).catch(() => {});
        }
        this.innerHTML = `
            <div>
                <label for="entity">${_t("mower_entity", this._hass)}</label>
                <span id="picker-mower"></span>
                <br />
                <label for="zone_entity">${_t("zone_entity", this._hass)}</label>
                <span id="picker-zone"></span>
                <br />
                <label for="camera_entity">${_t("camera_entity", this._hass)}</label>
                <span id="picker-camera"></span>
                <br />
                <label for="header">${_t("header_label", this._hass)}</label>
                <input
                    type="text"
                    id="header"
                    value="${this._header}"
                    placeholder="${_t("header_label", this._hass)}"
                />
                <br />
                <label>
                    <input
                        type="checkbox"
                        id="show_header"
                        ${this._showHeader ? "checked" : ""}
                    />
                    ${_t("show_header", this._hass)}
                </label>
            </div>
        `;

        // Mower picker
        const pickerMower = document.createElement("ha-entity-picker");
        pickerMower.hass = this._hass;
        pickerMower.value = this._entity;
        pickerMower.setAttribute("data-config-value", "entity");
        pickerMower.includeDomains = ["vacuum", "lawn_mower", "mower"];
        //pickerMower.setAttribute("domain-filter", "mower,vacuum,lawn_mower");
        pickerMower.addEventListener("value-changed", (ev) => {
            this._config = { ...this._config, entity: ev.detail.value };
            this._fireConfigChanged();
        });
        this.querySelector("#picker-mower").appendChild(pickerMower);

        // Zone picker
        const pickerZone = document.createElement("ha-entity-picker");
        pickerZone.hass = this._hass;
        pickerZone.value = this._zoneEntity;
        pickerZone.setAttribute("data-config-value", "zone_entity");
        pickerMower.includeDomains = ["select"];
        //pickerZone.setAttribute("domain-filter", "select");
        pickerZone.addEventListener("value-changed", (ev) => {
            this._config = { ...this._config, zone_entity: ev.detail.value };
            this._fireConfigChanged();
        });
        this.querySelector("#picker-zone").appendChild(pickerZone);

        // Camera picker
        const pickerCamera = document.createElement("ha-entity-picker");
        pickerCamera.hass = this._hass;
        pickerCamera.value = this._cameraEntity;
        pickerCamera.setAttribute("data-config-value", "camera_entity");
        pickerCamera.setAttribute("domain-filter", "camera,image");
        pickerMower.includeDomains = ["camera", "image"];
        pickerCamera.addEventListener("value-changed", (ev) => {
            this._config = { ...this._config, camera_entity: ev.detail.value };
            this._fireConfigChanged();
        });
        this.querySelector("#picker-camera").appendChild(pickerCamera);

        // Other input handlers
        this.querySelector("#header").onchange = (ev) => {
            this._config = { ...this._config, header: ev.target.value };
            this._fireConfigChanged();
        };
        this.querySelector("#show_header").onchange = (ev) => {
            this._config = { ...this._config, show_header: ev.target.checked };
            this._fireConfigChanged();
        };
    }

    _fireConfigChanged() {
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: this._config },
                bubbles: true,
                composed: true,
            })
        );
    }
}

customElements.define("sunseeker-mower-control-card", SunseekerMowerControlCard);
customElements.define("sunseeker-mower-control-card-editor", SunseekerMowerControlCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "sunseeker-mower-control-card",
  name: "Sunseeker Mower Control Card",
  preview: false,
  description: "Custom card to allow cutting special zones",
});

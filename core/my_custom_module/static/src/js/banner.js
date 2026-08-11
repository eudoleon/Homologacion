/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const BANNER_ID = "account_closure_banner";
const SERVICE_NAME = "my_custom_module.banner";

function renderBanner(message) {
    if (document.getElementById(BANNER_ID)) {
        return;
    }

    const banner = document.createElement("div");
    banner.id = BANNER_ID;
    banner.style.cssText = [
        "background:#ffc107",
        "padding:10px",
        "text-align:center",
        "border-bottom:1px solid #e5b100",
        "z-index:1000",
        "position:relative",
    ].join(";");

    const title = document.createElement("strong");
    title.style.cssText = "display:block;font-size:16px;margin-bottom:5px;color:#b42318";
    title.textContent = `${_t("ADVERTENCIA:")} ${message || ""}`;

    const text = document.createElement("span");
    text.style.cssText = "color:#333;font-weight:600";
    text.innerHTML = `${_t("Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.")}<br>${_t("Por favor, revise y complete el cierre correspondiente para evitar inconsistencias en los registros.")}`;

    banner.appendChild(title);
    banner.appendChild(text);

    const header = document.querySelector("body > header");
    if (header) {
        document.body.insertBefore(banner, header);
    } else {
        document.body.insertBefore(banner, document.body.firstChild);
    }
}

export const customBannerService = {
    start() {
        const run = () => {
            fetch("/banner/status", {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                },
            })
                .then((res) => {
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status}`);
                    }
                    return res.json();
                })
                .then((response) => {
                    if (response && response.show_banner) {
                        renderBanner(response.message);
                    }
                })
                .catch(() => {
                    // Silently ignore failures to avoid blocking the web client.
                });
        };

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", run, { once: true });
        } else {
            run();
        }

        return {};
    },
};

const services = registry.category("services");
if (!services.contains(SERVICE_NAME)) {
    services.add(SERVICE_NAME, customBannerService);
}

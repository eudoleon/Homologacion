/** @odoo-module **/

import { user } from "@web/core/user";

(function () {
    let observer = null;

    // Array de selectores a ocultar
    const selectors = [
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > button",
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > div",
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > div > span.dropdown-item.text-truncate.o_menu_item.focus"
    ];

    // Función que oculta los elementos que coinciden con los selectores
    function hideActionButtons() {
        selectors.forEach((selector) => {
            const element = document.querySelector(selector);
            if (element) {
                element.style.display = "none";
            }
        });
    }

    function isInvoiceView() {
        return !!document.querySelector('.o_form_view[data-model="account.move"]');
    }

    // Esperar a que el DOM esté listo y verificar el grupo del usuario
    async function runConditionalActions() {
        if (!isInvoiceView()) {
            if (observer) {
                observer.disconnect();
                observer = null;
            }
            return;
        }
        try {
            const userHasGroup = await user.hasGroup("conditional_invoice_actions.group_enable_action_button");
            console.log("[ConditionalActions] Resultado de hasGroup:", userHasGroup);
            if (!userHasGroup) {
                console.log("[ConditionalActions] Usuario NO autorizado: ocultando botones de acciones.");
                hideActionButtons();
                // Configurar un MutationObserver para detectar cambios en el DOM
                if (!observer) {
                    observer = new MutationObserver(() => {
                        if (isInvoiceView()) {
                            hideActionButtons();
                        }
                    });
                    observer.observe(document.body, { childList: true, subtree: true });
                }
            } else {
                console.log("[ConditionalActions] Usuario autorizado: se mostrará el boton de acciones.");
                if (observer) {
                    observer.disconnect();
                    observer = null;
                }
            }
        } catch (error) {
            console.error("[ConditionalActions] Error evaluando permisos de grupo:", error);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", runConditionalActions, { once: true });
    } else {
        runConditionalActions();
    }
})();

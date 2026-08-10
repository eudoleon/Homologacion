/** @odoo-module **/

import session from "web.session";

(function() {
    // Array de selectores a ocultar
    const selectors = [
        "body > div.o_action_manager > div > div > div.o_control_panel > div > div.o_cp_bottom_right.w-auto.flex-shrink-0.justify-content-between.align-items-center > div.o_cp_action_menus > div:nth-child(2) > button",
        "body > div.o_action_manager > div > div.o_control_panel > div.o_cp_bottom > div.o_cp_bottom_left > div.o_cp_action_menus > div:nth-child(2)",
        "body > div.o_action_manager > div > div.o_control_panel > div.o_cp_bottom > div.o_cp_bottom_left > div.o_cp_action_menus > div.o-dropdown.dropdown.d-inline-block.o-dropdown--no-caret.show > div",
        "body > div.o_action_manager > div > div.o_control_panel > div.o_cp_bottom > div.o_cp_bottom_left > div.o_cp_action_menus > div.o-dropdown.dropdown.d-inline-block.o-dropdown--no-caret.show > button",
        "body > div.o_action_manager > div > div > div.o_control_panel > div > div.o_cp_bottom_right.w-auto.flex-shrink-0.justify-content-between.align-items-center > div.o_cp_action_menus > div > button",
        "body > div.o_action_manager > div > div > div.o_control_panel > div > div.o_cp_bottom_right.w-auto.flex-shrink-0.justify-content-between.align-items-center > div.o_cp_action_menus",
        "body > div.o_action_manager > div > div.o_control_panel > div.o_cp_bottom > div.o_cp_bottom_left > div.o_cp_action_menus"
    ];

    // Función que oculta los elementos que coinciden con los selectores
    function hideActionButtons() {
        selectors.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                console.log(`[ConditionalActions] Ocultando elemento con selector "${selector}"`);
                element.style.display = "none";
            } else {
                console.log(`[ConditionalActions] No se encontró elemento con selector "${selector}"`);
            }
        });
    }

    // Esperar a que el DOM esté listo y verificar el grupo del usuario
    document.addEventListener("DOMContentLoaded", function() {
        session.user_has_group('conditional_invoice_actions.group_enable_action_button').then(function(userHasGroup) {
            console.log("[ConditionalActions] Resultado de user_has_group:", userHasGroup);
            if (!userHasGroup) {
                console.log("[ConditionalActions] Usuario NO autorizado: ocultando botones de acciones.");
                hideActionButtons();
                // Configurar un MutationObserver para detectar cambios en el DOM
                const observer = new MutationObserver(() => {
                    hideActionButtons();
                });
                observer.observe(document.body, { childList: true, subtree: true });
            } else {
                console.log("[ConditionalActions] Usuario autorizado: se mostrará el botón de acciones.");
            }
        });
    });
})();

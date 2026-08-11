/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

const GROUPS = {
    hidePrint: "bi_advance_hide_show_menu.group_hide_print_btn",
    hideAction: "bi_advance_hide_show_menu.group_hide_action_btn",
    hideDelete: "bi_advance_hide_show_menu.group_hide_delete_action",
    hideDuplicate: "bi_advance_hide_show_menu.group_hide_duplicate_action",
    hideExportAction: "bi_advance_hide_show_menu.group_hide_export_action",
};

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this._biHideDelete = false;
        this._biHideDuplicate = false;
        this._biHidePrint = false;
        onWillStart(async () => {
            const [hideDelete, hideDuplicate, hidePrint] = await Promise.all([
                user.hasGroup(GROUPS.hideDelete),
                user.hasGroup(GROUPS.hideDuplicate),
                user.hasGroup(GROUPS.hidePrint),
            ]);
            this._biHideDelete = hideDelete;
            this._biHideDuplicate = hideDuplicate;
            this._biHidePrint = hidePrint;
        });
    },

    getStaticActionMenuItems() {
        const menuItems = { ...super.getStaticActionMenuItems() };
        if (this._biHideDuplicate && menuItems.duplicate) {
            delete menuItems.duplicate;
        }
        if (this._biHideDelete && menuItems.delete) {
            delete menuItems.delete;
        }
        if (this._biHidePrint && menuItems.print) {
            delete menuItems.print;
        }
        return menuItems;
    },
});

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        this._biHideDelete = false;
        this._biHideDuplicate = false;
        this._biHideExportAction = false;
        onWillStart(async () => {
            const [hideDelete, hideDuplicate, hideExportAction] = await Promise.all([
                user.hasGroup(GROUPS.hideDelete),
                user.hasGroup(GROUPS.hideDuplicate),
                user.hasGroup(GROUPS.hideExportAction),
            ]);
            this._biHideDelete = hideDelete;
            this._biHideDuplicate = hideDuplicate;
            this._biHideExportAction = hideExportAction;
        });
    },

    getStaticActionMenuItems() {
        const menuItems = { ...super.getStaticActionMenuItems() };
        if (this._biHideDuplicate && menuItems.duplicate) {
            delete menuItems.duplicate;
        }
        if (this._biHideDelete && menuItems.delete) {
            delete menuItems.delete;
        }
        if (this._biHideExportAction && menuItems.export) {
            delete menuItems.export;
        }
        return menuItems;
    },
});

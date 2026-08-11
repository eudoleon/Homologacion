/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";
import { ExportAll } from "@web/views/list/export_all/export_all";
import { user } from "@web/core/user";

export const patchImportMenuHide = {
    setup() {
        super.setup(...arguments);
        this.hasimportmenu = true;
        onWillStart(async () => {
            const hasGroup = await user.hasGroup(
                "bi_advance_hide_show_menu.group_export_btn_access"
            );
            this.hasimportmenu = !hasGroup;
        });
    }
};

patch(ExportAll.prototype, patchImportMenuHide);

/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ImportRecords } from "@base_import/import_records/import_records";
import { onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";

export const patchImportMenuHide = {
    setup() {
        super.setup(...arguments);
        this.hasimportmenu = true;
        onWillStart(async () => {
            const hasGroup = await user.hasGroup(
                "bi_advance_hide_show_menu.group_import_btn_access"
            );
            this.hasimportmenu = !hasGroup;
        });
    }
};

patch(ImportRecords.prototype, patchImportMenuHide);


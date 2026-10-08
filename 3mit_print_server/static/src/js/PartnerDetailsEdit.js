/** @odoo-module **/

import { useState } from "@odoo/owl";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import PartnerDetailsEdit from "point_of_sale.PartnerDetailsEdit";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup();
        const partner = this.props.partner;
        this.changes = useState({
            ...this.changes,
            company_type: partner.company_type,
            vat: partner.vat,
        });
    },

    validateRIF(rif) {
        const rifRegex = /^[VEJPG][0-9]{9}$/;
        if (!rifRegex.test(rif)) {
            return false;
        }

        const weights = [3, 2, 7, 6, 5, 4, 3, 2];
        let sum = 0;
        for (let index = 0; index < 8; index++) {
            sum += parseInt(rif[index + 1]) * weights[index];
        }
        const remainder = 11 - (sum % 11);
        const checkDigit = remainder === 10 ? 0 : remainder === 11 ? 1 : remainder;

        return parseInt(rif[9]) === checkDigit;
    },

    saveChanges() {
        this.changes.vat = this.changes.vat || this.props.partner.vat;

        const requiredFields = ["vat"];
        const fieldNames = {
            vat: "RIF",
        };
        const missingFields = requiredFields.filter(
            (field) => !this.changes[field] && !this.props.partner[field]
        );

        if (missingFields.length > 0) {
            const missingFieldNames = missingFields.map((field) => fieldNames[field]);
            this.env.services.dialog.add(AlertDialog, {
                title: "Campos obligatorios",
                body: `Los siguientes campos son obligatorios: ${missingFieldNames.join(", ")}`,
            });
            return;
        }
        return super.saveChanges();
    },
});
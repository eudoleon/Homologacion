# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError


class TestCustomContact(common.TransactionCase):

    def test_unique_id_type_vat(self):
        """Verificar la validación de unicidad de la combinación id_type y vat."""
        # 1. Creación exitosa
        p1 = self.env['res.partner'].create({
            'name': 'Contacto Test 1',
            'id_type': 'J',
            'vat': '123456789',
        })
        self.assertEqual(p1.id_type, 'J')
        self.assertEqual(p1.vat, '123456789')

        # 2. Mismo vat pero distinto id_type debe permitirse
        p2 = self.env['res.partner'].create({
            'name': 'Contacto Test 2',
            'id_type': 'V',
            'vat': '123456789',
        })
        self.assertEqual(p2.id_type, 'V')

        # 3. Mismo vat y mismo id_type en create debe lanzar ValidationError
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Contacto Duplicado Create',
                'id_type': 'J',
                'vat': '123456789',
            })

        # 4. Modificar p2 para que coincida con p1 (write) debe lanzar ValidationError
        with self.assertRaises(ValidationError):
            p2.write({'id_type': 'J'})

        # 5. Modificar otros campos no relacionados debe funcionar sin error
        p1.write({'name': 'Contacto Test 1 Renombrado'})
        self.assertEqual(p1.name, 'Contacto Test 1 Renombrado')

    def test_contact_form_view_id_type(self):
        """Verificar que la vista de formulario compile y contenga el campo id_type."""
        view = self.env.ref('custom_contact.view_partner_form_inherit_custom_contact')
        self.assertTrue(view.exists())
        view_arch = self.env['res.partner'].get_view(view.id, 'form')['arch']
        self.assertIn('name="id_type"', view_arch)

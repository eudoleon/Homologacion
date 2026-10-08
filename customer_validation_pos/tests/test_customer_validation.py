from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestCustomerValidationPos(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config = cls.env['pos.config'].create({
            'name': 'Test POS Config Validation',
            'required_name': True,
            'required_phone': True,
            'required_email': True,
            'unique_phone': True,
        })

    def test_01_backend_creation_not_blocked(self):
        """Creación normal desde el backend sin contexto de POS no debe bloquearse."""
        partner = self.env['res.partner'].create({
            'name': 'Backend Partner Sin Telefono',
        })
        self.assertTrue(partner.id)

    def test_02_pos_missing_phone_blocked(self):
        """Creación desde POS sin teléfono debe lanzar ValidationError."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        with self.assertRaises(ValidationError):
            self.env['res.partner'].with_context(**ctx).create({
                'name': 'POS Partner Sin Telefono',
                'email': 'test@example.com',
            })

    def test_03_pos_invalid_phone_digits_blocked(self):
        """Teléfono con menos de 11 dígitos debe lanzar ValidationError."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        with self.assertRaises(ValidationError):
            self.env['res.partner'].with_context(**ctx).create({
                'name': 'POS Partner Telefono Corto',
                'phone': '0412123',
                'email': 'test@example.com',
            })

    def test_04_pos_missing_email_blocked(self):
        """Creación desde POS sin correo debe lanzar ValidationError."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        with self.assertRaises(ValidationError):
            self.env['res.partner'].with_context(**ctx).create({
                'name': 'POS Partner Sin Correo',
                'phone': '04121234567',
            })

    def test_05_pos_valid_partner_success(self):
        """Creación desde POS con teléfono de 11 dígitos y correo debe ser exitosa."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        partner = self.env['res.partner'].with_context(**ctx).create({
            'name': 'POS Partner Valido',
            'phone': '04121234567',
            'email': 'valido@example.com',
            'identification_id': '12345678',
            'street': 'Calle Principal',
        })
        self.assertTrue(partner.id)

    def test_07_pos_phone_with_plus_58_success(self):
        """Teléfono con prefijo +58 no debe ser rechazado si tiene 10 o más dígitos locales."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        partner = self.env['res.partner'].with_context(**ctx).create({
            'name': 'POS Partner Con Mas 58',
            'phone': '+58 414-1234567',
            'email': 'mas58@example.com',
            'identification_id': '23456789',
            'street': 'Av. Principal',
        })
        self.assertTrue(partner.id)

    def test_08_pos_invalid_cedula_blocked(self):
        """Cédula corta (menos de 6 dígitos) debe lanzar ValidationError."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        with self.assertRaises(ValidationError):
            self.env['res.partner'].with_context(**ctx).create({
                'name': 'POS Partner Cedula Corta',
                'phone': '04149876543',
                'email': 'cedulacorta@example.com',
                'identification_id': '123',
                'street': 'Av. Principal',
            })

    def test_06_pos_duplicate_phone_blocked(self):
        """Teléfono duplicado cuando unique_phone=True debe lanzar ValidationError."""
        ctx = {
            'in_pos_partner_edit': True,
            'pos_config_id': self.pos_config.id,
        }
        self.env['res.partner'].with_context(**ctx).create({
            'name': 'Primer Cliente Con Telefono',
            'phone': '04149876543',
            'email': 'primero@example.com',
        })
        with self.assertRaises(ValidationError):
            self.env['res.partner'].with_context(**ctx).create({
                'name': 'Segundo Cliente Mismo Telefono',
                'phone': '04149876543',
                'email': 'segundo@example.com',
            })

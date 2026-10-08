# --- TESTS EXHAUSTIVOS PARA ODOO 19 (DUAL CURRENCY) ---
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

class AccountDualCurrencyTestBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.usd = cls.env.ref("base.USD")
        # Ajuste de moneda para Odoo 19
        cls.bs = cls.env.ref("base.VEF", raise_if_not_found=False) or \
                 cls.env['res.currency'].search([('symbol', '=', 'Bs')], limit=1) or \
                 cls.env['res.currency'].create({'name': 'Bolivares', 'symbol': 'Bs', 'rate': 1.0})
        
        if getattr(cls.company, "currency_id_dif", None) != cls.usd:
            cls.company.write({"currency_id_dif": cls.usd.id})
            
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product', 
            'list_price': 100, 
            'standard_price': 50,
            'type': 'consu'
        })
        cls.journal = cls.env['account.journal'].create({
            'name': 'Test Bank', 
            'type': 'bank', 
            'code': 'TBNK', 
            'currency_id': cls.bs.id, 
            'company_id': cls.company.id
        })

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyConfig(AccountDualCurrencyTestBase):
    def test_manifest_data_xml_ids_exist(self):
        # Verifica que los registros XML del módulo existan
        xmlids = [
            "account_dual_currency.group_edit_trm",
            "account_dual_currency.ir_cron_fix_missing_tax_today",
            "account_dual_currency.update_trm_res_currency",
            "account_dual_currency.decimal_dual_currency",
            "account_dual_currency.account_payment_register_dual_currency",
            "account_dual_currency.account_move_form_inherit_views",
        ]
        for xmlid in xmlids:
            record = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(record, "XML-ID no encontrado: %s" % xmlid)

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyModels(AccountDualCurrencyTestBase):
    def test_model_fields_are_registered(self):
        # Esta lista valida que las extensiones de campos sigan presentes en el ORM de v19
        expected_fields = {
            "res.company": {"currency_id_dif"},
            "res.currency": {"facturas_por_actualizar", "sincronizar"},
            "account.move": {"currency_id_dif", "tax_today", "amount_total_usd", "amount_total_bs"},
            "account.move.line": {"debit_usd", "credit_usd", "tax_today", "subtotal_ref"},
            "product.template": {"list_price_usd", "standard_price_usd"},
        }
        for model_name, fields_set in expected_fields.items():
            model = self.env[model_name]
            missing = fields_set - set(model._fields.keys())
            self.assertFalse(missing, "Faltan campos en %s: %s" % (model_name, ", ".join(missing)))

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyMoveLogic(AccountDualCurrencyTestBase):
    def test_post_and_dual_fields_full(self):
        # BUSQUEDA COMPATIBLE V19 (asset_receivable)
        acc_receivable = self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1)
        
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.bs.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2,
                'price_unit': 200,
                'account_id': acc_receivable.id,
            })]
        })
        move.action_post()
        
        # Validaciones de cálculo
        self.assertGreater(move.tax_today, 0)
        self.assertAlmostEqual(move.amount_total_bs, move.amount_total_usd * move.tax_today, places=2)
        
        # Probar onchanges y métodos de refresco
        move._onchange_tax_today()
        move._onchange_refresh_dual_amounts()

    def test_move_line_sync(self):
        acc_receivable = self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.bs.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100,
                'account_id': acc_receivable.id,
            })]
        })
        move.action_post()
        line = move.line_ids.filtered(lambda l: l.product_id)
        
        # Sincronización ref_unit <-> price_unit
        old_price = line.price_unit
        line.write({'ref_unit': 10}) 
        self.assertAlmostEqual(line.price_unit, 10 * move.tax_today)

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyPayments(AccountDualCurrencyTestBase):
    def test_payment_register_and_igtf(self):
        # Seteamos porcentaje IGTF en compañía
        self.company.igtf_divisa_porcentage = 3.0
        
        acc_receivable = self.env['account.account'].search([('account_type', '=', 'asset_receivable')], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.bs.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100,
                'account_id': acc_receivable.id,
            })]
        })
        move.action_post()

        wizard = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids).create({
            'journal_id': self.journal.id,
            'aplicar_igtf': True,
        })
        wizard._compute_mount_igtf()
        self.assertGreater(wizard.mount_igtf, 0)
        self.assertEqual(wizard.amount_total_pagar, wizard.amount + wizard.mount_igtf)

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyAssets(AccountDualCurrencyTestBase):
    def test_asset_dual_values(self):
        # Odoo 19: Validar si existe el modelo account.asset (requiere Contabilidad Enterprise)
        if 'account.asset' not in self.env:
            self.skipTest("Módulo de Activos no instalado")
            
        asset = self.env['account.asset'].create({
            'name': 'Laptop Test',
            'original_value': 1000,
            'acquisition_date': fields.Date.today(),
            'company_id': self.company.id,
            'tax_today': 10.0,
        })
        if hasattr(asset, '_compute_values_ref'):
            asset._compute_values_ref()
            self.assertEqual(asset.original_value_ref, 100)

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyLandedCosts(AccountDualCurrencyTestBase):
    def test_landed_cost_dual(self):
        if 'stock.landed.cost' not in self.env:
            self.skipTest("Módulo Landed Costs no instalado")
            
        lc = self.env['stock.landed.cost'].create({
            'name': 'Gastos de Importación',
            'company_id': self.company.id,
        })
        self.assertTrue(lc)

@tagged("-at_install", "post_install")
class TestAccountDualCurrencyViews(AccountDualCurrencyTestBase):
    def test_views_presence(self):
        # Verifica que las vistas heredadas existan en v19
        views = [
            'account_move_form_inherit_views',
            'view_move_line_tree_inherit_dual_currency',
            'account_payment_dual_currency',
        ]
        for v in views:
            view = self.env.ref(f'account_dual_currency.{v}', raise_if_not_found=False)
            self.assertTrue(view, f"Falta la vista: {v}")
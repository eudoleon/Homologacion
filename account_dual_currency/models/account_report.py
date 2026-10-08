# -*- coding: utf-8 -*-
import ast
import datetime
import io
import json
import logging
import math
import re
import base64
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key

import markupsafe
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta

from odoo.addons.web.controllers.utils import clean_action
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date
# xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    CURRENCY_DIF = None

    search_template = fields.Char(string="Search Template", required=True, compute='_compute_search_template')

    def _get_query_currency_table(self, options):
        """Backward-compatible currency table getter.

        Odoo v19 uses ``_get_currency_table`` while older custom code relies on
        ``_get_query_currency_table`` returning an SQL fragment.
        """
        currency_table_sql = None
        try:
            currency_table_sql = super()._get_query_currency_table(options)
        except AttributeError:
            currency_table = self._get_currency_table(options)
            currency_table_sql = getattr(currency_table, 'code', str(currency_table))

        # v19 may return "... AS (company_id, period_key, ...)" without a table alias.
        currency_table_sql = re.sub(r'\bAS\s*\(', 'AS currency_table (', str(currency_table_sql), flags=re.IGNORECASE)
        if 'currency_table' not in currency_table_sql.lower():
            currency_table_sql = f"({currency_table_sql}) AS currency_table"
        return currency_table_sql

    def _query_get(self, options, date_scope='strict_range', domain=None):
        """Backward-compatible wrapper for custom report handlers.

        Odoo v19 removed ``account.report._query_get`` in favor of
        ``_get_report_query``. Our custom handlers still call ``_query_get``,
        so we rebuild the old triple: (tables, where_clause, where_params).
        """
        domain = domain or []
        # v17/v18 used `normal`; v19 expects `from_beginning`.
        if date_scope == 'normal':
            date_scope = 'from_beginning'

        # Keep compatibility with versions where _query_get still exists upstream.
        try:
            return super()._query_get(options, date_scope, domain=domain)
        except (AttributeError, TypeError):
            pass

        report_query = None
        # Signature compatibility across versions.
        for call in (
            lambda: self._get_report_query(options, date_scope=date_scope, domain=domain),
            lambda: self._get_report_query(options, domain=domain, date_scope=date_scope),
            lambda: self._get_report_query(options, date_scope, domain),
            lambda: self._get_report_query(options, date_scope),
            lambda: self._get_report_query(options),
        ):
            try:
                report_query = call()
                break
            except TypeError:
                continue

        if report_query is None:
            raise UserError(_('Unable to build report SQL query for this Odoo version.'))

        if isinstance(report_query, tuple) and len(report_query) == 3:
            return report_query

        def _to_param_list(value):
            if value is None:
                return []
            nested_params = getattr(value, 'params', None)
            if nested_params is not None:
                return list(nested_params)
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]

        def _to_sql_text(value):
            if value is None:
                return ''
            sql_code = getattr(value, 'code', None)
            if sql_code is not None:
                return sql_code
            return str(value)

        tables = getattr(report_query, 'from_clause', None) or getattr(report_query, 'tables', None)
        where_clause = getattr(report_query, 'where_clause', '')
        where_params = getattr(report_query, 'where_clause_params', None)
        if where_params is None:
            where_params = getattr(report_query, 'where_params', None)
        from_params = getattr(report_query, 'from_clause_params', None)
        if from_params is None:
            from_params = getattr(report_query, 'tables_params', None)
        if from_params is None:
            from_params = getattr(report_query, 'from_params', None)

        if isinstance(where_clause, (list, tuple)):
            where_clause = ' AND '.join(_to_sql_text(part) for part in where_clause if part)
        else:
            where_clause = _to_sql_text(where_clause)

        tables = _to_sql_text(tables)

        if not tables:
            raise UserError(_('Unable to extract SQL FROM clause from report query object.'))

        # Some v19 query objects store all placeholders in ``params`` already;
        # others split them between FROM and WHERE sections.
        params_all = _to_param_list(getattr(report_query, 'params', None))
        params_from = _to_param_list(from_params) or _to_param_list(getattr(getattr(report_query, 'from_clause', None), 'params', None)) or _to_param_list(getattr(getattr(report_query, 'tables', None), 'params', None))
        params_where = _to_param_list(where_params) or _to_param_list(getattr(getattr(report_query, 'where_clause', None), 'params', None))
        params_joined = params_from + params_where

        expected_placeholders = (tables or '').count('%s') + (where_clause or '').count('%s')
        candidates = [params_all, params_joined, params_where, params_from]

        all_params = []
        for candidate in candidates:
            if expected_placeholders and len(candidate) == expected_placeholders:
                all_params = candidate
                break
        if not all_params:
            # Fall back to the richest candidate if exact matching isn't possible.
            all_params = max(candidates, key=lambda p: len(p)) if candidates else []

        return tables, where_clause or 'TRUE', all_params

    def export_to_pdf(self, options):
        """
        Método para exportar el reporte a PDF en Odoo 17
        """
        self.ensure_one()
        if not config['test_enable']:
            self = self.with_context(commit_assetsbundle=True)

        # Configuración de moneda dual
        new_context = {
            **self._context,
            'currency_dif': options.get('currency_dif'),
            'currency_id_company_name': options.get('currency_id_company_name'),
        }
        self = self.with_context(**new_context)

        # Obtener líneas del reporte
        lines = self._get_lines(options)
        
        # Generar contenido HTML
        body_html = self._generate_report_html(options, lines)
        
        # Generar PDF
        return {
            'file_name': self._get_report_filename(options),
            'file_content': self.env['ir.actions.report']._run_wkhtmltopdf(
                [body_html],
                landscape=self._is_landscape(options)
            ),
            'file_type': 'pdf',
        }

    def _generate_report_html(self, options, lines):
        """
        Genera el contenido HTML del reporte con encabezado en dos columnas
        """
        # Obtener filtros aplicados
        filters_applied = self._get_applied_filters(options)
        
        # Encabezado de columnas del reporte
        headers = []
        for column in options.get('columns', []):
            headers.append(f'<th style="text-align: right; padding: 5px; border: 1px solid #ddd;">{column.get("name", "")}</th>')
        
        # Líneas del reporte
        html_lines = []
        for line in lines:
            style = f"margin-left: {line.get('level', 0) * 20}px;"
            if line.get('level') == 0:
                style += " font-weight: bold; background-color: #f5f5f5;"
            
            columns_html = []
            for col in line.get('columns', []):
                align = 'right' if col.get('figure_type') == 'monetary' else 'left'
                columns_html.append(f'<td style="text-align: {align}; padding: 3px 5px; border: 1px solid #ddd;">{col.get("name", "")}</td>')
            
            html_lines.append(f'''
                <tr style="{style}">
                    <td style="padding: 3px 5px; border: 1px solid #ddd;">{line.get('name', '')}</td>
                    {''.join(columns_html)}
                </tr>
            ''')
        
        # HTML completo con encabezado de dos columnas
        return f'''
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>{self.name}</title>
                    <style>
                        body {{ font-family: Arial; margin: 0; padding: 20px; }}
                        table.report {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        .header-table {{ width: 100%; margin-bottom: 15px; }}
                        .header-left {{ width: 60%; vertical-align: top; }}
                        .header-right {{ width: 40%; vertical-align: top; text-align: right; }}
                        th {{ background-color: #f2f2f2; font-weight: bold; }}
                        .total-row {{ font-weight: bold; background-color: #e6e6e6; }}
                        .filter-label {{ font-weight: bold; display: inline-block; min-width: 100px; }}
                        .company-name {{ font-size: 1.2em; font-weight: bold; }}
                    </style>
                </head>
                <body>
                    <table class="header-table">
                        <tr>
                            <td class="header-left">
                                <div class="company-name">{self.env.company.name}</div>
                                <div style="font-size: 1.5em; font-weight: bold; color: #666; margin: 5px 0 10px 0;">{self.name}</div>
                                <div>Generado el: {fields.Date.today()}</div>
                            </td>
                            <td class="header-right">
                                {filters_applied}
                            </td>
                        </tr>
                    </table>
                    
                    <table class="report">
                        <thead>
                            <tr>
                                <th style="text-align: left; padding: 5px; border: 1px solid #ddd;">Descripción</th>
                                {''.join(headers)}
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(html_lines)}
                        </tbody>
                    </table>
                </body>
            </html>
        '''

    def _get_applied_filters(self, options):
        """
        Devuelve HTML con los filtros aplicados alineados a la derecha
        (Versión corregida del error de sintaxis)
        """
        filter_html = []
        
        # Filtro de fechas (siempre visible)
        date_from = options.get('date', {}).get('date_from')
        date_to = options.get('date', {}).get('date_to')
        if date_from and date_to:
            filter_html.append(
                f'<div><span class="filter-label">Período:</span> {date_from} al {date_to}</div>'
            )
        
        # Filtro "Solo asientos publicados" - Versión corregida
        status = "Solo asientos publicados" if options.get('all_entries') is False else "Todos los asientos"
        filter_html.append(
            f'<div><span class="filter-label">Estado:</span> {status}</div>'
        )
        
        # Filtro "Base devengada" o "Base de efectivo" - Versión corregida
        accounting_base = "Base devengada" if options.get('cash_basis') else "Base de efectivo"
        filter_html.append(
            f'<div><span class="filter-label">Base contable:</span> {accounting_base}</div>'
        )
        
        # Filtro de diario (solo si hay filtro aplicado)
        journal_ids = options.get('journal_ids')
        if journal_ids and journal_ids != ['all']:
            journals = self.env['account.journal'].browse([int(id) for id in journal_ids])
            journal_names = ', '.join(journals.mapped('name'))
            filter_html.append(
                f'<div><span class="filter-label">Diario(s):</span> {journal_names}</div>'
            )
        
        return ''.join(filter_html)

    def _is_landscape(self, options):
        """Determina si el reporte debe estar en formato horizontal"""
        return len(options.get('columns', [])) > 4

    def _get_report_filename(self, options):
        """Genera el nombre del archivo del reporte"""
        return f"{self.name.replace(' ', '_')}_{fields.Date.today()}.pdf"


    def _compute_search_template(self):
        super_compute = getattr(super(), '_compute_search_template', None)
        if super_compute:
            super_compute()
        for report in self:
            # Keep the upstream template by default on v19 to avoid legacy UI behaviors.
            if not report.search_template:
                report.search_template = 'account_dual_currency.search_template_generic_currency_dif'

    def get_options(self, previous_options=None):
        self.ensure_one()

        initializers_in_sequence = self._get_options_initializers_in_sequence()
        options = {}

        if (previous_options or {}).get('_running_export_test'):
            options['_running_export_test'] = True

        # We need report_id to be initialized. Compute the necessary options to check for reroute.
        for reroute_initializer_index, initializer in enumerate(initializers_in_sequence):
            initializer(options, previous_options=previous_options or {})

            # pylint: disable=W0143
            if initializer == self._init_options_report_id:
                break

        # Stop the computation to check for reroute once we have computed the necessary information
        no_reroute = (previous_options or {}).get('no_report_reroute')
        if not no_reroute and (not self.root_report_id or (self.use_sections and self.section_report_ids)) and options['report_id'] != self.id:
            # Load the variant/section instead of the root report
            variant_options = {**(previous_options or {})}
            for reroute_opt_key in ('selected_variant_id', 'selected_section_id', 'variants_source_id', 'sections_source_id'):
                opt_val = options.get(reroute_opt_key)
                if opt_val:
                    variant_options[reroute_opt_key] = opt_val

            return self.env['account.report'].browse(options['report_id']).get_options(variant_options)

        # No reroute; keep on and compute the other options
        for initializer_index in range(reroute_initializer_index + 1, len(initializers_in_sequence)):
            initializer = initializers_in_sequence[initializer_index]
            initializer(options, previous_options=previous_options)

        # Sort the buttons list by sequence, for rendering
        if not self.env['res.company']._all_branches_selected():
            options['buttons'] = [button for button in options['buttons'] if button.get('branch_allowed')]
        options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))
        main_company = self.env.company or self.env['res.company']._get_main_company()
        currency_id_company_name = 'Bs'
        currency_id_dif_name = 'USD'
        if main_company:
            currency_id_company_name = main_company.currency_id.symbol
            currency_id_dif_name = main_company.currency_id_dif.symbol
        currency_dif = currency_id_company_name
        if previous_options and "currency_dif" in previous_options:
            currency_dif = previous_options['currency_dif']
        elif self.env.context.get('currency_dif'):
            currency_dif = self.env.context.get('currency_dif')

        # Accept legacy labels such as "En $" / "En .Bs.F".
        currency_dif = (currency_dif or '').strip()
        if currency_dif.lower().startswith('en '):
            currency_dif = currency_dif[3:].strip()

        if currency_dif not in (currency_id_company_name, currency_id_dif_name):
            currency_dif = currency_id_company_name
        options['currency_dif'] = currency_dif
        options['currency_id_company_name'] = currency_id_company_name
        options['currency_id_dif_name'] = currency_id_dif_name

        # Some actions can reuse previous options coming from a different report.
        # If the saved sort column doesn't exist in the current report columns,
        # Odoo raises: "The column '<label>' is not available for this report".
        order_column = options.get('order_column')
        if order_column is not None:
            available_labels = {
                col.get('expression_label')
                for col in options.get('columns', [])
                if isinstance(col, dict) and col.get('expression_label')
            }

            invalid_order_column = False
            if isinstance(order_column, dict):
                expression_label = order_column.get('expression_label')
                column_index = order_column.get('column_index')
                if expression_label:
                    invalid_order_column = expression_label not in available_labels
                elif column_index is not None:
                    invalid_order_column = not (
                        isinstance(column_index, int)
                        and 0 <= column_index < len(options.get('columns', []))
                    )
            elif isinstance(order_column, str):
                invalid_order_column = order_column not in available_labels
            elif isinstance(order_column, int):
                invalid_order_column = not (0 <= order_column < len(options.get('columns', [])))

            if invalid_order_column:
                options.pop('order_column', None)

        # v19 frontend expects this key to always exist when rendering account reports.
        options.setdefault('custom_display_config', {'templates': {}})

        # COMENTADO ODOO 19: No se puede asignar directamente el contexto
        # new_context = {
        #     **self._context,
        #     'currency_dif': currency_dif,
        #     'currency_id_company_name': currency_id_company_name,
        # }
        # self.env.context = new_context

        return options

    # antiguo metodo de v16, reemplazado por el nuevo de v17
    # def _get_options(self, previous_options=None):
    #     self.ensure_one()
    #     # Create default options.
    #     options = {'unfolded_lines': (previous_options or {}).get('unfolded_lines', [])}
    #
    #     for initializer in self._get_options_initializers_in_sequence():
    #         initializer(options, previous_options=previous_options)
    #
    #     # Sort the buttons list by sequence, for rendering
    #     options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))
    #
    #     currency_id_company_name = 'Bs'
    #     currency_id_dif_name = 'USD'
    #     if self._context.get('allowed_company_ids'):
    #         company_id = self._context.get('allowed_company_ids')[0]
    #         company = self.env['res.company'].browse(company_id)
    #         if company:
    #             currency_id_company_name = company.currency_id.symbol
    #             currency_id_dif_name = company.currency_id_dif.symbol
    #     currency_dif = currency_id_company_name
    #     if previous_options:
    #         if "currency_dif" in previous_options:
    #             currency_dif = previous_options['currency_dif']
    #     options['currency_dif'] = currency_dif
    #     options['currency_id_company_name'] = currency_id_company_name
    #     options['currency_id_dif_name'] = currency_id_dif_name
    #     new_context = {
    #         **self._context,
    #         'currency_dif': currency_dif,
    #         'currency_id_company_name': currency_id_company_name,
    #     }
    #     self.env.context = new_context
    #     print('options', options)
    #     return options

    @api.model
    def format_value(self, options, value=None, currency=False, blank_if_zero=False, figure_type=None, digits=2, format_params=None, **kwargs):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        # Backward compatibility:
        # - v17 style calls often pass only `value` as first positional argument.
        # - v19 style passes `(options, value, ...)` and may include `format_params`.
        if value is None and not isinstance(options, dict):
            value = options
            options = {}
        elif options is None:
            options = {}

        if value is None:
            return ''

        if figure_type == 'none':
            return value

        if isinstance(value, str) or figure_type == 'string':
            return str(value)

        # v19 can send date objects without figure_type='date'.
        if isinstance(value, (datetime.date, datetime.datetime)):
            return format_date(self.env, value)

        if figure_type == 'monetary':
            currency = currency or self.env.company.currency_id
            if options.get('currency_dif'):
                if options.get('currency_dif') == options.get('currency_id_company_name'):
                    currency = self.env.company.currency_id
                else:
                    currency = self.env.company.currency_id_dif
            digits = currency.decimal_places if currency.decimal_places >= 2 else 2
        elif figure_type == 'integer':
            currency = None
            digits = 0
        elif figure_type == 'boolean':
            return bool(value)
        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)
        else:
            currency = None
            digits = 2 if digits is None or digits < 2 else digits

        is_zero_value = False
        if figure_type == 'monetary' and currency:
            is_zero_value = currency.is_zero(value)
        else:
            precision_digits = digits if digits is not None else 2
            is_zero_value = float_is_zero(value, precision_digits=precision_digits)

        if is_zero_value:
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            value = abs(value)

        if self.env.context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount

    def _compute_formula_batch_with_engine_domain(self, options, date_scope, formulas_dict, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        """ Report engine.

        Formulas made for this engine consist of a domain on account.move.line. Only those move lines will be used to compute the result.

        This engine supports a few subformulas, each returning a slighlty different result:
        - sum: the result will be sum of the matched move lines' balances

        - sum_if_pos: the result will be the same as sum only if it's positive; else, it will be 0

        - sum_if_neg: the result will be the same as sum only if it's negative; else, it will be 0

        - count_rows: the result will be the number of sublines this expression has. If the parent report line has no groupby,
                      then it will be the number of matching amls. If there is a groupby, it will be the number of distinct grouping
                      keys at the first level of this groupby (so, if groupby is 'partner_id, account_id', the number of partners).
        """
        currency_dif = options['currency_dif']
        def _format_result_depending_on_groupby(formula_rslt):
            if not current_groupby:
                if formula_rslt:
                    # There should be only one element in the list; we only return its totals (a dict) ; so that a list is only returned in case
                    # of a groupby being unfolded.
                    return formula_rslt[0][1]
                else:
                    # No result at all
                    return {
                        'sum': 0,
                        'sum_if_pos': 0,
                        'sum_if_neg': 0,
                        'count_rows': 0,
                        'has_sublines': False,
                    }
            return formula_rslt

        self._check_groupby_fields((next_groupby.split(',') if next_groupby else []) + ([current_groupby] if current_groupby else []))

        groupby_sql = f'account_move_line.{current_groupby}' if current_groupby else None

        rslt = {}

        for formula, expressions in formulas_dict.items():
            try:
                line_domain = literal_eval(formula)
            except (ValueError, SyntaxError):
                raise UserError(_("Invalid domain formula in expression %r of line %r: %s", expressions.label, expressions.report_line_id.name, formula))
            tables, where_clause, where_params = self._query_get(options, date_scope, domain=line_domain)

            tail_query, tail_params = self._get_engine_query_tail(offset, limit)
            if currency_dif == self.env.company.currency_id.symbol:
                query = f"""
                    SELECT
                        COALESCE(SUM(ROUND(account_move_line.balance, 2)), 0.0) AS sum,
                        COUNT(DISTINCT account_move_line.{next_groupby.split(',')[0] if next_groupby else 'id'}) AS count_rows
                        {f', {groupby_sql} AS grouping_key' if groupby_sql else ''}
                    FROM {tables}
                    WHERE {where_clause}
                    {f' GROUP BY {groupby_sql}' if groupby_sql else ''}
                    {tail_query}
                """
            else:
                query = f"""
                                    SELECT
                                        COALESCE(SUM(ROUND(account_move_line.balance_usd, 2)), 0.0) AS sum,
                                        COUNT(DISTINCT account_move_line.{next_groupby.split(',')[0] if next_groupby else 'id'}) AS count_rows
                                        {f', {groupby_sql} AS grouping_key' if groupby_sql else ''}
                                    FROM {tables}
                                    WHERE {where_clause}
                                    {f' GROUP BY {groupby_sql}' if groupby_sql else ''}
                                    {tail_query}
                                """

            # Fetch the results.
            formula_rslt = []
            self._cr.execute(query, list(where_params) + tail_params)
            all_query_res = self._cr.dictfetchall()

            total_sum = 0
            for query_res in all_query_res:
                res_sum = query_res['sum']
                total_sum += res_sum
                totals = {
                    'sum': res_sum,
                    'sum_if_pos': 0,
                    'sum_if_neg': 0,
                    'count_rows': query_res['count_rows'],
                    'has_sublines': query_res['count_rows'] > 0,
                }
                formula_rslt.append((query_res.get('grouping_key', None), totals))

            # Handle sum_if_pos, -sum_if_pos, sum_if_neg and -sum_if_neg
            expressions_by_sign_policy = defaultdict(lambda: self.env['account.report.expression'])
            for expression in expressions:
                subformula_without_sign = expression.subformula.replace('-', '').strip()
                if subformula_without_sign in ('sum_if_pos', 'sum_if_neg'):
                    expressions_by_sign_policy[subformula_without_sign] += expression
                else:
                    expressions_by_sign_policy['no_sign_check'] += expression

            # Then we have to check the total of the line and only give results if its sign matches the desired policy.
            # This is important for groupby managements, for which we can't just check the sign query_res by query_res
            if expressions_by_sign_policy['sum_if_pos'] or expressions_by_sign_policy['sum_if_neg']:
                sign_policy_with_value = 'sum_if_pos' if self.env.company.currency_id.compare_amounts(total_sum, 0.0) >= 0 else 'sum_if_neg'
                # >= instead of > is intended; usability decision: 0 is considered positive

                formula_rslt_with_sign = [(grouping_key, {**totals, sign_policy_with_value: totals['sum']}) for grouping_key, totals in formula_rslt]

                for sign_policy in ('sum_if_pos', 'sum_if_neg'):
                    policy_expressions = expressions_by_sign_policy[sign_policy]

                    if policy_expressions:
                        if sign_policy == sign_policy_with_value:
                            rslt[(formula, policy_expressions)] = _format_result_depending_on_groupby(formula_rslt_with_sign)
                        else:
                            rslt[(formula, policy_expressions)] = _format_result_depending_on_groupby([])

            if expressions_by_sign_policy['no_sign_check']:
                rslt[(formula, expressions_by_sign_policy['no_sign_check'])] = _format_result_depending_on_groupby(formula_rslt)

        return rslt

    @api.model
    def _prepare_lines_for_cash_basis(self):
        """Prepare the cash_basis_temp_account_move_line substitue.

        This method should be used once before all the SQL queries using the
        table account_move_line for reports in cash basis.
        It will create a new table like the account_move_line table, but with
        amounts and the date relative to the cash basis.
        """
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='cash_basis_temp_account_move_line'")
        if self.env.cr.fetchone():
            return
        #print('entra en el informe de cash basis')
        # TODO gawa Analytic + CABA, check the shadowing
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='account_move_line'")
        changed_fields = ['date', 'amount_currency', 'amount_residual', 'balance', 'debit', 'credit', 'amount_residual_usd', 'balance_usd', 'debit_usd', 'credit_usd']
        unchanged_fields = list(set(f[0] for f in self.env.cr.fetchall()) - set(changed_fields))
        selected_journals = tuple(self.env.context.get('journal_ids', []))
        sql = """   -- Create a temporary table
                CREATE TEMPORARY TABLE IF NOT EXISTS cash_basis_temp_account_move_line () INHERITS (account_move_line) ON COMMIT DROP;

                INSERT INTO cash_basis_temp_account_move_line ({all_fields}) SELECT
                    {unchanged_fields},
                    "account_move_line".date,
                    "account_move_line".amount_currency,
                    "account_move_line".amount_residual,
                    "account_move_line".balance,
                    "account_move_line".debit,
                    "account_move_line".credit,
                    "account_move_line".amount_residual_usd,
                    "account_move_line".balance_usd,
                    "account_move_line".debit_usd,
                    "account_move_line".credit_usd
                FROM ONLY account_move_line
                WHERE (
                    "account_move_line".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                    OR "account_move_line".move_id NOT IN (
                        SELECT DISTINCT aml.move_id
                        FROM ONLY account_move_line aml
                        JOIN account_account account ON aml.account_id = account.id
                        WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                    )
                )
                {where_journals};

                WITH payment_table AS (
                    SELECT
                        aml.move_id,
                        GREATEST(aml.date, aml2.date) AS date,
                        CASE WHEN (aml.balance = 0 OR sub_aml.total_per_account = 0)
                            THEN 0
                            ELSE part.amount / ABS(sub_aml.total_per_account)
                        END as matched_percentage
                    FROM account_partial_reconcile part
                    JOIN ONLY account_move_line aml ON aml.id = part.debit_move_id OR aml.id = part.credit_move_id
                    JOIN ONLY account_move_line aml2 ON
                        (aml2.id = part.credit_move_id OR aml2.id = part.debit_move_id)
                        AND aml.id != aml2.id
                    JOIN (
                        SELECT move_id, account_id, ABS(SUM(balance)) AS total_per_account
                        FROM ONLY account_move_line account_move_line
                        GROUP BY move_id, account_id
                    ) sub_aml ON (aml.account_id = sub_aml.account_id AND aml.move_id=sub_aml.move_id)
                    JOIN account_account account ON aml.account_id = account.id
                    WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                )
                INSERT INTO cash_basis_temp_account_move_line ({all_fields}) SELECT
                    {unchanged_fields},
                    ref.date,
                    ref.matched_percentage * "account_move_line".amount_currency,
                    ref.matched_percentage * "account_move_line".amount_residual,
                    ref.matched_percentage * "account_move_line".balance,
                    ref.matched_percentage * "account_move_line".debit,
                    ref.matched_percentage * "account_move_line".credit,
                    ref.matched_percentage * "account_move_line".amount_residual_usd,
                    ref.matched_percentage * "account_move_line".balance_usd,
                    ref.matched_percentage * "account_move_line".debit_usd,
                    ref.matched_percentage * "account_move_line".credit_usd
                FROM payment_table ref
                JOIN ONLY account_move_line account_move_line ON "account_move_line".move_id = ref.move_id
                WHERE NOT (
                    "account_move_line".journal_id IN (SELECT id FROM account_journal WHERE type in ('cash', 'bank'))
                    OR "account_move_line".move_id NOT IN (
                        SELECT DISTINCT aml.move_id
                        FROM ONLY account_move_line aml
                        JOIN account_account account ON aml.account_id = account.id
                        WHERE account.account_type IN ('asset_receivable', 'liability_payable')
                    )
                )
                {where_journals};
            """.format(
            all_fields=', '.join(f'"{f}"' for f in (unchanged_fields + changed_fields)),
            unchanged_fields=', '.join([f'"account_move_line"."{f}"' for f in unchanged_fields]),
            where_journals=selected_journals and 'AND "account_move_line".journal_id IN %(journal_ids)s' or ''
        )
        params = {
            'journal_ids': selected_journals,
        }
        self.env.cr.execute(sql, params)
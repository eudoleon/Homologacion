# -*- coding: utf-8 -*-
# Libro mayor y balance general
import json

from odoo import models, fields, api, _
from odoo.tools.misc import format_date
from odoo.tools import get_lang
from odoo.exceptions import UserError

from datetime import timedelta
from collections import defaultdict


class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _get_query_sums(self, report, options):
        """ Construct a query retrieving all the aggregated sums to build the report. It includes:
        - sums for all accounts.
        - sums for the initial balances.
        - sums for the unaffected earnings.
        - sums for the tax declaration.
        :return:                    (query, params)
        """
        options_by_column_group = report._split_options_per_column_group(options)

        params = []
        queries = []

        # Create the currency table.
        # As the currency table is the same whatever the comparisons, create it only once.
        ct_query = report._get_query_currency_table(options)
        currency_dif = (options.get('currency_dif') or '').strip()
        if currency_dif.lower().startswith('en '):
            currency_dif = currency_dif[3:].strip()
        company_currency_name = options.get('currency_id_company_name', self.env.company.currency_id.symbol)
        is_company_currency = currency_dif == company_currency_name
        # ============================================
        # 1) Get sums for all accounts.
        # ============================================
        for column_group_key, options_group in options_by_column_group.items():
            # Sum is computed including the initial balance of the accounts configured to do so, unless a special option key is used
            # (this is required for trial balance, which is based on general ledger)
            sum_date_scope = 'strict_range' if options_group.get('general_ledger_strict_range') else 'normal'

            query_domain = []

            if options.get('filter_search_bar'):
                query_domain.append(('account_id', 'ilike', options['filter_search_bar']))

            if options_group.get('include_current_year_in_unaff_earnings'):
                query_domain += [('account_id.include_initial_balance', '=', True)]

            tables, where_clause, where_params = report._query_get(options_group, sum_date_scope, domain=query_domain)
            params.append(column_group_key)
            params += where_params
            if is_company_currency:
                queries.append(f"""
                    SELECT
                        account_move_line.account_id                            AS groupby,
                        'sum'                                                   AS key,
                        MAX(account_move_line.date)                             AS max_date,
                        %s                                                      AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM {tables}
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    WHERE {where_clause}
                    GROUP BY account_move_line.account_id
                """)
            else:
                queries.append(f"""
                                    SELECT
                                        account_move_line.account_id                            AS groupby,
                                        'sum'                                                   AS key,
                                        MAX(account_move_line.date)                             AS max_date,
                                        %s                                                      AS column_group_key,
                                        COALESCE(SUM(0), 0.0)   AS amount_currency,
                                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                                    FROM {tables}
                                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                                    WHERE {where_clause}
                                    GROUP BY account_move_line.account_id
                                """)
            # ============================================
            # 2) Get sums for the unaffected earnings.
            # ============================================
            if not options_group.get('general_ledger_strict_range'):
                unaff_earnings_domain = [('account_id.include_initial_balance', '=', False)]

                # The period domain is expressed as:
                # [
                #   ('date' <= fiscalyear['date_from'] - 1),
                #   ('account_id.include_initial_balance', '=', False),
                # ]

                new_options = self._get_options_unaffected_earnings(options_group)
                tables, where_clause, where_params = report._query_get(new_options, 'strict_range', domain=unaff_earnings_domain)
                params.append(column_group_key)
                params += where_params
                if is_company_currency:
                    queries.append(f"""
                        SELECT
                            account_move_line.company_id                            AS groupby,
                            'unaffected_earnings'                                   AS key,
                            NULL                                                    AS max_date,
                            %s                                                      AS column_group_key,
                            COALESCE(SUM(account_move_line.amount_currency), 0.0)   AS amount_currency,
                            SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                            SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                            SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                        FROM {tables}
                        LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                        WHERE {where_clause}
                        GROUP BY account_move_line.company_id
                    """)
                else:
                    queries.append(f"""
                                            SELECT
                                                account_move_line.company_id                            AS groupby,
                                                'unaffected_earnings'                                   AS key,
                                                NULL                                                    AS max_date,
                                                %s                                                      AS column_group_key,
                                                COALESCE(SUM(0), 0.0)   AS amount_currency,
                                                SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                                SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                                SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                                            FROM {tables}
                                            LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                                            WHERE {where_clause}
                                            GROUP BY account_move_line.company_id
                                        """)

        return ' UNION ALL '.join(queries), params

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        """ Construct a query retrieving the account.move.lines when expanding a report line with or without the load
        more.
        :param options:               The report options.
        :param expanded_account_ids:  The account.account ids corresponding to consider. If None, match every account.
        :param offset:                The offset of the query (used by the load more).
        :param limit:                 The limit of the query (used by the load more).
        :return:                      (query, params)
        """
        additional_domain = [('account_id', 'in', expanded_account_ids)] if expanded_account_ids is not None else None
        queries = []
        all_params = []
        lang = self.env.user.lang or get_lang(self.env).code
        journal_name = f"COALESCE(journal.name->>'{lang}', journal.name->>'en_US')" if \
            self.pool['account.journal'].name.translate else 'journal.name'
        account_name = f"COALESCE(account.name->>'{lang}', account.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'account.name'
        currency_dif = (options.get('currency_dif') or '').strip()
        if currency_dif.lower().startswith('en '):
            currency_dif = currency_dif[3:].strip()
        company_currency_name = options.get('currency_id_company_name', self.env.company.currency_id.symbol)
        is_company_currency = currency_dif == company_currency_name
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            # Get sums for the account move lines.
            # period: [('date' <= options['date_to']), ('date', '>=', options['date_from'])]
            tables, where_clause, where_params = report._query_get(group_options, domain=additional_domain,
                                                                   date_scope='strict_range')
            ct_query = report._get_query_currency_table(group_options)
            if is_company_currency:
                query = f'''
                    (SELECT
                        account_move_line.id,
                        account_move_line.date,
                        account_move_line.date_maturity,
                        account_move_line.name,
                        account_move_line.ref,
                        account_move_line.company_id,
                        account_move_line.account_id,
                        account_move_line.payment_id,
                        account_move_line.partner_id,
                        account_move_line.currency_id,
                        account_move_line.amount_currency,
                        COALESCE(account_move_line.invoice_date, account_move_line.date)                 AS invoice_date,
                        ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                        ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                        ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance,
                        move.name                               AS move_name,
                        company.currency_id                     AS company_currency_id,
                        partner.name                            AS partner_name,
                        move.move_type                          AS move_type,
                        account.code                            AS account_code,
                        {account_name}                          AS account_name,
                        journal.code                            AS journal_code,
                        {journal_name}                          AS journal_name,
                        full_rec.id                             AS full_rec_name,
                        %s                                      AS column_group_key
                    FROM {tables}
                    JOIN account_move move                      ON move.id = account_move_line.move_id
                    LEFT JOIN {ct_query}                        ON currency_table.company_id = account_move_line.company_id
                    LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                    LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                    LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                    LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                    LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                    WHERE {where_clause}
                    ORDER BY account_move_line.date, account_move_line.id)
                '''
            else:
                query = f'''
                                (SELECT
                                    account_move_line.id,
                                    account_move_line.date,
                                    account_move_line.date_maturity,
                                    account_move_line.name,
                                    account_move_line.ref,
                                    account_move_line.company_id,
                                    account_move_line.account_id,
                                    account_move_line.payment_id,
                                    account_move_line.partner_id,
                                    account_move_line.currency_id,
                                    account_move_line.amount_currency,
                                    COALESCE(account_move_line.invoice_date, account_move_line.date)                 AS invoice_date,
                                    ROUND(account_move_line.debit_usd, currency_table.precision)   AS debit,
                                    ROUND(account_move_line.credit_usd, currency_table.precision)  AS credit,
                                    ROUND(account_move_line.balance_usd, currency_table.precision) AS balance,
                                    move.name                               AS move_name,
                                    company.currency_id                     AS company_currency_id,
                                    partner.name                            AS partner_name,
                                    move.move_type                          AS move_type,
                                    account.code                            AS account_code,
                                    {account_name}                          AS account_name,
                                    journal.code                            AS journal_code,
                                    {journal_name}                          AS journal_name,
                                    full_rec.id                             AS full_rec_name,
                                    %s                                      AS column_group_key
                                FROM {tables}
                                JOIN account_move move                      ON move.id = account_move_line.move_id
                                LEFT JOIN {ct_query}                        ON currency_table.company_id = account_move_line.company_id
                                LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                                LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                                LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                                LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                                LEFT JOIN account_full_reconcile full_rec   ON full_rec.id = account_move_line.full_reconcile_id
                                WHERE {where_clause}
                                ORDER BY account_move_line.date, account_move_line.id)
                            '''

            queries.append(query)
            all_params.append(column_group_key)
            all_params += where_params

        full_query = " UNION ALL ".join(queries)

        if offset:
            full_query += ' OFFSET %s '
            all_params.append(offset)
        if limit:
            full_query += ' LIMIT %s '
            all_params.append(limit)

        return (full_query, all_params)

    def _get_initial_balance_values(self, report, account_ids, options):
        """
        Get sums for the initial balance.
        """
        queries = []
        params = []
        currency_dif = (options.get('currency_dif') or '').strip()
        if currency_dif.lower().startswith('en '):
            currency_dif = currency_dif[3:].strip()
        company_currency_name = options.get('currency_id_company_name', self.env.company.currency_id.symbol)
        is_company_currency = currency_dif == company_currency_name
        for column_group_key, options_group in report._split_options_per_column_group(options).items():
            new_options = self._get_options_initial_balance(options_group)
            ct_query = report._get_query_currency_table(new_options)
            tables, where_clause, where_params = report._query_get(new_options, 'normal', domain=[
                ('account_id', 'in', account_ids),
                ('account_id.include_initial_balance', '=', True),
            ])
            params.append(column_group_key)
            params += where_params
            if is_company_currency:
                queries.append(f"""
                    SELECT
                        account_move_line.account_id                                                          AS groupby,
                        'initial_balance'                                                                     AS key,
                        NULL                                                                                  AS max_date,
                        %s                                                                                    AS column_group_key,
                        COALESCE(SUM(account_move_line.amount_currency), 0.0)                                 AS amount_currency,
                        SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                        SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
                    FROM {tables}
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    WHERE {where_clause}
                    GROUP BY account_move_line.account_id
                """)
            else:
                queries.append(f"""
                                    SELECT
                                        account_move_line.account_id                                                          AS groupby,
                                        'initial_balance'                                                                     AS key,
                                        NULL                                                                                  AS max_date,
                                        %s                                                                                    AS column_group_key,
                                        COALESCE(SUM(0), 0.0)                                 AS amount_currency,
                                        SUM(ROUND(account_move_line.debit_usd, currency_table.precision))   AS debit,
                                        SUM(ROUND(account_move_line.credit_usd, currency_table.precision))  AS credit,
                                        SUM(ROUND(account_move_line.balance_usd, currency_table.precision)) AS balance
                                    FROM {tables}
                                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                                    WHERE {where_clause}
                                    GROUP BY account_move_line.account_id
                                """)

        self._cr.execute(" UNION ALL ".join(queries), params)

        init_balance_by_col_group = {
            account_id: {column_group_key: {} for column_group_key in options['column_groups']}
            for account_id in account_ids
        }
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result['groupby']][result['column_group_key']] = result

        accounts = self.env['account.account'].browse(account_ids)
        return {
            account.id: (account, init_balance_by_col_group[account.id])
            for account in accounts
        }

    def _is_secondary_currency_report(self, options):
        currency_dif = (options.get('currency_dif') or '').strip()
        if currency_dif.lower().startswith('en '):
            currency_dif = currency_dif[3:].strip()
        company_currency_name = options.get('currency_id_company_name', self.env.company.currency_id.symbol)
        return bool(currency_dif and currency_dif != company_currency_name)

    def _apply_usd_amounts_to_custom_engine_result(self, res, options, date_scope, current_groupby):
        """Reemplaza debit, credit y balance por las columnas *_usd cuando el reporte está en divisa."""
        if not res or not self._is_secondary_currency_report(options):
            return res

        report = self.env['account.report'].browse(options['report_id'])
        effective_scope = 'from_beginning' if options.get('trial_balance_column_type') == 'end_balance' else date_scope
        tables, where_clause, where_params = report._query_get(options, effective_scope)

        if current_groupby == 'id_with_accumulated_balance':
            def _extract_aml_id(k):
                if isinstance(k, str):
                    try:
                        k = json.loads(k)
                    except Exception:
                        return None
                if isinstance(k, (list, tuple)) and len(k) > 1 and k[1]:
                    return k[1]
                return None

            aml_ids = [aid for aid in (_extract_aml_id(k) for k, _ in res) if aid]
            if not aml_ids:
                return res
            query = """
                SELECT
                    account_move_line.id                                  AS aml_id,
                    COALESCE(ROUND(account_move_line.debit_usd, 2), 0.0)  AS debit,
                    COALESCE(ROUND(account_move_line.credit_usd, 2), 0.0) AS credit,
                    COALESCE(ROUND(account_move_line.balance_usd, 2), 0.0) AS balance
                FROM account_move_line
                WHERE account_move_line.id IN %s
            """
            self._cr.execute(query, [tuple(aml_ids)])
            usd_by_id = {row['aml_id']: row for row in self._cr.dictfetchall()}
            for key, vals in res:
                aml_id = _extract_aml_id(key)
                row = usd_by_id.get(aml_id)
                if row:
                    vals['debit'] = row['debit']
                    vals['credit'] = row['credit']
                    vals['balance'] = row['balance']
                elif aml_id:
                    vals['debit'] = 0.0
                    vals['credit'] = 0.0
                    vals['balance'] = 0.0
        elif current_groupby:
            if current_groupby not in self.env['account.move.line']._fields:
                return res
            keys = [k for k, _ in res if k is not None]
            if not keys:
                return res
            query = f"""
                SELECT
                    account_move_line.{current_groupby}                     AS groupby_key,
                    COALESCE(SUM(ROUND(account_move_line.debit_usd, 2)), 0.0)   AS debit,
                    COALESCE(SUM(ROUND(account_move_line.credit_usd, 2)), 0.0)  AS credit,
                    COALESCE(SUM(ROUND(account_move_line.balance_usd, 2)), 0.0) AS balance
                FROM {tables}
                WHERE {where_clause}
                  AND account_move_line.{current_groupby} IN %s
                GROUP BY account_move_line.{current_groupby}
            """
            self._cr.execute(query, list(where_params) + [tuple(keys)])
            usd_by_key = {row['groupby_key']: row for row in self._cr.dictfetchall()}
            for key, vals in res:
                row = usd_by_key.get(key)
                if row:
                    vals['debit'] = row['debit']
                    vals['credit'] = row['credit']
                    vals['balance'] = row['balance']
                else:
                    vals['debit'] = 0.0
                    vals['credit'] = 0.0
                    vals['balance'] = 0.0
        else:
            query = f"""
                SELECT
                    COALESCE(SUM(ROUND(account_move_line.debit_usd, 2)), 0.0)   AS debit,
                    COALESCE(SUM(ROUND(account_move_line.credit_usd, 2)), 0.0)  AS credit,
                    COALESCE(SUM(ROUND(account_move_line.balance_usd, 2)), 0.0) AS balance
                FROM {tables}
                WHERE {where_clause}
            """
            self._cr.execute(query, list(where_params))
            row = self._cr.dictfetchone()
            if row and isinstance(res, dict):
                res['debit'] = row['debit']
                res['credit'] = row['credit']
                res['balance'] = row['balance']
        return res

    def _report_custom_engine_general_ledger(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        res = super()._report_custom_engine_general_ledger(
            expressions, options, date_scope, current_groupby, next_groupby,
            offset=offset, limit=limit, warnings=warnings,
        )
        return self.env['account.general.ledger.report.handler']._apply_usd_amounts_to_custom_engine_result(
            res, options, date_scope, current_groupby,
        )


class TrialBalanceCustomHandler(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'

    def _report_custom_engine_trial_balance(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        res = super()._report_custom_engine_trial_balance(
            expressions, options, date_scope, current_groupby, next_groupby,
            offset=offset, limit=limit, warnings=warnings,
        )
        return self.env['account.general.ledger.report.handler']._apply_usd_amounts_to_custom_engine_result(
            res, options, date_scope, current_groupby,
        )
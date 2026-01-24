# Merge comparison: LOCAL vs INCOMING (dcc24ff "working")

You're merging **origin/main** (commit `dcc24ff` – "working") into your local **main**.  
Below: what **you have locally** vs what **the merge would bring in**.

---

## Summary

| File | Local (yours) | Incoming (dcc24ff) | Notes |
|------|---------------|--------------------|--------|
| **__init__.py** | + `from . import wizard` | Same | Match |
| **__manifest__.py** | + `account`, + SOA views, optional XLSX | + partner + create_account_wizard only, no SOA | **Differs** – you have SOA + account |
| **controllers/controllers.py** | + `logging`, `_logger`, blank lines | Same | Match |
| **models/__init__.py** | + res_partner, **account_soa** (enabled), account_soa_xlsx commented | + res_partner, **account_soa** commented, account_soa_xlsx commented | **Differs** – you enable SOA |
| **models/invoice.py** | + `currency_selection`, **_currency_convert** fix (loop, limit=1) | + `currency_selection` only | **Differs** – you have _currency_convert fix |
| **models/models.py** | email_ref_no, is_delivered compute, name_search, _compute_is_delivered, _compute_is_invoiced, contact fix, **no** po_number in payload / _logger | Same + **po_number** in payloads, **_logger** in action_booked | **Differs** – incoming adds API payload + logging |
| **report/invoice.xml** | font 11px, **AED/USD/EUR** bank blocks | Same (AED/USD/EUR) | Largely same |
| **security/ir.model.access.csv** | + SOA access, + create_account_wizard | + create_account_wizard only | **Differs** – you have SOA access |
| **views/account_view.xml** | **Full** tree (contact, PO, shipper, consignee, ports, countries, pcs, CW, commodity, sale/tracking ref, BL/AWB, amounts, profit, etc.) | Minimal tree (shipper, type, terms, port, origin, CW, **profit_only** extra) | **Differs** – you have many more optional columns |
| **views/sale_views.xml** | email_ref search, **many** optional fields (contact, PO, shipment, ports, countries, cargo, tracking, delivery, etc.), **new_state** decorations | email_ref search, **email_ref + contact_person** only, **state** decorations | **Differs** – you have full optional tree |

**Untracked (would be overwritten by merge):**  
`CHANGES_SUMMARY.md`, `models/res_partner.py`, `views/create_account_wizard_view.xml`, `views/partner_view.xml`  
→ Incoming **adds** these files. You have local untracked copies; merge would replace them with the incoming versions.

---

## Differences that matter

### 1. **SOA (Statement of Account)**  
- **Local:** SOA enabled (manifest, `account_soa` import, SOA views, access rules). Optional XLSX.  
- **Incoming:** No SOA (account_soa commented, no SOA in manifest).  
→ **Keeping yours** preserves SOA.

### 2. **Account move tree**  
- **Local:** Many optional columns (contact, PO, shipper, consignee, ports, countries, cargo, sale/tracking ref, BL/AWB, amounts, profit, etc.).  
- **Incoming:** Basic optional columns + profit only.  
→ **Keeping yours** keeps the full invoice tree.

### 3. **Sales tree**  
- **Local:** Many optional columns + `new_state` decorations.  
- **Incoming:** email_ref + contact_person + `state` decorations.  
→ **Keeping yours** keeps the full sales tree.

### 4. **models/models.py**  
- **Local:** contact fix, _compute_is_invoiced, etc. No `po_number` in API payloads, no `_logger` in action_booked.  
- **Incoming:** Adds `po_number` to tracking API payloads and `_logger.error` in action_booked.  
→ **Merge**: keep your logic, **add** po_number + _logger from incoming.

### 5. **models/invoice.py**  
- **Local:** `_currency_convert` fix (proper loop, `limit=1`).  
- **Incoming:** Only `currency_selection`; no compute fix.  
→ **Keep yours** to avoid CacheMiss/singleton issues.

### 6. **Wizard & partner**  
- **Incoming:** Adds `wizard` (create_account_wizard), `res_partner`, partner/create_account_wizard views + access.  
- **Local:** You have `partner_view` / `create_account_wizard` in manifest and untracked views; **no** `from . import wizard` in root `__init__.py` if you only add it in models.  
→ **Merge**: take incoming’s **wizard** + **res_partner** + partner/create_account_wizard views/code, but keep your **manifest** (SOA, account, etc.) and **models/__init__** (account_soa enabled).

---

## Recommended approach before merging

1. **Back up your work**
   ```bash
   cd /Users/admin/projects/kuriercrm/custom/deepu_sale
   git stash push -u -m "local-deepu_sale"
   ```
   (`-u` stashes untracked too.)

2. **Merge**
   ```bash
   git merge origin/main
   ```

3. **Re-apply your version where you want to keep it**
   - Option A: `git stash pop` and resolve conflicts by keeping your SOA, account tree, sales tree, invoice _currency_convert, and manifest/models init choices; add po_number + _logger from incoming into `models/models.py`.
   - Option B: After merge, selectively `git checkout stash -- <path>` for files you want to keep as-is, then manually add **po_number** and **_logger** from incoming into `models/models.py`.

4. **Untracked files**  
   Incoming adds `res_partner`, `create_account_wizard` (wizard), and their views. After merge, prefer the **incoming** versions of those new files. Your stash might have local copies; resolve by choosing incoming for wizard/partner, and your version for SOA/account/sales/invoice.

5. **Verify**
   - Manifest: `account`, SOA views, optional XLSX, partner + create_account_wizard.
   - `models/__init__`: `res_partner`, `account_soa` (and optionally account_soa_xlsx when report_xlsx used).
   - Root `__init__.py`: `from . import wizard` if create_account_wizard lives in `wizard/`.
   - `models/models.py`: your contact/compute logic **plus** po_number in payloads and _logger in action_booked.

---

## Quick reference: keep local vs take incoming

| Keep LOCAL | Take INCOMING (or merge both) |
|------------|-------------------------------|
| __manifest__.py (SOA, account, XLSX comment) | wizard, res_partner, create_account_wizard views |
| models/__init__.py (account_soa enabled) | models/models.py: po_number in payloads, _logger |
| models/invoice.py (full _currency_convert fix) | |
| models/models.py (contact, _compute_is_invoiced, etc.) | |
| security: SOA + create_account_wizard | |
| views/account_view.xml (full tree) | |
| views/sale_views.xml (full optional tree) | |
| report/invoice.xml (your styling + AED/USD/EUR) | |

Use this as a checklist when resolving conflicts and re-applying stashed changes.

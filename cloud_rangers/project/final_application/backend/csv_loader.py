"""
CSV Regulatory Database Loader
Parses verified regulatory additive records into indexed lookups.
Quarantined/synthetic records are excluded from production serving.
"""
import csv
import os
import logging

from lps.shared.regulatory_audit import classify_row

logger = logging.getLogger(__name__)

_DEFAULT_VERIFIED = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "regulatory_database_verified.csv",
)
_DEFAULT_LEGACY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "regulatory_database.csv",
)


def resolve_regulatory_csv_path(explicit_path: str | None = None) -> str:
    """Prefer audited verified CSV; fall back to legacy source."""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    if os.path.exists(_DEFAULT_VERIFIED):
        return _DEFAULT_VERIFIED
    return _DEFAULT_LEGACY


class RegulatoryCSVDatabase:
    """In-memory regulatory database loaded from verified CSV records."""

    def __init__(self, csv_path=None):
        self.csv_path = resolve_regulatory_csv_path(csv_path)
        self.quarantined_count = 0
        # Primary index: e_number -> list of records (one per country)
        self.by_e_number = {}
        # Secondary index: additive_name (lowercase) -> list of records
        self.by_name = {}
        # Tertiary index: country (lowercase) -> list of banned records
        self.banned_by_country = {}
        # All records flat list
        self.all_records = []
        
        self._load()

    def _load(self):
        """Parse CSV into indexed structures."""
        if not os.path.exists(self.csv_path):
            logger.warning(f"Regulatory CSV not found at {self.csv_path}")
            return

        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    quarantine_reason = classify_row(row)
                    if quarantine_reason:
                        self.quarantined_count += 1
                        continue

                    record = self._normalize_row(row)
                    if not record:
                        continue

                    self.all_records.append(record)
                    
                    # Index by E-number
                    e_num = record['e_number'].upper()
                    if e_num not in self.by_e_number:
                        self.by_e_number[e_num] = []
                    self.by_e_number[e_num].append(record)
                    
                    # Index by name
                    name_key = record['name'].lower()
                    if name_key not in self.by_name:
                        self.by_name[name_key] = []
                    self.by_name[name_key].append(record)
                    
                    # Index banned items by country
                    if record['status'].lower() in ('banned', 'banned in india'):
                        country_key = record['country'].lower()
                        if country_key not in self.banned_by_country:
                            self.banned_by_country[country_key] = []
                        self.banned_by_country[country_key].append(record)

            logger.info(
                "Regulatory CSV loaded: %d verified records (%d quarantined/skipped), "
                "%d unique E-numbers, %d countries with bans — source: %s",
                len(self.all_records),
                self.quarantined_count,
                len(self.by_e_number),
                len(self.banned_by_country),
                os.path.basename(self.csv_path),
            )
        except Exception as e:
            logger.error(f"Failed to load regulatory CSV: {e}")

    def _normalize_row(self, row):
        """Normalize a CSV row into a clean record dict."""
        e_number = (row.get('E_number') or row.get('E_Number') or '').strip()
        name = (row.get('Additive_name') or row.get('Additive_Name') or '').strip()
        country = (row.get('Country') or row.get('Region') or '').strip()
        status = (row.get('Status') or '').strip()
        reason = (row.get('Reason') or row.get('Ban_Reason') or row.get('Scientific_Concern') or '').strip()
        risk_level = (row.get('Risk_Level') or 'Low').strip()
        ban_date = (row.get('Ban_or_Restriction_Date') or row.get('Ban_Date') or '').strip()
        authority = (row.get('Regulatory_authority') or '').strip()
        category = (row.get('Category') or row.get('Functional_Class') or '').strip()
        
        if not e_number and not name:
            return None
            
        return {
            'e_number': e_number,
            'name': name,
            'country': country,
            'status': status,
            'reason': reason,
            'risk_level': risk_level,
            'ban_date': ban_date,
            'authority': authority,
            'category': category,
        }

    def lookup_additive(self, identifier):
        """
        Look up an additive by E-number or name.
        Returns list of records (one per country) or empty list.
        """
        identifier = identifier.strip()
        
        # Try E-number first
        upper_id = identifier.upper()
        if upper_id in self.by_e_number:
            return self.by_e_number[upper_id]
        
        # Try with E prefix
        if not upper_id.startswith('E') and upper_id.isdigit():
            e_key = f"E{upper_id}"
            if e_key in self.by_e_number:
                return self.by_e_number[e_key]
        
        # Try by name (exact, lowercase)
        lower_id = identifier.lower()
        if lower_id in self.by_name:
            return self.by_name[lower_id]
        
        # Try partial name match
        for name_key, records in self.by_name.items():
            if lower_id in name_key or name_key in lower_id:
                return records
        
        return []

    def check_ingredients_against_csv(self, ingredients_text):
        """
        Check an ingredients text string against the full CSV database.
        Returns list of matched additive records with their regulatory status.
        """
        if not ingredients_text or ingredients_text.lower() == 'not available':
            return []
        
        ingredients_lower = ingredients_text.lower()
        found = []
        seen_names = set()
        
        for name_key, records in self.by_name.items():
            # Skip very short names to avoid false positives (e.g., "gum" in "chewing gum")
            if len(name_key) < 4:
                continue
            
            if name_key in ingredients_lower and name_key not in seen_names:
                seen_names.add(name_key)
                # Group by additive, return all country records
                found.append({
                    'name': records[0]['name'],
                    'e_number': records[0]['e_number'],
                    'records': records
                })
        
        # Also check E-number patterns (e.g., "E621", "E171")
        import re
        e_numbers_in_text = re.findall(r'\b[Ee]\d{3,4}[a-z]?\b', ingredients_text)
        for e_num in e_numbers_in_text:
            e_upper = e_num.upper()
            if e_upper in self.by_e_number:
                name = self.by_e_number[e_upper][0]['name']
                if name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    found.append({
                        'name': name,
                        'e_number': e_upper,
                        'records': self.by_e_number[e_upper]
                    })
        
        return found

    def get_additive_status_by_country(self, identifier, country):
        """Get the status of a specific additive in a specific country."""
        records = self.lookup_additive(identifier)
        country_lower = country.lower()
        for r in records:
            if r['country'].lower() == country_lower:
                return r
        return None

    def get_global_regulatory_status(self, ingredients_text):
        """
        Get regulatory status for FSSAI, FDA, EFSA based on real CSV data.
        Returns a list of agency status dicts.
        """
        matched = self.check_ingredients_against_csv(ingredients_text)
        
        status_map = {
            "🇮🇳 FSSAI (India)": {"status": "Approved", "risk": "Safe", "flagged": []},
            "🇺🇸 FDA (USA)": {"status": "Approved", "risk": "Safe", "flagged": []},
            "🇪🇺 EFSA (EU)": {"status": "Approved", "risk": "Safe", "flagged": []},
        }
        
        country_agency = {
            'india': "🇮🇳 FSSAI (India)",
            'usa': "🇺🇸 FDA (USA)",
            'eu': "🇪🇺 EFSA (EU)",
        }

        for additive in matched:
            for record in additive['records']:
                country_lower = record['country'].lower()
                status_lower = record['status'].lower()
                
                agency_key = None
                if country_lower == 'india':
                    agency_key = country_agency['india']
                elif country_lower == 'usa':
                    agency_key = country_agency['usa']
                elif country_lower == 'eu':
                    agency_key = country_agency['eu']
                
                if agency_key and ('banned' in status_lower or 'restricted' in status_lower):
                    status_map[agency_key]["status"] = "Banned"
                    status_map[agency_key]["risk"] = "High"
                    status_map[agency_key]["flagged"].append({
                        "additive": additive['name'],
                        "e_number": additive['e_number'],
                        "reason": record['reason']
                    })
        
        return [
            {"country": k, "status": v["status"], "risk": v["risk"], "flagged_additives": v["flagged"]}
            for k, v in status_map.items()
        ]

    def get_banned_additives_for_country(self, country):
        """Get all banned additives for a specific country."""
        return self.banned_by_country.get(country.lower(), [])

    def get_detailed_additive_report(self, ingredients_text, additives_tags=None):
        """
        Generate a detailed additive report from ingredients text and OFF additive tags.
        Returns a list of additive details with full cross-country regulatory info.
        """
        report = []
        seen = set()
        
        # From ingredients text
        matched = self.check_ingredients_against_csv(ingredients_text)
        for m in matched:
            if m['name'].lower() in seen:
                continue
            seen.add(m['name'].lower())
            
            countries = {}
            risk = 'Low'
            reason = ''
            for r in m['records']:
                countries[r['country']] = r['status']
                if r['risk_level'] in ('High', 'Medium') and r['risk_level'] > risk:
                    risk = r['risk_level']
                if r['reason'] and not reason:
                    reason = r['reason']
            
            report.append({
                'name': m['name'],
                'e_number': m['e_number'],
                'risk_level': risk,
                'reason': reason,
                'country_status': countries,
                'category': m['records'][0].get('category', ''),
            })
        
        # From OFF additive tags (e.g., ['en:e322', 'en:e471'])
        if additives_tags:
            for tag in additives_tags:
                e_num = tag.replace('en:', '').upper()
                if e_num in self.by_e_number:
                    name = self.by_e_number[e_num][0]['name']
                    if name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    
                    countries = {}
                    risk = 'Low'
                    reason = ''
                    for r in self.by_e_number[e_num]:
                        countries[r['country']] = r['status']
                        if r['risk_level'] in ('High', 'Medium'):
                            risk = r['risk_level']
                        if r['reason'] and not reason:
                            reason = r['reason']
                    
                    report.append({
                        'name': name,
                        'e_number': e_num,
                        'risk_level': risk,
                        'reason': reason,
                        'country_status': countries,
                        'category': self.by_e_number[e_num][0].get('category', ''),
                    })
        
        return report

# CSV Data Normalization Improvements

## Current Status
- **Expected leads**: 655
- **Actually inserted**: 484 (74% success rate)
- **Missing**: 171 leads (26% loss)

## Root Causes Identified

### 1. **Column Mapping Issues**
Current mappings miss several variations found in actual CSVs:

**Problems**:
- Missing case-insensitive handling for "EMAIL" (all caps)
- Missing "CORREO" without accents
- Missing "Tel" for phone
- Column names with trailing spaces not handled

**Fix Required** in `csv_data_processor.py` line 28-37:
```python
COLUMN_MAPPINGS = {
    'full_name': [
        'NOMBRE COMPLETO', 'Nombre Completo', 'Name', 'Full Name',
        'NOMBRE', 'Nombre', 'nombre completo', 'nombre',
        # Handle with trailing spaces
    ],
    'email': [
        'CORREO', 'Correo', 'Email', 'E-mail', 'EMAIL', 'email',
        'Correo electrónico', 'Correo electronico', 'CORREO ELECTRONICO',
        'E-MAIL', 'e-mail'
    ],
    'phone': [
        'CELULAR', 'Celular', 'celular', 'Teléfono', 'Telefono', 'TELEFONO',
        'Phone', 'PHONE', 'phone', 'Móvil', 'Movil', 'MOVIL',
        'Tel', 'TEL', 'tel', 'Cel', 'CEL', 'cel'
    ],
}
```

### 2. **Column Name Normalization**
Columns need better normalization before matching:
- Strip whitespace: `"NOMBRE COMPLETO "` → `"NOMBRE COMPLETO"`
- Case-insensitive: `columns_lower` already does this, good
- Handle Unicode/accents in column names themselves

**Fix Required** in `find_column()` method (line 65-74):
```python
def find_column(self, df: pd.DataFrame, field_name: str) -> Optional[str]:
    """Find column name for a given field with fuzzy matching."""
    possible_names = self.COLUMN_MAPPINGS.get(field_name, [])
    
    # Normalize column names
    columns_normalized = {}
    for col in df.columns:
        # Strip whitespace and normalize
        normalized = str(col).strip().lower()
        normalized = unidecode(normalized)  # Remove accents
        columns_normalized[normalized] = col
    
    for possible_name in possible_names:
        normalized_search = unidecode(possible_name.lower().strip())
        if normalized_search in columns_normalized:
            return columns_normalized[normalized_search]
    
    return None
```

### 3. **Name Filtering Too Strict**
Line 123: `if not normalized_name or len(normalized_name) < 3:`

This skips valid single-letter + surname combinations common in Spanish names.

**Fix**: Change threshold to 2 characters minimum or add special handling for surnames.

### 4. **Empty Row Handling**
Many CSVs have empty first rows or rows with only "Unnamed: 0" data.

**Fix Required** in `extract_persons_from_csv()` (line 115-118):
```python
# Extract name - handle multiple possible name sources
name = None

# Try the identified name column
if pd.notna(row[name_col]):
    name = str(row[name_col]).strip()

# If name column is empty but row has data in other columns, skip gracefully
if not name or name == 'nan' or name == '':
    # Check if row has ANY non-null data
    has_data = any(pd.notna(val) and str(val).strip() and str(val).strip() != 'nan' 
                   for col, val in row.items() if col != name_col)
    if not has_data:
        continue  # Completely empty row
    # Row has data but no name - this is a data quality issue, log it
    logger.debug(f"Row {idx} has data but no name, skipping")
    continue
```

### 5. **Birth Date Parsing Issues**
171 failed inserts likely include date parsing failures even with our safe parser.

**Current date formats seen**:
- `"25/ sep/1999"` - Space after day
- `"2006-01-16 00:00:00"` - Timestamp format
- `"26 años"` - Age instead of date
- Missing dates

**Enhancement Required** in `_parse_date_safely()`:
```python
def _parse_date_safely(self, date_value: Any) -> Any:
    """Enhanced date parsing with multiple format support."""
    if not date_value or pd.isna(date_value):
        return None
    
    # If already a date/datetime object
    if isinstance(date_value, (datetime, pd.Timestamp)):
        return date_value.date() if hasattr(date_value, 'date') else date_value
    
    # String processing
    if isinstance(date_value, str):
        date_str = date_value.strip()
        
        # Skip invalid patterns
        if not date_str or date_str.lower() in ['nan', 'none', '']:
            return None
        
        # Skip age patterns (e.g., "26 años", "30 years")
        if 'año' in date_str.lower() or 'year' in date_str.lower():
            return None
        
        # Clean up common issues
        date_str = date_str.replace('/ ', '/').replace(' /', '/')  # "25/ sep" → "25/sep"
        
        # Try parsing with dateutil (flexible)
        try:
            from dateutil import parser
            parsed = parser.parse(date_str, dayfirst=True)
            return parsed.date()
        except:
            logger.debug(f"Cannot parse date: {date_value}")
            return None
    
    # Handle numeric dates (Excel serial numbers)
    if isinstance(date_value, (int, float)):
        try:
            # Excel epoch is 1899-12-30
            from datetime import timedelta
            excel_epoch = datetime(1899, 12, 30)
            return (excel_epoch + timedelta(days=date_value)).date()
        except:
            return None
    
    return None
```

### 6. **Deduplication Issues**
Line 150: `person_key = (normalized_name, email or 'no-email')`

This creates duplicates when people have no email but different phone numbers.

**Fix**: Use more intelligent deduplication:
```python
# Better deduplication key
def _get_person_key(self, name: str, email: Optional[str], phone: Optional[str], cedula: Optional[str]) -> tuple:
    """Generate unique key for person deduplication."""
    # Priority: cedula > email > name+phone > name
    if cedula and cedula != 'nan':
        return ('cedula', cedula)
    if email and email != 'nan' and '@' in email:
        return ('email', email.lower())
    if phone and phone != 'nan' and len(phone) >= 7:
        # Normalize phone: remove spaces, dashes, parentheses
        clean_phone = re.sub(r'[^\d]', '', phone)
        return ('phone', f"{name}:{clean_phone}")
    return ('name', name)
```

### 7. **Missing Status Detection**
Sheet: "CAMP 2025" should be detected as enrolled students, but might be classified as leads.

**Enhancement**: Add more status keywords and handle year patterns.

## Implementation Priority

1. **HIGH** - Fix column mapping with more variations ✅
2. **HIGH** - Improve column name normalization (strip, accents) ✅
3. **HIGH** - Enhanced date parsing with format cleanup ✅
4. **MEDIUM** - Better deduplication logic
5. **MEDIUM** - Relaxed name filtering (2 chars minimum)
6. **LOW** - Empty row handling optimization

## Expected Improvement
With these fixes, we should capture **600-630 out of 655 leads** (92-96% success rate).

The remaining 25-55 failures will be legitimate data quality issues (missing names, completely invalid data, etc.).

## Testing Command
```bash
cd /home/sebastiangarcia/planmaestro-ecosystem/packages/tools/api/python
python3 ingestion_to_staging_v3.py
# Check: "Inserted X leads (Y failed)" in output
# Target: X >= 600, Y <= 55
```

import re
from datetime import datetime
from typing import Dict, Tuple, Optional

class ParameterValidator:
    """Handles validation of API parameters"""
    
    def __init__(self):
        self.validation_rules = self._setup_validation_rules()

    def _setup_validation_rules(self) -> Dict:
        """Setup validation rules for common parameters"""
        return {
            # Airport/city codes
            'origin': {'type': 'iata_code', 'description': 'IATA airport/city code (e.g., NYC, JFK, LON)'},
            'originLocationCode': {'type': 'iata_code', 'description': 'IATA airport/city code (e.g., NYC, JFK, LON)'},
            'destination': {'type': 'iata_code', 'description': 'IATA airport/city code (e.g., NYC, JFK, LON)'},
            'destinationLocationCode': {'type': 'iata_code', 'description': 'IATA airport/city code (e.g., NYC, JFK, LON)'},
            'locationCode': {'type': 'iata_code', 'description': 'IATA airport/city code (e.g., NYC, JFK, LON)'},
            
            # Dates
            'departureDate': {'type': 'date', 'description': 'Date in YYYY-MM-DD format (e.g., 2024-12-25)'},
            'returnDate': {'type': 'date', 'description': 'Date in YYYY-MM-DD format (e.g., 2024-12-30)'},
            'checkInDate': {'type': 'date', 'description': 'Check-in date in YYYY-MM-DD format'},
            'checkOutDate': {'type': 'date', 'description': 'Check-out date in YYYY-MM-DD format'},
            
            # Numbers
            'adults': {'type': 'number', 'min': 1, 'max': 9, 'description': 'Number of adult passengers (1-9)'},
            'children': {'type': 'number', 'min': 0, 'max': 9, 'description': 'Number of children (0-9)'},
            'infants': {'type': 'number', 'min': 0, 'max': 9, 'description': 'Number of infants (0-9)'},
            'rooms': {'type': 'number', 'min': 1, 'max': 9, 'description': 'Number of rooms (1-9)'},
            'max': {'type': 'number', 'min': 1, 'max': 250, 'description': 'Maximum results (1-250)'},
            'radius': {'type': 'number', 'min': 1, 'max': 500, 'description': 'Search radius in km (1-500)'},
            
            # Currency codes
            'currencyCode': {'type': 'currency', 'description': 'Currency code (e.g., USD, EUR, GBP)'},
            
            # Travel class
            'travelClass': {'type': 'travel_class', 'description': 'Travel class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST'},
            'class': {'type': 'travel_class', 'description': 'Travel class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST'},
            
            # Boolean values
            'nonStop': {'type': 'boolean', 'description': 'Non-stop flights only: true or false'},
            'includedAirlineCodes': {'type': 'airline_codes', 'description': 'Airline codes separated by commas (e.g., BA,LH,AF)'},
            'excludedAirlineCodes': {'type': 'airline_codes', 'description': 'Airline codes separated by commas (e.g., FR,W6)'}
        }
    
    def validate_parameter(self, param_name: str, value: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a parameter value

        Returns:
            Tuple[bool, str, Optional[str]]: (is_valid, error_message, normalized_value)
        """
        if param_name not in self.validation_rules:
            return True, "", value
        
        rule = self.validation_rules[param_name]
        param_type = rule['type']

        # Map validation types to methods
        validators = {
            'iata_code': self._validate_iata_code,
            'date': self._validate_date,
            'number': lambda v: self._validate_number(v, rule.get('min'), rule.get('max')),
            'currency': self._validate_currency,
            'travel_class': self._validate_travel_class,
            'boolean': self._validate_boolean,
            'airline_codes': self._validate_airline_codes
        }

        validator = validators.get(param_type)
        if not validator:
            return True, "", value
        
        try:
            return validator(value)
        except Exception as e:
            return False, f"Validation error: {str(e)}", None
        
    def get_parameter_hint(self, param_name: str) -> str:
        """Get helpful hint for parameter"""
        return self.validation_rules.get(param_name, {}).get('description', "Enter value for this parameter")
    
    def _validate_iata_code(self, value: str) -> Tuple[bool, str, str]:
        """Validate IATA airport/city code"""
        normalized = value.upper().strip()
        if len(normalized) != 3 or not normalized.isalpha():
            return False, "IATA code must be exactly 3 letters (e.g., JFK, NYC, LON)", None
        return True, "", normalized
    
    def _validate_date(self, value: str) -> Tuple[bool, str, str]:
        """Validate date format and ensure it's not in the past"""
        try:
            date_obj = datetime.strptime(value, '%Y-%m-%d')
            if date_obj.date() < datetime.now().date():
                return False, "Date cannot be in the past", None
            return True, "", value
        except ValueError:
            return False, "Date must be in YYYY-MM-DD format (e.g., 2024-12-25)", None
        
    def _validate_number(self, value: str, min_val: int = None, max_val: int = None) -> Tuple[bool, str, str]:
        """Validate number within range"""
        try:
            num = int(value)
            if min_val is not None and num < min_val:
                return False, f"Value must be at least {min_val}", None
            if max_val is not None and num > max_val:
                return False, f"Value must at most {max_val}", None
            return True, "", str(num)
        except ValueError:
            return False, "Must be a valid number", None
    
    def _validate_currency(self, value: str) -> Tuple[bool, str, str]:
        """Validate currency code"""
        normalized = value.upper().strip()
        valid_currencies = {
            'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD', 
            'MXN', 'SGD', 'HKD', 'NOK', 'TRY', 'ZAR', 'BRL', 'INR', 'KRW', 'THB'
        }
        if normalized not in valid_currencies:
            common = ', '.join(list(valid_currencies)[:10])
            return False, f"Invalid currency code. Common codes: {common}, etc.", None
        return True, "", normalized
    
    def _validate_travel_class(self, value: str) -> Tuple[bool, str, str]:
        """Validate travel class"""
        normalized = value.upper().strip()
        valid_classes = {'ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST'}
        if normalized not in valid_classes:
            return False, f"Invalid travel class. Valid options: {', '.join(valid_classes)}", None
        return True, "", normalized
        

    def _validate_boolean(self, value: str) -> Tuple[bool, str, str]:
        """Validate boolean value"""
        normalized = value.lower().strip()
        true_values = {'true', 'yes', '1'}
        false_values = {'false', 'no', '0'}

        if normalized in true_values:
            return True, "", 'true'
        elif normalized in false_values:
            return True, "", 'false'
        else:
            return False, "Must be 'true', 'false', 'yes', 'no', '1', or '0'", None

    def _validate_airline_codes(self, value: str) -> Tuple[bool, str, str]:
        """Validate airline codes"""
        codes = [code.strip().upper() for code in value.split(',')]
        normalized_codes = []

        for code in codes:
            if len(code) != 2 or not code.isalpha():
                return False, f"Invalid airline code '{code}'. Must be 2 letters (e.g., BA, LH, AF)", None
            normalized_codes.append(code)
        
        return True, "", ','.join(normalized_codes)
    
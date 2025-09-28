"""
QR Code parsing service for Korean lottery tickets.

Parses QR codes from lottery tickets and extracts lottery number data.
This service only supports QR code recognition.
"""

import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs


def parse_lotto_qr_url(qr_url: str) -> Dict:
    """
    Parse lottery QR code URL and extract lottery data.

    Args:
        qr_url: QR code URL from lottery ticket

    Returns:
        Dictionary containing parsed lottery data:
        {
            'round': int,
            'games': [
                {
                    'numbers': [1, 2, 3, 4, 5, 6],
                    'raw_data': '050910333844'
                }, ...
            ],
            'raw_url': str,
            'valid': bool,
            'error': str or None
        }
    """
    try:
        # Parse URL
        parsed_url = urlparse(qr_url)

        # Extract 'v' parameter which contains the lottery data
        query_params = parse_qs(parsed_url.query)
        if 'v' not in query_params:
            return {
                'round': None,
                'games': [],
                'raw_url': qr_url,
                'valid': False,
                'error': 'No lottery data found in QR URL'
            }

        lottery_data = query_params['v'][0]

        # Parse the lottery data string
        # Format: {round}q{game1}q{game2}q{game3}...
        parts = lottery_data.split('q')

        if len(parts) < 2:
            return {
                'round': None,
                'games': [],
                'raw_url': qr_url,
                'valid': False,
                'error': 'Invalid lottery data format'
            }

        # First part is the round number
        try:
            round_number = int(parts[0])
        except ValueError:
            return {
                'round': None,
                'games': [],
                'raw_url': qr_url,
                'valid': False,
                'error': f'Invalid round number: {parts[0]}'
            }

        # Parse each game's numbers
        games = []
        for i, game_data in enumerate(parts[1:], 1):
            if not game_data:
                continue

            numbers = parse_game_numbers(game_data)
            if numbers:
                games.append({
                    'numbers': numbers,
                    'raw_data': game_data,
                    'game_index': i
                })

        return {
            'round': round_number,
            'games': games,
            'raw_url': qr_url,
            'valid': len(games) > 0,
            'error': None if len(games) > 0 else 'No valid games found'
        }

    except Exception as e:
        return {
            'round': None,
            'games': [],
            'raw_url': qr_url,
            'valid': False,
            'error': f'Parsing error: {str(e)}'
        }


def parse_game_numbers(game_data: str) -> Optional[List[int]]:
    """
    Parse lottery numbers from a single game's data string.

    Korean lottery numbers are 1-45, so we look for 2-digit numbers.

    Args:
        game_data: Raw game data string like '050910333844'

    Returns:
        List of 6 lottery numbers, or None if parsing fails
    """
    try:
        # Extract all 2-digit numbers from the string
        # Korean lottery numbers are between 01-45
        numbers = []

        # Try to extract 6 consecutive 2-digit numbers from the start
        if len(game_data) >= 12:
            for i in range(0, 12, 2):
                num_str = game_data[i:i+2]
                if num_str.isdigit():
                    num = int(num_str)
                    if 1 <= num <= 45:
                        numbers.append(num)

        # If we got exactly 6 valid numbers, return them
        if len(numbers) == 6:
            return sorted(numbers)

        # Alternative parsing: try to find 6 valid lottery numbers anywhere in the string
        numbers = []
        i = 0
        while i < len(game_data) - 1 and len(numbers) < 6:
            num_str = game_data[i:i+2]
            if num_str.isdigit():
                num = int(num_str)
                if 1 <= num <= 45 and num not in numbers:
                    numbers.append(num)
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        # Return sorted numbers if we found exactly 6
        if len(numbers) == 6:
            return sorted(numbers)

        return None

    except Exception:
        return None


def validate_lottery_numbers(numbers: List[int]) -> Tuple[bool, str]:
    """
    Validate lottery numbers.

    Args:
        numbers: List of lottery numbers

    Returns:
        (is_valid, error_message)
    """
    if not numbers:
        return False, "No numbers provided"

    if len(numbers) != 6:
        return False, f"Expected 6 numbers, got {len(numbers)}"

    if len(set(numbers)) != 6:
        return False, "Numbers must be unique"

    for num in numbers:
        if not isinstance(num, int) or num < 1 or num > 45:
            return False, f"Number {num} is not valid (must be 1-45)"

    return True, ""


def format_numbers_for_storage(numbers: List[int]) -> str:
    """
    Format lottery numbers for database storage.

    Args:
        numbers: List of lottery numbers

    Returns:
        Comma-separated string of numbers
    """
    return ",".join(str(num).zfill(2) for num in sorted(numbers))


def parse_qr_data_to_purchases(qr_data: Dict, user_id: int, confidence_score: float = 95.0) -> List[Dict]:
    """
    Convert parsed QR data to purchase records ready for database insertion.

    Args:
        qr_data: Parsed QR data from parse_lotto_qr_url()
        user_id: User ID for the purchases
        confidence_score: QR recognition confidence score

    Returns:
        List of purchase record dictionaries
    """
    if not qr_data['valid'] or not qr_data['games']:
        return []

    purchases = []
    round_number = qr_data['round']

    for game in qr_data['games']:
        numbers = game['numbers']

        # Validate numbers
        is_valid, error = validate_lottery_numbers(numbers)
        if not is_valid:
            continue

        purchase_record = {
            'user_id': user_id,
            'purchase_round': round_number,
            'numbers': format_numbers_for_storage(numbers),
            'purchase_method': '자동',  # Default to auto for QR codes
            'recognition_method': 'QR',
            'confidence_score': confidence_score,
            'source': 'local_collector',
            'result_checked': False
        }

        purchases.append(purchase_record)

    return purchases

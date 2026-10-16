# Extracted configuration loader; see vendor/README.md.

import datetime as dt

import json

from typing import Any

import yaml

from environment_classes.bank_accounts import BankAccount, Transaction

from environment_classes.calendar_client import Calendar

from environment_classes.cloud_drive import CloudDrive

from environment_classes.corporate_discounts import CorporateDiscounts

from environment_classes.flight_reviews import FlightReviews

from environment_classes.inbox import Inbox

from environment_classes.linkedin import LinkedInNetwork

from environment_classes.phone import Phone

from environment_classes.spam_email import SpamEmail

from environment_classes.travel_booking import (
    Flight,
    Flights,
    Hotel,
    Hotels,
    Reservation,
    Restaurant,
    Restaurants,
    User,
)

from environment_classes.venmo import VenmoAccount

from environment_classes.web import Web

from environment_classes.zelle import ZelleAccount

from utils.path_utils import resolve_path, resolve_yaml_path

CURRENT_TIME = dt.datetime(2024, 5, 15, 8, 2)

def load_bank_account(component: str) -> BankAccount:
    """Load bank account configuration from JSON file.
    
    Returns:
        BankAccount: Initialized bank account object with transactions
    """
    bank_account_path = resolve_path(f'universe_related_stuff/bank/{component}.json')
    with open(bank_account_path) as f:
        config = json.load(f)
    
    transactions = [Transaction(**t) for t in config['transactions']]
    scheduled_transactions = [Transaction(**t) for t in config['scheduled_transactions']]
    
    return BankAccount(
        iban=config['iban'],
        balance=config['balance'], 
        transactions=transactions,
        scheduled_transactions=scheduled_transactions
    )

def load_config(component: str) -> Any:
    """Load configuration for the specified workspace component.
    
    Args:
        component (str): One of 'inbox', 'cloud_drive', 'calendar', etc.
        
    Returns:
        tuple: Configuration dict and initialized component object
    """
    if component == 'linkedin':
        return LinkedInNetwork.from_yaml(str(resolve_yaml_path('universe_related_stuff/linkedin.yaml')), CURRENT_TIME)
    if 'spam' in component:
        return SpamEmail(spam_file=str(resolve_yaml_path(f'universe_related_stuff/spam/{component}.yaml')))
    if component == 'corporate_discounts':
        return CorporateDiscounts(yaml_path=resolve_yaml_path('universe_related_stuff/corporate_discounts.yaml'))
    if component == 'flight_reviews':
        return FlightReviews(yaml_path=str(resolve_yaml_path('universe_related_stuff/flight_reviews.yaml')))
    if 'zelle' in component:
        return ZelleAccount.from_yaml(str(resolve_yaml_path(f'universe_related_stuff/zelle/{component}.yaml')), CURRENT_TIME)
    if 'venmo' in component:
        return VenmoAccount.from_yaml(str(resolve_yaml_path(f'universe_related_stuff/venmo/{component}.yaml')), CURRENT_TIME)
    if 'phone' in component:
        phone = Phone(
            owner_name="",  # Temporary value
            owner_number="",  # Temporary value
            current_time=CURRENT_TIME
        )
        phone.load_from_yaml(str(resolve_yaml_path(f'universe_related_stuff/phone/{component}.yaml')))
        return phone
    if 'bank' in component:
        return load_bank_account(component)
    if 'calendar' in component:
        path = resolve_yaml_path(f'universe_related_stuff/calendar/{component}.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        return Calendar(account_email=config['account_email'],
                       current_day=config['current_day'],
                       initial_events=config.get('initial_events', []))
    if 'cloud_drive' in component:
        path = resolve_yaml_path(f'universe_related_stuff/cloud_drive/{component}.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        return CloudDrive(account_email=config['account_email'],
                         initial_files=config['initial_files'])
    if 'inbox' in component:
        path = resolve_yaml_path(f'universe_related_stuff/inbox/{component}.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
        return Inbox(account_email=config['account_email'],
                    initial_emails=config.get('initial_emails', []))
    if component in ['flights', 'hotels', 'restaurants', 'user', 'reservation']:
        path = resolve_yaml_path('universe_related_stuff/travel.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
    else:
        path = resolve_yaml_path(f'universe_related_stuff/{component}.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
    if component == 'flights':
        return Flights(
            flight_list=[Flight(**c) for c in config['flights']['flight_list']]
        )
    if component == 'hotels':
        return Hotels(
            hotel_list=[Hotel(**c) for c in config['hotels']['hotel_list']]
        )
    if 'restaurants' in component:
        return Restaurants(
            restaurant_list=[Restaurant(**c) for c in config['restaurants']['restaurant_list']]
        )
    if component == 'user':
        return User(
            **config['user']
        )
    if component == 'reservation':
        return Reservation(
            **config['reservation']
        )
    if component == 'web':
        return Web(
            **config['web']
        )
    raise ValueError(f"Unknown component: {component}")

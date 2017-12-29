import json

import logging
import requests
import dns.resolver
import dns.exception

from flask import Flask
from flask import request
from flask import jsonify

app = Flask(__name__)
app.logger.level = logging.INFO
app.logger.handlers.extend(logging.getLogger("gunicorn.error").handlers)

CONFIG_FILE = 'config.json'

def update_record(config, ip_address):
    """Updates the record for the specified domain"""

    session = requests.Session()
    session.headers.update({
        'Authorization': 'Bearer {}'.format(config['token']),
        'Accept': 'application/json'
    })

    # Get account id (we assume that this token only has access to one account)
    account_info = session.get('{}/v2/accounts'.format(config['url']))
    app.logger.debug('API response: %s', account_info.text)
    account_info.raise_for_status()

    account_id = account_info.json()['data'][0]['id']
    app.logger.debug('Account ID is: %s', account_id)

    # Get the record ID
    all_records = session.get(
        '{}/v2/{}/zones/{}/records'.format(config['url'], account_id, config['zone']))
    app.logger.debug('API response: %s', all_records.text)
    all_records.raise_for_status()

    record_id = None
    for record in all_records.json()['data']:
        if record['type'] == 'A' and record['name'] == config['record_name']:
            record_id = record['id']

    # Update record if exists, otherwise create record
    if record_id:
        app.logger.debug('Record exists. Record ID is: %s', record_id)
        response = session.patch(
            '{}/v2/{}/zones/{}/records/{}'.format(
                config['url'], account_id, config['zone'], record_id),
            json={'content': ip_address}
        )
    else:
        app.logger.debug('Record does not exist. Creating.')
        response = session.post(
            '{}/v2/{}/zones/{}/records'.format(config['url'], account_id, config['zone']),
            json={'name': config['record_name'], 'content': ip_address, 'type': 'A'}
        )
    app.logger.debug('API response: %s', response.text)
    response.raise_for_status()

def read_config():
    """Reads the config file"""
    with open(CONFIG_FILE, 'r') as open_file:
        config_file = open_file.read()
    return json.loads(config_file)

def check_if_needs_updating(domain, ip_address):
    """Check if we need to update the record"""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5
    try:
        response = resolver.query(domain, 'A')
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        app.logger.debug('Could not retrieve existing record')
        return True

    if response[0].address == ip_address:
        app.logger.debug('New IP: %s, existing record: %s. Not updating',
                         ip_address, response[0].address)
        return False
    else:
        app.logger.debug('New IP: %s, existing record: %s. Updating',
                         ip_address, response[0].address)
        return True

@app.errorhandler(Exception)
def handle_unexpected_error(_):
    """Handles errors that's not caught. Logs the exception and returns a generic error message"""
    app.logger.exception('An exception occured:')
    response = jsonify({'status': 'An error occured'})
    response.status_code = 500
    return response

@app.route("/updateDNS", methods=['GET'])
def update_dns():
    # As this is not supposed to be used that often, it is OK to read the config on every request
    config = read_config()

    # As we are behind a proxy, we need to get the client IP from the XFF header
    client_ip = request.headers['X-Forwarded-For']

    if check_if_needs_updating(config['domain'], client_ip):
        app.logger.info('Updating record. New IP: %s', client_ip)
        update_record(config, client_ip)
        response = {'status': 'Updated'}
    else:
        response = {'status': 'No update needed'}
        app.logger.info('No update needed')

    return jsonify(response)

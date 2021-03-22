#!/usr/bin/env python
#
# Dynamic DNS publisher for Frafos SBC
#
# The publisher monitors the SBC's registration cache and publishes A
# records into the DNS that can be used to map a particular user to a
# particular SIP server.
#
# Requires python-dns, python-redis, and python-netifaces packages.
#
# Written by Jan Janak <janakj@cs.columbia.edu>
#
from __future__ import print_function
import os
import sys
import redis
import netifaces
import dns.query
import dns.zone
import dns.update
from datetime import datetime
from time import sleep

DEBUG      = os.environ.get('DEBUG', None)
DNS_SERVER = os.environ['DNS_SERVER']
ZONE       = os.environ['ZONE']
SUBDOMAIN  = os.environ['SUBDOMAIN']
PTR_NAME   = os.environ.get('PTR_NAME', None)

ADDRESS    = os.environ.get('ADDRESS', None)
REDIS_URL  = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')
REDIS_KEYS = os.environ.get('REDIS_KEYS', "reg_cache_aor:*")
TTL        = int(os.environ.get('TTL', 5))

SRV_PREFIX = os.environ.get('SRV_PREFIX', '_sips._tcp')
SRV_PORT   = int(os.environ.get('SRV_PORT', 5061))


if ZONE[-1] != '.':
    ZONE = ZONE + '.'

r = redis.StrictRedis.from_url(REDIS_URL)

print('Enabling REDIS keyspace notifications')
r.config_set('notify-keyspace-events', 'AKE')

p = r.pubsub()
p.psubscribe('__keyspace@0__:reg_cache_aor:*')
p.get_message()


# Return the IPv4 address of the interface that has the default IPv4
# gateway pointed to. This IP address should be reachable from the
# rest of the world and we ca put it into DNS A recores.
def get_ip():
    try:
        ifname = netifaces.gateways()['default'][netifaces.AF_INET][1]
    except KeyError:
        # If there is no default gateway, use the IP address of the
        # first interface that is not the local interface.
        ifname = [n for n in netifaces.interfaces() if n != 'lo'][0]
    return netifaces.ifaddresses(ifname)[netifaces.AF_INET][0]['addr']


def sync():
    do_update = False
    records = dict()

    # Do a zone transfer first so that we can see what records are
    # currently stored in the zone.
    print('Downloading zone %s from server %s' % (ZONE, DNS_SERVER))
    zone = dns.zone.from_xfr(dns.query.xfr(DNS_SERVER, ZONE))
    for name, _, rdata in zone.iterate_rdatas('A'):
        if len(name) != 2: continue
        if str(name[1]) != SUBDOMAIN: continue
        records[str(name)] = str(rdata.address)

    update = dns.update.Update(ZONE)


    # Query REDIS so see what clients are currently registered in the
    # registration cache.
    print('Searching REDIS for %s records' % REDIS_KEYS)
    keys = r.keys(REDIS_KEYS)

    # If an IP address was provided in an environment variable, use
    # that address, otherwise obtain the IP address dynamically
    if ADDRESS is None:
        addr = get_ip()
    else:
        addr = ADDRESS

    # A dictionary of targets (names) to be added to the DNS-SDR PTR
    # record (if configured)
    ptr_targets = dict()

    print('Synchronizing DNS subdomain %s.%s with REDIS' % (SUBDOMAIN, ZONE))
    for key in keys:
        _, _, v = key.split(':')
        user = v.split('@')[0]

        name = '%s.%s' % (user, SUBDOMAIN)
        ptr_targets[name] = True

        if name in records:
            # If the records is in the zone already and has the same A
            # address, there is nothing to do. Otherwise we need to
            # update the record.
            if records[name] == addr:
                if DEBUG is not None:
                    print ('= %s [%s]' % (name, addr))
            else:
                if DEBUG is not None:
                    print('~ %s [%s] -> %s' % (name, records[name], addr))
                update.replace(name, TTL, 'A', addr)
                if SRV_PREFIX and SRV_PORT:
                    update.replace('%s.%s' % (SRV_PREFIX, name), TTL, 'SRV', '1 1 %d %s' % (SRV_PORT, name))
                do_update = True

            # "Touch" the record to indicate to the code run later
            # that the record should not be deleted.
            records[name] = True
        else:
            # If the name is not in the zone yet, add it.
            if DEBUG is not None:
                print('+ %s [%s]' % (name, addr))
            update.add(name, TTL, 'A', addr)
            if SRV_PREFIX and SRV_PORT:
                update.add('%s.%s' % (SRV_PREFIX, name), TTL, 'SRV', '1 1 %d %s' % (SRV_PORT, name))
            do_update = True

    # Delete any records from the zone that do not have matching
    # records in the registration cache.
    for name, keep in records.iteritems():
        if keep is True: continue
        if DEBUG is not None:
            print('- %s' % name)
        update.delete(name)
        if SRV_PREFIX and SRV_PORT:
            update.delete('%s.%s' % (SRV_PREFIX, name))
        do_update = True

    # If we're doing an update and PTR_NAME was configured, set the
    # PTR record with pointers to all numbers.
    if do_update and PTR_NAME is not None:
        print('Updating PTR record %s.%s' % (PTR_NAME, ZONE))
        update.delete(PTR_NAME)

        for target in ptr_targets.keys():
            if DEBUG is not None:
                print('  %s' % target)
            update.add(PTR_NAME, TTL, 'PTR', target)

    if do_update:
        print('Sending DNS UPDATE to zone %s on server %s' % (ZONE, DNS_SERVER))
        query = dns.query.tcp(update, DNS_SERVER)
        rc = query.rcode()
        if rc != dns.rcode.NOERROR:
            raise Exception('Error while updating zone %s on DNS server %s: %s'
                % (ZONE, DNS_SERVER, dns.rcode.to_text(rc)))
    else:
        print('Skipping DNS UPDATE, subdomain %s.%s is in sync already' % (SUBDOMAIN, ZONE))


while True:
    t1 = datetime.now()
    sync()

    # Block until the next message arrives and then drain the
    # notification queue.
    for _ in p.listen(): break
    while p.get_message(): pass

    dt = datetime.now() - t1
    if dt.seconds < 1:
        print("Throttling")
        sleep(1)

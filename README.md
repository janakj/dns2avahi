# DNS to Avahi Gateway

This project provides tools to publish and resolve ordinary DNS zones in multicast DNS via [Avahi](https://www.avahi.org). The [`avahi-publisher`](avahi-publisher.py) program downloads an entire DNS zone from the DNS server and publishes all its resource records to multicast DNS via the local Avahi daemon instance. The [`avahi-resolver`](avahi-resolver.py) program implements an extension module for the [Unbound](https://www.nlnetlabs.nl/projects/unbound/about/) DNS resolver that can be used to lookup ordinary DNS queries in multicast DNS via Avahi.

![Architecture diagram](https://github.com/janakj/dns2avahi/blob/main/dns2avahi.png?raw=true)

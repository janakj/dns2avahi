# DNS to Avahi Gateway

This project provides tools to publish and resolve ordinary DNS zones in multicast DNS via [Avahi](https://www.avahi.org). The [`avahi-publisher`](avahi-publisher.py) program downloads an entire DNS zone from the DNS server and publishes all its resource records to multicast DNS via the local Avahi daemon instance. The [`avahi-resolver`](avahi-resolver.py) program implements an extension module for the [Unbound](https://www.nlnetlabs.nl/projects/unbound/about/) DNS resolver that can be used to lookup ordinary DNS queries in multicast DNS via Avahi.

The tools were originally designed to implement peer-to-peer DNS service in an OLSR-based wireless mesh network. The following diagram illustrates the architecture.
![Architecture diagram](https://github.com/janakj/dns2avahi/blob/main/dns2avahi.png?raw=true)
Each node runs a local DNS server serving a DNS zone shared by all nodes in the network. The DNS server has only a subset of the zone's records. An Avahi publisher process makes those records available to the network via Avahi Daemon. Multicast DNS packets from Avahi Daemon are propagated across the OLSR network by `olsrd`'s multicast forwarding plugin (bmf).

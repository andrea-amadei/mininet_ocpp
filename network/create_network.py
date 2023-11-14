from ipmininet.cli import IPCLI
from ipmininet.ipnet import IPNet
from mininet.log import lg

from topologies import CustomTopology

lg.setLogLevel('info')

net = IPNet(topo=CustomTopology(), use_v4=False, use_v6=True)

try:
    net.start()

    for h in net.hosts:
        h.cmdPrint(f'/usr/bin/dbus-launch ./new_terminal.sh {h.name} &')

    IPCLI(net)

finally:
    net.stop()

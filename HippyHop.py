#!/bin/python

# A python script to record hops and other mesh information.

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
import google
from pubsub import pub
from meshtastic import mesh_pb2,  portnums_pb2, telemetry_pb2

connect = False
# Count to target from base
hh_hop_count = {}

# A dict of lists of where a node can tx to.
hh_hop = {}

# A dictionary of nodes.
hh_nodes = {}

class HhNode:
    def __init__(self):
        self.short = "?"
        self.long = "?"

DOT_HEAD = '''
# shape=circle,height=0.12,width=0.12,fontsize=5
digraph G  {
    graph [overlap=false];
    fontname="Helvetica,Arial,sans-serif";
    node [fontname="Helvetica,Arial,sans-serif"];
    edge [fontname="Helvetica,Arial,sans-serif"];
    layout=neato;
    center="";
    node[width=.25,height=.375,fontsize=9];
'''

DOT_TAIL = '''
}
'''

def fixUp(id):
    if id.startswith('!'):
        return "_" + id[1:]
    else:
        return "_" + id

def createDot():
    with open("mesh.dot", 'w') as file:
        nodes_shown = set()
        file.write(DOT_HEAD)
        for start, list in hh_hop.items():
            nodes_shown.add(start)
            for end in list:
                file.write(f"{fixUp(start)} -> {fixUp(end)};\n")
                nodes_shown.add(end)
        for node_id in nodes_shown:
            long = ""
            short = ""
            label = ""
            if node_id in hh_nodes:
                node = hh_nodes[node_id]
                long = node.long
                short = node.short
                label = f"{long}\\n{short}\\n({node_id})"
            else:
                long = node_id
                short = "?"
                label = node_id
            #short = hh_nodes[node].short
            file.write(f"{fixUp(node_id)} [label=\"{label}\"];\n")
        file.write(DOT_TAIL)


def onResponseTraceRoute(p):
    """on response for trace route"""
    routeDiscovery = mesh_pb2.RouteDiscovery()
    routeDiscovery.ParseFromString(p["decoded"]["payload"])
    asDict = google.protobuf.json_format.MessageToDict(routeDiscovery)

    print("> Route traced")
    me = interface._nodeNumToId(p["to"])
    to = interface._nodeNumToId(p["from"])
    first = me
    if "route" in asDict:
        route = asDict["route"]
        count = len(route)
        hh_hop_count[to] =  count
        print(f"{count} hop(s) to {to}")
        for nodeNum in route:
            node_id = interface._nodeNumToId(nodeNum)
            # TODO: Add time stamp?
            if first not in hh_hop:
                hh_hop[first] = {} 
            hh_hop[first][node_id] = 1
            print(f"> {first} --> {node_id}")
            first = node_id
        if first not in hh_hop:
            hh_hop[first] = {}
        hh_hop[first][to] = 1
        print(f"> {first} --> {to}")
    else:
        if me not in hh_hop:
            hh_hop[me] = {}
        hh_hop[me][to] = 1
        print(f"> {me} --> {to}")
    #createDot()
    interface._acknowledgment.receivedTraceRoute = True

#hh = HippyHop

def sendTraceRoute(interface, to_id):
    print(f"> Trace route {to_id}")
    #hh.interface = interface
    r = mesh_pb2.RouteDiscovery()
    interface.sendData(r, destinationId=to_id, portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True, onResponse=onResponseTraceRoute)
        
def onReceive( packet, interface): # called when a packet arrives
        if 'decoded' in packet:
            if 'portnum' in packet['decoded']:
                app = packet['decoded']['portnum']
                print(f"> {packet['decoded']['portnum']}")
                if app == "POSITION_APP":
                    lat = packet['decoded']['position']['latitude']
                    long = packet['decoded']['position']['longitude']
                    from_id = packet['fromId']
                    print(f"> {interface.nodes[from_id]['user']['longName']} ({interface.nodes[from_id]['user']['shortName']}) {from_id} {lat},{long} ")
                    if from_id not in hh_nodes:
                        hh_nodes[from_id] = HhNode()
                    hh_nodes[from_id].short = interface.nodes[from_id]['user']['shortName']
                    hh_nodes[from_id].long = interface.nodes[from_id]['user']['longName']
                    sendTraceRoute(interface, from_id)
                if app == "NODEINFO_APP":
                    print(f"{packet}")
            else:
                print("No decoded?")
                #print(f"{packet}")
        else:
            print("No decoded?")
            #print(f"{packet}")

        #print(f"RX")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    #interface.sendText("hello mesh")
    print("> Connected")
    global connect
    connect = True


pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")

# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()
#interface = meshtastic.tcp_interface.TCPInterface(hostname = "192.168.0.10", debugOut=None, noProto=False, connectNow=True, portNumber=4403)

quit = False
listed = False
todo = set()
while not quit:
    time.sleep(10)
    if not listed:
        if connect:
            time.sleep(10)
            print("> Getting stored nodes")
            listed = True
            for node in interface.nodes.values():
                user = node.get('user')
                if user:
                    if user['id'] not in hh_nodes:
                        hh_nodes[user['id']] = HhNode()
                    hh_nodes[user['id']].long = user['longName']
                    hh_nodes[user['id']].short = user['shortName']
                    todo.add(user['id'])
    if len(todo) > 0:
        print(f"> Working though stored nodes {len(todo)} to go")
        node_id = todo.pop()
        sendTraceRoute(interface, node_id)
        time.sleep(10)
    createDot()




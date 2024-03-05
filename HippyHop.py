#!/bin/python

# A python script to record hops and other mesh information.

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
import google
from pubsub import pub
from meshtastic import mesh_pb2,  portnums_pb2, telemetry_pb2

from hippyhopdata import *

connect = False
redraw = False
# Count to target from base
hh_hop_count = {}

# A dict of lists of where a node can tx to.
hh_hop = {}

# A dictionary of nodes.
hh_nodes = {}

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

def queueTrace(id):
    if id is None:
        print("> ID IS NONE")
    else:
        global needs_trace
        needs_trace.add(id)

def createDot():
    print("> Redrawing DOT file")
    with open("mesh.dot", 'w') as file:
        nodes_shown = set()
        file.write(DOT_HEAD)
        for start, list in hh_hop.items():
            nodes_shown.add(start)
            for end in list:
                file.write(f"{fixUp(start)} -> {fixUp(end)};\n")
                nodes_shown.add(end)
        # loop through to scale map
        lat_min = None
        lat_max = None
        long_min = None
        long_max = None
        
        for node_id in nodes_shown:
            if node_id in hh_nodes:
                node = hh_nodes[node_id]
                if node.pos is not None:
                    pos = node.pos
                    if lat_min is None:
                        lat_min = pos.lat
                    if lat_max is None:
                        lat_max = pos.lat
                    if long_min is None:
                        long_min = pos.long
                    if long_max is None:
                        long_max = pos.lat
                    if pos.lat < lat_min:
                        lat_min = pos.lat
                    if pos.lat > lat_max:
                        lat_max - pos.lat
                    if pos.long < long_min:
                        long_min = pos.long
                    if pos.long > long_max:
                        long_max = pos.long
                else:
                    print(">POS MISSING FROM NODE")
            else:
                print("> NODE MISSING FROM LIST?")
        long_diff = long_max - long_min
        lat_diff = lat_max - lat_min
        for node_id in nodes_shown:
            long = ""
            short = ""
            label = ""
            pos_text = ""
            if node_id in hh_nodes:
                node = hh_nodes[node_id]
                long = node.long
                short = node.short
                label = f"{long}\\n{short}\\n({node_id})"
                if not node.pos is None:
                    #pos="1,1!"
                    pos_text = f",pos=\"{node.pos.long * 30},{node.pos.lat * 30}!\""
            else:
                long = node_id
                short = "?"
                label = node_id
            #short = hh_nodes[node].short
            file.write(f"{fixUp(node_id)} [label=\"{label}\"{pos_text}];\n")
        file.write(DOT_TAIL)

def recordTraceRout(packet):

    global redraw
    print("> Route traced")
    print(f"packet")
    me = interface._nodeNumToId(packet["to"])
    to = interface._nodeNumToId(packet["from"])
    first = me
    if 'decoded' in packet:
        decoded = packet['decoded']
        if 'rxTime' in packet:
            rx_time = packet['rxTime']
        if "traceroute" in decoded:
            if "route" in decoded['traceroute']:
                route = decoded['traceroute']["route"]
                count = len(route)
                hh_hop_count[to] =  count
                print(f"{count} hop(s) to {to}")
                for nodeNum in route:
                    node_id = interface._nodeNumToId(nodeNum)
                    # TODO: Add time stamp?
                    if first not in hh_hop:
                        hh_hop[first] = {} 
                    hh_hop[first][node_id] = rx_time
                    print(f"> {first} --> {node_id}")
                    first = node_id
                if first not in hh_hop:
                    hh_hop[first] = {}
                hh_hop[first][to] = 1
                print(f"> {first} --> {to}")
            else:
                if me not in hh_hop:
                    hh_hop[me] = {}
                hh_hop[me][to] = rx_time
                print(f"> {me} --> {to}")
            redraw = True
        else:
            print("> NO TRACEROUTE ?")
    else:
        print("> NO DECODED?")

def sendTraceRoute(interface, to_id):
    print(f"> Trace route {to_id}")
    #hh.interface = interface
    r = mesh_pb2.RouteDiscovery()
    interface.sendData(
        r,
        destinationId=to_id,
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True)
    time.sleep(1)
        
def onReceive( packet, interface): # called when a packet arrives
        rx_time = 0
        if 'rxTime' in packet:
            rx_time = packet['rxTime']
        else:
            print("> NO rxTime?")
        if 'decoded' in packet:
            decoded = packet['decoded']
            if 'portnum' in decoded:
                app = decoded['portnum']
                print(f"> {decoded['portnum']}")
                #if (app == "POSITION_APP") or (app == "NODEINFO_APP"):
                if 'fromId' in packet:
                    from_id = packet['fromId']
                    if 'user' in decoded:
                        if from_id not in hh_nodes:
                            print(f"{packet}")
                            hh_nodes[from_id] = HhNode(
                                decoded['user']['shortName'],
                                decoded['user']['longName'],
                                rx_time)
                        if 'position' in decoded:
                            pos = HhPos(
                                decoded['position']['longitude'],
                                decoded['position']['latitude'],
                                rx_time)
                            hh_nodes[from_id].pos = pos
                        #queueTrace(from_id)
                        hh_nodes[from_id].Show()
                    else:
                        print(f"{packet}")
                if app == "TRACEROUTE_APP":
                    #print(f"{packet}")
                    recordTraceRout(packet)
                else:
                    if 'fromId' in packet:
                        from_id = packet['fromId']
                        queueTrace(from_id)
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

quit = False
needs_trace = set()

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")

# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()
#interface = meshtastic.tcp_interface.TCPInterface(hostname = "192.168.0.10", debugOut=None, noProto=False, connectNow=True, portNumber=4403)

time.sleep(10)
while not connect:
    print("> Waiting for connection.")
    time.sleep(10)

print("> Getting stored nodes")

for node in interface.nodes.values():
    user = node.get('user')
    if user:
        if user['id'] not in hh_nodes:
            hh_nodes[user['id']] = HhNode(user['shortName'], user['longName'], 0)
            #print(f"{node}")
        queueTrace(user['id'])
        pos = node.get('position')
        if pos:
            long = pos.get("longitude")
            lat = pos.get("latitude")
            if (not long is None) and (not lat is None): 
                hh_nodes[user['id']].pos = HhPos(long,lat,node.get("lastHeard"))
            else:
                print("> LONG OR LAT is None")

while not quit:            
    if len(needs_trace) > 0:
        print(f"> {len(needs_trace)} traces left.")
        node_id = needs_trace.pop()
        sendTraceRoute(interface, node_id)
    print(f"> redraw = {redraw}")
    if redraw:
        redraw = False
        createDot()
    else:
        if len(needs_trace) == 0:
            time.sleep(10)




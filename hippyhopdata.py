

class HhNode:
    def __init__(self, short, long, stamp, pos = None):
        self.short = short
        self.long = long
        self.stamp = stamp
        self.pos = pos
    def Show(self):
        print(f"> {self.long} ({self.short})")
        if self.pos:
            print(f"> {self.pos.long},{self.pos.lat}")

class HhPos:
    def __init__(self, long, lat, stamp):
        self.long = long
        self.lat = lat
        self.stamp = stamp


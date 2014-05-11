import bacon

class Rect(object):
    def __init__(self, x1, y1, x2, y2):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    @property
    def center_x(self):
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self):
        return (self.y1 + self.y2) / 2

    def contains(self, x, y):
        return (x >= self.x1 and
                x <= self.x2 and
                y >= self.y1 and
                y <= self.y2)

    def draw(self):
        bacon.draw_rect(self.x1, self.y1, self.x2, self.y2)

    def fill(self):
        bacon.fill_rect(self.x1, self.y1, self.x2, self.y2)

def clamp(value, lower, upper):
    return max(lower, min(value, upper))
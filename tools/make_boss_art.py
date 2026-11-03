"""Generate the animated boss portraits in ``rpg/ui/assets/animations/boss_*.json``.

Each boss is a small scene of shapes (circles, boxes, capsules, polygons, gears) described as signed distance
functions. Every cell is shaded from a top-left light into the density ramp ``.:-=+*#%@`` and a material's
color ramp, so the art matches ASCII Motion exports like the campfire. Emissive shapes (eyes, cracks, cores)
glow and cast a faint halo, and particles (dust, embers, smoke, souls) drift over the top.

    python tools/make_boss_art.py            # all bosses
    python tools/make_boss_art.py titan      # just one

Tweak a scene function below and re-run. The output uses the same asset format as
``tools/import_ascii_motion.py``, played by ``rpg.ui.widgets.AsciiAnimation``.
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ASSET_DIR = Path(__file__).resolve().parent.parent / "rpg" / "ui" / "assets" / "animations"
W, H = 48, 21  # cells; shapes use x in [0, W) and y in [0, 2H) so circles look round
FRAMES, FPS = 24, 8
LIGHT = (-0.55, -0.83)  # direction *towards* the light: up and to the left
SOLID_RAMP = "░░▒▒▓▓██"
GLOW_RAMP = "▒▓█"


# ------------------------------------------------------------------ SDF primitives
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ellipse(cx, cy, rx, ry):
    k = min(rx, ry)
    return lambda x, y: (math.hypot((x - cx) / rx, (y - cy) / ry) - 1.0) * k


def box(cx, cy, hw, hh, r=0.0):
    def sdf(x, y):
        qx, qy = abs(x - cx) - (hw - r), abs(y - cy) - (hh - r)
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r
    return sdf


def capsule(ax, ay, bx, by, r1, r2=None):
    r2 = r1 if r2 is None else r2
    ex, ey = bx - ax, by - ay
    length2 = ex * ex + ey * ey or 1e-9

    def sdf(x, y):
        t = clamp(((x - ax) * ex + (y - ay) * ey) / length2, 0.0, 1.0)
        return math.hypot(x - ax - ex * t, y - ay - ey * t) - (r1 + (r2 - r1) * t)
    return sdf


def polygon(points):
    pts = list(points)

    def sdf(px, py):
        d = (px - pts[0][0]) ** 2 + (py - pts[0][1]) ** 2
        s, j = 1.0, len(pts) - 1
        for i in range(len(pts)):
            ex, ey = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
            wx, wy = px - pts[i][0], py - pts[i][1]
            t = clamp((wx * ex + wy * ey) / (ex * ex + ey * ey or 1e-9), 0.0, 1.0)
            bx, by = wx - ex * t, wy - ey * t
            d = min(d, bx * bx + by * by)
            c1, c2, c3 = py >= pts[i][1], py < pts[j][1], ex * wy > ey * wx
            if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
                s = -s
            j = i
        return s * math.sqrt(d)
    return sdf


def gear(cx, cy, radius, teeth, rotation, tooth=1.0):
    def sdf(x, y):
        angle = math.atan2(y - cy, x - cx)
        bump = clamp(3 * math.cos(teeth * angle + rotation), -1, 1) * tooth * 0.5
        return math.hypot(x - cx, y - cy) - (radius + bump)
    return sdf


def union(*sdfs):
    return lambda x, y: min(f(x, y) for f in sdfs)


def smooth_union(k, *sdfs):
    def sdf(x, y):
        d = sdfs[0](x, y)
        for f in sdfs[1:]:
            e = f(x, y)
            h = clamp(0.5 + 0.5 * (e - d) / k, 0, 1)
            d = e * (1 - h) + d * h - k * h * (1 - h)
        return d
    return sdf


def subtract(a, b):
    return lambda x, y: max(a(x, y), -b(x, y))


def offset(sdf, dx, dy=0.0):
    return lambda x, y: sdf(x - dx, y - dy)


# ------------------------------------------------------------------ scene
@dataclass(frozen=True)
class Material:
    colors: tuple[str, ...]  # dark -> light
    ramp: str = SOLID_RAMP
    depth: float = 4.0  # how far inside an edge counts as "deep" (rounder look with bigger values)
    emissive: bool = False
    halo: float = 0.0  # glow radius outside the shape
    intensity: float = 1.0  # emissive brightness 0..1 (animate it for pulses)

    def at(self, intensity: float) -> "Material":
        return Material(self.colors, self.ramp, self.depth, self.emissive, self.halo, intensity)


@dataclass
class Shape:
    sdf: Callable[[float, float], float]
    material: Material


@dataclass
class Particle:
    x: float
    y: float
    char: str
    color: str
    behind: bool = False


@dataclass
class Scene:
    shapes: list[Shape] = field(default_factory=list)  # painter's order: later shapes are on top
    particles: list[Particle] = field(default_factory=list)
    shift: int = 0  # whole-frame horizontal shake

    def add(self, sdf, material):
        self.shapes.append(Shape(sdf, material))

    def dot(self, x, y, char, color, behind=False):
        self.particles.append(Particle(x, y, char, color, behind))


def render(scene: Scene) -> tuple[list[str], list[list[str | None]]]:
    chars = [[" "] * W for _ in range(H)]
    colors: list[list[str | None]] = [[None] * W for _ in range(H)]
    lx, ly = LIGHT
    for p in scene.particles:
        if p.behind:
            _plot(chars, colors, p)
    for row in range(H):
        for col in range(W):
            x, y = col + 0.5 - scene.shift, (row + 0.5) * 2
            hit, hit_d = None, 0.0
            for shape in reversed(scene.shapes):
                d = shape.sdf(x, y)
                if d < 0:
                    hit, hit_d = shape, d
                    break
            if hit is None:
                _halo(scene, x, y, chars, colors, row, col)
                continue
            m = hit.material
            if m.emissive:
                level = clamp(0.45 + 0.55 * m.intensity * min(1.0, -hit_d / 1.2 + 0.5), 0, 1)
                chars[row][col] = m.ramp[min(len(m.ramp) - 1, int(level * len(m.ramp)))]
                colors[row][col] = m.colors[min(len(m.colors) - 1, int(level * len(m.colors)))]
                continue
            e = 0.35
            nx = hit.sdf(x + e, y) - hit.sdf(x - e, y)
            ny = hit.sdf(x, y + e) - hit.sdf(x, y - e)
            n = math.hypot(nx, ny) or 1.0
            facing = max(0.0, (nx * lx + ny * ly) / n)
            depth = min(1.0, -hit_d / m.depth)
            shade = 0.38 + 0.3 * depth + 0.45 * facing * (1 - 0.4 * depth)
            if -hit_d < 0.9:
                shade *= 0.6  # dark rim keeps silhouettes readable
            shade = clamp(shade, 0.0, 0.999)
            chars[row][col] = m.ramp[int(shade * len(m.ramp))]
            colors[row][col] = m.colors[int(shade * len(m.colors))]
    for p in scene.particles:
        if not p.behind:
            _plot(chars, colors, p)
    return ["".join(r) for r in chars], colors


def _halo(scene, x, y, chars, colors, row, col):
    best = None
    for shape in scene.shapes:
        m = shape.material
        if m.emissive and m.halo and m.intensity > 0.2:
            d = shape.sdf(x, y)
            if 0 <= d < m.halo * m.intensity and (best is None or d < best[0]):
                best = (d, m)
    if best:
        d, m = best
        chars[row][col] = ":" if d < m.halo * 0.4 else "."
        colors[row][col] = m.colors[0]


def _plot(chars, colors, p: Particle):
    col, row = int(p.x), int(p.y / 2)
    if 0 <= col < W and 0 <= row < H:
        chars[row][col] = p.char
        colors[row][col] = p.color


# ------------------------------------------------------------------ shared effects
def falling(scene, t, seed, count, color, chars=".,'", top=0.0, bottom=2 * H, speed=1.0, behind=True):
    rng = random.Random(seed)
    for _ in range(count):
        x0, y0, v = rng.uniform(0, W), rng.uniform(top, bottom), rng.uniform(0.7, 1.3)
        y = top + (y0 - top + t * (bottom - top) * speed * v) % (bottom - top)
        scene.dot(x0 + math.sin(t * 6.28 + y0) * 0.6, y, rng.choice(chars), color, behind)


def rising(scene, t, seed, count, colors, chars="'.`", x_range=(0, W), bottom=2 * H, top=0.0, sway=1.5,
           behind=False):
    rng = random.Random(seed)
    for _ in range(count):
        x0, y0, v = rng.uniform(*x_range), rng.uniform(top, bottom), rng.choice((1, 1, 2))
        y = bottom - ((bottom - y0) + t * (bottom - top) * v) % (bottom - top)
        x = x0 + math.sin(t * 6.28 * v + y0) * sway
        scene.dot(x, y, rng.choice(chars), rng.choice(colors), behind)


def pulse(t, cycles=1.0, low=0.4, high=1.0):
    return low + (high - low) * (0.5 + 0.5 * math.sin(t * 2 * math.pi * cycles))


# ------------------------------------------------------------------ bosses
STONE = Material(("#2B2622", "#4A423A", "#6F655A", "#9A8F80", "#C9BFAE"))
DARK_STONE = Material(("#1E1A17", "#332D28", "#4A423A", "#6F655A"))
RUBBLE = Material(("#1E1A17", "#2B2622", "#4A423A"), ramp="░▒▓")
GLOW = ("#7A1E0E", "#C2410C", "#F97316", "#FFD08A")  # titan default (fire); recolored per titan element


def titan(t):
    s = Scene()
    stomp = 0.80 <= t < 0.92
    s.shift = (1 if int(t * FRAMES) % 2 else -1) if stomp else 0
    breath = math.sin(t * 2 * math.pi) * 0.5
    glow = Material(GLOW, GLOW_RAMP, emissive=True, halo=1.6, intensity=pulse(t, 1, 0.55, 1.0))
    eyes = Material(GLOW, "▓█", emissive=True, halo=2.4, intensity=pulse(t, 2, 0.7, 1.0))
    lift = -2.5 * math.sin(clamp((t - 0.55) / 0.25, 0, 1) * math.pi / 2) if t < 0.8 else 0.0  # fists rise, then slam
    s.add(box(24, 41.5, 30, 1.4), RUBBLE)
    s.add(box(18.5, 35.5, 3.6, 5.2, 1.2), DARK_STONE)
    s.add(box(29.5, 35.5, 3.6, 5.2, 1.2), DARK_STONE)
    s.add(ellipse(24, 24, 11.5, 10 + breath), STONE)
    s.add(circle(12.5, 17.5, 5.2), STONE)
    s.add(circle(35.5, 17.5, 5.2), STONE)
    s.add(capsule(11, 20, 7, 30 + lift, 3.6, 3.1), STONE)
    s.add(capsule(37, 20, 41, 30 + lift, 3.6, 3.1), STONE)
    s.add(circle(6.5, 33.5 + lift, 4.3), DARK_STONE)
    s.add(circle(41.5, 33.5 + lift, 4.3), DARK_STONE)
    s.add(union(capsule(20, 17, 23, 23, 0.5), capsule(23, 23, 20.5, 30, 0.45), capsule(28.5, 19, 26, 26, 0.45),
                capsule(26, 26, 28, 31, 0.4), capsule(11, 15, 14, 19, 0.4), capsule(37, 15, 34.5, 19.5, 0.4)), glow)
    s.add(circle(24, 9.5, 4.6), STONE)
    s.add(box(24, 7.2, 5.2, 1.1, 0.5), DARK_STONE)
    s.add(box(24, 13.6, 3.2, 1.5, 0.6), DARK_STONE)
    s.add(union(circle(21.9, 9.8, 0.95), circle(26.1, 9.8, 0.95)), eyes)
    falling(s, t, 1, 14, "#6F655A", top=0, bottom=40)
    if stomp or t < 0.06:
        rng = random.Random(int(t * 100))
        for _ in range(10):
            s.dot(rng.uniform(2, 46), rng.uniform(36, 40), rng.choice(".,:"), "#9A8F80")
    return s


SCALE = Material(("#1F0E0B", "#4A1A12", "#7A2A1A", "#A8452A", "#D9774F"), depth=5)
BONE = Material(("#5A4E3E", "#9A8F80", "#D8CFC0", "#F2ECE0"))
WING = Material(("#2A1410", "#3E1E16", "#5A2A1E", "#7A3A28"), ramp="░▒▒▓", depth=6)
FIRE = ("#7A1E0E", "#E8604F", "#FF8C42", "#FFD08A")


def elder_dragon(t):
    s = Scene()
    s.shift = 7  # leave room on the left for the fire
    dx = s.shift
    breathing = 0.55 <= t < 0.9
    jaw = 3.5 * math.sin(clamp((t - 0.45) / 0.15, 0, 1) * math.pi / 2) if t < 0.9 else 3.5 * (1 - (t - 0.9) / 0.1)
    s.add(polygon([(30, 30), (47, 2), (44, 15), (48, 17), (42, 24), (47, 28), (38, 36)]), WING)
    s.add(capsule(36, 44, 29, 22, 7.5, 5.2), SCALE)
    for i in range(5):  # neck spines
        y = 24 + i * 4
        s.add(polygon([(36.5 + i * 1.5, y - 1.5), (41 + i * 1.5, y), (36.5 + i * 1.5, y + 1.5)]), BONE)
    s.add(capsule(30, 11, 37, 4, 2.0, 1.0), BONE)
    s.add(capsule(37, 4, 41, 1, 1.0, 0.3), BONE)
    s.add(capsule(27, 10, 30, 3, 1.4, 0.3), BONE)
    s.add(ellipse(27, 16, 8.5, 6.2), SCALE)
    s.add(polygon([(9, 15.5), (19, 11.5), (29, 12.5), (31, 19), (19, 21), (9.5, 19.5)]), SCALE)
    mouth = Material(FIRE[:3], GLOW_RAMP, emissive=True, halo=1.5 if breathing else 0.0,
                     intensity=0.65 if breathing else 0.3)
    s.add(polygon([(10, 19.5), (27, 19.5), (27, 21 + jaw), (12, 20.5 + jaw * 0.8)]), mouth)
    s.add(polygon([(11, 20.5 + jaw * 0.9), (26, 21.5 + jaw), (31, 21.5), (29, 25.5 + jaw * 0.4), (14, 24 + jaw),
                   (10, 22.5 + jaw * 0.9)]), SCALE)
    for i in range(5):  # upper and lower teeth
        x = 11.5 + i * 3
        s.add(polygon([(x, 19.6), (x + 1.2, 19.6), (x + 0.6, 21.2)]), BONE)
        s.add(polygon([(x + 1, 21.2 + jaw * 0.9), (x + 2.2, 21.2 + jaw * 0.9), (x + 1.6, 19.8 + jaw * 0.9)]), BONE)
    s.add(capsule(20, 12.2, 29, 11.2, 1.3), Material(("#2B120D", "#4A1A12", "#7A2A1A")))
    s.add(ellipse(24.5, 14.6, 1.5, 0.65), Material(("#B8860B", "#F2C46D", "#FFF1B8"), "▓█", emissive=True,
                                                    halo=1.8, intensity=pulse(t, 1.5, 0.6, 1.0)))
    s.add(circle(11.5, 15.4, 0.6), Material(("#0A0505", "#1F0E0B")))
    if breathing:
        rng = random.Random(int(t * 1000))
        reach = clamp((t - 0.55) / 0.12, 0, 1)
        for _ in range(110):
            d = rng.uniform(0, 16 * reach)
            spread = 1 + d * 0.45
            x, y = 9.5 + dx - d, 21.5 + rng.uniform(-spread, spread)
            heat = 1 - d / 17
            s.dot(x, y, rng.choice("#*+:" if heat > 0.5 else "+:."), FIRE[min(3, int(heat * 4))])
    rising(s, t, 7, 6, ("#6F655A", "#4A423A"), "~.'", x_range=(9 + dx, 13 + dx), bottom=14, top=0, sway=1.2)
    rising(s, t, 9, 10, ("#FF8C42", "#E8604F"), ".'", bottom=42, top=0, sway=2, behind=True)
    return s


FLESH = Material(("#2A1A12", "#5A3A26", "#8A5A3A", "#B98A5E", "#D9B48A"), depth=5)
EARTH = Material(("#14100C", "#2B2017", "#45362A", "#5E4A38"), ramp="░▒▓▓")
VOID = Material(("#050303", "#120808"), ramp=" .")


def earth_eater_worm(t):
    s = Scene()
    phase = t * 2 * math.pi
    segments = 11
    top_x = 24 + 5 * math.sin(phase)
    points = []
    for i in range(segments):
        u = i / (segments - 1)
        x = 24 + 5 * math.sin(phase + 2.2 * u - 2.2) * (1 - u) + (top_x - 24) * u
        y = 41 - u * 26
        points.append((x, y, 6.6 - 0.5 * u))
    s.add(box(24, 41, 30, 2.2), EARTH)
    for x, y, r in points:
        s.add(circle(x, y, r), FLESH)
    s.add(polygon([(8, 44), (13, 37), (17, 40), (31, 40), (35, 37), (40, 44)]), EARTH)
    hx, hy = top_x, 12.5
    s.add(circle(hx, hy, 9.2), FLESH)
    s.add(circle(hx, hy, 6.4), Material(("#3A1010", "#5A1A1A", "#7A2626")))
    s.add(circle(hx, hy, 4.6), VOID)
    s.add(circle(hx, hy, 1.4), Material(("#5A0A0A", "#B8323A", "#E8604F"), "▓█", emissive=True, halo=1.2,
                                        intensity=pulse(t, 2, 0.4, 0.9)))
    rotation = t * 2 * math.pi / 3
    for ring, (radius, length, count) in enumerate(((6.6, 3.0, 9), (4.6, 2.2, 7))):
        for k in range(count):
            a = rotation * (1 if ring == 0 else -1.5) + k * 2 * math.pi / count
            base = (hx + math.cos(a) * radius, hy + math.sin(a) * radius)
            tip = (hx + math.cos(a) * (radius - length), hy + math.sin(a) * (radius - length))
            side = (-math.sin(a) * 1.1, math.cos(a) * 1.1)
            s.add(polygon([(base[0] + side[0], base[1] + side[1]), (base[0] - side[0], base[1] - side[1]), tip]), BONE)
    rng = random.Random(3)
    for _ in range(12):  # flung rocks
        x0, v, life = rng.uniform(6, 42), rng.uniform(0.6, 1.4), (t * 1.5 + rng.random()) % 1
        x = x0 + (x0 - 24) * life * 0.4
        y = 38 - 30 * v * life + 34 * life * life
        s.dot(x, y, rng.choice("o.,*"), rng.choice(("#5E4A38", "#8A6A4E", "#45362A")))
    return s


FUR = Material(("#1A1512", "#332A23", "#4F4236", "#6E5F50", "#8F7F6E"), depth=2.5)
GOLD = Material(("#5A4210", "#9C7414", "#D9A62E", "#F2C46D", "#FFF1B8"), depth=2)
RED_EYE = ("#5A0A0A", "#B8323A", "#FF5C5C")


def rat_king(t):
    s = Scene()
    rng = random.Random(11)
    rows = [(39, 7, 6.2), (33.5, 6, 6.4), (28, 5, 6.6), (22.5, 3, 7.0)]
    for y, count, spacing in rows:
        for i in range(count):
            x = 24 + (i - (count - 1) / 2) * spacing
            facing = rng.choice((-1, 1))
            wiggle = math.sin(t * 2 * math.pi * 2 + x) * 0.3
            seed = rng.random()
            s.add(capsule(x - facing * 3, y + 1, x - facing * 6, y + 3.5 + wiggle, 0.35), Material(("#5A3A3A", "#8F5F5F")))
            s.add(ellipse(x + wiggle, y, 3.4, 2.4), FUR)
            s.add(circle(x + facing * 2.8 + wiggle, y - 1, 1.6), FUR)
            s.add(circle(x + facing * 2.2 + wiggle, y - 2.6, 0.7), Material(("#4F3030", "#8F5F5F")))
            blink = (t * 3 + seed) % 1 < 0.12
            if not blink:
                s.add(circle(x + facing * 3.0 + wiggle, y - 1.2, 0.75), Material(RED_EYE, "█", emissive=True,
                                                                                 halo=0.9, intensity=0.8))
    for k in range(4):  # knotted tails beneath the mound
        pts = [(8 + i * 4, 42.5 + math.sin(i * 1.3 + k * 1.7 + t * 6.28) * 1.1) for i in range(9)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            s.add(capsule(ax, ay, bx, by, 0.4), Material(("#5A3A3A", "#8F5F5F", "#B98080")))
    s.add(ellipse(24, 16, 5.6, 4.6), FUR)
    s.add(circle(24, 10.2, 3.4), FUR)
    s.add(circle(20.6, 7.6, 1.2), Material(("#4F3030", "#8F5F5F")))
    s.add(circle(27.4, 7.6, 1.2), Material(("#4F3030", "#8F5F5F")))
    s.add(ellipse(24, 12.4, 1.4, 1.6), Material(("#4F3030", "#6E4A4A")))
    king_eyes = Material(RED_EYE, "▓█", emissive=True, halo=1.6, intensity=pulse(t, 1, 0.7, 1.0))
    s.add(union(circle(22.6, 9.4, 0.6), circle(25.4, 9.4, 0.6)), king_eyes)
    crown = [(19.5, 7), (19.5, 3.6), (21, 5.2), (22.4, 1.6), (24, 4.6), (25.6, 1.6), (27, 5.2), (28.5, 3.6), (28.5, 7)]
    s.add(polygon(crown), GOLD)
    for gx, gy, color in ((22.4, 5.4, "#E8604F"), (24, 6, "#7FD1C8"), (25.6, 5.4, "#E8604F")):
        s.add(circle(gx, gy, 0.5), Material((color,), "█", emissive=True))
    glint = 19 + (t * 3 % 1) * 10
    s.dot(glint, 3.5, "*", "#FFFFFF")
    for k in range(3):  # rats scurrying along the floor
        x = (t * 60 + k * 17) % 56 - 4
        s.dot(x, 41, "~", "#8F7F6E")
        s.dot(x + 1, 41, ">", "#6E5F50")
    return s


STEEL = Material(("#1F242B", "#3A434F", "#5C6878", "#8C99AA", "#C9D3DE"), depth=3)
ARCH = Material(("#1E1A17", "#2E2924", "#403830", "#544A40"), ramp="░▒▓", depth=6)
CLOTH = Material(("#3A0E0E", "#6A1A1A", "#9A2A26", "#C24A3A"), depth=3)
WOOD = Material(("#2B1D12", "#4A3320", "#6E4E30"))
VISOR = ("#1E4A6A", "#4F9AD0", "#9EDCF2", "#E3F6FF")


def valorian_warden(t):
    s = Scene()
    s.add(box(24, 22, 23, 22), ARCH)
    s.add(union(box(24, 28, 13, 16), circle(24, 14.5, 13)), VOID)
    for i in range(7):  # portcullis bars
        s.add(box(12 + i * 4, 28, 0.6, 16), Material(("#14171B", "#2A3038", "#3A434F")))
    for i in range(6):
        s.add(box(24, 16 + i * 5, 13, 0.5), Material(("#14171B", "#2A3038")))
    for i in range(9):  # runes around the arch light up one after another
        a = math.pi + i * math.pi / 8
        x, y = 24 + math.cos(a) * 15.2, 14.5 + math.sin(a) * 13.2
        lit = abs(((t * 9) % 9) - i) < 1.2
        s.add(box(x, y, 0.6, 0.9), Material(VISOR, "▓█", emissive=True, halo=1.2 if lit else 0,
                                            intensity=1.0 if lit else 0.25))
    s.add(polygon([(32, 4), (39, 6), (36.5, 11), (32, 9)]), STEEL)
    s.add(capsule(33, 2, 33, 42, 0.55), WOOD)
    s.add(box(18.5, 34, 2.4, 6, 0.8), STEEL)
    s.add(box(29.5, 34, 2.4, 6, 0.8), STEEL)
    sway = math.sin(t * 2 * math.pi) * 0.4
    s.add(box(24, 22, 5.6, 7, 1.2), STEEL)
    s.add(polygon([(21.6, 16), (26.4, 16), (26.6 + sway, 33), (21.4 + sway, 33)]), CLOTH)
    s.add(circle(17.6, 16.5, 3.4), STEEL)
    s.add(circle(30.4, 16.5, 3.4), STEEL)
    s.add(box(12.5, 26, 5.2, 10, 2), Material(("#1A1E24", "#2E3540", "#46505E", "#6A7686"), depth=4))
    s.add(polygon([(12.5, 20), (14.5, 25), (12.5, 31), (10.5, 25)]), GOLD)
    s.add(capsule(31, 18, 33, 24, 1.3), STEEL)
    s.add(capsule(25, 2, 28, -1, 0.9, 0.4), CLOTH)
    s.add(box(24, 8.5, 4.1, 4.6, 1.4), STEEL)
    s.add(box(24, 8.3, 2.9, 0.42), Material(VISOR, "▓█", emissive=True, halo=2.0, intensity=pulse(t, 1, 0.55, 1.0)))
    rising(s, t, 4, 8, ("#4F9AD0", "#3A434F"), ".'", top=0, bottom=42, sway=1.0, behind=True)
    return s


ROBE = Material(("#1E1228", "#2E1C40", "#44285C", "#5E3A7A"), ramp="░▒▓█", depth=5)
LICH_EYES = ("#3A1A5A", "#8A4FD0", "#C99BE8", "#F2E6FF")
SOUL = ("#6A8A9E", "#9EDCF2", "#E3F6FF")


def lich_regent(t):
    s = Scene()
    orbit = []
    for i in range(7):
        a = 2 * math.pi * (t + i / 7)
        x, y = 24 + math.cos(a) * 20, 23 + math.sin(a) * 9
        orbit.append((x, y, math.sin(a) < 0, a))
    for x, y, behind, a in orbit:
        if behind:
            s.dot(x, y, "o", SOUL[0], True)
            s.dot(x - math.sin(a) * 1.5, y + math.cos(a) * 0.8, ".", SOUL[0], True)
    s.add(polygon([(17, 19), (31, 19), (39, 43), (9, 43)]), ROBE)
    s.add(polygon([(14.5, 17), (33.5, 17), (31, 22), (17, 22)]), ROBE)
    s.add(capsule(37, 13, 37, 42, 0.6), GOLD)
    s.add(circle(37, 11.5, 1.8), Material(LICH_EYES, "▓█", emissive=True, halo=2.2, intensity=pulse(t, 1, 0.5, 1.0)))
    s.add(union(circle(36, 26, 1.6), circle(12.5, 28, 1.6)), BONE)
    s.add(circle(24, 12, 6.3), BONE)
    s.add(box(24, 18.6, 3.8, 1.9, 0.7), BONE)
    sockets = Material(("#050308", "#120A18"), "  ")
    s.add(union(circle(21.4, 11.8, 2.0), circle(26.6, 11.8, 2.0), polygon([(23.1, 16), (24.9, 16), (24, 14)])),
          sockets)
    for i in range(5):
        s.add(box(21.6 + i * 1.2, 19.2, 0.2, 0.9), sockets)
    flame = pulse(t, 2, 0.5, 1.0)
    s.add(union(circle(21.4, 11.9, 0.6 + 0.45 * flame), circle(26.6, 11.9, 0.6 + 0.45 * flame)),
          Material(LICH_EYES, "▓█", emissive=True, halo=2.2, intensity=flame))
    s.add(box(24, 5.6, 6.2, 1.0, 0.3), GOLD)
    for i, height in enumerate((2.8, 3.8, 5.0, 3.8, 2.8)):
        x = 19.2 + i * 2.4
        s.add(polygon([(x - 1.0, 5.0), (x + 1.0, 5.0), (x, 5.0 - height)]), GOLD)
    s.add(circle(24, 5.6, 0.7), Material(LICH_EYES, "█", emissive=True, halo=1.0))
    for x, y, behind, a in orbit:
        if not behind:
            s.dot(x, y, "o", SOUL[2])
            s.dot(x - math.sin(a) * 1.5, y + math.cos(a) * 0.8, "~", SOUL[1])
    rising(s, t, 5, 9, ("#8A4FD0", "#5A3A7A"), "+x.", x_range=(10, 38), top=0, bottom=40, sway=0.8, behind=True)
    return s


BRASS = Material(("#3A2A10", "#6A4E1E", "#9C7A34", "#C9A45A", "#EBD08E"), depth=2.5)
IRON = Material(("#16181C", "#2A2E35", "#40464F", "#5C646F", "#7E8794"), depth=4)
AMBER = ("#6A3A0A", "#D98A1E", "#F2C46D", "#FFF1B8")
RED_GLOW = ("#5A0A0A", "#B8323A", "#FF5C5C", "#FFC2B8")


def clockwork_colossus(t):
    s = Scene()
    spin = t * 2 * math.pi / 5  # gears turn one tooth per loop
    piston = math.sin(t * 2 * math.pi) * 1.6
    s.add(box(18, 37, 3.2, 5, 0.8), IRON)
    s.add(box(30, 37, 3.2, 5, 0.8), IRON)
    s.add(box(24, 23, 12.5, 10.5, 2), IRON)
    s.add(gear(24, 23.5, 6.2, 10, spin), BRASS)
    s.add(circle(24, 23.5, 3.2), IRON)
    s.add(circle(24, 23.5, 1.4), Material(AMBER, "▓█", emissive=True, halo=1.4, intensity=pulse(t, 2, 0.5, 1.0)))
    s.add(gear(15, 15.5, 2.8, 6, -spin * 10 / 6), BRASS)
    s.add(gear(33, 31, 2.8, 6, -spin * 10 / 6 + 0.5), BRASS)
    s.add(circle(15, 15.5, 1.0), IRON)
    s.add(circle(33, 31, 1.0), IRON)
    for side in (-1, 1):
        sx = 24 + side * 14
        s.add(circle(sx, 15, 3.2), BRASS)
        s.add(capsule(sx, 16, sx + side * 3, 26, 2.2), IRON)
        s.add(capsule(sx + side * 3, 26, sx + side * 3, 30 + piston * side, 1.0), BRASS)
        s.add(box(sx + side * 3, 33 + piston * side, 2.6, 2.4, 0.8), IRON)
        s.add(polygon([(sx + side * 1.2, 35 + piston * side), (sx + side * 2.2, 39 + piston * side),
                       (sx + side * 3, 35.5 + piston * side)]), BRASS)
        s.add(polygon([(sx + side * 3.6, 35.5 + piston * side), (sx + side * 4.8, 39 + piston * side),
                       (sx + side * 5, 35 + piston * side)]), BRASS)
    s.add(box(24, 10.2, 2, 1.5), IRON)
    s.add(box(24, 6.5, 5.8, 4.2, 1), BRASS)
    s.add(union(*(box(21.8 + i * 1.5, 9, 0.35, 0.9) for i in range(4))), IRON)
    s.add(union(circle(21.6, 5.6, 1.3), circle(26.4, 5.6, 1.3)), Material(RED_GLOW, "▓█", emissive=True, halo=1.8,
                                                                        intensity=pulse(t, 1, 0.65, 1.0)))
    for vent_x in (13, 35):
        rising(s, t, vent_x, 7, ("#9AA4B0", "#C9D3DE", "#6A7686"), "~o.", x_range=(vent_x - 1, vent_x + 1),
               bottom=11, top=0, sway=1.6)
    return s


SENTINEL = Material(("#26231F", "#3E3832", "#5A524A", "#7E756A", "#A69C8E"), depth=3)
PLINTH = Material(("#1A1714", "#2B2622", "#3E3832", "#544C44"), depth=3)
RUNE = ("#1E4A6A", "#4F9AD0", "#9EDCF2", "#E3F6FF")
CORE = ("#6A1E0E", "#E8604F", "#FFB347", "#FFF1B8")


def stone_sentinel(t):
    s = Scene()
    tick = int(t * 8) % 2 == 0  # the core ticks like a slow heart
    s.add(box(24, 40, 14, 2.5, 0.5), PLINTH)
    s.add(box(24, 37, 12, 1, 0.3), SENTINEL)
    s.add(box(20.6, 30.5, 2.8, 5.5, 0.8), SENTINEL)
    s.add(box(27.4, 30.5, 2.8, 5.5, 0.8), SENTINEL)
    s.add(box(24, 18.5, 7.2, 7.4, 1.5), SENTINEL)
    s.add(polygon([(23, 12), (25.5, 15), (23.5, 18), (26, 22), (24.5, 25.5), (24, 25.5), (25, 22), (22.6, 18),
                   (24.6, 15), (22.4, 12)]), Material(("#0A0908", "#14120F"), " ."))
    s.add(circle(24, 18, 1.6 if tick else 1.2), Material(CORE, "▓█", emissive=True, halo=2.4 if tick else 1.2,
                                                         intensity=1.0 if tick else 0.55))
    for side in (-1, 1):
        x = 24 + side * 10.2
        s.add(circle(24 + side * 7.5, 12.5, 2.6), SENTINEL)
        s.add(box(x, 20.5, 2.3, 7.5, 0.8), SENTINEL)
        s.add(box(x, 30, 2.8, 2.4, 0.8), SENTINEL)
        flicker = (t * 5 + side * 0.3) % 1 < 0.7
        s.add(union(box(x, 29.3, 1.8, 0.25), box(x - 0.8, 30.6, 0.25, 0.7), box(x + 0.8, 30.6, 0.25, 0.7)),
              Material(RUNE, "▓█", emissive=True, halo=1.0 if flicker else 0, intensity=1.0 if flicker else 0.3))
    s.add(box(24, 10.2, 1.4, 1.2), SENTINEL)
    s.add(box(24, 6, 3.4, 3.9, 1.5), SENTINEL)
    s.add(union(box(22.4, 5.6, 0.9, 0.22), box(25.6, 5.6, 0.9, 0.22)), Material(("#14120F", "#1E1A17"), " ."))
    falling(s, t, 21, 10, "#5A524A", top=0, bottom=34)
    return s


SPECTRE = Material(("#2E4050", "#4A6478", "#7A98AE", "#B8D0E0"), ramp="░░▒▒▓", depth=6)
GHOST_EYES = ("#3A6A8A", "#9EDCF2", "#E3F6FF", "#FFFFFF")


def ghost_horror(t):
    s = Scene()
    a = t * 2 * math.pi
    blobs = [circle(24 + 3 * math.sin(a), 16, 9), circle(17 + 2 * math.sin(a + 1), 22, 7),
             circle(31 + 2 * math.sin(a + 2), 22, 7), circle(24, 27, 7.5 + math.sin(a * 2) * 0.8)]
    tendrils = [capsule(14 + i * 5, 28, 13 + i * 5 + 3 * math.sin(a + i), 41, 2.4, 0.3) for i in range(5)]
    s.add(smooth_union(4.0, *blobs, *tendrils), SPECTRE)
    stretch = 1.6 + 1.0 * (0.5 + 0.5 * math.sin(a * 1.5))
    s.add(ellipse(24 + 3 * math.sin(a), 22, 2.2, stretch), Material(("#05080B", "#0A1218"), " ."))
    hollow = Material(("#05080B", "#0A1218"), "  ")
    ex = 3 * math.sin(a)
    s.add(union(ellipse(20.3 + ex, 14.5, 2.2, 1.6), ellipse(27.7 + ex, 14.5, 2.2, 1.6)), hollow)
    eyes = Material(GHOST_EYES, "▓█", emissive=True, halo=1.4, intensity=pulse(t, 3, 0.4, 1.0))
    s.add(union(circle(20.3 + ex, 14.6, 0.55), circle(27.7 + ex, 14.6, 0.55)), eyes)
    falling(s, t, 31, 18, "#B8D0E0", chars="*.'", top=0, bottom=42, speed=0.6)
    rng = random.Random(int(t * 24) // 3)
    for _ in range(3):  # faces that flicker in the mist
        x, y = rng.uniform(10, 38), rng.uniform(16, 32)
        s.dot(x, y, "o", "#4A6478")
        s.dot(x + 2, y, "o", "#4A6478")
    return s


BOSSES: dict[str, Callable[[float], Scene]] = {
    "titan": titan, "elder_dragon": elder_dragon, "earth_eater_worm": earth_eater_worm, "rat_king": rat_king,
    "valorian_warden": valorian_warden, "lich_regent": lich_regent, "clockwork_colossus": clockwork_colossus,
    "stone_sentinel": stone_sentinel, "ghost_horror": ghost_horror,
}
# Colors the game may swap at runtime (each Titan has its own element).
SLOTS = {"titan": {"glow": GLOW}}

KEYS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def build(name: str) -> dict:
    palette: dict[str, str] = {}
    keys: dict[str, str] = {}

    def key_for(color: str) -> str:
        if color not in keys:
            keys[color] = KEYS[len(keys)]
            palette[keys[color]] = color
        return keys[color]

    for slot_colors in SLOTS.get(name, {}).values():  # reserve slot colors first so their keys are stable
        for color in slot_colors:
            key_for(color)
    frames = []
    for i in range(FRAMES):
        lines, colors = render(BOSSES[name](i / FRAMES))
        frames.append({"lines": lines,
                       "colors": ["".join(key_for(c) if c else " " for c in row) for row in colors]})
    slots = {slot: [keys[c] for c in colors] for slot, colors in SLOTS.get(name, {}).items()}
    return {"fps": FPS, "width": W, "height": H, "palette": palette, "slots": slots, "frames": frames}


def main(names: list[str]) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for name in names or list(BOSSES):
        asset = build(name)
        (ASSET_DIR / f"boss_{name}.json").write_text(json.dumps(asset, separators=(",", ":")), encoding="utf-8")
        print(f"boss_{name}.json: {len(asset['frames'])} frames, {len(asset['palette'])} colors")


if __name__ == "__main__":
    main(sys.argv[1:])

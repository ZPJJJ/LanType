#!/usr/bin/env python3
"""Build deterministic stroke templates, without CASIA, OCHWPro, or MathWriting.

Chinese medians: MakeMeAHanzi, Arphic Public License (full source preserved).
Latin letter/digit polylines below: original LanType geometry, CC0-1.0.
Generator code: GPL-3.0-or-later.
"""
from __future__ import annotations
import gzip
import io
import json
import math
from pathlib import Path
import struct
from prepare_resources import ASSETS, source


def arc(cx, cy, rx, ry, start=0, end=360, count=25):
    return [[cx + rx * math.cos(math.radians(start + (end - start) * i / (count - 1))),
             cy + ry * math.sin(math.radians(start + (end - start) * i / (count - 1)))] for i in range(count)]


def latin():
    # Deliberately simple geometrical handwriting models, not a traced font.
    d = {
        'A': [[[5,95],[50,5],[95,95]], [[25,60],[75,60]]],
        'B': [[[15,95],[15,5],[60,5],[85,20],[85,35],[60,50],[15,50],[65,50],[90,65],[90,80],[65,95],[15,95]]],
        'C': [arc(52,50,42,45,315,45)],
        'D': [[[15,95],[15,5],[50,5],[85,25],[90,50],[85,75],[50,95],[15,95]]],
        'E': [[[85,5],[15,5],[15,95],[85,95]], [[15,50],[70,50]]],
        'F': [[[15,95],[15,5],[85,5]], [[15,50],[70,50]]],
        'G': [arc(52,50,42,45,315,45)+[[95,60],[60,60]]],
        'H': [[[15,5],[15,95]], [[85,5],[85,95]], [[15,50],[85,50]]],
        'I': [[[20,5],[80,5]], [[50,5],[50,95]], [[20,95],[80,95]]],
        'J': [[[80,5],[80,75],[65,95],[35,95],[20,80]]],
        'K': [[[15,5],[15,95]], [[85,5],[15,55],[85,95]]],
        'L': [[[15,5],[15,95],[85,95]]],
        'M': [[[10,95],[10,5],[50,65],[90,5],[90,95]]],
        'N': [[[15,95],[15,5],[85,95],[85,5]]],
        'O': [arc(50,50,40,45)],
        'P': [[[15,95],[15,5],[60,5],[85,20],[85,40],[60,55],[15,55]]],
        'Q': [arc(50,50,40,45), [[55,65],[95,100]]],
        'R': [[[15,95],[15,5],[60,5],[85,20],[85,40],[60,55],[15,55]], [[50,55],[90,95]]],
        'S': [[[85,15],[65,5],[35,5],[15,20],[15,35],[35,50],[65,50],[85,65],[85,80],[65,95],[35,95],[15,85]]],
        'T': [[[10,5],[90,5]], [[50,5],[50,95]]],
        'U': [[[15,5],[15,70],[25,90],[50,97],[75,90],[85,70],[85,5]]],
        'V': [[[10,5],[50,95],[90,5]]],
        'W': [[[5,5],[25,95],[50,30],[75,95],[95,5]]],
        'X': [[[10,5],[90,95]], [[90,5],[10,95]]],
        'Y': [[[10,5],[50,50],[90,5]], [[50,50],[50,95]]],
        'Z': [[[10,5],[90,5],[10,95],[90,95]]],
        'a': [arc(45,60,30,32), [[75,30],[75,92]]],
        'b': [[[20,5],[20,95]], arc(48,65,28,30,180,-180)],
        'c': [arc(50,60,35,32,315,45)],
        'd': [arc(45,65,28,30), [[73,5],[73,95]]],
        'e': [[[15,60],[85,60]]+arc(50,60,35,32,0,-315)],
        'f': [[[75,12],[60,5],[45,15],[45,95]], [[20,38],[75,38]]],
        'g': [arc(45,45,28,28), [[73,18],[73,88],[60,105],[35,105],[20,95]]],
        'h': [[[20,5],[20,95]], [[20,55],[35,35],[60,35],[75,50],[75,95]]],
        'i': [[[50,36],[50,95]], [[50,8],[50,12]]],
        'j': [[[65,35],[65,90],[50,105],[30,95]], [[65,8],[65,12]]],
        'k': [[[20,5],[20,95]], [[80,35],[20,68],[80,95]]],
        'l': [[[45,5],[45,85],[55,95],[70,90]]],
        'm': [[[10,95],[10,35],[25,30],[40,40],[40,95]], [[40,45],[55,30],[75,35],[85,50],[85,95]]],
        'n': [[[20,95],[20,35],[35,30],[60,35],[75,50],[75,95]]],
        'o': [arc(50,60,32,35)],
        'p': [[[20,30],[20,110]], arc(48,58,28,28,180,-180)],
        'q': [arc(45,55,28,28), [[73,28],[73,110]]],
        'r': [[[25,95],[25,35],[45,30],[70,40]]],
        's': [[[80,40],[60,30],[35,30],[20,42],[30,55],[65,65],[80,77],[70,90],[40,95],[20,85]]],
        't': [[[50,5],[50,85],[65,95],[80,88]], [[20,35],[80,35]]],
        'u': [[[20,30],[20,75],[30,93],[55,95],[75,75],[75,30],[75,95]]],
        'v': [[[15,30],[50,95],[85,30]]],
        'w': [[[5,30],[25,95],[50,45],[75,95],[95,30]]],
        'x': [[[20,30],[80,95]], [[80,30],[20,95]]],
        'y': [[[20,30],[50,80],[80,30]], [[80,30],[40,110]]],
        'z': [[[20,30],[80,30],[20,95],[80,95]]],
        '0': [arc(50,50,35,45)],
        '1': [[[30,25],[50,5],[50,95]]],
        '2': [[[15,25],[30,8],[65,5],[85,25],[78,45],[15,95],[90,95]]],
        '3': [[[15,10],[75,10],[45,45],[75,50],[90,70],[75,95],[35,95],[15,80]]],
        '4': [[[65,5],[10,65],[90,65]], [[65,5],[65,95]]],
        '5': [[[85,5],[20,5],[15,48],[65,45],[85,65],[85,80],[65,95],[30,95],[15,80]]],
        '6': [[[80,10],[55,5],[25,30],[15,65]]+arc(48,68,33,28,180,-180)],
        '7': [[[10,5],[90,5],[35,95]]],
        '8': [arc(50,28,30,24,90,450)+arc(50,73,35,26,270,-90)],
        '9': [arc(50,32,32,28), [[82,30],[75,70],[55,95],[25,95]]],
    }
    return d


def normalized(strokes):
    points = [p for s in strokes for p in s]
    lo = [min(p[i] for p in points) for i in range(2)]
    hi = [max(p[i] for p in points) for i in range(2)]
    span = max(hi[0]-lo[0], hi[1]-lo[1], 1e-6)
    scales = [max(hi[i]-lo[i], span * .35) for i in range(2)]
    centers = [(lo[i]+hi[i])/2 for i in range(2)]
    out = []
    for stroke in strokes:
        p = [[(v[i]-centers[i])/scales[i]+.5 for i in range(2)] for v in stroke]
        lengths = [0.0]
        for a,b in zip(p,p[1:]): lengths.append(lengths[-1]+math.dist(a,b))
        sampled=[]
        at=1
        for i in range(8):
            target=lengths[-1]*i/7
            while at<len(p)-1 and lengths[at]<target: at+=1
            if len(p)==1 or lengths[-1]<1e-9: sampled.append(p[0]);continue
            frac=(target-lengths[at-1])/max(lengths[at]-lengths[at-1],1e-9)
            sampled.append([p[at-1][j]*(1-frac)+p[at][j]*frac for j in range(2)])
        out.append(sampled)
    return out


def main():
    glyphs=[]
    for line in source("makemeahanzi-graphics.txt").decode().splitlines():
        row=json.loads(line)
        # Font coordinates have an upward y axis; touch coordinates point down.
        strokes=[[[p[0],-p[1]] for p in s] for s in row['medians'] if s]
        if strokes: glyphs.append((row['character'],strokes))
    glyphs += list(latin().items())
    metadata={"format":"LanType Stroke Templates 1", "modified":"2026-11-17",
        "notice":"Chinese medians Copyright (C) 1999 Arphic Technology Co., Ltd.; Arphic Public License. "
        "Modified by LanType: glyph medians only, y-axis flip, normalization and 8-point resampling. "
        "See licenses/Arphic-Public-License.txt and licensed source_data; modifications remain freely available under that licence. "
        "Latin polylines are original LanType geometry, CC0-1.0. No recorded handwriting datasets or neural weights.",
        "source":"https://github.com/skishore/makemeahanzi/tree/bddc96d41bef78427ed0e034e9f7e31d71fd1b92"}
    header=json.dumps(metadata,ensure_ascii=False).encode()
    out=io.BytesIO();out.write(b'LTH1');out.write(struct.pack('>I',len(header)));out.write(header);out.write(struct.pack('>I',len(glyphs)))
    for label,strokes in glyphs:
        normalized_strokes=normalized(strokes);text=label.encode()
        out.write(struct.pack('>H',len(text)));out.write(text);out.write(struct.pack('>H',len(strokes)))
        for stroke in normalized_strokes:
            for p in stroke: out.write(struct.pack('>HH',*(round(max(0,min(1,x))*4096) for x in p)))
    dest=ASSETS/'handwriting/lantype-strokes.lth';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(out.getvalue())
    print(json.dumps({'templates':len(glyphs),'chinese':len(glyphs)-len(latin()),'latin':len(latin()),'bytes':dest.stat().st_size}))


if __name__=='__main__':main()

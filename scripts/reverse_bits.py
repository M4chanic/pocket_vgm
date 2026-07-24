#!/usr/bin/env python3
"""RBF -> RBF_R: разворот порядка бит в каждом байте.

APF Pocket'а грузит битстрим с обратным порядком бит (см. Analogue docs,
"Packaging a Core"). Использование: reverse_bits.py in.rbf out.rev
"""
import sys

TABLE = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))

def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: reverse_bits.py <in.rbf> <out.rev>")
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    with open(sys.argv[2], "wb") as f:
        f.write(data.translate(TABLE))
    print(f"{sys.argv[1]} -> {sys.argv[2]}: {len(data)} байт")

if __name__ == "__main__":
    main()

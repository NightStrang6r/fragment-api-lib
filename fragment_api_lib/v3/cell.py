"""TON cells, just enough to build, hash, serialize and parse what API v3 needs.

Ordinary cells only. Checked bit for bit against tonutils (tests/test_v3_vectors.py).
"""
import base64
import hashlib

MAX_BITS = 1023
MAX_REFS = 4
BOC_MAGIC = 0xB5EE9C72


def _bits_to_bytes(bits):
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i >> 3] |= 0x80 >> (i & 7)
    return bytes(out)


def _bytes_to_bits(data, length):
    return [(data[i >> 3] >> (7 - (i & 7))) & 1 for i in range(length)]


class Cell:
    __slots__ = ("bits", "refs", "_hash", "_depth")

    def __init__(self, bits=(), refs=()):
        self.bits = tuple(bits)
        self.refs = tuple(refs)
        if len(self.bits) > MAX_BITS:
            raise ValueError(f"cell overflow: {len(self.bits)} bits")
        if len(self.refs) > MAX_REFS:
            raise ValueError(f"cell overflow: {len(self.refs)} refs")
        self._hash = None
        self._depth = None

    @staticmethod
    def empty():
        return Cell()

    def begin_parse(self):
        return Slice(self)

    def depth(self):
        if self._depth is None:
            self._depth = 1 + max(r.depth() for r in self.refs) if self.refs else 0
        return self._depth

    def descriptors(self):
        n = len(self.bits)
        return len(self.refs), n // 8 + (n + 7) // 8

    def data_bytes(self):
        bits = list(self.bits)
        if len(bits) % 8:
            bits.append(1)
            while len(bits) % 8:
                bits.append(0)
        return _bits_to_bytes(bits)

    def hash(self):
        if self._hash is None:
            d1, d2 = self.descriptors()
            parts = [bytes([d1, d2]), self.data_bytes()]
            parts += [r.depth().to_bytes(2, "big") for r in self.refs]
            parts += [r.hash() for r in self.refs]
            self._hash = hashlib.sha256(b"".join(parts)).digest()
        return self._hash

    def to_boc(self):
        return serialize_boc(self)

    def to_b64(self):
        return base64.b64encode(self.to_boc()).decode()


class Builder:
    def __init__(self):
        self.bits = []
        self.refs = []

    def store_bit(self, bit):
        self.bits.append(1 if bit else 0)
        return self

    def store_bits(self, bits):
        for b in bits:
            self.store_bit(b)
        return self

    def store_uint(self, value, length):
        value = int(value)
        if value < 0 or value >= 1 << length:
            raise ValueError(f"uint{length} out of range: {value}")
        self.bits.extend((value >> i) & 1 for i in range(length - 1, -1, -1))
        return self

    def store_int(self, value, length):
        value = int(value)
        if not -(1 << (length - 1)) <= value < 1 << (length - 1):
            raise ValueError(f"int{length} out of range: {value}")
        return self.store_uint(value + (1 << length) if value < 0 else value, length)

    def store_bytes(self, data):
        for byte in data:
            self.store_uint(byte, 8)
        return self

    def store_coins(self, amount):
        amount = int(amount)
        if amount < 0:
            raise ValueError("coins can not be negative")
        if amount == 0:
            return self.store_uint(0, 4)
        n = (amount.bit_length() + 7) // 8
        if n > 15:
            raise ValueError("coins out of range")
        return self.store_uint(n, 4).store_uint(amount, n * 8)

    def store_ref(self, cell):
        if len(self.refs) >= MAX_REFS:
            raise ValueError("too many refs")
        self.refs.append(cell)
        return self

    def store_maybe_ref(self, cell):
        if cell is None:
            return self.store_bit(0)
        return self.store_bit(1).store_ref(cell)

    def store_cell(self, cell):
        self.store_bits(cell.bits)
        for r in cell.refs:
            self.store_ref(r)
        return self

    @property
    def bit_length(self):
        return len(self.bits)

    @property
    def ref_count(self):
        return len(self.refs)

    def end_cell(self):
        return Cell(self.bits, self.refs)


def begin_cell():
    return Builder()


class Slice:
    def __init__(self, cell):
        self.cell = cell
        self.bit_pos = 0
        self.ref_pos = 0

    @property
    def remaining_bits(self):
        return len(self.cell.bits) - self.bit_pos

    @property
    def remaining_refs(self):
        return len(self.cell.refs) - self.ref_pos

    def load_bit(self):
        if self.remaining_bits < 1:
            raise ValueError("slice underflow")
        b = self.cell.bits[self.bit_pos]
        self.bit_pos += 1
        return b

    def load_bits(self, n):
        if self.remaining_bits < n:
            raise ValueError("slice underflow")
        out = list(self.cell.bits[self.bit_pos:self.bit_pos + n])
        self.bit_pos += n
        return out

    def load_uint(self, n):
        v = 0
        for b in self.load_bits(n):
            v = (v << 1) | b
        return v

    def load_int(self, n):
        v = self.load_uint(n)
        return v - (1 << n) if v >= 1 << (n - 1) else v

    def load_bytes(self, n):
        return _bits_to_bytes(self.load_bits(n * 8))

    def load_coins(self):
        n = self.load_uint(4)
        return self.load_uint(n * 8) if n else 0

    def load_ref(self):
        if self.remaining_refs < 1:
            raise ValueError("no more refs")
        r = self.cell.refs[self.ref_pos]
        self.ref_pos += 1
        return r

    def load_maybe_ref(self):
        return self.load_ref() if self.load_bit() else None


def _size_for(n):
    size = 1
    while n >= 1 << (8 * size):
        size += 1
    return size


def serialize_boc(root):
    """One root; parents before children; identical cells once; no index, no CRC."""
    order, index = [], {}

    def visit(cell):
        key = cell.hash()
        if key in index:
            return
        index[key] = len(order)
        order.append(cell)
        for r in cell.refs:
            visit(r)
    visit(root)
    changed = True
    while changed:
        changed = False
        for i, cell in enumerate(order):
            for r in cell.refs:
                j = index[r.hash()]
                if j < i:
                    moved = order.pop(j)
                    order.insert(i, moved)
                    index = {c.hash(): k for k, c in enumerate(order)}
                    changed = True
                    break
            if changed:
                break
    size = _size_for(len(order))
    blobs = []
    for cell in order:
        d1, d2 = cell.descriptors()
        blobs.append(bytes([d1, d2]) + cell.data_bytes()
                     + b"".join(index[r.hash()].to_bytes(size, "big") for r in cell.refs))
    data = b"".join(blobs)
    off = _size_for(len(data))
    return (BOC_MAGIC.to_bytes(4, "big") + bytes([size, off])
            + len(order).to_bytes(size, "big") + (1).to_bytes(size, "big") + (0).to_bytes(size, "big")
            + len(data).to_bytes(off, "big") + (0).to_bytes(size, "big") + data)


def parse_boc(data):
    """Root cells of a standard BoC (with or without index/CRC)."""
    if isinstance(data, str):
        s = data.strip()
        data = base64.b64decode(s.replace("-", "+").replace("_", "/") + "=" * (-len(s) % 4))
    if len(data) < 6 or int.from_bytes(data[:4], "big") != BOC_MAGIC:
        raise ValueError("not a BoC")
    flags = data[4]
    has_idx, has_crc, size = bool(flags & 0x80), bool(flags & 0x40), flags & 0x07
    off = data[5]
    pos = 6

    def take(n):
        nonlocal pos
        v = int.from_bytes(data[pos:pos + n], "big")
        pos += n
        return v
    count, roots_n, _absent, total = take(size), take(size), take(size), take(off)
    roots = [take(size) for _ in range(roots_n)]
    if has_idx:
        pos += count * off
    end = pos + total
    if end + (4 if has_crc else 0) > len(data):
        raise ValueError("truncated BoC")
    raw = []
    while pos < end:
        d1, d2 = data[pos], data[pos + 1]
        pos += 2
        if d1 & 0x08:
            raise ValueError("exotic cells are not supported")
        if d1 & 0x10:
            raise ValueError("cells with stored hashes are not supported")
        n = (d2 + 1) // 2
        chunk = data[pos:pos + n]
        pos += n
        bit_len = n * 8
        if d2 % 2:
            while bit_len and not (chunk[(bit_len - 1) >> 3] >> (7 - ((bit_len - 1) & 7))) & 1:
                bit_len -= 1
            bit_len -= 1
        refs = [take(size) for _ in range(d1 & 0x07)]
        raw.append((_bytes_to_bits(chunk, bit_len), refs))
    if len(raw) != count:
        raise ValueError("BoC cell count mismatch")
    built = [None] * count
    for i in range(count - 1, -1, -1):
        bits, refs = raw[i]
        if any(r <= i for r in refs):
            raise ValueError("BoC refs are not in topological order")
        built[i] = Cell(bits, [built[r] for r in refs])
    return [built[r] for r in roots]


def cell_from_b64(value):
    roots = parse_boc(value)
    if len(roots) != 1:
        raise ValueError("expected exactly one root cell")
    return roots[0]

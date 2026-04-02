KEYSPACE = "fw59eorpma2nvxb07liqt83_u6kgzs41-ycdjh"
CHAFF_SIZE = 150
CHAFF_MODULUS = 7


def encode_int(value):
    value = int(value)
    if value < 0:
        raise ValueError("Value must be non-negative.")

    chaffified = value * CHAFF_SIZE
    if chaffified == 0:
        return KEYSPACE[0]

    out = ""
    while chaffified > 0:
        chaffified, digit = divmod(chaffified, len(KEYSPACE))
        out += KEYSPACE[digit]
    return out[::-1]


def decode_int(token):
    value = 0
    for char in token:
        value = value * len(KEYSPACE) + KEYSPACE.index(char)

    decoded, remainder = divmod(value, CHAFF_SIZE)
    if remainder % CHAFF_MODULUS != 0:
        raise ValueError("Invalid encoded integer.")
    return decoded

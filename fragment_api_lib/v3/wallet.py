"""Wallets v4r2 and v5r1: state init, address, and the signed external paying a list of
messages. Mirrors tonutils; checked bit for bit against it (tests/test_v3_vectors.py)."""
from .address import Address, store_address
from .cell import Cell, begin_cell, cell_from_b64

CODE = {
    "v4r2": "b5ee9c72010214010002d4000114ff00f4a413f4bcf2c80b01020120020f020148030602e6d001d0d3032171b0925f04e022d749c120925f04e002d31f218210706c7567bd22821064737472bdb0925f05e003fa403020fa4401c8ca07cbffc9d0ed44d0810140d721f404305c810108f40a6fa131b3925f07e005d33fc8258210706c7567ba923830e30d03821064737472ba925f06e30d0405007801fa00f40430f8276f2230500aa121bef2e0508210706c7567831eb17080185004cb0526cf1658fa0219f400cb6917cb1f5260cb3f20c98040fb0006008a5004810108f45930ed44d0810140d720c801cf16f400c9ed540172b08e23821064737472831eb17080185005cb055003cf1623fa0213cb6acb1fcb3fc98040fb00925f03e2020120070e020120080d020158090a003db29dfb513420405035c87d010c00b23281f2fff274006040423d029be84c600201200b0c0019adce76a26840206b90eb85ffc00019af1df6a26840106b90eb858fc00011b8c97ed44d0d70b1f80059bd242b6f6a2684080a06b90fa0218470d4080847a4937d29910ce6903e9ff9837812801b7810148987159f318404f8f28308d71820d31fd31fd31f02f823bbf264ed44d0d31fd31fd3fff404d15143baf2a15151baf2a205f901541064f910f2a3f80024a4c8cb1f5240cb1f5230cbff5210f400c9ed54f80f01d30721c0009f6c519320d74a96d307d402fb00e830e021c001e30021c002e30001c0039130e30d03a4c8cb1f12cb1fcbff10111213006ed207fa00d4d422f90005c8ca0715cbffc9d077748018c8cb05cb0222cf165005fa0214cb6b12ccccc973fb00c84014810108f451f2a7020070810108d718fa00d33fc8542047810108f451f2a782106e6f746570748018c8cb05cb025006cf165004fa0214cb6a12cb1fcb3fc973fb0002006c810108d718fa00d33f305224810108f459f2a782106473747270748018c8cb05cb025005cf165003fa0213cb6acb1f12cb3fc973fb00000af400c9ed54",
    "v5r1": "b5ee9c7201021401000281000114ff00f4a413f4bcf2c80b01020120020d020148030402dcd020d749c120915b8f6320d70b1f2082106578746ebd21821073696e74bdb0925f03e082106578746eba8eb48020d72101d074d721fa4030fa44f828fa443058bd915be0ed44d0810141d721f4058307f40e6fa1319130e18040d721707fdb3ce03120d749810280b99130e070e2100f020120050c020120060902016e07080019adce76a2684020eb90eb85ffc00019af1df6a2684010eb90eb858fc00201480a0b0017b325fb51341c75c875c2c7e00011b262fb513435c280200019be5f0f6a2684080a0eb90fa02c0102f20e011e20d70b1f82107369676ebaf2e08a7f0f01e68ef0eda2edfb218308d722028308d723208020d721d31fd31fd31fed44d0d200d31f20d31fd3ffd70a000af90140ccf9109a28945f0adb31e1f2c087df02b35007b0f2d0845125baf2e0855036baf2e086f823bbf2d0882292f800de01a47fc8ca00cb1f01cf16c9ed542092f80fde70db3cd81003f6eda2edfb02f404216e926c218e4c0221d73930709421c700b38e2d01d72820761e436c20d749c008f2e09320d74ac002f2e09320d71d06c712c2005230b0f2d089d74cd7393001a4e86c128407bbf2e093d74ac000f2e093ed55e2d20001c000915be0ebd72c08142091709601d72c081c12e25210b1e30f20d74a111213009601fa4001fa44f828fa443058baf2e091ed44d0810141d718f405049d7fc8ca0040048307f453f2e08b8e14038307f45bf2e08c22d70a00216e01b3b0f2d090e2c85003cf1612f400c9ed54007230d72c08248e2d21f2e092d200ed44d0d2005113baf2d08f54503091319c01810140d721d70a00f2e08ee2c8ca0058cf16c9ed5493f2c08de20010935bdb31e1d74cd0",
}
MAX_MESSAGES = {"v4r2": 4, "v5r1": 255}
V4_SUBWALLET_ID = 698983191
MAINNET, TESTNET = -239, -3
V5_SIGNED_EXTERNAL = 0x7369676E
V5_SEND_MSG = 0x0EC3C86D
SEND_MODE = 3   # pay fees separately + ignore errors, as every wallet signs


def default_wallet_id(wallet_type, testnet=False):
    if wallet_type == "v4r2":
        return V4_SUBWALLET_ID
    # client context: client flag, workchain 0, version 0, subwallet 0; XOR network id
    return 0x80000000 ^ ((TESTNET if testnet else MAINNET) & 0xFFFFFFFF)


def _data(wallet_type, public_key, testnet):
    if wallet_type == "v4r2":
        return begin_cell().store_uint(0, 32).store_uint(V4_SUBWALLET_ID, 32).store_bytes(public_key).store_bit(0).end_cell()
    return (begin_cell().store_bit(1).store_uint(0, 32).store_uint(default_wallet_id(wallet_type, testnet), 32)
            .store_bytes(public_key).store_bit(0).end_cell())


def state_init(wallet_type, public_key, testnet=False):
    code = cell_from_b64(bytes.fromhex(CODE[wallet_type]))
    return (begin_cell().store_bit(0).store_bit(0).store_maybe_ref(code)
            .store_maybe_ref(_data(wallet_type, public_key, testnet)).store_bit(0).end_cell())


def wallet_address(wallet_type, public_key, testnet=False):
    return Address(0, state_init(wallet_type, public_key, testnet).hash(), False, testnet)


def _store_init(b, init):
    """A StateInit / body goes inline when it fits (pytoniq / @ton/core layout), else a ref."""
    if init is None:
        b.store_bit(0)
        return
    b.store_bit(1)
    if len(init.bits) <= 1023 - b.bit_length - 2 and len(init.refs) <= 4 - b.ref_count:
        b.store_bit(0).store_cell(init)
    else:
        b.store_bit(1).store_ref(init)


def _store_body(b, body):
    if len(body.bits) <= 1023 - b.bit_length - 1 and len(body.refs) <= 4 - b.ref_count:
        b.store_bit(0).store_cell(body)
    else:
        b.store_bit(1).store_ref(body)


def internal_message(address, amount, body):
    """int_msg_info: ihr disabled, bounce from the address flag, src none, no extras."""
    dest = Address.parse(address)
    b = begin_cell().store_bit(0).store_bit(1).store_bit(dest.bounceable).store_bit(0)
    store_address(b, None)
    store_address(b, dest)
    b.store_coins(amount).store_bit(0).store_coins(0).store_coins(0).store_uint(0, 64).store_uint(0, 32)
    _store_init(b, None)
    _store_body(b, body)
    return b.end_cell()


def _signing_message(wallet_type, seqno, valid_until, messages, testnet):
    wallet_id = default_wallet_id(wallet_type, testnet)
    if wallet_type == "v4r2":
        b = begin_cell().store_uint(wallet_id, 32).store_uint(valid_until, 32).store_uint(seqno, 32).store_uint(0, 8)
        for m in messages:
            b.store_uint(SEND_MODE, 8).store_ref(internal_message(*m))
        return b.end_cell()
    actions = Cell.empty()
    for m in messages:
        actions = (begin_cell().store_ref(actions).store_uint(V5_SEND_MSG, 32).store_uint(SEND_MODE, 8)
                   .store_ref(internal_message(*m)).end_cell())
    return (begin_cell().store_uint(V5_SIGNED_EXTERNAL, 32).store_uint(wallet_id, 32).store_uint(valid_until, 32)
            .store_uint(seqno, 32).store_bit(1).store_ref(actions).store_bit(0).end_cell())


def sign_external(wallet_type, key_pair, seqno, valid_until, messages, include_state_init=False, testnet=False):
    """messages: [(address, amount_nano, body_cell)]. Returns (boc_b64, normalized_hash_hex, cell)."""
    if not messages:
        raise ValueError("nothing to send")
    if len(messages) > MAX_MESSAGES[wallet_type]:
        raise ValueError(f"{wallet_type} sends at most {MAX_MESSAGES[wallet_type]} messages")
    unsigned = _signing_message(wallet_type, seqno, valid_until, messages, testnet)
    signature = key_pair.sign(unsigned.hash())
    body = begin_cell()
    if wallet_type == "v4r2":
        body.store_bytes(signature).store_cell(unsigned)
    else:
        body.store_cell(unsigned).store_bytes(signature)
    body = body.end_cell()
    wallet = wallet_address(wallet_type, key_pair.public_key, testnet)
    ext = begin_cell().store_uint(2, 2)
    store_address(ext, None)
    store_address(ext, wallet)
    ext.store_coins(0)
    _store_init(ext, state_init(wallet_type, key_pair.public_key, testnet) if include_state_init else None)
    _store_body(ext, body)
    cell = ext.end_cell()
    norm = begin_cell().store_uint(2, 2)
    store_address(norm, None)
    store_address(norm, wallet)
    norm.store_coins(0).store_bit(0).store_bit(1).store_ref(body)
    return cell.to_b64(), norm.end_cell().hash().hex(), cell

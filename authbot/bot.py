import asyncio
import functools
import logging

import urllib.parse

import aioxmpp


logger = logging.getLogger(__name__)


def on_join(workqueue, member, **kwargs):
    logger.debug("new member: %s", member.nick)
    if member.affiliation != "none":
        # member already configured, skip
        logger.debug("%s already has affiliation %s, ignoring",
                     member.nick, member.affiliation)
        return

    workqueue.put_nowait(member.direct_jid)


def extract_contact_form(info):
    for ext in info.exts:
        if ext.get_form_type() != "http://jabber.org/network/serverinfo":
            continue
        return ext
    return None


def extract_relevant_addresses(contact_info_form):
    RELEVANT_FIELDS = [
        "abuse-addresses",
        "admin-addresses",
        "security-addresses",
    ]
    for field in contact_info_form.fields:
        if field.var not in RELEVANT_FIELDS:
            continue
        for value in field.values:
            if not value:
                continue
            try:
                url = urllib.parse.urlparse(value)
            except ValueError:
                logger.debug("ignoring malformed URI: %s", value)
                continue
            if url.scheme != "xmpp":
                continue
            try:
                jid = aioxmpp.JID.fromstr(url.path)
            except ValueError:
                logger.debug("ignoring malformed XMPP address: %s",
                             url.path)
                continue
            yield jid


async def lookup_and_adjust(service, room_address, disco_client, address):
    logger.debug("checking whether %s should have member affiliation",
                 address)
    domain = address.replace(localpart=None, resource=None)
    info = await disco_client.query_info(
        domain,
        require_fresh=True,
    )
    contact_info = extract_contact_form(info)
    if contact_info is None:
        logger.debug("%s has no contact info published, "
                     "not granting anything")
        return

    addresses = list(extract_relevant_addresses(contact_info))
    logger.debug("found admin addresses %s for domain %s", addresses, domain)
    if address in addresses:
        new_affiliation = "member"
        logger.info("%s is a relevant contact for %s, "
                    "granting affiliation %s",
                    address, domain, new_affiliation)
        await service.set_affiliation(
            room_address,
            address,
            new_affiliation,
            reason="is relevant contact for an XMPP domain",
        )
    else:
        logger.info("%s is not one of %s, hence not granting affiliation",
                    address, addresses)


async def run_in_room(
        client: aioxmpp.Client,
        room_address: aioxmpp.JID,
        nickname: str):
    muc_client = client.summon(aioxmpp.MUCClient)
    disco_client = client.summon(aioxmpp.DiscoClient)

    room, join_fut = muc_client.join(
        room_address,
        nickname,
    )

    workqueue = asyncio.Queue(1024)

    def connect_join_signal(*args, **kwargs) -> bool:
        room.on_join.connect(functools.partial(on_join, workqueue))
        return True

    room.on_enter.connect(connect_join_signal)
    await join_fut
    logger.info("joined %s as %s", room_address, nickname)

    while True:
        jid = await workqueue.get()
        await lookup_and_adjust(muc_client, room_address, disco_client, jid)

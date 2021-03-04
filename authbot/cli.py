import asyncio
import logging
import signal

import environ

import aioxmpp

from . import bot


logger = logging.getLogger(__name__)


@environ.config(prefix="AUTHBOT")
class Config:
    address = environ.var(converter=aioxmpp.JID.fromstr)
    password = environ.var()
    room_address = environ.var(converter=aioxmpp.JID.fromstr)
    room_nickname = environ.var()

    log_level = environ.var(2, converter=int)
    lib_log_level = environ.var(1, converter=int)


async def amain() -> int:
    config: Config = environ.to_config(Config)

    logging.basicConfig(
        level={
            0: logging.ERROR,
            1: logging.WARNING,
            2: logging.INFO,
        }.get(config.lib_log_level, logging.DEBUG),
    )
    logging.getLogger("authbot").setLevel({
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
    }.get(config.log_level, logging.DEBUG))

    client = aioxmpp.PresenceManagedClient(
        config.address,
        aioxmpp.make_security_layer(
            config.password,
        ),
    )

    client.summon(aioxmpp.MUCClient)
    client.summon(aioxmpp.DiscoClient)

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop_event.set)
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    stop_future = asyncio.create_task(stop_event.wait())

    async with client.connected() as stream:
        logger.info("connected as %s", stream.local_jid)

        bot_task = asyncio.create_task(bot.run_in_room(
            client,
            config.room_address,
            config.room_nickname,
        ))

        done, pending = await asyncio.wait(
            [bot_task, stop_future],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for fut in pending:
            fut.cancel()

        for fut in done:
            fut.result()

        for fut in pending:
            try:
                await fut
            except asyncio.CancelledError:
                pass


def main() -> int:
    return asyncio.run(amain())

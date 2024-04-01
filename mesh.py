#!/usr/bin/env python3
"""Meshtastic Telegram Gateway"""

#
import argparse
import logging
import os
import sys
import time
#
from mtg.bot.meshtastic import MeshtasticBot
from mtg.connection.meshtastic import MeshtasticConnection
from mtg.config import Config
from mtg.connection.meshtastic import FIFO, FIFO_CMD
from mtg.connection.mqtt import MQTTInterface
from mtg.log import setup_logger, LOGFORMAT
from mtg.utils import create_fifo
#


# pylint:disable=too-many-locals,too-many-statements
def main(args):
    """
    Main function :)

    :return:
    """
    config = Config(config_path=args.config)
    config.read()
    level = logging.INFO
    if config.enforce_type(bool, config.DEFAULT.Debug):
        level = logging.DEBUG

    logger = setup_logger('mesh', level)
    # meshtastic logger
    logging.basicConfig(level=level, format=LOGFORMAT)
    basedir = os.path.abspath(os.path.dirname(__file__))

    meshtastic_connection = MeshtasticConnection(config.Meshtastic.Device, logger, config)
    meshtastic_connection.connect()

    mqtt_interface = MQTTInterface(debugOut=sys.stdout, cfg=config, logger=logger)

    meshtastic_bot = MeshtasticBot(config, meshtastic_connection,mqtt_interface)
    meshtastic_bot.set_logger(logger)
    meshtastic_bot.subscribe()
    meshtastic_connection.run()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            meshtastic_connection.shutdown()
            logger.info('Exit requested...')
            sys.exit(0)


def post2mesh(args):
    """
    post2mesh - send messages from console using Meshtastic networks. For alerts etc

    :return:
    """
    if args.message is None:
        print('Cannot send empty message...')
        return
    print("Opening fifo...")
    create_fifo(FIFO)
    print("Writing to fifo...")
    with open(FIFO, 'w', encoding='utf-8') as fifo:
        print("Sending message...")
        fifo.write(args.message + '\n')

def post_cmd(args):
    """
    post_cmd - send commands to Meshtastic connection

    :param args:
    :return:
    """
    if args.command is None:
        print('Cannot send empty command...')
        return
    create_fifo(FIFO_CMD)
    with open(FIFO_CMD, 'w', encoding='utf-8') as fifo:
        fifo.write(args.command + '\n')

def cmd():
    """
    cmd - Run argument parser and process command line parameters

    :return:
    """
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(title="commands", help="commands")

    post = subparser.add_parser("post2mesh", help="site command")
    post.add_argument("-m", "--message", help="message to post to Meshtastic")
    post.set_defaults(func=post2mesh)
    #
    run = subparser.add_parser("run", help="run")
    run.add_argument("-c", "--config", help="path to config", default="./mesh.ini")
    run.set_defaults(func=main)
    #
    reboot = subparser.add_parser("command", help="Send command")
    reboot.add_argument("-c", "--command", help="Send command")
    reboot.set_defaults(func=post_cmd)
    #
    argv = sys.argv[1:]
    if len(argv) == 0:
        argv = ['run']
    args = parser.parse_args(argv)
    print(args.func(args))


if __name__ == '__main__':
    cmd()

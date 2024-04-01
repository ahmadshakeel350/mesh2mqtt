# -*- coding: utf-8 -*-
""" Meshtastic bot module """

import logging
import pkg_resources
import re
import time

import humanize

from meshtastic import (
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    portnums_pb2 as meshtastic_portnums_pb2
) 

from pubsub import pub

from mtg.config import Config
from mtg.connection.rich import RichConnection
from mtg.connection.telegram import TelegramConnection
from mtg.database import MeshtasticDB
from mtg.filter import MeshtasticFilter
from mtg.geo import get_lat_lon_distance
from mtg.log import VERSION
from mtg.output.file import CSVFileWriter
from mtg.connection.mqtt import MQTTInterface


class MeshtasticBot:  # pylint:disable=too-many-instance-attributes
    """
    Meshtastic bot class
    """

    # pylint:disable=too-many-arguments
    def __init__(self, config: Config, meshtastic_connection: RichConnection, mqtt_interface: MQTTInterface):
        self.config = config
        self.filter = None
        self.logger = None
        self.meshtastic_connection = meshtastic_connection
        self.mqtt_interface = mqtt_interface
        self.ping_container = {}

    def set_logger(self, logger: logging.Logger):
        """
        Set logger

        :param logger:
        :return:
        """
        self.logger = logger
        self.writer.set_logger(self.logger)

    def on_connection(self, interface: meshtastic_serial_interface.SerialInterface, topic=pub.AUTO_TOPIC) -> None:
        """
        on radio connection event

        :param interface:
        :param topic:
        :return:
        """
        self.logger.debug("connection on %s topic %s", interface, topic)

    def on_node_info(self, node, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        on node information event

        :param node:
        :param interface:
        :return:
        """
        self.logger.debug("node info %s on interface %s", node, interface)

    def subscribe(self) -> None:
        """
        Subscribe to Meshtastic events

        :return:
        """
        subscription_map = {
            "meshtastic.receive": self.on_receive,
            "meshtastic.connection.established": self.on_connection,
            "meshtastic.connection.lost": self.on_connection,
        }

        for topic, callback in subscription_map.items():
            pub.subscribe(callback, topic)

    # pylint:disable=too-many-branches, too-many-statements, too-many-return-statements
    def on_receive(self, packet, interface: meshtastic_serial_interface.SerialInterface) -> None:
        """
        onReceive is called when a packet arrives

        :param packet:
        :param interface:
        :return:
        """
        self.logger.debug(f"Received: {packet}")
        self.mqtt_interface.sendData(str(packet).encode('utf-8'))

# -*- coding: utf-8 -*-
""" Meshtastic connection module """

import logging
import re
import sys
import time
#
from threading import RLock, Thread
from typing import (
    Dict,
    List,
)
#
from meshtastic import (
    LOCAL_ADDR as MESHTASTIC_LOCAL_ADDR,
    BROADCAST_ADDR as MESHTASTIC_BROADCAST_ADDR,
    serial_interface as meshtastic_serial_interface,
    tcp_interface as meshtastic_tcp_interface,
    mesh_pb2
)
# pylint:disable=no-name-in-module
from setproctitle import setthreadtitle

from mtg.utils import create_fifo, split_message
from mtg.connection.mqtt import MQTTInterface

FIFO = '/tmp/mtg.fifo'
FIFO_CMD = '/tmp/mtg.cmd.fifo'


# pylint:disable=too-many-instance-attributes
class MeshtasticConnection:
    """
    Meshtastic device connection
    """

    # pylint:disable=too-many-arguments
    def __init__(self, dev_path: str, logger: logging.Logger, config, startup_ts=time.time()):
        self.dev_path = dev_path
        self.interface = None
        self.logger = logger
        self.config = config
        self.startup_ts = startup_ts
        self.mqtt_nodes = {}
        self.name = 'Meshtastic Connection'
        self.lock = RLock()
        # exit
        self.exit = False

    @property
    def get_startup_ts(self):
        """
        Get startup timestamp

        :return:
        """
        return self.startup_ts

    def connect(self):
        """
        Connect to Meshtastic device. Interface can be later updated during reboot procedure

        :return:
        """
        self.interface = meshtastic_serial_interface.SerialInterface(devPath=self.dev_path, debugOut=sys.stdout)


    def send_text(self, msg, **kwargs) -> None:
        """
        Send Meshtastic message

        :param args:
        :param kwargs:
        :return:
        """
        if len(msg) < mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2:  # pylint:disable=no-member
            with self.lock:
                self.interface.sendText(msg, **kwargs)
                return
        # pylint:disable=no-member
        split_message(msg, mesh_pb2.Constants.DATA_PAYLOAD_LEN // 2, self.interface.sendText, **kwargs)
        return

    def send_data(self, *args, **kwargs) -> None:
        """
        Send Meshtastic data message

        :param args:
        :param kwargs:
        :return:
        """
        with self.lock:
            self.interface.sendData(*args, **kwargs)

    def node_info(self, node_id) -> Dict:
        """
        Return node information for a specific node ID

        :param node_id:
        :return:
        """
        return self.interface.nodes.get(node_id, {})

    def reboot(self):
        """
        Execute Meshtastic device reboot

        :return:
        """
        self.logger.info("Reboot requested...")
        self.interface.getNode(MESHTASTIC_LOCAL_ADDR).reboot(10)
        self.interface.close()
        time.sleep(20)
        self.connect()
        self.logger.info("Reboot completed...")

    def run_loop(self):
        """
        Meshtastic loop runner. Used for messages

        :return:
        """
        setthreadtitle(self.name)

        self.logger.debug("Opening FIFO...")
        create_fifo(FIFO)
        while not self.exit:
            with open(FIFO, encoding='utf-8') as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    self.send_text(line, destinationId=MESHTASTIC_BROADCAST_ADDR)

    def run_cmd_loop(self):
        """
        Meshtastic loop runner. Used for commands

        :return:
        """
        setthreadtitle("MeshtasticCmd")

        self.logger.debug("Opening FIFO...")
        create_fifo(FIFO_CMD)
        while not self.exit:
            with open(FIFO_CMD, encoding='utf-8') as fifo:
                for line in fifo:
                    line = line.rstrip('\n')
                    if line.startswith("reboot"):
                        self.logger.warning("Reboot requested using CMD...")
                        self.reboot()
                    if line.startswith("reset_db"):
                        self.logger.warning("Reset DB requested using CMD...")
                        self.reset_db()

    def shutdown(self):
        """
        Stop Meshtastic connection
        """
        self.exit = True

    def run(self):
        """
        Meshtastic connection runner

        :return:
        """
        if self.config.enforce_type(bool, self.config.Meshtastic.FIFOEnabled):
            thread = Thread(target=self.run_loop, daemon=True, name=self.name)
            thread.start()
            cmd_thread = Thread(target=self.run_cmd_loop, daemon=True, name="MeshtasticCmd")
            cmd_thread.start()

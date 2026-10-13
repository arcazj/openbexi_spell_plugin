# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.config import ConfigInterface
from . import connection


class Config(ConfigInterface):
    def setup(self, context, driver):
        super().setup(context,driver)
        connection.setup()

    def cleanup(self, shutdown=False):
        connection.close()
        super().cleanup(shutdown)


CONFIG = Config()

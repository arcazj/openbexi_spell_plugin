"""GPL original-driver host: context --config <private operator configuration>.

The standalone Apache server never imports or enables this optional GPL adapter.
"""

# SPDX-License-Identifier: GPL-3.0-or-later
from openbexi_spell_server.__main__ import main

from .context_driver import ContextDriver


if __name__ == "__main__":
    main(driver_factory=ContextDriver)

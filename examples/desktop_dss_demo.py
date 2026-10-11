"""Native Python Run/Debug example with an explicitly installed SPELL adapter."""
import argparse

from openbexi_spell_plugin.runtime import activate
from spell.lang import Display, GetTM, BuildTC, Send


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dss-url', default='http://127.0.0.1:8085')
    args = parser.parse_args()
    activate(args.dss_url)
    Display('Explicit desktop SPELL development test')
    Display('Initial TM1: ' + str(GetTM('TM1')))
    Send(BuildTC('CMD1'))
    Display('DSS command completed through the binary transport')


if __name__ == '__main__':
    main()

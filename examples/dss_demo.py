"""Use --language spell; calls stay explicit, with no builtins injection."""
from spell.lang import Display, GetTM, BuildTC, Send

Display('DSS development test')
Display('Initial TM1: ' + str(GetTM('TM1')))
Send(BuildTC('CMD1'))
Display('Command sent through the original binary DSS transport')
Display('Current TM1: ' + str(GetTM('TM1')))

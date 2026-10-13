# SPDX-License-Identifier: GPL-3.0-or-later
from spell.lib.adapter.usr import UserInterface
from spell.stubs.SPELLDriver_pb2 import LoginCred
from .connection import call
from .common import settings


class Users(UserInterface):
    def _login(self,username,password,config=None):
        return call('USER','Login',LoginCred(username=username,password=password,config=settings(config))).value

    def _logout(self,username,config=None):
        return call('USER','Logout',LoginCred(username=username,config=settings(config))).value

    def _isLoggedIn(self,username,config=None):
        return call('USER','IsLoggedIn',LoginCred(username=username,config=settings(config))).value


USER = Users()

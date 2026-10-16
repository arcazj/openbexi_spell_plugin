"""Durable, authority-bound group observations over original database lookup RPC."""
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import re

from .journal import authority,canonical

SOURCE='OPENBEXI_COMMAND_RESULTS'
KEY='_OpenBEXICommandGroup'


class Results:
    def __init__(self,journal,namespace):
        self.journal,self.namespace=journal,namespace
        with journal.transaction():
            journal.db.execute('''CREATE TABLE IF NOT EXISTS command_results(
                namespace TEXT,session TEXT,procedure TEXT,token TEXT,authority TEXT NOT NULL,
                request_id TEXT NOT NULL,result TEXT NOT NULL,
                PRIMARY KEY(namespace,session,procedure,token))''')

    def key(self,identity,token):
        authority(identity)
        if type(token) is not str or re.fullmatch('[0-9a-f]{32}',token) is None:
            raise ValueError('Invalid private command group identity')
        return self.namespace,identity['session'],identity['procedure'],token

    def validate(self,identity,token,request_id):
        key=self.key(identity,token)
        with self.journal.lock:
            row=self.journal.db.execute('SELECT authority,request_id FROM command_results WHERE namespace=? AND session=? AND procedure=? AND token=?',key).fetchone()
            if row and row!=(authority(identity),request_id):
                raise PermissionError('Command group identity cannot be reused for another request')
            if not row and self.journal.db.execute('SELECT count(*) FROM command_results WHERE namespace=? AND session=? AND procedure=?',key[:3]).fetchone()[0]>=4096:
                raise ValueError('Command group result capacity exceeded')

    def save(self,identity,token,request_id,result):
        key=self.key(identity,token);encoded=canonical(result)
        if len(encoded.encode())>32768:raise ValueError('Command group result exceeds bounds')
        with self.journal.transaction():
            self.validate(identity,token,request_id)
            row=self.journal.db.execute('SELECT result FROM command_results WHERE namespace=? AND session=? AND procedure=? AND token=?',key).fetchone()
            if row:
                if row[0]!=encoded:raise ValueError('Command group result is immutable')
                return
            self.journal.db.execute('INSERT INTO command_results VALUES(?,?,?,?,?,?,?)',
                (*key,authority(identity),request_id,encoded))

    def read(self,identity,token):
        key=self.key(identity,token)
        with self.journal.lock:
            row=self.journal.db.execute('SELECT authority,result FROM command_results WHERE namespace=? AND session=? AND procedure=? AND token=?',key).fetchone()
            if not row:raise ValueError('Command group result unavailable')
            if row[0]!=authority(identity):raise PermissionError('Command group authority differs')
            return json.loads(row[1])


def observation(executor,commands,token,operation,success,error):
    members=[]
    for index,command in enumerate(commands):
        row=executor.member_results[index] if index<len(executor.member_results) else dict(state='NOT_SENT',receipts=[])
        receipts=row['receipts']
        attempted='command-'+str(index) in executor.attempted_elements
        terminal=row['state'] in ('SUCCEEDED','FAILED','REJECTED','NACKED') or (command.load_only and row['state']=='LOADED')
        uncertain=bool(error and attempted and not terminal)
        stages=[[r['stage'],r['outcome'],hashlib.sha256(canonical(r).encode()).hexdigest()] for r in receipts]
        members.append(dict(index=index,name=command.name,state=row['state'],load_only=command.load_only,
            attempted=attempted,uncertain=uncertain,stages=stages))
    return dict(schema='openbexi.command-group-result/1',token=token,operation=operation,
                outcome='UNCERTAIN' if error else 'SUCCEEDED' if success else 'FAILED',members=members)

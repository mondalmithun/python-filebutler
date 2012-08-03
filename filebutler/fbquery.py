#!/usr/bin/env python
# Copyright (c) 2011-2012, Johan Haals <johan.haals@gmail.com>
# All rights reserved.

from peewee import UpdateQuery, Q
from database import *
from password import Password
import sqlite3
import os
from ConfigParser import RawConfigParser
from datetime import datetime


class FbQuery:

    def __init__(self):
        paths = [
            'python-filebutler.conf',
            '/etc/python-filebutler.conf',
        ]

        config = RawConfigParser()

        if not config.read(paths):
            sys.exit("Couldn't read configuration file")

        self.secret_key = config.get('settings', 'secret_key')
        self.storage_path = config.get('settings', 'storage_path')
        # Create tables
        try:
            File.create_table()
        except sqlite3.OperationalError as e:
            if 'table "file" already exists' in e:
                pass
            else:
                sys.exit(e)
        try:
            User.create_table()
        except sqlite3.OperationalError as e:
            if 'table "user" already exists' in e:
                pass
            else:
                sys.exit(e)

    def file_get(self, hash):
        """ Get all fileinfo from database """
        try:
            return File.get(hash=hash)
        except File.DoesNotExist:
            return None

    def user_exist(self, user):
        """ Check if user exists """
        try:
            User.get(username=user)
        except User.DoesNotExist:
            return False
        return True

    def user_get(self, user):
        """ Get all userdata from database """
        try:
            return User.get(username=user)
        except User.DoesNotExist:
            return None

    def user_create(self, user, password):
        """ Create new user """
        encrypted_password = Password(self.secret_key).generate(password)
        if not self.user_exist(user):
            u = User(username=user, password=encrypted_password)
            u.save()
            return 'Created %s with password %s' % (user, password)
        else:
            return 'User already exist'

    def user_delete(self, user):
        dq = User.delete().where(username=user)
        rows = dq.execute()
        if rows != 0:
            return True
        return False

    def user_change_password(self, user, password):
        encrypted_password = Password(self.secret_key).generate(password)
        if self.user_exist(user):
            uq = UpdateQuery(User,
                password=encrypted_password).where(username=user)
            rows = uq.execute()
            if rows != 0:
                return True
        return False

    def file_add(self, download_hash, user_id, filename, expire,
            one_time_download, download_password):
        ''' Add file information to database. '''
        f = File(hash=download_hash, user=user_id, filename=filename,
                expire=expire, one_time_download=one_time_download,
                download_password=download_password)
        f.save()
        return True

    def file_set_expiry(self, download_hash, date):
        uq = File.update(expire=date).where(hash=download_hash)
        uq.execute()
        return True

    def file_expired(expire, expire_date):
        expire_date = datetime.strptime(expire_date, '%Y%m%d%H%M%S')

        if datetime.now() > expire_date:
            # Expired
            return True
        else:
            return False

    def file_remove(self, download_hash, filename):
        ''' remove file from storage and database '''

        try:
            os.remove(os.path.join(self.storage_path, download_hash, filename))
            os.removedirs(os.path.join(self.storage_path, download_hash))
        except OSError:
            return False
        dq = File.delete().where(hash=download_hash)
        dq.execute()
        # Todo: make sure it works
        return True

    def file_remove_expired(self):
        ''' remove all expired files from database '''
        sq = File.select().where(~Q(expire='0'))

        for e in sq.execute():
            if self.file_expired(e.expire):
                print 'removed %s' % e.filename
                self.file_remove(e.hash, e.filename)
        return True

    def user_list_files(self, user):
        ''' return a dict with all files for user '''
        user = self.user_get(user)
        files = {}
        if not user:
            return None

        sq = File.select().where(user_id=user.id)
        # add to dict
        for e in sq.execute():
            files[e.hash] = e.filename

        return files
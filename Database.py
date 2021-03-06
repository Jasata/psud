#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# PATE Monitor / Agilent PSU Controller
#
# Database.py - Jani Tammi <jasata@utu.fi>
#
#   0.1.0   2018.11.14  Initial version.
#   0.1.1   2018.11.16  Replace print()'s with exceptions.
#   0.1.2   2018.11.18  Static 'status' methods added.
#   0.1.3   2019.06.12  No longer dependent on Config.py:Config.
#   0.2.0   2019.06.12  New static method Database.check_db_file() for
#                       database file and directory checking.
#                       (Used by the top level script "psud").
#   0.2.1   2019.06.13  Logging now provided by log.py.
#
#
import os
import sqlite3
import decimal


#
# Application specific
#
import log

class Database:
    # Class instance will have only '.connection' member.
    # If cursor is needed, it has to be created on-demand.

    class Command:
        def __init__(self, db):
            # Store the provided parent Database object instance
            self.db = db

        def next(self) -> tuple:
            """Return oldest unprocessed command, if any."""
            sql = """
            SELECT      id,
                        command,
                        value
            FROM        command
            WHERE       interface = "PSU"
                        AND
                        handled IS NULL
            ORDER BY    created ASC
            LIMIT       1
            """
            return self.db.connection.execute(sql).fetchone()

        def close(self, id: int, result: str):
            """Store command result and close command."""
            try:
                sql = """
                UPDATE      command
                SET         result  = :result,
                            handled = CURRENT_TIMESTAMP
                WHERE       id      = :id
                """
                self.db.connection.execute(sql, {"id": id, "result": result})
            except Exception as e:
                self.db.connection.rollback()
                raise ValueError("ID: {}, SQL: {}".format(id, sql)) from None
            else:
                self.db.connection.commit()


    class PSU:
        def __init__(self, db):
            # Store the provided parent Database object instance
            self.db = db

        def update(self, values: dict):
            try:
                insert = "INSERT INTO psu (id, {}) VALUES (0, {})".format(
                    ",".join([k for k, _ in values.items()]),
                    ",".join([":"+k for k, _ in values.items()])
                )
                update = "UPDATE psu SET {} WHERE id = 0".format(
                    ",".join([k+" = :"+k for k, _ in values.items()])
                )
                cursor = self.db.connection.cursor()
                cursor.execute(update, values)
                if cursor.rowcount != 1:
                    cursor.execute(insert, values)
            except Exception as e:
                self.db.connection.rollback()
                log.error(update)
                log.error(values)
                raise ValueError(
                    "values: {}, update SQL: {}, insert SQL: {}".format(
                        str(values), update, insert
                    )
                ) from None
            else:
                self.db.connection.commit()


    #
    # Class Database initializer
    #
    def __init__(self, filename: str):
        """Initialize object and test that table 'psu' exists."""
        self.command = self.Command(self)
        self.psu     = self.PSU(self)

        self.connection = sqlite3.connect(filename, timeout=3)
        self.connection.execute("PRAGMA foreign_keys = ON")
        sql = "SELECT 1 FROM sqlite_master WHERE type='table' AND name='psu'"
        if not self.connection.execute(sql).fetchall():
            raise ValueError("Table 'psu' does not exist!")

        # Register Decimal() adapters
        sqlite3.register_adapter(decimal.Decimal, Database.decimal2string)
        sqlite3.register_converter("decimal", Database.string2decimal)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        # Empty 'psu' table signals to the middleware that
        # the controller daemon is not running.
        # There is also no reason to keep old voltage/current data.
        self.connection.execute("DELETE FROM psu")
        self.connection.commit()
        self.connection.close()


    @staticmethod
    def decimal2string(dec):
        return str(dec)


    @staticmethod
    def string2decimal(string):
        return decimal.Decimal(string)


    @staticmethod
    def lastupdate(filename: str) -> float:
        """Returns the number of seconds since last update."""
        try:
            # The 'psu' table can have only zero or one rows.
            # Locked with primary key column value constraint.
            sql = """
                SELECT (julianday('now') - julianday(modified)) * 86400
                FROM psu
                """
            with sqlite3.connect(filename) as db:
                result = db.execute(sql).fetchone()

            if result:
                return float(result[0])
            else:
                return None
        except:
            return None


    ##########################################################################
    #
    # Methods to verify prerequisites for execution
    # CHECK_ -functions
    #
    ##########################################################################

    #
    # CHECK Database file (and directory)
    #
    @staticmethod
    def check_db_file(filename : str):
        """Check the specified database file and the directory it is located for access. Raises and exception if a problem is discovered, otherwise returns silently."""
        import stat
        import pwd
        import grp

        # 1. File exists and it is a file
        if not os.path.isfile(filename):
            raise ValueError(
                "Database file '{}' does not exist?".format(filename)
            )
        # 2. File is owned by patemon.www-data
        correct_owner = "patemon.www-data"
        current_owner = \
            pwd.getpwuid(os.stat(filename).st_uid).pw_name + "." + \
            grp.getgrgid(os.stat(filename).st_gid).gr_name
        if current_owner != correct_owner:
            raise ValueError(
                "Database file '{}' has incorrect ownership ('{}', should be '{}')"
                .format(filename, current_owner, correct_owner)
            )
        # 3. File permissions are 66x
        correct_permissions = 0o660
        current_permissions = os.stat(filename)[stat.ST_MODE] & 0o770
        if current_permissions != correct_permissions:
            raise ValueError(
                "Database file '{}' has incorrect permissions ('{}', should be '{}')"
                .format(
                    filename,
                    format(current_permissions, 'o'),
                    format(correct_permissions, 'o')
                )
            )
        # 4. Directory is owned by patemon.www-data (because temporary files)
        directory = os.path.dirname(filename)
        correct_owner = "patemon.www-data"
        current_owner = \
            pwd.getpwuid(os.stat(directory).st_uid).pw_name + "." + \
            grp.getgrgid(os.stat(directory).st_gid).gr_name
        if current_owner != correct_owner:
            raise ValueError(
                "Database directory '{}' has incorrect ownership ('{}', should be '{}')"
                .format(directory, current_owner, correct_owner)
            )
        # 5. Directory permissions are 77x
        correct_permissions = 0o770
        current_permissions = os.stat(directory)[stat.ST_MODE] & 0o770
        if current_permissions != correct_permissions:
            raise ValueError(
                "Database file '{}' has incorrect permissions ('{}', should be '{}')"
                .format(
                    filename,
                    format(current_permissions, 'o'),
                    format(correct_permissions, 'o')
                )
            )


    #
    # CHECK 'psu' -table structure
    #
    @staticmethod
    def check_psu_table(filename : str):
        try:
            sql = """
                SELECT  id, power, voltage_setting, current_limit,
                        measured_current, measured_voltage, modified
                FROM    psu
            """
            with sqlite3.connect(filename) as db:
                result = db.execute(sql).fetchone()

            if result:
                _ = float(result[0])
            else:
                pass
        except sqlite3.Error as e:
            raise ValueError("'psu' -table query failed!\n" + str(e))
        except Exception as e:
            raise ValueError("Unexpected 'psu' querying error!\n" + str(e))


    ##########################################################################
    #
    # Methods to show status information
    # STATUS_ -functions
    #
    ##########################################################################

    # filestatus() -> status_fileaccess()
    @staticmethod
    def filestatus(filename: str) -> tuple:
        """Returns tuple of boolean values (isfile, accessread, accesswrite)."""
        return (
            os.path.isfile(filename),
            os.access(filename, os.R_OK),
            os.access(filename, os.W_OK)
        )

    # filestatusstring() -> status_fileaccess_str()
    @staticmethod
    def filestatusstring(filename: str) -> str:
        t = Database.filestatus(filename)
        if not t[0]:
            return "file does not exist!"
        if not t[1] and not t[2]:
            return "not readable or writable!"
        if not t[1]:
            return "not readable!"
        if not t[2]:
            return "not writable!"
        return "OK"


    @staticmethod
    def psutablestatus(filename: str) -> tuple:
        """Returns tuple of boolean 'exists' values (psu_table, psu_row)."""
        if not os.path.isfile(filename):
            raise ValueError(
                "Specifield database file '{}' does not exist!".format(
                    filename
                )
            )
        if not os.access(filename, os.R_OK):
            raise ValueError(
                "Database file '{}' is not readable!".format(
                    filename
                )
            )
        if not os.access(filename, os.W_OK):
            raise ValueError(
                "Database file '{}' is not writable!".format(
                    filename
                )
            )
        try:
            with sqlite3.connect(filename) as db:
                result = db.execute("SELECT * FROM psu").fetchone()
            if result:
                return (True, True)
            else:
                return (True, False)
        except sqlite3.OperationalError as e:
            if str(e)[:len("no such table")] == "no such table":
                return (False, False)


    @staticmethod
    def psutablestatusstring(filename: str) -> str:
        t = Database.psutablestatus(filename)
        if not t[0]:
            return "table does not exist!"
        if not t[1]:
            return "no data!"
        return "OK"




# EOF
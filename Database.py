#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# PATE Monitor / Agilent PSU Controller
#
# Database.py - Jani Tammi <jasata@utu.fi>
#
#   0.1.0   2018.11.14  Initial version.
#   0.1.1   2018.11.16  Replace print()'s with exceptions.
#   0.1.2   2018.11.18  Static 'status' methods added.
#
#
import os
import sqlite3

from Config import Config

class Database:
    # Class instance will have only .connection
    # If cursor is needed, it has to be created on-demand.

    class Command:
        def __init__(self, db):
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

        # def enter_command(self, values: dict) -> int:
        #     sql = "INSERT INTO command (session_id, {}) VALUES (1, {})".format(
        #         ",".join([k for k, _ in values.items()]),
        #         ",".join([":"+k for k, _ in values.items()])
        #     )
        #     self.cursor.execute(sql, values)
        #     return self.cursor.lastrowid

    class PSU:
        def __init__(self, db):
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
                raise ValueError(
                    "values: {}, update SQL: {}, insert SQL: {}".format(
                        str(values), update, insert
                    )
                ) from None
            else:
                self.db.connection.commit()

        # def get_psu(self) -> tuple:
        #     return self.cursor.execute("SELECT * FROM psu").fetchone()


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
        #self.connection.execute("PRAGMA journal_mode=WAL")


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
    def filestatus(filename: str) -> tuple:
        """Returns tuple of boolean values (isfile, accessread, accesswrite)."""
        return (
            os.path.isfile(filename),
            os.access(filename, os.R_OK),
            os.access(filename, os.W_OK)
        )


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


    @staticmethod
    def lastupdate(filename: str) -> float:
        """Returns the number of seconds since last update."""
        try:
            sql = """
                SELECT (julianday('now') - julianday(modified)) * 86400
                FROM psu
                """
            with sqlite3.connect(Config.database_file) as db:
                result = db.execute(sql).fetchone()

            if result:
                return float(result[0])
            else:
                return None
        except:
            return None


# EOF
#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# PATE Monitor / Agilent PSU Controller
#
# Database.py - Jani Tammi <jasata@utu.fi>
#
#   0.1.0   2018.11.14  Initial version.
#
#
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
                print(str(e))
                self.db.connection.rollback()
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
                print("Database.PSU:", str(e))
                self.db.connection.rollback()
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

# EOF
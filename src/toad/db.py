from datetime import datetime, timezone
from typing import cast, TypedDict
from toad import paths

import aiosqlite


class Session(TypedDict):
    """Agent session fields."""

    id: int
    """Primary key."""
    agent: str
    """Title of the agent."""
    agent_identity: str
    """Agent identity."""
    agent_session_id: str
    """Agent's session id."""
    title: str
    """Title of session."""
    protocol: str
    """Protocol used."""
    created_at: datetime
    """Time session was created."""
    last_used: datetime
    """Time sesison was last used."""
    meta_json: str
    """Text field containing JSON meta."""


class DB:
    """Toads database, for anything that isn't strictly configuration."""

    def __init__(self):
        self.path = paths.get_state() / "toad.db"

    def open(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.path)

    async def create(self) -> bool:
        """Create the tables if requried."""
        try:
            async with self.open() as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent TEXT NOT NULL,
                        agent_identity TEXT NOT NULL,
                        agent_session_id TEXT NOT NULL,                                
                        title TEXT NOT NULL,      
                        protocol TEXT NOT NULL,                  
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        meta_json TEXT DEFAULT '{}'
                    )
                    """
                )
        except aiosqlite.Error:
            return False
        return True

    async def session_new(
        self,
        title: str,
        agent: str,
        agent_identity: str,
        agent_session_id: str,
        protocol: str = "acp",
    ) -> int | None:
        try:
            async with self.open() as db:
                cursor = await db.execute(
                    """
                    INSERT INTO sessions (title, agent, agent_identity, agent_session_id, protocol) VALUES (?, ?, ?, ?, ?)    
                    """,
                    (
                        title,
                        agent,
                        agent_identity,
                        agent_session_id,
                        protocol,
                    ),
                )
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.Error:
            return None

    async def session_update_last_used(self, agent_session_id: str) -> bool:
        """Update the last used timestamp.

        Args:
            id: Session ID.

        Returns:
            Boolenan that indicates success.
        """
        now_utc = datetime.now(timezone.utc)
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET last_used = ? WHERE agent_session_id = ?",
                    (
                        now_utc.isoformat(),
                        agent_session_id,
                    ),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_update_title(self, id: int, title: str) -> bool:
        """Update the last used timestamp.

        Args:
            id: Session ID.
            title: New title.

        Returns:
            Boolenan that indicates success.
        """
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (
                        title,
                        id,
                    ),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_get(self, id: int) -> Session | None:
        """Get a sesison from its ID (PK).

        Args:
            session_id: The ID field (PK, not the agent_session_id)

        Returns:
            A Session if one is found, or `None`.
        """
        try:
            async with self.open() as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * from sessions WHERE id = ?", (id,))
                row = await cursor.fetchone()
        except aiosqlite.Error:
            return None
        if row is None:
            return None
        session = cast(Session, dict(row))
        return session

    async def session_get_recent(self, max_results: int = 100) -> list[Session] | None:
        """Get the most recent sessions."""
        try:
            async with self.open() as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """SELECT * from sessions
                    ORDER BY last_used DESC
                    LIMIT ?""",
                    (max_results,),
                )
                rows = await cursor.fetchall()
        except aiosqlite.Error as error:
            print(error)
            return None
        sessions = [cast(Session, dict(row)) for row in rows]
        return sessions

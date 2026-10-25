"""Cache files sent on their own until the user asks a question.

Images, videos, documents, and similar attachments are kept per session and
attached automatically to the next question.
"""
import logging
import threading

from common.expired_dict import ExpiredDict

logger = logging.getLogger(__name__)


class FileCache:
    """Per-session file cache. Default TTL is 5 minutes."""

    def __init__(self, ttl=300):
        """
        Args:
            ttl: cache lifetime in seconds. Default is 5 minutes.
        """
        self.cache = ExpiredDict(ttl)
        self.ttl = ttl
        self._lock = threading.Lock()

    def add(self, session_id: str, file_path: str, file_type: str = "image"):
        """Add a file to the cache.

        Args:
            session_id: session id
            file_path: local file path
            file_type: file type (image, video, file, and so on)
        """
        # Every add rewrites the entry, so the TTL runs from the most recent
        # file: a burst of files is one batch and must not lose its head.
        file_info = {'path': file_path, 'type': file_type}
        with self._lock:
            files = self.cache.get(session_id) or []
            added = file_info not in files
            if added:
                files.append(file_info)
            self.cache[session_id] = files
        if added:
            logger.info(f"[FileCache] Added {file_type} to cache for session {session_id}: {file_path}")

    def get(self, session_id: str) -> list:
        """Return cached files for a session.

        Args:
            session_id: session id

        Returns:
            A list of file info dicts, or an empty list when nothing is cached
            or the entry has expired.
        """
        with self._lock:
            return self.cache.get(session_id) or []

    def clear(self, session_id: str):
        """Clear one session's cache.

        Args:
            session_id: session id
        """
        with self._lock:
            removed = self.cache.pop(session_id, None)
        if removed is not None:
            logger.info(f"[FileCache] Cleared cache for session {session_id}")


_file_cache = FileCache()


def get_file_cache() -> FileCache:
    """Return the process-wide file cache."""
    return _file_cache

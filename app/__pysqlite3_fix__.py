"""
SQLite3 compatibility fix for ChromaDB

This module must be imported BEFORE chromadb to override the system sqlite3
with a newer version from pysqlite3-binary package.
"""

# Override system sqlite3 with pysqlite3
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

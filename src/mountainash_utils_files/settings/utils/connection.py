# #utils/connection.py

# from typing import Optional, Dict, Any, Tuple, List
# from datetime import datetime, timedelta
# from threading import Lock
# import asyncio
# from contextlib import asynccontextmanager
# from abc import abstractmethod

# from mountainash_settings.auth.storage.exceptions import (
#     StorageConnectionError,
#     StorageTimeoutError,
#     StoragePoolError
# )

# class ConnectionState:
#     """Connection state tracking"""
#     def __init__(self):
#         self.connected: bool = False
#         self.last_used: Optional[datetime] = None
#         self.error_count: int = 0
#         self.last_error: Optional[Exception] = None
#         self.created_at: datetime = datetime.now()
#         self.metadata: Dict[str, Any] = {}

#     def mark_used(self) -> None:
#         """Mark connection as used"""
#         self.last_used = datetime.now()

#     def record_error(self, error: Exception) -> None:
#         """Record connection error"""
#         self.error_count += 1
#         self.last_error = error

#     def is_stale(self, max_age: timedelta) -> bool:
#         """Check if connection is stale"""
#         if not self.last_used:
#             return True
#         return datetime.now() - self.last_used > max_age

#     def is_healthy(self, max_errors: int = 3) -> bool:
#         """Check if connection is healthy"""
#         return self.connected and self.error_count < max_errors

# class ConnectionPool:
#     """Connection pool management"""
#     def __init__(
#         self,
#         min_size: int = 1,
#         max_size: int = 10,
#         max_overflow: int = 5,
#         timeout: float = 30.0,
#         max_age: Optional[timedelta] = None,
#         max_errors: int = 3
#     ):
#         self.min_size = min_size
#         self.max_size = max_size
#         self.max_overflow = max_overflow
#         self.timeout = timeout
#         self.max_age = max_age or timedelta(minutes=30)
#         self.max_errors = max_errors

#         self._pool: List[Tuple[Any, ConnectionState]] = []
#         self._overflow: List[Tuple[Any, ConnectionState]] = []
#         self._lock = Lock()
#         self._semaphore = asyncio.Semaphore(max_size + max_overflow)

#     async def initialize(self) -> None:
#         """Initialize the connection pool"""
#         async with self._lock:
#             for _ in range(self.min_size):
#                 conn = await self._create_connection()
#                 self._pool.append((conn, ConnectionState()))

#     @asynccontextmanager
#     async def acquire(self) -> Any:
#         """Acquire a connection from the pool"""
#         try:
#             async with self._semaphore:
#                 conn, state = await self._get_connection()
#                 state.mark_used()
#                 yield conn
#         except Exception as e:
#             state.record_error(e)
#             raise
#         finally:
#             await self._return_connection(conn, state)

#     async def _get_connection(self) -> Tuple[Any, ConnectionState]:
#         """Get a connection from the pool"""
#         async with self._lock:
#             # Try to get an existing connection
#             while self._pool:
#                 conn, state = self._pool.pop()
#                 if self._is_connection_valid(conn, state):
#                     return conn, state
#                 await self._close_connection(conn)

#             # Create new connection if within limits
#             if len(self._pool) + len(self._overflow) < self.max_size + self.max_overflow:
#                 conn = await self._create_connection()
#                 state = ConnectionState()
#                 if len(self._pool) < self.max_size:
#                     self._pool.append((conn, state))
#                 else:
#                     self._overflow.append((conn, state))
#                 return conn, state

#             raise StoragePoolError(
#                 "Connection pool exhausted",
#                 pool_status=self.get_status()
#             )

#     async def _return_connection(self, conn: Any, state: ConnectionState) -> None:
#         """Return a connection to the pool"""
#         async with self._lock:
#             if not state.is_healthy(self.max_errors):
#                 await self._close_connection(conn)
#                 return

#             if state.is_stale(self.max_age):
#                 await self._close_connection(conn)
#                 return

#             if len(self._pool) < self.max_size:
#                 self._pool.append((conn, state))
#             else:
#                 self._overflow.append((conn, state))

#     @abstractmethod
#     async def _create_connection(self) -> Any:
#         """Create a new connection"""
#         pass

#     @abstractmethod
#     async def _close_connection(self, conn: Any) -> None:
#         """Close a connection"""
#         pass

#     @abstractmethod
#     def _is_connection_valid(self, conn: Any, state: ConnectionState) -> bool:
#         """Check if a connection is valid"""
#         pass

#     def get_status(self) -> Dict[str, Any]:
#         """Get pool status information"""
#         return {
#             "pool_size": len(self._pool),
#             "overflow_size": len(self._overflow),
#             "available_connections": self._semaphore._value,
#             "min_size": self.min_size,
#             "max_size": self.max_size,
#             "max_overflow": self.max_overflow
#         }

# class RetryManager:
#     """Connection retry management"""
#     def __init__(
#         self,
#         max_retries: int = 3,
#         base_delay: float = 1.0,
#         max_delay: float = 60.0,
#         exponential_base: float = 2.0,
#         jitter: bool = True
#     ):
#         self.max_retries = max_retries
#         self.base_delay = base_delay
#         self.max_delay = max_delay
#         self.exponential_base = exponential_base
#         self.jitter = jitter

#     async def execute_with_retry(
#         self,
#         operation: callable,
#         *args,
#         **kwargs
#     ) -> Any:
#         """Execute operation with retry logic"""
#         last_error = None
        
#         for attempt in range(self.max_retries + 1):
#             try:
#                 return await operation(*args, **kwargs)
#             except Exception as e:
#                 last_error = e
#                 if not self._should_retry(e, attempt):
#                     raise

#                 delay = self._calculate_delay(attempt)
#                 await asyncio.sleep(delay)

#         raise StorageConnectionError(
#             f"Operation failed after {self.max_retries} retries",
#             str(last_error) if last_error else None
#         )

#     def _should_retry(self, error: Exception, attempt: int) -> bool:
#         """Determine if operation should be retried"""
#         if attempt >= self.max_retries:
#             return False

#         # Add specific error types that should be retried
#         retriable_errors = (
#             ConnectionError,
#             TimeoutError,
#             StorageTimeoutError
#         )

#         return isinstance(error, retriable_errors)

#     def _calculate_delay(self, attempt: int) -> float:
#         """Calculate delay for retry attempt"""
#         delay = min(
#             self.base_delay * (self.exponential_base ** attempt),
#             self.max_delay
#         )

#         if self.jitter:
#             import random
#             delay *= (0.5 + random.random())

#         return delay

# class ConnectionMonitor:
#     """Connection monitoring and health checks"""
#     def __init__(self, check_interval: float = 60.0):
#         self.check_interval = check_interval
#         self._connections: Dict[str, Tuple[Any, ConnectionState]] = {}
#         self._lock = Lock()
#         self._task: Optional[asyncio.Task] = None

#     async def start(self) -> None:
#         """Start connection monitoring"""
#         self._task = asyncio.create_task(self._monitor_connections())

#     async def stop(self) -> None:
#         """Stop connection monitoring"""
#         if self._task:
#             self._task.cancel()
#             try:
#                 await self._task
#             except asyncio.CancelledError:
#                 pass

#     async def _monitor_connections(self) -> None:
#         """Monitor connection health"""
#         while True:
#             try:
#                 await self._check_connections()
#                 await asyncio.sleep(self.check_interval)
#             except asyncio.CancelledError:
#                 break
#             except Exception as e:
#                 # Log error but continue monitoring
#                 print(f"Error in connection monitor: {e}")

#     async def _check_connections(self) -> None:
#         """Check all connections"""
#         async with self._lock:
#             for conn_id, (conn, state) in list(self._connections.items()):
#                 try:
#                     if not await self._check_connection(conn, state):
#                         await self._handle_unhealthy_connection(conn_id, conn, state)
#                 except Exception as e:
#                     state.record_error(e)
#                     await self._handle_unhealthy_connection(conn_id, conn, state)

#     @abstractmethod
#     async def _check_connection(self, conn: Any, state: ConnectionState) -> bool:
#         """Check single connection health"""
#         pass

#     @abstractmethod
#     async def _handle_unhealthy_connection(
#         self,
#         conn_id: str,
#         conn: Any,
#         state: ConnectionState
#     ) -> None:
#         """Handle unhealthy connection"""
#         pass

#     def add_connection(self, conn_id: str, conn: Any) -> None:
#         """Add connection to monitor"""
#         self._connections[conn_id] = (conn, ConnectionState())

#     def remove_connection(self, conn_id: str) -> None:
#         """Remove connection from monitor"""
#         self._connections.pop(conn_id, None)

#     def get_status(self) -> Dict[str, Any]:
#         """Get monitoring status"""
#         return {
#             "total_connections": len(self._connections),
#             "healthy_connections": sum(
#                 1 for _, state in self._connections.values()
#                 if state.is_healthy()
#             ),
#             "check_interval": self.check_interval
#         }
import json
import time
import redis as redis_lib
from typing import Optional

_client: Optional[redis_lib.Redis] = None


def get_client(host: str = "localhost", port: int = 6379) -> redis_lib.Redis:
    global _client
    if _client is None:
        _client = redis_lib.Redis(host=host, port=port, decode_responses=True)
    return _client


def _key(session_id: str) -> str:
    return f"ai-mem:session:{session_id}"


def _meta_key(session_id: str) -> str:
    return f"ai-mem:meta:{session_id}"


def append_turn(session_id: str, role: str, content: str,
                ttl_hours: int = 24) -> None:
    r = get_client()
    key = _key(session_id)
    turn = {"role": role, "content": content, "ts": time.time()}
    pipe = r.pipeline()
    pipe.rpush(key, json.dumps(turn))
    pipe.expire(key, ttl_hours * 3600)
    pipe.execute()


def get_turns(session_id: str) -> list[dict]:
    r = get_client()
    raw = r.lrange(_key(session_id), 0, -1)
    return [json.loads(t) for t in raw]


def mark_consolidated(session_id: str) -> None:
    r = get_client()
    r.set(_meta_key(session_id) + ":consolidated", "1", ex=7 * 86400)


def is_consolidated(session_id: str) -> bool:
    r = get_client()
    return r.exists(_meta_key(session_id) + ":consolidated") > 0


def list_pending_sessions() -> list[str]:
    r = get_client()
    keys = r.keys("ai-mem:session:*")
    pending = []
    for key in keys:
        sid = key.replace("ai-mem:session:", "")
        if not is_consolidated(sid):
            count = r.llen(key)
            if count > 0:
                pending.append(sid)
    return pending


def delete_session(session_id: str) -> None:
    r = get_client()
    r.delete(_key(session_id))
    r.delete(_meta_key(session_id) + ":consolidated")

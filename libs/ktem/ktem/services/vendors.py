"""Model vendors and MCP servers, mirroring the classic *Resources* page.

A stored entry is ``{name: spec}`` where ``spec`` is the vendor class dotted path
under ``__type__`` plus that vendor's parameters (an API key, a base URL, a model
name …). The classic page edits the spec as YAML; the web UI builds a form from
the vendor's ``describe()`` metadata instead, so both sides read the same record.
"""

from __future__ import annotations

from typing import Any

KINDS = ("llms", "embeddings", "rerankings", "mcp")
MODEL_KINDS = ("llms", "embeddings", "rerankings")

_SECRET_HINTS = ("key", "token", "secret", "password")


def _manager(kind: str):
    if kind == "mcp":
        from ktem.mcp.manager import mcp_manager

        return mcp_manager
    if kind == "llms":
        from ktem.llms.manager import llms

        return llms
    if kind == "embeddings":
        from ktem.embeddings.manager import embedding_models_manager

        return embedding_models_manager
    if kind == "rerankings":
        from ktem.rerankings.manager import reranking_models_manager

        return reranking_models_manager
    raise ValueError(f"未知资源类型：{kind}")


def _type_name(raw: Any) -> str:
    """``"<class 'str'>"`` → ``"str"``; ``typing.Optional[str]`` → ``"str?"``."""
    text = str(raw)
    if text.startswith("<class '") and text.endswith("'>"):
        return text[len("<class '") : -2]
    if text.startswith("typing.Optional["):
        inner = text[len("typing.Optional[") :].rstrip("]")
        return f"{inner}?"
    if text.startswith("typing."):
        return text[len("typing.") :]
    return text


def _is_unset(value: Any) -> bool:
    return isinstance(value, dict) and "__type__" in value and "unset_" in str(
        value.get("__type__")
    )


def _plain(value: Any) -> Any:
    """JSON-friendly default; ``unset`` markers become ``None``."""
    if _is_unset(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_secret(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def catalog(kind: str) -> list[dict]:
    """Vendors a user can pick, with the metadata needed to render a form."""
    if kind not in MODEL_KINDS:
        return []
    vendors = _manager(kind).vendors()
    output = []
    for name, vendor in vendors.items():
        try:
            describe = vendor.describe()
        except Exception:  # noqa: BLE001 - a broken vendor must not break the list
            describe = {}
        params = []
        for key, meta in (describe.get("params") or {}).items():
            if isinstance(meta.get("auto_callback"), str):
                continue
            params.append(
                {
                    "name": key,
                    "type": _type_name(meta.get("type", "")),
                    "help": str(meta.get("help", "") or ""),
                    "required": bool(meta.get("required", False)),
                    "default": _plain(meta.get("default")),
                    "secret": _is_secret(key),
                }
            )
        output.append(
            {
                "name": name,
                "doc": (vendor.__doc__ or "").strip().split("\n")[0],
                "params": params,
            }
        )
    # keep the manager's registry order: the most common vendor comes first
    return output


def _entry(kind: str, name: str, item: dict) -> dict:
    if kind == "mcp":
        return {"name": name, "default": False, "config": item.get("config") or {}}
    spec = item.get("spec") or {}
    vendor = str(spec.get("__type__") or "").rsplit(".", 1)[-1]
    model = spec.get("model") or spec.get("model_name") or spec.get("model_id") or ""
    return {
        "name": name,
        "vendor": vendor,
        "model": str(model),
        "default": bool(item.get("default")),
    }


def list_entries(kind: str) -> list[dict]:
    info = _manager(kind).info()
    rows = [_entry(kind, name, item) for name, item in info.items()]
    rows.sort(key=lambda row: row["name"].lower())
    return rows


def get_entry(kind: str, name: str) -> dict:
    info = _manager(kind).info()
    if name not in info:
        raise KeyError("资源不存在")
    item = info[name]
    payload = _entry(kind, name, item)
    if kind == "mcp":
        payload["config"] = item.get("config") or {}
    else:
        payload["spec"] = item.get("spec") or {}
    return payload


def _vendor_class(kind: str, vendor: str):
    vendors = _manager(kind).vendors()
    if vendor not in vendors:
        raise ValueError(f"未知供应商：{vendor}")
    return vendors[vendor]


def create(
    kind: str,
    *,
    name: str,
    vendor: str | None = None,
    params: dict | None = None,
    default: bool = False,
    config: dict | None = None,
) -> dict:
    clean = (name or "").strip()
    if not clean:
        raise ValueError("名称不能为空")
    manager = _manager(kind)
    if clean in manager.info():
        raise ValueError("名称已存在")

    if kind == "mcp":
        if not isinstance(config, dict) or not config:
            raise ValueError("MCP 配置不能为空")
        manager.add(clean, config)
    else:
        if not vendor:
            raise ValueError("请选择供应商")
        cls = _vendor_class(kind, vendor)
        if params is not None and not isinstance(params, dict):
            raise ValueError("参数格式无效")
        spec = {
            "__type__": f"{cls.__module__}.{cls.__qualname__}",
            **(params or {}),
        }
        manager.add(clean, spec=spec, default=bool(default))
    return get_entry(kind, clean)


def update(
    kind: str,
    name: str,
    *,
    new_name: str | None = None,
    params: dict | None = None,
    default: bool | None = None,
    config: dict | None = None,
) -> dict:
    manager = _manager(kind)
    info = manager.info()
    if name not in info:
        raise KeyError("资源不存在")

    target = (new_name or "").strip() if new_name is not None else name
    if target and target != name and target in info:
        raise ValueError("名称已存在")

    if kind == "mcp":
        if config is not None:
            if not isinstance(config, dict):
                raise ValueError("MCP 配置格式无效")
            manager.update(name, config)
        if target and target != name:
            # the MCP manager has no rename: recreate the record
            manager.delete(name)
            manager.add(target, config if config is not None else info[name]["config"])
    else:
        item = info[name]
        spec = dict(item.get("spec") or {})
        if params is not None:
            if not isinstance(params, dict):
                raise ValueError("参数格式无效")
            spec.update(params)
        manager.update(
            name,
            spec=spec,
            default=bool(item.get("default")) if default is None else bool(default),
            new_name=target if target != name else "",
        )
    return get_entry(kind, target or name)


def delete(kind: str, name: str) -> None:
    manager = _manager(kind)
    if name not in manager.info():
        raise KeyError("资源不存在")
    manager.delete(name)


def test_llm(vendor: str, params: dict | None = None) -> dict:
    """Build the chat client without sending a request.

    The classic page sends ``"Hi"``; a read-only check (constructing the client)
    catches typos in the spec without spending tokens or hanging on the network.
    """
    from theflow.utils.modules import deserialize

    from ktem.llms.manager import llms

    cls = _vendor_class("llms", vendor)
    spec = {"__type__": f"{cls.__module__}.{cls.__qualname__}", **(params or {})}
    try:
        model = deserialize(spec, safe=False)
    except Exception as exc:  # noqa: BLE001 - reported to the caller
        return {"ok": False, "message": str(exc)}
    if model is None:
        return {"ok": False, "message": "无法创建该模型"}
    default_name = llms.get_default_name() if llms.options() else ""
    return {
        "ok": True,
        "message": "模型配置有效（未实际发送请求）",
        "default": default_name,
    }


__all__ = [
    "KINDS",
    "MODEL_KINDS",
    "catalog",
    "create",
    "delete",
    "get_entry",
    "list_entries",
    "test_llm",
    "update",
]

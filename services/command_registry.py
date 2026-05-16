
import ast
import json
from pathlib import Path
from datetime import datetime

COGS_DIR = Path("cogs")
REPORT_FILE = Path("logs/command_registry_report.json")

FINAL_OWNERS = {
    "cmds": "cogs.command_center",
    "commands": "cogs.command_center",
    "helpme": "cogs.command_center",

    "launch": "cogs.launch_admin",
    "admin": "cogs.launch_admin",
    "audit": "cogs.launch_admin",

    "deepaudit": "cogs.audit_hardening",
    "hardaudit": "cogs.audit_hardening",
    "auditdeep": "cogs.audit_hardening",
    "health": "cogs.audit_hardening",
    "healthcheck": "cogs.audit_hardening",
    "logtest": "cogs.audit_hardening",

    "addowner": "cogs.admin_access",
    "removeowner": "cogs.admin_access",
    "owners": "cogs.admin_access",
    "allowid": "cogs.admin_access",
    "denyid": "cogs.admin_access",
    "allowedids": "cogs.admin_access",

    "setupall": "cogs.server_setup",
    "vsetup": "cogs.server_setup",
    "fullsetup": "cogs.server_setup",
    "setupserver": "cogs.server_setup",
    "vroles": "cogs.server_setup",
    "fixroles": "cogs.server_setup",
    "vchannels": "cogs.server_setup",
    "fixchannels": "cogs.server_setup",
    "vperms": "cogs.server_setup",
    "fixperms": "cogs.server_setup",
    "vclean": "cogs.server_setup",
    "serverplan": "cogs.server_setup",

    "cleanmsgs": "cogs.message_polish",
    "msgclean": "cogs.message_polish",
    "cleanmarkers": "cogs.message_polish",
    "msgs": "cogs.message_polish",
    "postmsgs": "cogs.message_polish",
    "refreshmsgs": "cogs.message_polish",
    "msg": "cogs.message_polish",
    "postmsg": "cogs.message_polish",
    "setimage": "cogs.message_polish",
    "setbanner": "cogs.message_polish",
    "clearimage": "cogs.message_polish",
    "clearbanner": "cogs.message_polish",
    "imagekeys": "cogs.message_polish",
    "imgs": "cogs.message_polish",
    "banners": "cogs.message_polish",
    "imagepreset": "cogs.message_polish",
    "presetimages": "cogs.message_polish",
    "previewimage": "cogs.message_polish",
    "previewbanner": "cogs.message_polish",

    "estock": "cogs.eldorado_stock",
    "eldostock": "cogs.eldorado_stock",
    "syncstock": "cogs.eldorado_stock",
    "stockboard": "cogs.eldorado_stock",
    "sb": "cogs.eldorado_stock",
    "persistviews": "cogs.eldorado_stock",
    "stocksetup": "cogs.eldorado_stock",
    "ssu": "cogs.eldorado_stock",
    "eroute": "cogs.eldorado_stock",
    "egame": "cogs.eldorado_stock",
    "eall": "cogs.eldorado_stock",

    "claim": "cogs.ticket_ops",
    "cl": "cogs.ticket_ops",
    "paid": "cogs.ticket_ops",
    "p": "cogs.ticket_ops",
    "delivering": "cogs.ticket_ops",
    "d": "cogs.ticket_ops",
    "transcript": "cogs.ticket_ops",
    "tr": "cogs.ticket_ops",
    "closeticket": "cogs.ticket_ops",
    "ct": "cogs.ticket_ops",
    "close": "cogs.ticket_ops",
    "cancelorder": "cogs.ticket_ops",
    "co": "cogs.ticket_ops",

    "complete": "cogs.orders",
    "done": "cogs.orders",
    "ship": "cogs.orders",
    "finish": "cogs.orders",
    "fill": "cogs.orders",
    "sent": "cogs.orders",
    "ok": "cogs.orders",
    "orderstats": "cogs.orders",
    "os": "cogs.orders",
    "stats": "cogs.orders",

    "find": "cogs.product_search",
    "searchproduct": "cogs.product_search",
    "fp": "cogs.product_search",
}

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def _string_from_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def _list_strings(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return [x.value for x in node.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
    return []

def decorator_command_info(decorator):
    if not isinstance(decorator, ast.Call):
        return None

    func = decorator.func
    attr = getattr(func, "attr", None)
    if attr not in {"command", "hybrid_command"}:
        return None

    name = None
    aliases = []

    if decorator.args:
        first = _string_from_node(decorator.args[0])
        if first:
            name = first

    for kw in decorator.keywords:
        if kw.arg == "name":
            value = _string_from_node(kw.value)
            if value:
                name = value
        elif kw.arg == "aliases":
            aliases += _list_strings(kw.value)

    return name, aliases

def scan_file(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], [{"file": str(path), "error": str(exc)}]

    commands = []
    errors = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for dec in node.decorator_list:
            info = decorator_command_info(dec)
            if not info:
                continue

            name, aliases = info
            if not name:
                name = node.name

            module = "cogs." + path.stem
            commands.append({
                "module": module,
                "file": str(path),
                "function": node.name,
                "name": name,
                "aliases": aliases,
                "all_names": [name] + aliases,
                "line": getattr(node, "lineno", None),
            })

    return commands, errors

def scan_commands():
    all_commands = []
    errors = []

    if not COGS_DIR.exists():
        return {
            "generated_at": now_iso(),
            "commands": [],
            "duplicates": {},
            "wrong_owners": [],
            "errors": [{"error": "cogs directory missing"}],
        }

    for path in sorted(COGS_DIR.glob("*.py")):
        commands, file_errors = scan_file(path)
        all_commands.extend(commands)
        errors.extend(file_errors)

    ownership = {}
    for command in all_commands:
        for name in command["all_names"]:
            key = name.lower()
            ownership.setdefault(key, []).append(command)

    duplicates = {
        name: entries
        for name, entries in ownership.items()
        if len({e["module"] + "." + e["function"] for e in entries}) > 1
    }

    wrong_owners = []
    for name, entries in ownership.items():
        expected = FINAL_OWNERS.get(name)
        if not expected:
            continue
        for entry in entries:
            if entry["module"] != expected:
                wrong_owners.append({
                    "name": name,
                    "expected": expected,
                    "actual": entry["module"],
                    "function": entry["function"],
                    "file": entry["file"],
                    "line": entry["line"],
                })

    report = {
        "generated_at": now_iso(),
        "commands": all_commands,
        "duplicates": duplicates,
        "wrong_owners": wrong_owners,
        "errors": errors,
    }

    REPORT_FILE.parent.mkdir(exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

def command_map_lines(report=None):
    if report is None:
        report = scan_commands()

    by_module = {}
    for command in report["commands"]:
        by_module.setdefault(command["module"], []).append(command)

    lines = []
    for module in sorted(by_module):
        parts = []
        for cmd in sorted(by_module[module], key=lambda x: x["name"]):
            aliases = ", ".join(cmd["aliases"])
            if aliases:
                parts.append(f"`!{cmd['name']}` ({aliases})")
            else:
                parts.append(f"`!{cmd['name']}`")
        lines.append(f"**{module}**\n" + ", ".join(parts))

    return lines

def duplicate_lines(report=None):
    if report is None:
        report = scan_commands()

    lines = []

    if not report["duplicates"]:
        lines.append("No duplicate command names or aliases found by source scan.")
    else:
        for name, entries in sorted(report["duplicates"].items()):
            sources = []
            seen = set()
            for e in entries:
                src = f"{e['module']}.{e['function']}:L{e.get('line')}"
                if src not in seen:
                    seen.add(src)
                    sources.append(src)
            lines.append(f"`!{name}` → " + " | ".join(sources))

    if report["wrong_owners"]:
        lines.append("\n**Wrong final owner warnings:**")
        for item in report["wrong_owners"][:25]:
            lines.append(
                f"`!{item['name']}` expected `{item['expected']}`, found `{item['actual']}.{item['function']}`"
            )

    if report["errors"]:
        lines.append("\n**Scan errors:**")
        for err in report["errors"][:10]:
            lines.append(str(err))

    return lines

def runtime_command_lines(bot):
    lines = []
    for cmd in sorted(bot.commands, key=lambda c: c.name):
        cog = cmd.cog.qualified_name if cmd.cog else "None"
        aliases = ", ".join(cmd.aliases)
        lines.append(f"`!{cmd.name}` → `{cog}`" + (f" | aliases: `{aliases}`" if aliases else ""))
    return lines

def runtime_duplicates(bot):
    seen = {}
    duplicates = {}

    for cmd in bot.commands:
        names = [cmd.name] + list(cmd.aliases)
        for name in names:
            key = name.lower()
            ref = f"{cmd.cog.qualified_name if cmd.cog else 'None'}.{cmd.callback.__name__}"
            if key in seen and seen[key] != ref:
                duplicates.setdefault(key, set()).update({seen[key], ref})
            else:
                seen[key] = ref

    return {k: sorted(v) for k, v in duplicates.items()}
